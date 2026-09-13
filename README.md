# Resume ATS Agent

A local Streamlit app that reads PDF or DOCX resumes, compares them with a job
description, identifies missing ATS keywords, calculates a transparent ATS
score, and generates an ATS-friendly DOCX resume using the visual language of
the uploaded DOCX where possible.

## What it does

- Accepts PDF and DOCX resumes.
- Extracts role-specific hard skills, tools, certifications, and action terms
  from the job description.
- Highlights missing terms in the source-resume preview.
- Scores semantic similarity, keyword coverage, formatting safety, and section
  completeness. The breakdown is visible; it is not a vendor ATS guarantee.
- Uses an optional OpenAI API key to rewrite experience bullets truthfully.
  Without an API key, it creates a conservative keyword-focused draft.
- Produces a clean DOCX with no AI watermark, hidden prompt, or attribution.

## Run

Python 3.14 is supported by the app code. In PowerShell, from this folder:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
streamlit run app.py
```

The first time an API key is used, set it in the app sidebar or define
`OPENAI_API_KEY` before launching. The key is used only for that session and is
not saved by this app.

## Important resume-safety rule

The agent is designed to improve phrasing and surface relevant terminology; it
must not invent employers, dates, degrees, achievements, tools, or metrics.
Review the draft before submitting it.

