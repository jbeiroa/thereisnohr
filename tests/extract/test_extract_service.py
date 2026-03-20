import pytest
from unittest.mock import MagicMock

from src.extract.service import ExtractionService
from src.extract.types import CandidateSignals, JobRequirements, ExtractionDiagnostics
from src.llm.client import LLMClient
from src.llm.types import LLMCallMetadata, LLMUsage, LLMAttempt


@pytest.fixture
def mock_llm_client():
    return MagicMock(spec=LLMClient)


@pytest.fixture
def extraction_service(mock_llm_client):
    return ExtractionService(llm_client=mock_llm_client, extractor_model_alias="extractor_default")


def test_extract_job_requirements(extraction_service, mock_llm_client):
    job_description = "We need a Python developer with 3 years of experience, a BS in Computer Science, and AWS skills."
    expected_result = JobRequirements(
        hard_skills=["Python", "AWS"],
        soft_skills=[],
        years_experience_min=3,
        education_requirements=["BS in Computer Science"],
        certifications=[]
    )
    mock_llm_client.generate_structured.return_value = expected_result

    result = extraction_service.extract_job_requirements(job_description)
    
    assert result == expected_result
    mock_llm_client.generate_structured.assert_called_once()
    kwargs = mock_llm_client.generate_structured.call_args.kwargs
    assert "Python developer" in kwargs["prompt"]
    assert kwargs["schema"] == JobRequirements
    assert kwargs["model_alias"] == "extractor_default"


def test_extract_candidate_signals(extraction_service, mock_llm_client):
    sections = {
        "experience": "Software Engineer at Google\n- Developed Python APIs",
        "skills": "Python, FastApi, PostgreSQL",
    }
    expected_result = CandidateSignals(
        skills=["Python", "FastApi", "PostgreSQL"],
        experience_highlights=["Software Engineer at Google - Developed Python APIs"],
        education=[],
        certifications=[],
        summary=None
    )
    meta = LLMCallMetadata(
        model_alias="extractor_default",
        attempts=[LLMAttempt(attempt_index=1, model="test-model", succeeded=True)],
        usage=LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, estimated_cost_usd=0.001)
    )
    
    mock_llm_client.generate_structured_with_meta.return_value = (expected_result, meta)

    result = extraction_service.extract_candidate_signals(sections)
    
    assert result == expected_result
    mock_llm_client.generate_structured_with_meta.assert_called_once()


def test_extract_with_diagnostics(extraction_service, mock_llm_client):
    sections = {
        "experience": "Backend Dev",
    }
    expected_result = CandidateSignals(
        skills=[],
        experience_highlights=["Backend Dev"],
        education=[],
        certifications=[],
        summary=None
    )
    meta = LLMCallMetadata(
        model_alias="extractor_default",
        selected_model="test-model",
        attempts=[LLMAttempt(attempt_index=1, model="test-model", succeeded=True)],
        fallback_used=False,
        latency_ms=150.0,
        usage=LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, estimated_cost_usd=0.001)
    )
    
    mock_llm_client.generate_structured_with_meta.return_value = (expected_result, meta)

    result, diagnostics = extraction_service.extract_with_diagnostics(sections)
    
    assert result == expected_result
    assert isinstance(diagnostics, ExtractionDiagnostics)
    assert diagnostics.model_alias == "extractor_default"
    assert diagnostics.attempts == 1
    assert diagnostics.fallback_used is False
    assert diagnostics.latency_ms == 150.0
    assert diagnostics.prompt_tokens == 100
    assert diagnostics.completion_tokens == 50
    assert diagnostics.total_tokens == 150
    assert diagnostics.estimated_cost_usd == 0.001


def test_extract_job_requirements_raises_error(extraction_service, mock_llm_client):
    mock_llm_client.generate_structured.side_effect = Exception("Provider failed")
    
    with pytest.raises(Exception):
        extraction_service.extract_job_requirements("Test")
