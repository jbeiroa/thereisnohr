"""Application module `src.ingest.identity`."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from src.ingest.entities import IdentityCandidate, ParsedResume
from src.ingest.model_fallback import LLMFallbackResolver

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
NON_NAME_PHRASES = {
    "data models",
    "model building",
    "information analysis",
    "top skills",
    "languages",
    "publications",
}
LOCATION_HINTS = {
    "argentina",
    "buenos aires",
    "bs as",
    "bs. as.",
    "caba",
}


class NameResolver(Protocol):
    """Represents NameResolver."""

    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        """Run resolve name.

        Args:
            text: Input parameter.
            context: Input parameter.

        Returns:
            object: Computed result.

        """
        ...


@dataclass
class RulesOnlyNameResolver:
    """Represents RulesOnlyNameResolver."""

    max_lines: int = 8

    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        """Run resolve name.

        Args:
            text: Input parameter.
            context: Input parameter.

        Returns:
            object: Computed result.

        """
        emails: list[str] = context.get("emails", [])
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_lines = [_strip_line_prefix(line) for line in lines[: self.max_lines]]

        best_name: str | None = None
        best_score = 0.0
        reasons: list[dict] = []

        for idx, line in enumerate(candidate_lines):
            candidate = _normalize_candidate_name_line(line)
            score, reason_codes = self._score_name_line(candidate, idx, emails)
            reasons.append(
                {
                    "line": line,
                    "candidate": candidate,
                    "score": round(score, 4),
                    "reason_codes": reason_codes,
                }
            )
            if score > best_score:
                best_score = score
                best_name = _normalize_name(candidate)

        if best_score < 0.35:
            return None, round(best_score, 4), {"method": "rules", "candidates": reasons}
        return best_name, round(best_score, 4), {"method": "rules", "candidates": reasons}

    def _score_name_line(self, line: str, line_index: int, emails: list[str]) -> tuple[float, list[str]]:
        """Helper for  score name line.

        Args:
            line: Input parameter.
            line_index: Input parameter.
            emails: Input parameter.

        Returns:
            object: Computed result.

        """
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
        if any(phrase in lowered for phrase in NON_NAME_PHRASES):
            return 0.0, ["non_name_phrase_match"]
        if any(hint in lowered for hint in LOCATION_HINTS):
            return 0.0, ["location_hint_match"]

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
    """Represents ModelNameResolver."""

    llm_resolver: LLMFallbackResolver | None = None

    def resolve_name(self, text: str, context: dict) -> tuple[str | None, float, dict]:
        """Run resolve name.

        Args:
            text: Input parameter.
            context: Input parameter.

        Returns:
            object: Computed result.

        """
        if self.llm_resolver is None:
            return None, 0.0, {"method": "model_llm", "enabled": False}

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_lines = [_normalize_candidate_name_line(_strip_line_prefix(line)) for line in lines[:10]]
        candidate_lines = [line for line in candidate_lines if line]

        try:
            result = self.llm_resolver.resolve_name(
                candidate_lines=candidate_lines,
                emails=context.get("emails", []),
                phones=context.get("phones", []),
                language=context.get("language"),
            )
        except Exception as exc:
            return None, 0.0, {"method": "model_llm", "enabled": True, "error": str(exc)}

        candidate = _normalize_name(result.name)
        if not _is_valid_person_name(candidate):
            return None, 0.0, {
                "method": "model_llm",
                "enabled": True,
                "rejected_reason": "invalid_name_shape",
                "reason": result.reason,
            }

        return candidate, float(result.confidence), {
            "method": "model_llm",
            "enabled": True,
            "reason": result.reason,
        }


def extract_identity(
    parsed: ParsedResume,
    *,
    name_resolver: NameResolver | None = None,
    model_name_resolver: NameResolver | None = None,
    allow_model_fallback: bool = False,
    name_fallback_trigger_threshold: float = 0.60,
    name_model_accept_threshold: float = 0.70,
) -> IdentityCandidate:
    """Extract identity.

    Args:
        parsed: Input parameter.
        name_resolver: Input parameter.
        model_name_resolver: Input parameter.
        allow_model_fallback: Input parameter.
        name_fallback_trigger_threshold: Input parameter.
        name_model_accept_threshold: Input parameter.

    Returns:
        object: Computed result.

    """
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
    model_signals: dict | None = None
    fallback_reason = "not_attempted"
    if allow_model_fallback and name_confidence < name_fallback_trigger_threshold and (emails or phones):
        fallback_reason = "attempted"
        model_resolver = model_name_resolver or ModelNameResolver()
        model_name, model_confidence, model_signals = model_resolver.resolve_name(
            parsed.raw_text,
            {
                "emails": emails,
                "phones": phones,
                "language": parsed.language,
            },
        )
        if model_name and model_confidence >= name_model_accept_threshold and model_confidence > name_confidence:
            name = model_name
            name_confidence = model_confidence
            name_signals = {
                "primary": name_signals,
                "fallback": model_signals,
            }
            model_used = True
            fallback_reason = "accepted"
        else:
            fallback_reason = "rejected"

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
        "name_resolution": {
            "primary_method": "rules",
            "fallback_method": "model_llm",
            "fallback_status": fallback_reason,
            "trigger_threshold": round(name_fallback_trigger_threshold, 4),
            "accept_threshold": round(name_model_accept_threshold, 4),
            "primary_confidence": round(float(confidence_inputs.get("name_confidence", 0.0)), 4),
            "fallback_signals": model_signals,
        },
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
    """Compute content hash.

    Args:
        text: Input parameter.

    Returns:
        object: Computed result.

    """
    normalized = _normalize_whitespace(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_identity_key(
    *,
    name: str | None,
    email: str | None,
    phone: str | None,
    clean_text: str,
) -> tuple[str, str]:
    """Compute identity key.

    Args:
        name: Input parameter.
        email: Input parameter.
        phone: Input parameter.
        clean_text: Input parameter.

    Returns:
        object: Computed result.

    """
    normalized_email = normalize_email(email) if email else None
    normalized_phone = normalize_phone(phone) if phone else None
    normalized_name = _normalize_name(name) if name else None

    if normalized_email:
        digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:24]
        return f"candidate:v2:email:{digest}", "email_primary"
    if normalized_phone:
        digest = hashlib.sha256(normalized_phone.encode("utf-8")).hexdigest()[:24]
        return f"candidate:v2:phone:{digest}", "phone_primary"
    if normalized_name:
        digest = hashlib.sha256(normalized_name.lower().encode("utf-8")).hexdigest()[:24]
        return f"candidate:v2:name:{digest}", "name_primary"

    digest = compute_content_hash(clean_text)[:24]
    return f"resume_content:{digest}", "content_fallback"


def extract_emails(text: str) -> list[str]:
    """Extract emails.

    Args:
        text: Input parameter.

    Returns:
        object: Computed result.

    """
    emails = [normalize_email(match.group(1)) for match in EMAIL_REGEX.finditer(text)]
    unique = sorted({email for email in emails if email})
    return unique


def extract_phones(text: str) -> list[str]:
    """Extract phones.

    Args:
        text: Input parameter.

    Returns:
        object: Computed result.

    """
    phones = [normalize_phone(match.group(0)) for match in PHONE_REGEX.finditer(text)]
    unique = sorted({phone for phone in phones if phone})
    return unique


def normalize_email(email: str | None) -> str | None:
    """Run normalize email.

    Args:
        email: Input parameter.

    Returns:
        object: Computed result.

    """
    if not email:
        return None
    value = email.strip().lower().replace("mailto:", "")
    value = value.rstrip(".,;:)")
    if "@" not in value:
        return None
    return value


def normalize_phone(phone: str | None) -> str | None:
    """Run normalize phone.

    Args:
        phone: Input parameter.

    Returns:
        object: Computed result.

    """
    if not phone:
        return None
    raw = phone.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if has_plus and not 8 <= len(digits) <= 15:
        return None
    if not has_plus and len(digits) < 10:
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
    """Run score identity confidence.

    Args:
        name: Input parameter.
        email: Input parameter.
        phone: Input parameter.
        name_confidence: Input parameter.

    Returns:
        object: Computed result.

    """
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


def estimate_name_quality(name: str | None) -> float:
    """Run estimate name quality.

    Args:
        name: Input parameter.

    Returns:
        object: Computed result.

    """
    if not name:
        return 0.0
    normalized = _normalize_name(name)
    if not normalized:
        return 0.0
    if not _is_valid_person_name(normalized):
        return 0.2
    score = 0.55
    token_count = len(normalized.split())
    if 2 <= token_count <= 4:
        score += 0.2
    lowered = normalized.lower()
    if any(hint in lowered for hint in LOCATION_HINTS):
        score -= 0.35
    if any(phrase in lowered for phrase in NON_NAME_PHRASES):
        score -= 0.35
    return round(max(0.0, min(1.0, score)), 4)


def _email_name_match_bonus(name: str, emails: list[str]) -> float:
    """Helper for  email name match bonus.

    Args:
        name: Input parameter.
        emails: Input parameter.

    Returns:
        object: Computed result.

    """
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
    """Helper for  normalize name.

    Args:
        value: Input parameter.

    Returns:
        object: Computed result.

    """
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = re.sub(r"[^\w\s'\-]", " ", cleaned)
    cleaned = _normalize_whitespace(cleaned)
    tokens = [token for token in cleaned.split(" ") if token]
    return " ".join(token.capitalize() for token in tokens)


def _normalize_whitespace(text: str) -> str:
    """Helper for  normalize whitespace.

    Args:
        text: Input parameter.

    Returns:
        object: Computed result.

    """
    return re.sub(r"\s+", " ", text).strip()


def _strip_line_prefix(text: str) -> str:
    """Helper for  strip line prefix.

    Args:
        text: Input parameter.

    Returns:
        object: Computed result.

    """
    stripped = text.strip()
    stripped = re.sub(r"^[#>\-\*\u2022]+\s*", "", stripped)
    return stripped


def _normalize_candidate_name_line(line: str) -> str:
    """Helper for  normalize candidate name line.

    Args:
        line: Input parameter.

    Returns:
        object: Computed result.

    """
    candidate = _normalize_whitespace(line)
    candidate = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", candidate)
    for sep in [" | ", " — ", " – ", " - "]:
        if sep in candidate:
            candidate = candidate.split(sep, 1)[0].strip()
            break
    candidate = re.sub(r"\s+", " ", candidate).strip(" -|,;")
    return candidate


def _is_valid_person_name(name: str | None) -> bool:
    """Helper for  is valid person name.

    Args:
        name: Input parameter.

    Returns:
        bool: True when the condition is met.

    """
    if not name:
        return False
    cleaned = _normalize_whitespace(name)
    parts = cleaned.split(" ")
    if not 2 <= len(parts) <= 4:
        return False
    lowered = cleaned.lower()
    if any(word in lowered for word in NON_NAME_SECTION_WORDS):
        return False
    if any(phrase in lowered for phrase in NON_NAME_PHRASES):
        return False
    if any(hint in lowered for hint in LOCATION_HINTS):
        return False
    if any(char.isdigit() for char in cleaned):
        return False
    name_like = sum(
        1
        for part in parts
        if (part[:1].isupper() and part[1:].islower()) or part.isupper()
    )
    return name_like >= 2
