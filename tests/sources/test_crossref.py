from braevity.core.models import Job
from braevity.sources.crossref import extract_board_tokens, discover_from_jobs
from braevity.core.registry import BoardRegistry


def _job_with_apply_url(apply_url: str) -> Job:
    return Job.from_fields(
        title="SDE", company="Acme", location=None,
        url="https://remoteok.com/jobs/1", posted_date=None,
        source="remoteok", apply_url=apply_url,
    )


def test_extract_greenhouse_token():
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/stripe/jobs/123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "greenhouse", "token": "stripe", "company": "Acme"} in tokens


def test_extract_lever_token():
    jobs = [_job_with_apply_url("https://jobs.lever.co/figma/abc-123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "lever", "token": "figma", "company": "Acme"} in tokens


def test_extract_ashby_token():
    jobs = [_job_with_apply_url("https://jobs.ashbyhq.com/linear/job-id")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "ashby", "token": "linear", "company": "Acme"} in tokens


def test_extract_workday_token():
    jobs = [_job_with_apply_url("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/123")]
    tokens = extract_board_tokens(jobs)
    assert {"ats": "workday", "token": "nvidia", "company": "Acme"} in tokens


def test_extract_no_match():
    jobs = [_job_with_apply_url("https://company.com/careers/apply")]
    tokens = extract_board_tokens(jobs)
    assert tokens == []


def test_extract_skips_none_apply_url():
    job = Job.from_fields(
        title="SDE", company="Acme", location=None,
        url="https://remoteok.com/1", posted_date=None, source="remoteok",
    )
    tokens = extract_board_tokens([job])
    assert tokens == []


def test_extract_malformed_url_no_crash():
    jobs = [_job_with_apply_url("javascript:void(0)")]
    tokens = extract_board_tokens(jobs)
    assert tokens == []


def test_discover_from_jobs_registers(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/newco/jobs/1")]
    count = discover_from_jobs(jobs, reg)
    assert count == 1
    boards = reg.get_active_boards("greenhouse")
    assert len(boards) == 1
    assert boards[0]["token"] == "newco"
    assert boards[0]["discovered_from"] == "crossref"
    reg.close()


def test_discover_from_jobs_skips_existing(tmp_path):
    reg = BoardRegistry(tmp_path / "reg.db")
    reg.register("greenhouse", "existing", "Existing Co", "seed")
    jobs = [_job_with_apply_url("https://boards.greenhouse.io/existing/jobs/1")]
    count = discover_from_jobs(jobs, reg)
    assert count == 0
    reg.close()
