import json

from .. import llm

COVER_SYSTEM = (
    "You write short, specific cover letters (150-220 words). Ground every claim "
    "strictly in the candidate profile JSON — NEVER invent employers, degrees, "
    "certifications, dates, or skills that are not in it. Reference 2-3 concrete "
    "specifics from the job description. No generic filler ('I am excited to "
    "apply', 'esteemed company'). Plain text only, no salutation placeholders."
)

MOTIVATION_SYSTEM = (
    "Answer the screening question 'Why do you want to work at this company?' in "
    "2-4 sentences, grounded strictly in the candidate profile and the job "
    "description. Never invent facts about the candidate. Plain text only."
)


def draft_cover_letter(profile_json: str, company: str, title: str, description: str) -> str:
    user = (
        f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
        f"COMPANY: {company}\nJOB TITLE: {title}\n\nJOB DESCRIPTION:\n{description[:6000]}"
    )
    return llm.chat(COVER_SYSTEM, user, temperature=0.5).strip()


def draft_answers(profile_json: str, bank: list, company: str, title: str, description: str) -> str:
    """Build the screening-answer sheet: bank answers verbatim, one LLM-composed
    motivation answer flagged for review, blanks flagged too."""
    answers = []
    for row in bank:
        answer = (row["answer"] or "").strip()
        answers.append(
            {
                "question": row["question"],
                "answer": answer,
                "source": "bank" if answer else "blank",
            }
        )
    try:
        motivation = llm.chat(
            MOTIVATION_SYSTEM,
            f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\nCOMPANY: {company}\n"
            f"JOB TITLE: {title}\n\nJOB DESCRIPTION:\n{description[:6000]}",
            temperature=0.5,
        ).strip()
        answers.append(
            {
                "question": f"Why do you want to work at {company}?",
                "answer": motivation,
                "source": "llm",
            }
        )
    except llm.LLMError:
        answers.append(
            {
                "question": f"Why do you want to work at {company}?",
                "answer": "",
                "source": "blank",
            }
        )
    return json.dumps(answers)
