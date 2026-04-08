import streamlit as st
import time
import fitz
from ui.api_client import APIClient

st.set_page_config(page_title="Rank Candidates", page_icon="🏆", layout="wide")

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
        
        # Simple text wrapping (very basic)
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

def main():
    st.title("Rank Candidates 🏆")
    st.markdown("Select a job to find and rank the most suitable candidates from the database.")

    api = APIClient()

    try:
        jobs = api.list_jobs()
        if not jobs:
            st.warning("No jobs found. Please create a job posting first.")
            return
        
        job_options = {f"{j['title']} (ID: {j['id']})": j['id'] for j in jobs}
        selected_job_label = st.selectbox("Select Job Posting", options=list(job_options.keys()))
        selected_job_id = job_options[selected_job_label]
        selected_job_title = selected_job_label.split(" (ID:")[0]

        top_k = st.slider("Number of Candidates to Rank", min_value=1, max_value=20, value=5)

        if st.button("Start Ranking Process"):
            try:
                task = api.rank_job(selected_job_id, top_k)
                task_id = task["id"]
                
                with st.status(f"Ranking candidates for {selected_job_title} (Task ID: {task_id})...") as status:
                    while True:
                        task_info = api.get_task(task_id)
                        status_str = task_info["status"]
                        
                        if status_str == "COMPLETED":
                            status.update(label=f"Ranking for {selected_job_title} complete!", state="complete", expanded=True)
                            st.success("Successfully ranked candidates.")
                            break
                        elif status_str == "FAILED":
                            status.update(label="Ranking failed!", state="error", expanded=True)
                            st.error(f"Error: {task_info.get('error_message')}")
                            break
                        
                        time.sleep(2)
            except Exception as e:
                st.error(f"Error starting ranking: {e}")

        st.divider()
        st.subheader(f"Matches for {selected_job_title}")
        
        matches = api.list_matches(job_id=selected_job_id)
        if not matches:
            st.info("No matches found for this job yet. Run the ranking process above.")
        else:
            # Export buttons
            col1, col2 = st.columns(2)
            
            # Text Export
            report_text = f"Ranking Report: {selected_job_title}\n" + "="*40 + "\n"
            for i, m in enumerate(matches):
                c = m.get('candidate') or {}
                name = c.get('name') or f"ID: {c.get('id')}"
                reasons = m.get('reasons_json') or {}
                explanation = reasons.get('explanation') or {}
                report_text += f"{i+1}. {name} | Score: {m['final_score']:.2f}\n"
                report_text += f"   Summary: {explanation.get('evidence_based_summary', 'N/A')}\n\n"
            
            col1.download_button("Export Results (TXT)", data=report_text, file_name=f"ranking_{selected_job_id}.txt")
            
            # PDF Export
            pdf_bytes = generate_pdf_report(matches, selected_job_title)
            col2.download_button("Export Results (PDF)", data=pdf_bytes, file_name=f"ranking_{selected_job_id}.pdf", mime="application/pdf")

            # Display Results
            for i, match in enumerate(matches):
                candidate = match.get("candidate") or {}
                name = candidate.get("name") or f"ID: {candidate.get('id')}"
                score = match.get("final_score", 0.0)
                
                with st.expander(f"#{i+1}: {name} (Score: {score:.2f})"):
                    reasons = match.get("reasons_json") or {}
                    explanation = reasons.get("explanation") or {}
                    
                    if explanation:
                        st.markdown(f"### Evidence-Based Summary\n{explanation.get('evidence_based_summary')}")
                        
                        gaps = explanation.get("gaps_and_risks") or []
                        if gaps:
                            st.markdown("### Gaps & Risks")
                            for gap in gaps:
                                st.warning(f"**{gap.get('missing_requirement')}**: {gap.get('impact')}")
                    
                    st.divider()
                    interview_pack = match.get("interview_pack_json")
                    if interview_pack:
                        st.info("Interview Prep Pack already generated.")
                        if st.checkbox(f"Show Prep Pack for {name}", key=f"show_prep_{match['id']}"):
                            pack = interview_pack or {}
                            st.subheader("Technical Questions")
                            for q in pack.get("technical_questions") or []:
                                st.write(f"- {q}")
                            st.subheader("Behavioral Questions")
                            for q in pack.get("behavioral_questions") or []:
                                st.write(f"- {q}")
                    else:
                        if st.button(f"Generate Interview Prep Pack for {name}", key=f"gen_prep_{match['id']}"):
                            try:
                                with st.spinner("Generating..."):
                                    task = api.generate_prep(match["id"])
                                    api.poll_task(task["id"])
                                    st.success("Prep pack generated! Refresh the page or toggle the checkbox to view.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error generating prep pack: {e}")

    except Exception as e:
        st.error(f"Error loading jobs: {e}")

if __name__ == "__main__":
    main()
