from types import SimpleNamespace

from scripts.backfill_candidate_identity_v2 import _candidate_rank, _group_key, _link_list


def test_group_key_prefers_email_over_phone() -> None:
    candidate = SimpleNamespace(email="JDOE@example.com", phone="+1 415 555 0100")
    assert _group_key(candidate) == "email:jdoe@example.com"


def test_link_list_supports_list_and_dict_shapes() -> None:
    assert _link_list(["https://a.example.com"]) == ["https://a.example.com"]
    assert _link_list({"urls": ["https://a.example.com"]}) == ["https://a.example.com"]


def test_candidate_rank_prefers_name_quality_then_resume_count() -> None:
    candidate = SimpleNamespace(id=2, name="John Doe")
    quality, resumes, _ = _candidate_rank(candidate, {2: 3})
    assert quality >= 0.7
    assert resumes == 3
