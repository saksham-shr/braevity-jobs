from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock
from braevity.core.models import Job
from braevity.core.exporter import export_jobs


def _job():
    return Job.from_fields(
        title="SDE", company="Acme", location="NYC",
        url="https://x.com/1", posted_date="2026-10-06", source="greenhouse",
    )


def test_export_load_permission_error_no_crash(tmp_path):
    """PermissionError on load_workbook creates fresh workbook instead of crashing."""
    jobs = [_job()]
    export_jobs(jobs, str(tmp_path))

    with patch("braevity.core.exporter.load_workbook", side_effect=PermissionError("locked")):
        path = export_jobs([_job()], str(tmp_path))
        assert path is not None
        assert path.exists()
