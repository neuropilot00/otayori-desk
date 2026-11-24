"""Tokyo-local windows shared by the collector and browser notifications."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TOKYO = ZoneInfo("Asia/Tokyo")
HOURS = (10, 19)
GRACE = timedelta(minutes=20)
DELIVERY_DELAY = timedelta(minutes=12)
DELIVERY_DEADLINE = timedelta(minutes=18)


def latest_slot(now):
    local = now.astimezone(TOKYO)
    last = local.replace(hour=19, minute=0, second=0, microsecond=0)
    if local.hour < 10:
        return last - timedelta(days=1)
    return last if local.hour >= 19 else last.replace(hour=10)


def active_slot(now=None, *, delay=timedelta()):
    now = now or datetime.now(timezone.utc)
    slot = latest_slot(now)
    return slot if delay <= now - slot < GRACE else None


def overdue(scanned_at, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(scanned_at) < latest_slot(now - GRACE)
    except (ValueError, TypeError):
        return True

def checked_this_slot(scanned_at, slot):
    try:
        return datetime.fromisoformat(scanned_at) >= slot
    except (ValueError, TypeError):
        return False


def delivery_slot(ready, now=None):
    now = now or datetime.now(timezone.utc)
    slot = active_slot(now, delay=DELIVERY_DELAY)
    if slot and (now - slot >= DELIVERY_DEADLINE or ready(slot)):
        return slot
    return None
