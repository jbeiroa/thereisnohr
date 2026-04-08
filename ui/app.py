import streamlit as st
import time
from pathlib import Path
import fitz
from ui.api_client import APIClient

st.set_page_config(page_title="thereisnohr ATS", page_icon="🤖", layout="wide")

def generate_pdf_report(matches, job_title):
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    
    page.insert_text((50, y), f"Ranking Report: {job_title}", fontsize=18)
    y += 30
    page.insert_text((50, y), f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}", fontsize=10)
    y += 40
    
    for i, match in enumerate(matches):
        if y > 750:
            page = doc.new_page()
            y = 50
            
        candidate = match.get("candidate") or {}
        name = candidate.get("name") or f"ID: {candidate.get('id')}"
        score = match.get("final_score", 0.0)
        
        page.insert_text((50, y), f"{i+1}. {name} | Score: {score:.2f}", fontsize=14)
        y += 20
        
        reasons = match.get("reasons_json") or {}
        explanation = reasons.get("explanation") or {}
        summary = explanation.get("evidence_based_summary", "No summary available.")
        
        # Simple text wrapping
        lines = [summary[i:i+90] for i in range(0, len(summary), 90)]
        for line in lines:
            page.insert_text((70, y), line, fontsize=10)
            y += 12
            if y > 780:
                page = doc.new_page()
                y = 50
        
        y += 20

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def check_ingest_task(api, task_id, label):
    try:
        with st.sidebar.status(f"{label} (Task ID: {task_id})...") as status:
            while True:
                task_info = api.get_task(task_id)
                status_str = task_info["status"]
                
                if status_str == "COMPLETED":
                    status.update(label="Ingestion complete!", state="complete", expanded=True)
                    output = task_info.get("output_payload", {})
                    processed = output.get("result", {}).get("processed", 0)
                    results = output.get("result", {}).get("results", [])
                    
                    st.sidebar.success(f"Successfully processed {processed} files.")
                    if results:
                        st.sidebar.write("Results Summary:")
                        st.sidebar.dataframe(results)
                        
                    if "active_ingest_task" in st.session_state:
                        del st.session_state["active_ingest_task"]
                    if "active_ingest_label" in st.session_state:
                        del st.session_state["active_ingest_label"]
                    break
                elif status_str == "FAILED":
                    status.update(label="Ingestion failed!", state="error", expanded=True)
                    st.sidebar.error(f"Error: {task_info.get('error_message')}")
                    if "active_ingest_task" in st.session_state:
                        del st.session_state["active_ingest_task"]
                    if "active_ingest_label" in st.session_state:
                        del st.session_state["active_ingest_label"]
                    break
                
                time.sleep(2)
    except Exception as e:
        st.sidebar.error(f"Error checking process: {e}")
        if "active_ingest_task" in st.session_state:
            del st.session_state["active_ingest_task"]

def check_job_task(api, task_id, job_title):
    try:
        with st.status(f"Ingesting job: {job_title} (Task ID: {task_id})...") as status:
            while True:
                task_info = api.get_task(task_id)
                status_str = task_info["status"]
                
                if status_str == "COMPLETED":
                    status.update(label=f"Job '{job_title}' created!", state="complete", expanded=True)
                    st.success(f"Successfully processed requirements for {job_title}.")
                    if "active_job_task" in st.session_state:
                        del st.session_state["active_job_task"]
                    if "active_job_title" in st.session_state:
                        del st.session_state["active_job_title"]
                    time.sleep(1)
                    st.rerun()
                    break
                elif status_str == "FAILED":
                    status.update(label="Job creation failed!", state="error", expanded=True)
                    st.error(f"Error: {task_info.get('error_message')}")
                    if "active_job_task" in st.session_state:
                        del st.session_state["active_job_task"]
                    if "active_job_title" in st.session_state:
                        del st.session_state["active_job_title"]
                    break
                
                time.sleep(2)
    except Exception as e:
        st.error(f"Error checking job creation: {e}")
        if "active_job_task" in st.session_state:
            del st.session_state["active_job_task"]

def check_ranking_task(api, task_id, job_title):
    with st.status(f"Ranking candidates for {job_title} (Task ID: {task_id})...") as status:
        while True:
            task_info = api.get_task(task_id)
            status_str = task_info["status"]
            
            if status_str == "COMPLETED":
                status.update(label=f"Ranking for {job_title} complete!", state="complete", expanded=True)
                st.success("Successfully ranked candidates.")
                if "active_ranking_task" in st.session_state:
                    del st.session_state["active_ranking_task"]
                if "active_ranking_job" in st.session_state:
                    del st.session_state["active_ranking_job"]
                time.sleep(1)
                st.rerun()
                break
            elif status_str == "FAILED":
                status.update(label="Ranking failed!", state="error", expanded=True)
                st.error(f"Error: {task_info.get('error_message')}")
                if "active_ranking_task" in st.session_state:
                    del st.session_state["active_ranking_task"]
                if "active_ranking_job" in st.session_state:
                    del st.session_state["active_ranking_job"]
                break
            
            time.sleep(2)

