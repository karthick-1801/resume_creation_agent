import os
import streamlit as st

from resume_agent import ai_draft, ats_analysis, extract_resume, fallback_draft, highlight_missing, make_docx

st.set_page_config(page_title="Resume ATS Agent", page_icon="📄", layout="wide")
st.title("Resume ATS Agent")
st.caption("Tailor a truthful, ATS-friendly resume from a PDF or DOCX. Your document stays in this local session unless you choose to use an AI API key.")

with st.sidebar:
    st.header("Optional AI rewrite")
    api_key = st.text_input("OpenAI API key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
    model = st.text_input("Model", value="gpt-4.1-mini")
    st.info("Without a key, the app creates a conservative draft and still runs the ATS analysis.")
    st.header("How the score works")
    st.caption("65% keyword coverage • 20% job-text similarity • 10% core sections • 5% basic format signals. It is an estimate, not a recruiter or vendor ATS decision.")

uploaded = st.file_uploader("Upload your current resume", type=["pdf", "docx"])
job_title = st.text_input("Target role", placeholder="e.g., Data Analyst")
job_description = st.text_area("Paste the job description", height=260)

if st.button("Analyze and create tailored resume", type="primary", disabled=not (uploaded and job_description.strip())):
    try:
        resume = extract_resume(uploaded)
        if len(resume.text.strip()) < 100:
            st.error("I could not extract enough text. For a scanned PDF, OCR it first or upload the DOCX original.")
            st.stop()
        analysis = ats_analysis(resume.text, job_description)
        with st.spinner("Creating a truthful ATS-friendly draft…"):
            draft = ai_draft(resume.text, job_description, analysis, api_key, model) if api_key else fallback_draft(resume.text, analysis["missing"], job_title)
        st.session_state.result = {"resume": resume, "analysis": analysis, "draft": draft}
    except Exception as exc:
        st.error(f"Could not process this file: {exc}")

result = st.session_state.get("result")
if result:
    analysis = result["analysis"]
    left, right, third, fourth = st.columns(4)
    left.metric("Estimated ATS score", f"{analysis['score']}/100")
    right.metric("Keyword coverage", f"{analysis['coverage']}%")
    third.metric("Job-text similarity", f"{analysis['similarity']}%")
    fourth.metric("Format signal", f"{analysis['format_score']}%")

    tabs = st.tabs(["Tailored resume", "Missing keywords", "Source review", "Score details"])
    with tabs[0]:
        st.text_area("Review before submitting — retain only truthful claims", result["draft"], height=520, key="draft_editor")
        file_bytes = make_docx(st.session_state.draft_editor, result["resume"].doc)
        st.download_button("Download clean ATS-friendly DOCX", file_bytes, "tailored_resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.caption("The downloaded document has no AI watermark, hidden prompt, or attribution.")
    with tabs[1]:
        if analysis["missing"]:
            st.warning("These terms appear in the job description but were not found in your uploaded resume. Add only terms you can support truthfully.")
            st.write(" • ".join(analysis["missing"]))
        else:
            st.success("All extracted job-description keywords were found in the uploaded resume.")
        st.caption("Detected terms already covered: " + (" • ".join(analysis["present"]) or "None"))
    with tabs[2]:
        st.markdown(highlight_missing(result["resume"].text, analysis["missing"]), unsafe_allow_html=True)
        st.caption("Yellow highlights mark text matching terms currently classified as missing; this preview is for review, not the output resume.")
    with tabs[3]:
        st.write({"extracted_keywords": analysis["keywords"], "detected_sections": analysis["sections"], "source_format": result["resume"].source_type})
        st.info("For best ATS compatibility, use the generated DOCX or export it to a text-based PDF; avoid columns, text boxes, graphics, and tables in the final submission.")
