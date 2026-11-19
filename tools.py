"""Tools Jarvis can call. Docstrings are sent to the model as the tool descriptions."""
from datetime import datetime

import requests

import docs
import gcal
import store
from config import DEFAULT_CITY


def get_time() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


WEATHER_CODES = {
    0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


def get_weather(city: str = "") -> str:
    """Get the current weather for a city.

    Args:
        city: City name, for example "Colombo". Leave empty to use the user's home city.
    """
    city = city or DEFAULT_CITY
    if not city:
        return "No city given and no home city configured."
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        ).json()
        if not geo.get("results"):
            return f"Could not find a place called {city}."
        place = geo["results"][0]

        cur = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            },
            timeout=10,
        ).json()["current"]

        sky = WEATHER_CODES.get(cur["weather_code"], "unknown conditions")
        return (
            f"{place['name']}, {place.get('country', '')}: {sky}, "
            f"{cur['temperature_2m']}°C (feels like {cur['apparent_temperature']}°C), "
            f"humidity {cur['relative_humidity_2m']}%, wind {cur['wind_speed_10m']} km/h."
        )
    except requests.RequestException:
        return "The weather service could not be reached."


# ---------- memory ----------

def remember(fact: str) -> str:
    """Save a lasting fact about Thisen (preferences, people, plans, details he tells you) so it is remembered in future conversations.

    Args:
        fact: One short, self-contained sentence, for example "Thisen's sister is called Nimali."
    """
    return store.add_fact(fact)


def recall(query: str = "") -> str:
    """Look up saved facts about Thisen. Leave the query empty to list everything.

    Args:
        query: Keywords to search for, for example "sister".
    """
    facts = store.search_facts(query)
    if not facts:
        return "Nothing saved matches that."
    return "\n".join(f"- {f['text']} (saved {f['saved']})" for f in facts)


def forget(query: str) -> str:
    """Delete every saved fact containing the given text. Only use when Thisen asks you to forget something.

    Args:
        query: Text that appears in the fact(s) to delete.
    """
    n = store.remove_facts(query)
    return f"Forgot {n} fact(s)." if n else "No saved fact matches that."


# ---------- documents ----------

def list_documents() -> str:
    """List the PDF documents Thisen has uploaded."""
    items = docs.all_docs()
    if not items:
        return "No documents have been uploaded yet."
    return "\n".join(
        f"- {d['name']}: {len(d['pages'])} pages"
        + (f", {d['scanned_pages']} scanned" if d["scanned_pages"] else "")
        for d in items
    )


def search_documents(query: str, document: str = "") -> str:
    """Search the uploaded documents for passages relevant to a question. Use this first for any question about an uploaded PDF. Cite page numbers in your answer.

    Args:
        query: What to look for, phrased as a short description or question.
        document: Optional document name (or part of it) to limit the search. Leave empty to search all.
    """
    try:
        hits = docs.search(query, document)
    except ValueError as e:
        return str(e)
    if not hits:
        return "No documents have been uploaded yet."
    return "\n\n".join(f"[{h['doc']}, page {h['page']}]\n{h['text']}" for h in hits)


def read_page(page: int, document: str = "") -> str:
    """Read the full text of one page of an uploaded document.

    Args:
        page: Page number, starting at 1.
        document: Document name (or part of it). Can be empty if only one document exists.
    """
    d = docs.find_doc(document)
    if isinstance(d, str):
        return d
    try:
        page = int(page)
    except (TypeError, ValueError):
        return "Page must be a number."
    if not 1 <= page <= len(d["pages"]):
        return f"{d['name']} has {len(d['pages'])} pages."
    return f"[{d['name']}, page {page}]\n{d['pages'][page - 1][:6000]}"


def summarize_document(document: str = "", focus: str = "") -> str:
    """Summarise a whole uploaded document. Slow for long documents; use search_documents for specific questions instead.

    Args:
        document: Document name (or part of it). Can be empty if only one document exists.
        focus: Optional topic to concentrate the summary on.
    """
    d = docs.find_doc(document)
    if isinstance(d, str):
        return d
    return docs.summarize(d, focus)


# ---------- calendar ----------

def _calendar_error(e: Exception) -> str:
    if isinstance(e, RuntimeError):
        return str(e)
    return f"The calendar request failed: {e}"


def add_calendar_event(title: str, start: str, end: str = "", location: str = "", notes: str = "") -> str:
    """Add an event to Thisen's Google Calendar. Use this when he asks to add an event, often with a pasted message describing it. Work out the date from today's date. Afterwards, tell him exactly what was added.

    Args:
        title: Short event name, for example "IESL tech talk".
        start: Start as ISO local time, for example "2026-11-28T15:30". For an all-day event give only the date, "2026-11-28".
        end: End in the same format. Leave empty if the message gives no end time (defaults to one hour).
        location: Place, if mentioned.
        notes: Other useful details from the message (links, what to bring, organiser). Keep it brief.
    """
    try:
        ev = gcal.add_event(title, start, end, location, notes)
    except ValueError as e:
        return f"Could not add the event: {e}"
    except Exception as e:
        return _calendar_error(e)
    return f"Added to Google Calendar: {gcal.describe(ev)}"


def list_calendar_events(days: int = 7, query: str = "") -> str:
    """List Thisen's upcoming Google Calendar events.

    Args:
        days: How many days ahead to look. Defaults to 7.
        query: Optional words to search for in the events.
    """
    try:
        events = gcal.upcoming(int(days), query)
    except Exception as e:
        return _calendar_error(e)
    if not events:
        return f"No events in the next {days} days" + (f" matching '{query}'." if query else ".")
    return "\n".join(f"- {gcal.describe(ev)}" for ev in events)


def delete_calendar_event(query: str) -> str:
    """Delete an upcoming Google Calendar event (next 60 days). Only use when Thisen asks to remove an event, for example one you added wrongly.

    Args:
        query: Words from the event's title, for example "tech talk".
    """
    try:
        matches = gcal.upcoming(60, query)
        if not matches:
            return f"No upcoming event matches '{query}'."
        if len(matches) > 1:
            listing = "\n".join(f"- {gcal.describe(ev)}" for ev in matches)
            return f"Several events match; ask Thisen which one, then search with more specific words:\n{listing}"
        gcal.delete_event(matches[0]["id"])
    except Exception as e:
        return _calendar_error(e)
    return f"Deleted: {gcal.describe(matches[0])}"


TOOLS = {f.__name__: f for f in (
    get_time, get_weather,
    remember, recall, forget,
    list_documents, search_documents, read_page, summarize_document,
    add_calendar_event, list_calendar_events, delete_calendar_event,
)}
