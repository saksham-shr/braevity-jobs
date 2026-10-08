import re


ROLE_SYNONYMS = [
    {"software engineer", "developer", "programmer", "sde", "swe", "software developer", "software development engineer", "coder",
     "java developer", "python developer", "golang developer", "go developer", "c++ developer", "rust developer",
     "ruby developer", "node developer", "nodejs developer", ".net developer", "php developer", "kotlin developer",
     "scala developer", "typescript developer"},
    {"backend engineer", "back-end engineer", "backend developer", "server side engineer", "api engineer"},
    {"frontend engineer", "front-end engineer", "frontend developer", "ui engineer", "ui developer"},
    {"full stack engineer", "fullstack engineer", "full-stack developer", "fullstack developer"},
    {"devops engineer", "sre", "site reliability engineer", "infrastructure engineer", "cloud engineer", "systems engineer"},
    {"data scientist", "ml engineer", "machine learning engineer", "applied scientist", "research scientist", "ai engineer"},
    {"data engineer", "analytics engineer", "big data engineer", "etl developer", "data platform engineer"},
    {"product manager", "product owner", "technical product manager", "product lead", "pm"},
    {"qa engineer", "quality assurance", "test engineer", "sdet", "automation engineer"},
    {"designer", "ui designer", "ux designer", "ux/ui designer", "user experience designer", "product designer"},
]

LOCATION_ALIASES = {
    "bangalore": "bengaluru", "bengaluru": "bangalore",
    "mumbai": "bombay", "bombay": "mumbai",
    "chennai": "madras", "madras": "chennai",
    "kolkata": "calcutta", "calcutta": "kolkata",
    "gurugram": "gurgaon", "gurgaon": "gurugram",
    "pune": "poona", "poona": "pune",
    "thiruvananthapuram": "trivandrum", "trivandrum": "thiruvananthapuram",
    "nyc": "new york", "new york": "nyc",
    "sf": "san francisco", "san francisco": "sf",
    "la": "los angeles", "los angeles": "la",
    "dc": "washington", "washington": "dc",
}

REMOTE_VARIANTS = {"remote", "work from home", "wfh", "anywhere", "distributed", "hybrid"}

SENIOR_SIGNALS = [r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bstaff\b", r"\bprincipal\b", r"\barchitect\b", r"\bl[4-7]\b", r"\bii+\b"]
JUNIOR_SIGNALS = [r"\bjunior\b", r"\bjr\.?\b", r"\bintern\b", r"\bentry\s*level\b", r"\bassociate\b", r"\bl[1-2]\b", r"\bnew\s*grad\b", r"\bfresher\b"]

def _matches_role(job_title, role) -> bool:
    job_title = job_title.lower()
    role = role.lower()

    if role in job_title:
        return True

    for synonym_group in ROLE_SYNONYMS:
        if role in synonym_group:
            for synonym in synonym_group:
                if synonym in job_title:
                    return True

    return False


def _matches_location(job_location, location) -> bool:
    if job_location is None:
        return True

    job_location = job_location.lower()
    location = location.lower()

    if location in REMOTE_VARIANTS:
        return any(rv in job_location for rv in REMOTE_VARIANTS)

    if location in job_location:
        return True

    alias = LOCATION_ALIASES.get(location)
    if alias and alias in job_location:
        return True

    return False


def _matches_experience(job_title, experience) -> bool:
    title = job_title.lower()
    experience = experience.lower()

    if experience == "senior":
        if any(re.search(p, title) for p in JUNIOR_SIGNALS):
            return False
        return True

    if experience == "junior":
        if any(re.search(p, title) for p in SENIOR_SIGNALS):
            return False
        return True

    return True


def filter_jobs(jobs, watch) -> list:
    role = watch.get("role")
    location = watch.get("location")
    experience = watch.get("experience")

    filtered = []
    for job in jobs:
        if role and not _matches_role(job.title, role):
            continue
        if location and not _matches_location(job.location, location):
            continue
        if experience and not _matches_experience(job.title, experience):
            continue
        filtered.append(job)
    return filtered