import streamlit as st
import os
import math
import tempfile
from pathlib import Path

from src.llm.registry import ModelAliasRegistry
from src.llm.client import LiteLLMClient
from src.ingest.parser import PDFResumeParser
from src.extract.service import ExtractionService
from src.ranking.service import RankingService
from src.ranking.types import RankInput

st.set_page_config(page_title="thereisnohr - Demo App", page_icon="🧪", layout="wide")

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    if magnitude1 * magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

def init_llm_client(api_key: str) -> LiteLLMClient:
    os.environ["OPENAI_API_KEY"] = api_key
    registry_path = Path("config/demo_aliases.yaml")
    if not registry_path.exists():
        st.error("Error: config/demo_aliases.yaml not found. Please ensure it exists for the demo app.")
        st.stop()
    registry = ModelAliasRegistry(registry_path)
    # Increased timeout and retries for more robust batch processing
    return LiteLLMClient(registry=registry, timeout_seconds=120.0, max_retries=5)

@st.fragment
def ingest_section(parser, extract_service, llm_client):
    st.subheader("1. Ingest Resumes")
    uploaded_files = st.file_uploader("Upload Resumes (Max 20 PDF files)", type=["pdf"], accept_multiple_files=True)
    if st.button("Process Resumes"):
        if not uploaded_files:
            st.warning("Please upload at least one PDF file.")
        elif len(uploaded_files) > 20:
            st.error("Maximum 20 files allowed in demo mode.")
        else:
            st.session_state.demo_candidates = []
            with st.spinner("Parsing, extracting, and embedding resumes..."):
                for idx, file in enumerate(uploaded_files):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(file.getvalue())
                        tmp_path = Path(tmp.name)
                    
                    try:
                        parsed = parser.parse(tmp_path)
                        sections = parsed.sections
                        texts_to_embed = [v.strip() for k, v in sections.items() if v.strip() and k not in ["skills", "languages", "certifications"]]
                        if not texts_to_embed and parsed.clean_text.strip():
                            texts_to_embed = [parsed.clean_text.strip()]
                        
                        if not texts_to_embed:
                            st.warning(f"Could not extract meaningful text from {file.name}. Skipping embedding.")
                            vectors = []
                        else:
                            vectors, _ = llm_client.embed_with_meta(
                                texts=texts_to_embed, 
                                embedding_model_alias="embedding_default"
                            )
                        
                        signals = extract_service.extract_candidate_signals(sections)
                        
                        st.session_state.demo_candidates.append({
                            "id": idx + 1,
                            "name": file.name,
                            "vectors": vectors,
                            "signals": signals
                        })
                    except Exception as e:
                        st.error(f"Error processing {file.name}: {e}")
                    finally:
                        if tmp_path.exists():
                            os.remove(tmp_path)
                st.success(f"Processed {len(st.session_state.demo_candidates)} resumes successfully.")
                st.rerun()

    if st.session_state.demo_candidates:
        st.info(f"Currently tracking {len(st.session_state.demo_candidates)} candidate(s) in memory.")

