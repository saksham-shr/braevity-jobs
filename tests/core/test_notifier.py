from unittest.mock import patch, MagicMock
from braevity.core.models import Job
from braevity.core.notifier import build_email_body, send_notification


def _job(title="SDE", company="Acme"):
    return Job.from_fields(
        title=title, company=company, location="NYC",
        url="https://x.com/1", posted_date="2026-10-06", source="greenhouse",
    )


def test_build_email_body_contains_jobs():
    jobs = [_job("Backend Engineer", "Stripe"), _job("SDE-2", "Microsoft")]
    body = build_email_body(jobs, "Backend Engineer")
    assert "Backend Engineer" in body
    assert "Stripe" in body
    assert "Microsoft" in body
    assert "<table" in body


def test_build_email_body_escapes_html():
    jobs = [_job('<script>alert("xss")</script>', 'Acme & Co "LLC"')]
    body = build_email_body(jobs, "SDE")
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "&amp; Co &quot;LLC&quot;" in body


@patch("braevity.core.notifier.smtplib.SMTP")
def test_send_notification_success(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    config = {
        "email": "to@test.com",
        "smtp_host": "smtp.test.com",
        "smtp_port": 587,
        "smtp_user": "from@test.com",
        "smtp_password": "pass",
    }
    result = send_notification([_job()], "SDE", config)
    assert result is True


@patch("braevity.core.notifier.smtplib.SMTP")
def test_send_notification_smtp_failure(mock_smtp_cls):
    mock_smtp_cls.side_effect = Exception("Connection refused")
    config = {
        "email": "to@test.com",
        "smtp_host": "bad.host",
        "smtp_port": 587,
        "smtp_user": "from@test.com",
        "smtp_password": "pass",
    }
    result = send_notification([_job()], "SDE", config)
    assert result is False
