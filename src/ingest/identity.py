import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from src.ingest.entities import IdentityCandidate, ParsedResume

EMAIL_REGEX = re.compile(r"(?:mailto:)?([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", re.IGNORECASE)
PHONE_REGEX = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().\-/]{6,}\d)(?!\w)",
    re.IGNORECASE,
)
NON_NAME_SECTION_WORDS = {
    "experience",
    "education",
    "skills",
    "projects",
    "summary",
    "contact",
    "certifications",
    "profile",
    "about",
    "work",
    "empleo",
    "experiencia",
    "educacion",
    "educación",
    "habilidades",
    "proyectos",
    "contacto",
}


class NameResolver(Protocol):
    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        ...


@dataclass
class RulesOnlyNameResolver:
    max_lines: int = 8

    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        emails: list[str] = context.get("emails", [])
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_lines = [_strip_line_prefix(line) for line in lines[: self.max_lines]]

        best_name: str | None = None
        best_score = 0.0
        reasons: list[dict] = []

        for idx, line in enumerate(candidate_lines):
            score, reason_codes = self._score_name_line(line, idx, emails)
            reasons.append({"line": line, "score": round(score, 4), "reason_codes": reason_codes})
            if score > best_score:
                best_score = score
                best_name = _normalize_name(line)

        if best_score < 0.35:
            return None, round(best_score, 4), {"method": "rules", "candidates": reasons}
        return best_name, round(best_score, 4), {"method": "rules", "candidates": reasons}

    def _score_name_line(self, line: str, line_index: int, emails: list[str]) -> tuple[float, list[str]]:
        reasons: list[str] = []
        cleaned = _normalize_whitespace(line)

        if len(cleaned) < 3 or len(cleaned) > 80:
            return 0.0, ["length_out_of_range"]

        parts = cleaned.split(" ")
        if not 2 <= len(parts) <= 4:
            return 0.0, ["token_count_out_of_range"]

        lowered = cleaned.lower()
        if any(word in lowered for word in NON_NAME_SECTION_WORDS):
            return 0.0, ["section_keyword_match"]

        digit_ratio = sum(char.isdigit() for char in cleaned) / max(len(cleaned), 1)
        if digit_ratio > 0.1:
            return 0.0, ["too_many_digits"]

        punct_ratio = sum(char in ",;:/|()[]{}" for char in cleaned) / max(len(cleaned), 1)
        if punct_ratio > 0.1:
            return 0.0, ["too_much_punctuation"]

        name_like_tokens = sum(
            1
            for part in parts
            if (part[:1].isupper() and part[1:].islower()) or part.isupper()
        )
        if name_like_tokens < 2:
            return 0.0, ["not_enough_name_like_tokens"]

        score = 0.25
        reasons.append("base_name_shape")

        title_case_tokens = sum(1 for part in parts if part[:1].isupper() and part[1:].islower())
        if title_case_tokens >= 2:
            score += 0.25
            reasons.append("title_case_tokens")

        if line_index <= 1:
            score += 0.2
            reasons.append("top_of_document")
        elif line_index <= 3:
            score += 0.1
            reasons.append("early_document")

        email_bonus = _email_name_match_bonus(cleaned, emails)
        if email_bonus > 0:
            score += email_bonus
            reasons.append("email_name_alignment")

        score = max(0.0, min(1.0, score))
        return score, reasons


@dataclass
class ModelNameResolver:
    threshold: float = 0.35

    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        # Placeholder interface for future Presidio/HF/GLiNER integration.
        return None, 0.0, {"method": "model_placeholder", "enabled": False}


