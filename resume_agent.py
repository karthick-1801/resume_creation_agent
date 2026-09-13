"""Core extraction, ATS analysis, and resume drafting functions."""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from docx import Document
from docx.shared import Pt
from pypdf import PdfReader
from rapidfuzz import fuzz


SECTION_NAMES = {
    "summary", "profile", "objective", "experience", "work experience",
    "employment", "education", "skills", "technical skills", "projects",
    "certifications", "awards", "publications", "contact",
}
STOPWORDS = {
    "and", "the", "for", "with", "from", "that", "this", "will", "are",
    "our", "your", "you", "have", "has", "years", "year", "role", "work",
    "team", "teams", "job", "candidate", "required", "preferred", "about",
    "their", "into", "using", "ability", "including", "within", "through",
    "strong", "excellent", "plus", "other", "new", "all", "who", "can",
}
SKILL_PATTERNS = [
    r"\b(?:python|java|javascript|typescript|sql|r|c\+\+|c#|go|rust|php|ruby)\b",
    r"\b(?:aws|azure|gcp|docker|kubernetes|terraform|linux|git|github|jenkins)\b",
    r"\b(?:react|angular|vue|node(?:\.js)?|django|flask|fastapi|spring|\.net)\b",
    r"\b(?:tableau|power bi|excel|salesforce|sap|snowflake|databricks|airflow)\b",
    r"\b(?:machine learning|deep learning|nlp|llm|generative ai|data analysis|data engineering)\b",
    r"\b(?:agile|scrum|jira|confluence|ci/cd|rest(?:ful)? api|microservices)\b",
    r"\b(?:pmp|cissp|comptia|six sigma|cpa|mba|bachelor(?:'s)?|master(?:'s)?)\b",
]


@dataclass
class ResumeData:
    text: str
    source_type: str
    doc: Document | None = None


def extract_resume(uploaded_file: Any) -> ResumeData:
    """Read an UploadedFile-like object containing a DOCX or PDF."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.getvalue()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(raw))
        paragraphs = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            paragraphs.extend(cell.text for row in table.rows for cell in row.cells)
        return ResumeData("\n".join(paragraphs), "DOCX", doc)
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return ResumeData("\n".join(page.extract_text() or "" for page in reader.pages), "PDF")
    raise ValueError("Please upload a PDF or DOCX resume.")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def extract_keywords(job_description: str, limit: int = 38) -> list[str]:
    """Extract transparent, deterministic ATS terms from a job description."""
    clean = normalise(job_description)
    candidates: list[str] = []
    for pattern in SKILL_PATTERNS:
        candidates.extend(re.findall(pattern, clean, flags=re.I))
    # Keep common two-/three-word noun phrases and meaningful capitalized terms.
    candidates.extend(re.findall(r"\b[a-z][a-z+#./-]{2,}(?:\s+[a-z][a-z+#./-]{2,}){1,2}\b", clean))
    candidates.extend(re.findall(r"\b[a-z][a-z+#./-]{2,}\b", clean))
    counts = Counter(c.strip(" .,-") for c in candidates if c not in STOPWORDS)
    ranked = sorted(counts, key=lambda item: (-counts[item], -len(item), item))
    seen: list[str] = []
    for item in ranked:
        item = re.sub(r"\s+", " ", item)
        if item not in seen and len(item) > 2:
            seen.append(item)
        if len(seen) >= limit:
            break
    return seen


def term_present(term: str, resume_text: str) -> bool:
    return fuzz.partial_ratio(normalise(term), normalise(resume_text)) >= 93


def find_sections(text: str) -> set[str]:
    return {normalise(line).strip(":") for line in text.splitlines()
            if normalise(line).strip(":") in SECTION_NAMES}


def ats_analysis(resume_text: str, job_description: str) -> dict[str, Any]:
    keywords = extract_keywords(job_description)
    present = [term for term in keywords if term_present(term, resume_text)]
    missing = [term for term in keywords if term not in present]
    coverage = len(present) / max(len(keywords), 1)
    similarity = fuzz.token_set_ratio(normalise(resume_text), normalise(job_description)) / 100
    sections = find_sections(resume_text)
    needed = {"experience", "education", "skills"}
    # Accommodate common resume labels.
    has_experience = bool(sections & {"experience", "work experience", "employment"})
    section_score = (int(has_experience) + int("education" in sections) +
                     int(bool(sections & {"skills", "technical skills"}))) / 3
    format_score = 1.0
    if len(resume_text) < 500:
        format_score -= 0.35
    if "|" in resume_text or "\t" in resume_text:
        format_score -= 0.10
    score = round(min(100, (coverage * 65 + similarity * 20 + section_score * 10 + format_score * 5)))
    return {
        "score": score, "keywords": keywords, "present": present, "missing": missing,
        "coverage": round(coverage * 100), "similarity": round(similarity * 100),
        "sections": sorted(sections), "format_score": round(format_score * 100),
    }


def highlight_missing(text: str, missing: list[str]) -> str:
    """Return safe Markdown highlighting exact occurrences of selected terms."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for term in sorted(missing, key=len, reverse=True):
        pattern = re.compile(rf"(?i)\b({re.escape(term)})\b")
        escaped = pattern.sub(r"<mark>\1</mark>", escaped)
    return escaped.replace("\n", "  \n")


