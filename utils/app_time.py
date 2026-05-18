from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> str:
    """Current timestamp in India timezone, ISO format."""
    return datetime.now(IST).isoformat()


def today_ist() -> str:
    """Current date in India timezone, YYYY-MM-DD."""
    return datetime.now(IST).date().isoformat()
