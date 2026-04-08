"""Workflow orchestration for job/candidate retrieval and ranking."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.extract.types import CandidateSignals, JobRequirements
from src.ranking.service import RankingService
from src.ranking.types import RankInput, RankedCandidate, ScoreBreakdown, RankExplanation
from src.retrieval.service import RetrievalService
from src.storage import models
from src.storage.repositories import MatchRepository, ResumeRepository


@dataclass
class RankingWorkflow:
    """Orchestrates the end-to-end retrieval and hybrid ranking pipeline."""

    session: Session

    def run(self, job_id: int, top_k: int = 5, generate_prep_packs: int = 3) -> list:
        """Runs the pipeline for a specific job posting."""
        # 1. Load Job Posting
        job = self.session.get(models.JobPosting, job_id)
        if not job:
            raise ValueError(f"Job posting with ID {job_id} not found.")

        requirements = JobRequirements.model_validate(job.requirements_json)

        # 2. Vector Retrieval
        retrieval_service = RetrievalService(session=self.session)
        top_candidates = retrieval_service.top_k(job.description, k=top_k * 2)

        # 3. Load structured signals and prepare inputs
        resume_repo = ResumeRepository(self.session)
        match_repo = MatchRepository(self.session)
        
        rank_inputs: list[RankInput] = []
        input_map: dict[int, RankInput] = {}
        existing_ranked: list[RankedCandidate] = []
        
        for candidate_id, score in top_candidates:
            existing = match_repo.get_by_job_and_candidate(job_id=job_id, candidate_id=candidate_id)
            
            if existing and existing.reasons_json and existing.final_score is not None:
                try:
                    reasons = existing.reasons_json
                    bd = reasons.get("breakdown", {})
                    exp = reasons.get("explanation")
                    
                    scores = ScoreBreakdown(**bd) if bd else ScoreBreakdown(
                        deterministic_score=existing.final_score,
                        final_score=existing.final_score,
                        matched_hard_skills=[],
                        missing_hard_skills=[]
                    )
                    explanation = RankExplanation(**exp) if exp else None
                    
                    existing_ranked.append(RankedCandidate(
                        candidate_id=candidate_id,
                        rank=reasons.get("rank", 0),
                        scores=scores,
                        explanation=explanation
                    ))
                    
                    # Store in input_map for potential prep pack generation
                    latest_resume = resume_repo.get_latest_resume_by_candidate_id(candidate_id)
                    if latest_resume and latest_resume.signals_json:
                        signals = CandidateSignals.model_validate(latest_resume.signals_json)
                        input_map[candidate_id] = RankInput(
                            candidate_id=candidate_id,
                            retrieval_score=score,
                            requirements=requirements,
                            signals=signals,
                        )
                    continue
                except Exception:
                    pass

            latest_resume = resume_repo.get_latest_resume_by_candidate_id(candidate_id)
            if not latest_resume or not latest_resume.signals_json:
                continue

            signals = CandidateSignals.model_validate(latest_resume.signals_json)
            rank_input = RankInput(
                candidate_id=candidate_id,
                retrieval_score=score,
                requirements=requirements,
                signals=signals,
            )
            rank_inputs.append(rank_input)
            input_map[candidate_id] = rank_input

        # 4. Hybrid Ranking
        ranking_service = RankingService()
        new_ranked = ranking_service.rank_candidates(rank_inputs, top_k=top_k) if rank_inputs else []

        all_ranked = existing_ranked + new_ranked
        all_ranked.sort(key=lambda x: x.scores.final_score, reverse=True)

        for i, candidate in enumerate(all_ranked, 1):
            candidate.rank = i

        ranked = all_ranked[:top_k]

        # 5. Persist Results
        for r in ranked:
            prep_pack_json = None
            existing = match_repo.get_by_job_and_candidate(job_id=job_id, candidate_id=r.candidate_id)
            
            if r.rank <= generate_prep_packs and r.explanation:
                if existing and existing.interview_pack_json:
                    prep_pack_json = existing.interview_pack_json
                else:
                    pack = ranking_service.generate_interview_pack(input_map[r.candidate_id], r.explanation)
                    if pack:
                        prep_pack_json = pack.model_dump()

            if existing:
                existing.retrieval_score = next((s for cid, s in top_candidates if cid == r.candidate_id), existing.retrieval_score)
                existing.rerank_score = r.scores.llm_adjustment
                existing.final_score = r.scores.final_score
                existing.reasons_json = {
                    "rank": r.rank,
                    "explanation": r.explanation.model_dump() if r.explanation else None,
                    "breakdown": r.scores.model_dump(),
                }
                if prep_pack_json:
                    existing.interview_pack_json = prep_pack_json
            else:
                match_repo.create(
                    job_id=job_id,
                    candidate_id=r.candidate_id,
                    retrieval_score=next((s for cid, s in top_candidates if cid == r.candidate_id), None),
                    rerank_score=r.scores.llm_adjustment,
                    final_score=r.scores.final_score,
                    reasons_json={
                        "rank": r.rank,
                        "explanation": r.explanation.model_dump() if r.explanation else None,
                        "breakdown": r.scores.model_dump(),
                    },
                    interview_pack_json=prep_pack_json,
                )

        return ranked
