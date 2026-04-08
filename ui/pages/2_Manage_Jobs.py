import streamlit as st
import time
from ui.api_client import APIClient

st.set_page_config(page_title="Manage Jobs", page_icon="💼", layout="wide")

def main():
    st.title("Manage Jobs 💼")
    st.markdown("Create and manage job descriptions for candidate matching.")

    api = APIClient()

    with st.expander("➕ Add New Job", expanded=True):
        job_title = st.text_input("Job Title", placeholder="Senior Python Engineer")
        
        tab1, tab2 = st.tabs(["Paste Text", "Upload File"])
        
        with tab1:
            job_description_text = st.text_area("Job Description", placeholder="Paste the full job description here...", height=300)
            
        with tab2:
            uploaded_file = st.file_uploader("Upload Text or Markdown file", type=["txt", "md"])
            if uploaded_file:
                job_description_text = uploaded_file.read().decode("utf-8")
                st.info(f"Loaded {len(job_description_text)} characters from {uploaded_file.name}")

        submit_button = st.button("Create Job Posting")

    if submit_button:
        if not job_title or not job_description_text:
            st.warning("Please provide both a job title and description.")
        else:
            try:
                task = api.create_job(job_title, job_description_text)
                task_id = task["id"]
                
                with st.status(f"Ingesting job: {job_title} (Task ID: {task_id})...") as status:
                    while True:
                        task_info = api.get_task(task_id)
                        status_str = task_info["status"]
                        
                        if status_str == "COMPLETED":
                            status.update(label=f"Job {job_title} created successfully!", state="complete", expanded=True)
                            st.success(f"Successfully processed requirements for {job_title}.")
                            break
                        elif status_str == "FAILED":
                            status.update(label="Job creation failed!", state="error", expanded=True)
                            st.error(f"Error: {task_info.get('error_message')}")
                            break
                        
                        time.sleep(2)
            except Exception as e:
                st.error(f"Error creating job: {e}")

    st.divider()
    st.subheader("Existing Jobs")
    try:
        jobs = api.list_jobs()
        if not jobs:
            st.info("No jobs found in the database.")
        else:
            st.dataframe(jobs, use_container_width=True)
    except Exception as e:
        st.error(f"Error fetching jobs: {e}")

if __name__ == "__main__":
    main()
