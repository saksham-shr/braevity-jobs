import logging
from braevity.core.models import Job

logger = logging.getLogger(__name__)


def send_toast(jobs: list[Job], role: str) -> bool:
    try:
        from plyer import notification
        msg = "\n".join(f"{j.title} @ {j.company}" for j in jobs[:3])
        if len(msg) > 200:
            msg = msg[:197] + "..."
        notification.notify(
            title=f"Braevity: {len(jobs)} new {role} postings",
            message=msg,
            timeout=10,
        )
        return True
    except Exception as e:
        logger.warning("Toast notification failed: %s", e)
        return False