@st.fragment
def ranking_section(extract_service, ranking_service, llm_client):
    st.subheader("2. Job Posting & Ranking")
    job_desc = st.text_area("Paste Job Description", height=200)
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Process Job Posting"):
            if not job_desc.strip():
                st.warning("Please provide a job description.")
            else:
                with st.spinner("Extracting requirements and embedding job description..."):
                    try:
                        reqs = extract_service.extract_job_requirements(job_desc)
                        vector = llm_client.embed([job_desc], "embedding_default")[0]
                        st.session_state.demo_job = {"requirements": reqs, "vector": vector, "desc": job_desc}
                        st.success("Job posting processed successfully.")
                    except Exception as e:
                        st.error(f"Error processing job: {e}")
    
    with col_btn2:
        top_k = st.slider("Top K Candidates", 1, 20, 5)
        if st.button("Rank Candidates"):
            if not st.session_state.demo_candidates:
                st.warning("Please process some resumes first.")
            elif not st.session_state.demo_job:
                st.warning("Please process a job description first.")
            else:
                with st.spinner("Calculating similarity and LLM Reranking..."):
                    job_vector = st.session_state.demo_job["vector"]
                    job_reqs = st.session_state.demo_job["requirements"]
                    
                    rank_inputs = []
                    for cand in st.session_state.demo_candidates:
                        max_sim = max(cosine_similarity(job_vector, v) for v in cand["vectors"]) if cand["vectors"] else 0.0
                        
                        rank_inputs.append(RankInput(
                            candidate_id=cand["id"],
                            retrieval_score=max_sim,
                            requirements=job_reqs,
                            signals=cand["signals"]
                        ))
                        
                    ranked = ranking_service.rank_candidates(rank_inputs, top_k=top_k)
                    st.session_state.demo_results = ranked
                    st.success("Ranking complete!")

    if st.session_state.demo_results:
        st.divider()
        st.subheader(f"Top {top_k} Candidates")
        
        # We show as many as the slider says, up to the results we have
        display_count = min(top_k, len(st.session_state.demo_results))
        display_results = st.session_state.demo_results[:display_count]
        
        for i, r in enumerate(display_results):
            cand = next((c for c in st.session_state.demo_candidates if c["id"] == r.candidate_id), None)
            if not cand:
                continue
            
            with st.expander(f"#{i+1}: {cand['name']} (Score: {r.scores.final_score:.2f})", expanded=(i==0)):
                if r.explanation:
                    # Qualitative Evaluation Column
                    st.markdown("### 📝 Qualitative Evaluation")
                    st.write(r.explanation.evidence_based_summary)
                    
                    col_eval1, col_eval2 = st.columns([1, 1])
                    with col_eval1:
                        st.markdown("**Strengths:**")
                        if r.explanation.strengths_with_evidence:
                            for s in r.explanation.strengths_with_evidence:
                                st.markdown(f"- **{s.skill_or_trait}**: *\"{s.resume_evidence_quote}\"*")
                        else:
                            st.write("None identified.")
                    
                    with col_eval2:
                        st.markdown("**Gaps & Risks:**")
                        if r.explanation.gaps_and_risks:
                            for gap in r.explanation.gaps_and_risks:
                                st.markdown(f"- **{gap.missing_requirement}**: {gap.impact} *(Hint: {gap.uncertainty_hint})*")
                        else:
                            st.write("No major gaps identified.")

                    # Interview Pack Section
                    if r.interview_pack:
                        st.divider()
                        st.markdown("### 🎤 Interview Prep Pack")
                        
                        ip_col1, ip_col2, ip_col3 = st.columns(3)
                        with ip_col1:
                            st.markdown("**Technical**")
                            for q in r.interview_pack.technical_questions:
                                st.write(f"- {q}")
                        with ip_col2:
                            st.markdown("**Behavioral**")
                            for q in r.interview_pack.behavioral_questions:
                                st.write(f"- {q}")
                        with ip_col3:
                            st.markdown("**Clarification**")
                            for q in r.interview_pack.clarification_questions:
                                st.write(f"- {q}")
                else:
                    st.info("No LLM reranking available for this candidate. Click 'Rank Candidates' with a higher Top K value to generate a qualitative evaluation.")
                
                # Show score breakdown clearly
                st.divider()
                st.markdown("**Score Breakdown:**")
                st_col1, st_col2, st_col3 = st.columns(3)
                st_col1.metric("Retrieval Score", f"{r.scores.deterministic_score - (r.scores.llm_adjustment if r.explanation else 0):.2f}")
                st_col2.metric("LLM Adjustment", f"{r.scores.llm_adjustment:+.2f}" if r.explanation else "N/A")
                st_col3.metric("Final Score", f"{r.scores.final_score:.2f}")

def main():
    st.title("thereisnohr - In-Memory Demo 🧪")
    st.markdown(
        "Upload up to 20 resumes, paste a job description, and rank candidates instantly using OpenAI models. "
        "No data is saved or persisted to any database."
    )

    api_key = st.text_input("OpenAI API Key (required)", type="password", help="Your key is not stored anywhere.")
    
    if not api_key:
        st.warning("Please enter your OpenAI API key to continue.")
        return

    try:
        llm_client = init_llm_client(api_key)
        extract_service = ExtractionService(llm_client)
        ranking_service = RankingService(llm_client=llm_client)
        parser = PDFResumeParser()
    except Exception as e:
        st.error(f"Failed to initialize LLM Client: {e}")
        return

    if "demo_candidates" not in st.session_state:
        st.session_state.demo_candidates = []
    if "demo_job" not in st.session_state:
        st.session_state.demo_job = None
    if "demo_results" not in st.session_state:
        st.session_state.demo_results = []
    
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        ingest_section(parser, extract_service, llm_client)

    with col2:
        ranking_section(extract_service, ranking_service, llm_client)

if __name__ == "__main__":
    main()
