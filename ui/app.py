import streamlit as st
from ui.api_client import APIClient

st.set_page_config(
    page_title="thereisnohr ATS",
    page_icon="🤖",
    layout="wide",
)

def main():
    st.sidebar.title("Navigation")
    st.title("Welcome to thereisnohr ATS 🤖")
    st.markdown("""
    This is a provider-agnostic Applicant Tracking System (ATS) designed to ingest resumes,
    extract candidate signals, and perform semantic retrieval and ranking.
    
    ### How to use this tool:
    1. **Ingest Resumes**: Add new candidate resumes to the database from a local folder.
    2. **Manage Jobs**: Define job requirements by pasting text or uploading descriptions.
    3. **Rank Candidates**: Select a job to find the best-matching candidates from your database.
    """)

    # Display some system stats (simplified for now)
    api = APIClient()
    try:
        jobs = api.list_jobs(limit=100)
        candidates = api.list_candidates(limit=100)
        
        col1, col2 = st.columns(2)
        col1.metric("Total Jobs", len(jobs))
        col2.metric("Total Candidates", len(candidates))
        
    except Exception as e:
        st.error(f"Could not connect to the ATS backend: {e}")
        st.info("Please ensure the FastAPI server is running with: `uv run uvicorn src.api.app:app`")

if __name__ == "__main__":
    main()