def start_ingest_task(api, task, label):
    try:
        st.session_state["active_ingest_task"] = task["id"]
        st.session_state["active_ingest_label"] = label
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error starting process: {e}")

def main():
    api = APIClient()

    # --- SIDEBAR: Ingestion Panel ---
    st.sidebar.title("Ingestion Panel")
    st.sidebar.markdown("Add resumes to the database.")

    # Check active ingest task
    active_ingest_id = st.session_state.get("active_ingest_task")
    active_ingest_lbl = st.session_state.get("active_ingest_label", "Ingesting Resumes")
    if active_ingest_id:
        check_ingest_task(api, active_ingest_id, active_ingest_lbl)

    default_data_path = (Path.cwd() / "data").resolve()
    tab1, tab2 = st.sidebar.tabs(["📂 Local Folder", "📤 Upload Files"])

    with tab1:
        with st.form("ingest_folder_form"):
            input_dir = st.text_input("Local Folder Path", value=str(default_data_path), help="Absolute path to folder.")
            pattern = st.text_input("Glob Pattern", value="*.pdf")
            submit_folder = st.form_submit_button("Start Batch Ingestion")

        if submit_folder:
            if not active_ingest_id:
                start_ingest_task(api, api.ingest_resumes(input_dir, pattern), f"Ingesting: {input_dir}")
            else:
                st.sidebar.warning("An ingestion task is already running.")

    with tab2:
        uploaded_files = st.file_uploader("Choose PDF resumes", type=["pdf"], accept_multiple_files=True)
        if st.button("Upload and Process"):
            if not uploaded_files:
                st.sidebar.warning("Please select at least one file to upload.")
            else:
                if not active_ingest_id:
                    start_ingest_task(api, api.upload_resumes(uploaded_files), f"Uploading {len(uploaded_files)} files")
                else:
                    st.sidebar.warning("An ingestion task is already running.")

    # --- MAIN AREA ---
    # Fetch data once per rerun
    try:
        jobs = api.list_jobs()
    except Exception as e:
        st.error(f"Could not connect to API: {e}")
        return

    col_job, col_rank = st.columns([1, 1], gap="large")

    # --- MIDDLE PANEL: Job Management ---
    with col_job:
        st.header("Job Panel")
        
        active_job_id = st.session_state.get("active_job_task")
        active_job_lbl = st.session_state.get("active_job_title", "New Job")
        if active_job_id:
            check_job_task(api, active_job_id, active_job_lbl)

        selected_job_id = None
        selected_job_title = None

        if jobs:
            st.subheader("Selected Job")
            job_options = {f"{j['title']} (ID: {j['id']})": j for j in jobs}
            
            # Selectbox to pick a job
            selected_label = st.selectbox("Select a Job Posting", options=list(job_options.keys()))
            selected_job = job_options[selected_label]
            selected_job_id = selected_job['id']
            selected_job_title = selected_job['title']
            
            with st.container(border=True):
                st.markdown(f"### {selected_job['title']}")
                st.write(f"**ID:** {selected_job['id']}")
                if selected_job.get('requirements_json'):
                    reqs = selected_job['requirements_json']
                    st.write("**Requirements:**")
                    st.write(f"- Role: {reqs.get('role', 'N/A')}")
                    st.write(f"- Seniority: {reqs.get('seniority_level', 'N/A')}")
                    st.write(f"- Hard Skills: {', '.join(reqs.get('hard_skills', []))}")
                    st.write(f"- Soft Skills: {', '.join(reqs.get('soft_skills', []))}")
                with st.expander("Show Full Description"):
                    st.text(selected_job.get('description', 'No description available.'))
        else:
            st.info("No jobs found. Add a new job below.")

        st.divider()

        with st.expander("➕ Add New Job"):
            new_job_title = st.text_input("Job Title", placeholder="Senior Python Engineer")
            t1, t2 = st.tabs(["Paste Text", "Upload File"])
            
            job_desc_text = ""
            with t1:
                paste_text = st.text_area("Job Description", placeholder="Paste the full job description here...", height=200)
                if paste_text:
                    job_desc_text = paste_text
            with t2:
                uploaded_file = st.file_uploader("Upload Text or Markdown file", type=["txt", "md"])
                if uploaded_file:
                    job_desc_text = uploaded_file.read().decode("utf-8")
                    st.info(f"Loaded {len(job_desc_text)} characters.")

            if st.button("Create Job Posting"):
                if not new_job_title or not job_desc_text:
                    st.warning("Please provide both a job title and description.")
                elif not active_job_id:
                    try:
                        task = api.create_job(new_job_title, job_desc_text)
                        st.session_state["active_job_task"] = task["id"]
                        st.session_state["active_job_title"] = new_job_title
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating job: {e}")
                else:
                    st.warning("A job creation task is already running.")
                    
        if jobs:
            st.subheader("Job List")
            st.dataframe(jobs, use_container_width=True)

    # --- RIGHT PANEL: Ranking ---
    with col_rank:
        st.header("Ranking Panel")
        
        active_ranking_id = st.session_state.get("active_ranking_task")
        active_ranking_lbl = st.session_state.get("active_ranking_job", "Unknown Job")
        if active_ranking_id:
            check_ranking_task(api, active_ranking_id, active_ranking_lbl)

        if not selected_job_id:
            st.info("Select or create a job in the Job Panel to rank candidates.")
        else:
            with st.container(border=True):
                top_k = st.slider("Number of Candidates to Rank", min_value=1, max_value=20, value=5)
                if st.button(f"Rank for {selected_job_title}"):
                    if not active_ranking_id:
                        try:
                            task = api.rank_job(selected_job_id, top_k)
                            st.session_state["active_ranking_task"] = task["id"]
                            st.session_state["active_ranking_job"] = selected_job_title
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error starting ranking: {e}")
                    else:
                        st.warning("A ranking task is already active.")
                        
            st.divider()
            
            matches = api.list_matches(job_id=selected_job_id, limit=top_k)
            if not matches:
                st.info("No matches found for this job yet. Run the ranking process above.")
            else:
                if len(matches) < top_k:
                    st.caption(f"Note: Only {len(matches)} distinct candidate(s) are available in the database for this job.")
                
                # Export buttons
                c1, c2 = st.columns(2)
                report_text = f"Ranking Report: {selected_job_title}\n" + "="*40 + "\n"
                for i, m in enumerate(matches):
                    c = m.get('candidate') or {}
                    name = c.get('name') or f"ID: {c.get('id')}"
                    reasons = m.get('reasons_json') or {}
                    explanation = reasons.get('explanation') or {}
                    report_text += f"{i+1}. {name} | Score: {m['final_score']:.2f}\n"
                    report_text += f"   Summary: {explanation.get('evidence_based_summary', 'N/A')}\n\n"
                c1.download_button("Export (TXT)", data=report_text, file_name=f"ranking_{selected_job_id}.txt")
                
                pdf_bytes = generate_pdf_report(matches, selected_job_title)
                c2.download_button("Export (PDF)", data=pdf_bytes, file_name=f"ranking_{selected_job_id}.pdf", mime="application/pdf")

                # Display Results in a Grid-like layout
                st.subheader("Top Candidates")
                for i, match in enumerate(matches):
                    candidate = match.get("candidate") or {}
                    name = candidate.get("name") or f"ID: {candidate.get('id')}"
                    score = match.get("final_score", 0.0)
                    
                    with st.expander(f"#{i+1}: {name} (Score: {score:.2f})", expanded=(i==0)):
                        reasons = match.get("reasons_json") or {}
                        explanation = reasons.get("explanation") or {}
                        
                        if explanation:
                            # 2-column layout matching the sketch grid concept
                            r_col1, r_col2 = st.columns([1, 1])
                            with r_col1:
                                st.markdown("##### Candidate Summary")
                                st.write(explanation.get('evidence_based_summary', 'No summary provided.'))
                            with r_col2:
                                st.markdown("##### Reasons")
                                
                                strengths = explanation.get("strengths_with_evidence") or []
                                if strengths:
                                    st.markdown("**Strengths:**")
                                    for s in strengths:
                                        st.write(f"- {s.get('skill_or_trait')}")
                                
                                gaps = explanation.get("gaps_and_risks") or []
                                if gaps:
                                    st.markdown("**Gaps & Risks:**")
                                    for gap in gaps:
                                        st.write(f"- {gap.get('missing_requirement')}")
                                        
                        st.divider()
                        interview_pack = match.get("interview_pack_json")
                        if interview_pack:
                            if st.checkbox("Show Prep Pack", key=f"show_prep_{match['id']}"):
                                st.markdown("##### Interview Prep Pack")
                                tq = interview_pack.get("technical_questions", [])
                                if tq:
                                    st.write("**Technical:**")
                                    for q in tq: 
                                        st.write(f"- {q}")
                                bq = interview_pack.get("behavioral_questions", [])
                                if bq:
                                    st.write("**Behavioral:**")
                                    for q in bq: 
                                        st.write(f"- {q}")
                        else:
                            if st.button("Generate Prep Pack", key=f"gen_prep_{match['id']}"):
                                try:
                                    with st.spinner("Generating..."):
                                        task = api.generate_prep(match["id"])
                                        while True:
                                            t = api.get_task(task["id"])
                                            if t["status"] == "COMPLETED": 
                                                break
                                            if t["status"] == "FAILED": 
                                                raise Exception(t.get("error_message"))
                                            time.sleep(2)
                                        st.success("Generated! Refresh to view.")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")

if __name__ == "__main__":
    main()