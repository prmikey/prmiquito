from dataclasses import dataclass


@dataclass
class Posting:
    source: str
    company: str
    title: str
    location: str
    remote: bool
    url: str
    description: str
    posted_at: str  # ISO date or ''