def extract_identity(
    parsed: ParsedResume,
    *,
    name_resolver: NameResolver | None = None,
    allow_model_fallback: bool = False,
) -> IdentityCandidate:
    emails = extract_emails(parsed.clean_text)
    phones = extract_phones(parsed.clean_text)

    resolver = name_resolver or RulesOnlyNameResolver()
    name, name_confidence, name_signals = resolver.resolve_name(
        parsed.raw_text,
        {
            "emails": emails,
            "phones": phones,
            "language": parsed.language,
            "links": parsed.links,
        },
    )

    model_used = False
    if allow_model_fallback and name_confidence < 0.35 and (emails or phones):
        model_name, model_confidence, model_signals = ModelNameResolver().resolve_name(
            parsed.raw_text,
            {
                "emails": emails,
                "phones": phones,
                "language": parsed.language,
            },
        )
        if model_name and model_confidence > name_confidence:
            name = model_name
            name_confidence = model_confidence
            name_signals = {
                "primary": name_signals,
                "fallback": model_signals,
            }
            model_used = True

    email = emails[0] if emails else None
    phone = phones[0] if phones else None

    identity_key, identity_key_reason = compute_identity_key(name=name, email=email, phone=phone, clean_text=parsed.clean_text)

    confidence, confidence_inputs = score_identity_confidence(
        name=name,
        email=email,
        phone=phone,
        name_confidence=name_confidence,
    )

    signals = {
        "emails": emails,
        "phones": phones,
        "name_signals": name_signals,
        "identity_key_reason": identity_key_reason,
        "confidence_inputs": confidence_inputs,
        "model_fallback_used": model_used,
    }

    return IdentityCandidate(
        name=name,
        email=email,
        phone=phone,
        identity_key=identity_key,
        confidence=confidence,
        signals=signals,
    )


def compute_content_hash(text: str) -> str:
    normalized = _normalize_whitespace(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_identity_key(
    *,
    name: str | None,
    email: str | None,
    phone: str | None,
    clean_text: str,
) -> tuple[str, str]:
    normalized_email = normalize_email(email) if email else None
    normalized_phone = normalize_phone(phone) if phone else None
    normalized_name = _normalize_name(name) if name else None

    if not any([normalized_email, normalized_phone, normalized_name]):
        digest = compute_content_hash(clean_text)[:24]
        return f"resume_content:{digest}", "content_fallback"

    payload = "idv1|" + "|".join(
        [
            normalized_email or "",
            normalized_phone or "",
            normalized_name.lower() if normalized_name else "",
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"candidate:v1:{digest}", "identity_tuple"


def extract_emails(text: str) -> list[str]:
    emails = [normalize_email(match.group(1)) for match in EMAIL_REGEX.finditer(text)]
    unique = sorted({email for email in emails if email})
    return unique


def extract_phones(text: str) -> list[str]:
    phones = [normalize_phone(match.group(0)) for match in PHONE_REGEX.finditer(text)]
    unique = sorted({phone for phone in phones if phone})
    return unique


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    value = email.strip().lower().replace("mailto:", "")
    value = value.rstrip(".,;:)")
    if "@" not in value:
        return None
    return value


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    raw = phone.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 7:
        return None
    if has_plus:
        return f"+{digits}"
    return digits


def score_identity_confidence(
    *,
    name: str | None,
    email: str | None,
    phone: str | None,
    name_confidence: float,
) -> tuple[float, dict]:
    score = 0.0
    reasons: list[str] = []

    if email:
        score += 0.45
        reasons.append("email_present")
    if phone:
        score += 0.25
        reasons.append("phone_present")
    if name:
        score += 0.15
        reasons.append("name_present")
        score += 0.15 * max(0.0, min(1.0, name_confidence))
        reasons.append("name_confidence")

    score = max(0.05, min(1.0, score))
    return round(score, 4), {"reason_codes": reasons, "name_confidence": round(name_confidence, 4)}


def _email_name_match_bonus(name: str, emails: list[str]) -> float:
    if not emails:
        return 0.0

    parts = [p.lower() for p in name.split() if p]
    if len(parts) < 2:
        return 0.0

    first, last = parts[0], parts[-1]
    initials = f"{first[:1]}{last}"

    for email in emails:
        local = email.split("@", 1)[0].lower()
        local_flat = re.sub(r"[^a-z0-9]", "", local)
        if first in local_flat and last in local_flat:
            return 0.15
        if initials in local_flat:
            return 0.12
        if f"{first}{last}" in local_flat:
            return 0.15
    return 0.0


def _normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    tokens = [token for token in cleaned.split(" ") if token]
    return " ".join(token.capitalize() for token in tokens)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_line_prefix(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^[#>\-\*\u2022]+\s*", "", stripped)
    return stripped
