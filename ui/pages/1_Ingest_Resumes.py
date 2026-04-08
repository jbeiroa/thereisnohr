import streamlit as st
import time
from pathlib import Path
from ui.api_client import APIClient

st.set_page_config(page_title="Ingest Resumes", page_icon="📄", layout="wide")

def main():
    st.title("Ingest Resumes 📄")
    st.markdown("Add resumes to the database using either a local directory path or by uploading files directly.")

    api = APIClient()

    # Default data path relative to project root
    default_data_path = (Path.cwd() / "data").resolve()

    tab1, tab2 = st.tabs(["📂 Local Folder", "📤 Upload Files"])

    with tab1:
        with st.form("ingest_folder_form"):
            input_dir = st.text_input("Local Folder Path", value=str(default_data_path), help="Absolute path to the folder containing PDF resumes.")
            pattern = st.text_input("Glob Pattern", value="*.pdf", help="Pattern to match resume files (e.g., *.pdf).")
            submit_folder = st.form_submit_button("Start Batch Ingestion")

        if submit_folder:
            process_task(api, api.ingest_resumes(input_dir, pattern), f"Ingesting folder: {input_dir}")

    with tab2:
        uploaded_files = st.file_uploader("Choose PDF resumes", type=["pdf"], accept_multiple_files=True)
        if st.button("Upload and Process"):
            if not uploaded_files:
                st.warning("Please select at least one file to upload.")
            else:
                process_task(api, api.upload_resumes(uploaded_files), f"Uploading and processing {len(uploaded_files)} files")

def process_task(api, task, label):
    try:
        task_id = task["id"]
        with st.status(f"{label} (Task ID: {task_id})...") as status:
            while True:
                task_info = api.get_task(task_id)
                status_str = task_info["status"]
                
                if status_str == "COMPLETED":
                    status.update(label="Process complete!", state="complete", expanded=True)
                    output = task_info.get("output_payload", {})
                    # For folder ingest, result is under "result", for upload it's the same run_ingest_resumes
                    processed = output.get("result", {}).get("processed", 0)
                    results = output.get("result", {}).get("results", [])
                    
                    st.success(f"Successfully processed {processed} files.")
                    if results:
                        st.write("Results Summary:")
                        st.dataframe(results)
                    break
                elif status_str == "FAILED":
                    status.update(label="Process failed!", state="error", expanded=True)
                    st.error(f"Error: {task_info.get('error_message')}")
                    break
                
                time.sleep(2)
    except Exception as e:
        st.error(f"Error starting process: {e}")

if __name__ == "__main__":
    main()