def fallback_draft(resume_text: str, missing: list[str], job_title: str) -> str:
    """Conservative draft when no language-model key is supplied."""
    additions = ", ".join(missing[:12]) or "relevant role-specific skills"
    return f"""{resume_text.strip()}

TARGETED SUMMARY (REVIEW BEFORE USING)
Candidate targeting a {job_title or 'relevant'} position. Align demonstrated experience with the role's priorities where truthful: {additions}. Do not add a term unless it accurately reflects your experience.
"""


def ai_draft(resume_text: str, job_description: str, analysis: dict[str, Any], api_key: str, model: str) -> str:
    from openai import OpenAI
    prompt = f"""You are a meticulous resume editor. Rewrite the resume below into a one- or two-page ATS-friendly plain-text resume for the job description. Preserve every factual claim: do not invent skills, employers, dates, education, credentials, metrics, or accomplishments. You may reorganize, tighten bullets, and use only missing keywords that are genuinely supported by the source resume. Keep standard headings: SUMMARY, SKILLS, EXPERIENCE, EDUCATION. Do not mention AI, prompts, ATS scores, or watermarking.

SOURCE RESUME:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_description}\n\nMISSING TERMS TO EVALUATE (only include when truthful): {', '.join(analysis['missing'])}"""
    client = OpenAI(api_key=api_key)
    response = client.responses.create(model=model, input=prompt)
    return response.output_text.strip()


def _copy_basic_style(source: Document | None, target: Document) -> None:
    if not source:
        target.styles["Normal"].font.name = "Aptos"
        target.styles["Normal"].font.size = Pt(10.5)
        return
    # A DOCX may use custom styles, but the body font, spacing, and page geometry
    # are its strongest visual cues. Copying these keeps the output recognisably
    # close to the supplied resume while retaining a simple ATS-safe structure.
    source_normal = source.styles["Normal"]
    target_normal = target.styles["Normal"]
    for attr in ("name", "size", "bold", "italic", "underline", "all_caps", "small_caps"):
        value = getattr(source_normal.font, attr)
        if value is not None:
            setattr(target_normal.font, attr, value)
    if source_normal.font.color.rgb:
        target_normal.font.color.rgb = source_normal.font.color.rgb
    target_normal.font.name = target_normal.font.name or "Aptos"
    target_normal.font.size = target_normal.font.size or Pt(10.5)
    target_normal.paragraph_format.space_after = source_normal.paragraph_format.space_after
    target_normal.paragraph_format.space_before = source_normal.paragraph_format.space_before
    target_normal.paragraph_format.line_spacing = source_normal.paragraph_format.line_spacing
    if source.sections:
        source_section, target_section = source.sections[0], target.sections[0]
        for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
            setattr(target_section, attr, getattr(source_section, attr))


def make_docx(draft: str, source_doc: Document | None = None) -> bytes:
    """Create a clean, ATS-readable DOCX; deliberately contains no watermark."""
    doc = Document()
    _copy_basic_style(source_doc, doc)
    for line in draft.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().strip(":") in {"SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS"}:
            p = doc.add_paragraph()
            run = p.add_run(line.upper().strip(":"))
            run.bold = True
        elif line.startswith(("-", "•", "–")):
            doc.add_paragraph(line.lstrip("-•– "), style="List Bullet")
        else:
            doc.add_paragraph(line)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
