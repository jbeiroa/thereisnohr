import pytest
from src.storage.models import JobPosting, Candidate
from src.storage.repositories import MatchRepository, JobPostingRepository, CandidateRepository

@pytest.mark.integration
def test_match_repository_interview_pack(db_session) -> None:
    # Setup test data
    job_repo = JobPostingRepository(db_session)
    job = job_repo.create(title="Test Job", description="Test Desc")
    
    cand_repo = CandidateRepository(db_session)
    cand = cand_repo.create(name="Test Candidate")
    
    match_repo = MatchRepository(db_session)
    
    reasons = {"rank": 1}
    interview_pack = {"technical_questions": ["Q1"]}
    
    match = match_repo.create(
        job_id=job.id,
        candidate_id=cand.id,
        final_score=0.9,
        reasons_json=reasons,
        interview_pack_json=interview_pack
    )
    
    assert match.id is not None
    assert match.interview_pack_json == interview_pack
    
    fetched_match = match_repo.get_by_job_and_candidate(job.id, cand.id)
    assert fetched_match is not None
    assert fetched_match.interview_pack_json["technical_questions"] == ["Q1"]
