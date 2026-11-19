"""Google Calendar access. Run `python gcal.py` once to sign in; the token is saved for later runs."""
from datetime import datetime, timedelta

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import GOOGLE_CREDENTIALS, GOOGLE_TOKEN

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
NOT_SET_UP = "Google Calendar is not connected yet. Thisen needs to run `python gcal.py` once to sign in."


def _service():
    if not GOOGLE_TOKEN.exists():
        raise RuntimeError(NOT_SET_UP)
    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:                      # revoked, or expired after 7 days in Testing mode
                raise RuntimeError(NOT_SET_UP)
            GOOGLE_TOKEN.write_text(creds.to_json())
        else:
            raise RuntimeError(NOT_SET_UP)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def parse_time(text: str) -> datetime:
    """Parse an ISO date/time from the model and attach the local time zone."""
    t = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    return t if t.tzinfo else t.astimezone()      # naive → local time


def describe(ev: dict) -> str:
    start = ev["start"].get("dateTime") or ev["start"].get("date")
    if "T" in start:
        s = datetime.fromisoformat(start).astimezone()
        e = datetime.fromisoformat(ev["end"]["dateTime"]).astimezone()
        when = f"{s:%a %d %b %Y, %I:%M %p} to {e:%I:%M %p}"
    else:
        when = f"{datetime.fromisoformat(start):%a %d %b %Y} (all day)"
    where = f", {ev['location']}" if ev.get("location") else ""
    return f"{ev.get('summary', '(no title)')}: {when}{where}"


def add_event(title: str, start: str, end: str = "", location: str = "", notes: str = "") -> dict:
    body = {"summary": title, "location": location, "description": notes}
    if "T" not in start:                                   # all-day event
        day = datetime.fromisoformat(start).date()
        last = datetime.fromisoformat(end).date() if end else day
        body["start"] = {"date": day.isoformat()}
        body["end"] = {"date": (last + timedelta(days=1)).isoformat()}   # Google's end date is exclusive
    else:
        s = parse_time(start)
        e = parse_time(end) if end else s + timedelta(hours=1)
        if e <= s:
            raise ValueError("The end time must be after the start time.")
        body["start"] = {"dateTime": s.isoformat()}
        body["end"] = {"dateTime": e.isoformat()}
    return _service().events().insert(calendarId="primary", body=body).execute()


def upcoming(days: int = 7, query: str = "") -> list[dict]:
    now = datetime.now().astimezone()
    resp = _service().events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=days)).isoformat(),
        q=query or None,
        singleEvents=True,
        orderBy="startTime",
        maxResults=25,
    ).execute()
    return resp.get("items", [])


def delete_event(event_id: str) -> None:
    _service().events().delete(calendarId="primary", eventId=event_id).execute()


def sign_in() -> None:
    if not GOOGLE_CREDENTIALS.exists():
        raise SystemExit(f"Put the OAuth client file from Google Cloud Console at {GOOGLE_CREDENTIALS} first.")
    flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=8765, open_browser=True)
    GOOGLE_TOKEN.write_text(creds.to_json())
    print(f"Signed in. Token saved to {GOOGLE_TOKEN}")


if __name__ == "__main__":
    sign_in()
