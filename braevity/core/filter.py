import re
from braevity.core.models import Job

ROLE_SYNONYMS = {
    "engineer": ["developer", "dev"],
    "developer": ["engineer", "dev"],
    "sde": ["software development engineer", "software dev engineer"],
}

LOCATION_ALIASES = {
    "bangalore": ["bengaluru"],
    "bengaluru": ["bangalore"],
    "mumbai": ["bombay"],
    "bombay": ["mumbai"],
    "new york": ["nyc", "ny"],
    "nyc": ["new york", "ny"],
}

REMOTE_VARIANTS = {"remote", "work from home", "wfh", "anywhere", "distributed"}

EXPERIENCE_PATTERNS = {
    "intern": re.compile(r"\b(intern|internship)\b", re.I),
    "entry_level": re.compile(r"\b(entry.level|fresh|graduate|new.grad)\b", re.I),
    "junior": re.compile(r"\b(junior|jr\.?|associate)\b|\bsde\s*i\b|\bi\b(?=\s*$)", re.I),
    "mid": re.compile(r"\b(mid|middle)\b|\b(sde|swe)[\s-]*2\b|\bii\b", re.I),
    "senior": re.compile(r"\b(senior|sr\.?)\b|\b(sde|swe)[\s-]*3\b|\biii\b", re.I),
    "staff": re.compile(r"\b(staff|lead)\b", re.I),
    "principal": re.compile(r"\b(principal|architect|distinguished|fellow)\b", re.I),
    "manager": re.compile(r"\b(manager|engineering\s+manager|head\s+of)\b", re.I),
    "director": re.compile(r"\b(director|vp|vice\s+president|cto|chief)\b", re.I),
}


def _normalize(text: str) -> str:
    return text.strip().lower()


def matches_role(job: Job, role: str) -> bool:
    title = _normalize(job.title)
    role_lower = _normalize(role)

    if role_lower in title:
        return True

    role_words = role_lower.split()
    for i, word in enumerate(role_words):
        synonyms = ROLE_SYNONYMS.get(word, [])
        for syn in synonyms:
            variant = " ".join(role_words[:i] + [syn] + role_words[i + 1:])
            if variant in title:
                return True

    for key, expansions in ROLE_SYNONYMS.items():
        if role_lower == key:
            for expansion in expansions:
                if expansion in title:
                    return True

    return False


def matches_location(
    job: Job, countries: list[str], cities: list[str]
) -> bool:
    if not countries and not cities:
        return True
    if job.location is None:
        return True

    loc = _normalize(job.location)

    for city in cities:
        city_lower = _normalize(city)
        if city_lower == "remote":
            if any(rv in loc for rv in REMOTE_VARIANTS):
                return True
            continue
        if city_lower in loc:
            return True
        for alias in LOCATION_ALIASES.get(city_lower, []):
            if alias in loc:
                return True

    for country in countries:
        if _normalize(country) in loc:
            return True

    return False


def matches_experience(job: Job, level: str) -> bool:
    if level == "any":
        return True
    pattern = EXPERIENCE_PATTERNS.get(level)
    if pattern is None:
        return True
    return bool(pattern.search(job.title))


def filter_jobs(jobs: list[Job], watch: dict) -> list[Job]:
    role = watch.get("role", "")
    experience = watch.get("experience", "any")
    locations = watch.get("locations", {})
    countries = locations.get("countries", [])
    cities = locations.get("cities", [])

    return [
        j for j in jobs
        if matches_role(j, role)
        and matches_location(j, countries, cities)
        and matches_experience(j, experience)
    ]
