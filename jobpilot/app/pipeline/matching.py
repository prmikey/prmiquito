from .. import llm

SYSTEM = (
    "You are a strict job-fit evaluator. Compare the candidate profile with the "
    "job posting and return ONLY a JSON object: "
    '{"score": <integer 0-100>, "reason": "<two short sentences>"}. '
    "Score honestly: 80+ means the candidate is a strong direct match for the "
    "role's core requirements, 50-79 a partial match, below 50 a poor match."
)


def score_job(profile_json: str, title: str, description: str) -> tuple[int, str]:
    user = (
        f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
        f"JOB TITLE: {title}\n\nJOB DESCRIPTION:\n{description[:6000]}"
    )
    data = llm.chat_json(SYSTEM, user)
    score = max(0, min(100, int(data.get("score", 0))))
    return score, str(data.get("reason", ""))[:500]
