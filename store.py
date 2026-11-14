"""Persistent memory: long-term facts and saved chats, stored on disk."""
import json
import os
import re
import threading
import uuid
from datetime import datetime

from config import DATA_DIR

CHATS_DIR = DATA_DIR / "chats"
CHATS_DIR.mkdir(exist_ok=True)

FACTS_FILE = DATA_DIR / "facts.json"
HISTORY_FILE = DATA_DIR / "history.json"
MAX_FACTS = 200
MAX_HISTORY = 40          # most recent messages sent to the model (the full chat stays on disk)

_lock = threading.Lock()


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ---------- long-term facts ----------

def list_facts() -> list[dict]:
    return _load(FACTS_FILE, [])


def add_fact(text: str) -> str:
    text = text.strip()
    if not text:
        return "Nothing to remember."
    with _lock:
        facts = list_facts()
        if any(f["text"].lower() == text.lower() for f in facts):
            return "Already remembered."
        facts.append({"text": text, "saved": datetime.now().strftime("%Y-%m-%d")})
        _save(FACTS_FILE, facts[-MAX_FACTS:])
    return "Remembered."


def search_facts(query: str = "") -> list[dict]:
    facts = list_facts()
    words = [w for w in query.lower().split() if len(w) > 2]
    if not words:
        return facts
    return [f for f in facts if any(w in f["text"].lower() for w in words)]


def remove_facts(query: str) -> int:
    query = query.strip().lower()
    if not query:
        return 0
    with _lock:
        facts = list_facts()
        kept = [f for f in facts if query not in f["text"].lower()]
        if len(kept) != len(facts):
            _save(FACTS_FILE, kept)
        return len(facts) - len(kept)


def facts_block() -> str:
    """Text injected into the system prompt so Jarvis always knows its facts."""
    facts = list_facts()
    if not facts:
        return ""
    lines = "\n".join(f"- {f['text']}" for f in facts)
    return f"\n\nThings you remember about Thisen:\n{lines}"


# ---------- conversation history ----------

def trim(messages: list[dict]) -> list[dict]:
    """Keep the last MAX_HISTORY messages, starting on a user turn so
    tool calls are never separated from their results."""
    if len(messages) <= MAX_HISTORY:
        return messages
    messages = messages[-MAX_HISTORY:]
    for i, m in enumerate(messages):
        if m.get("role") == "user":
            return messages[i:]
    return []


_CHAT_ID = re.compile(r"^[0-9a-f]{12}$")


def valid_chat_id(chat_id) -> bool:
    return isinstance(chat_id, str) and bool(_CHAT_ID.match(chat_id))


def _chat_path(chat_id: str):
    return CHATS_DIR / f"{chat_id}.json"


def new_chat_id() -> str:
    return uuid.uuid4().hex[:12]


def load_chat(chat_id: str) -> list[dict]:
    """The full saved conversation (trim() it before sending it to the model)."""
    if not valid_chat_id(chat_id):
        return []
    return _load(_chat_path(chat_id), {}).get("messages", [])


def save_chat(chat_id: str, messages: list[dict]) -> None:
    clean = []
    for m in messages:
        m = dict(m)
        if m.pop("images", None):
            m["content"] = (m.get("content") or "") + " [an image was attached here]"
        clean.append(m)
    first = next((m["content"] for m in clean if m.get("role") == "user" and m.get("content")), "")
    with _lock:
        title = _load(_chat_path(chat_id), {}).get("title") or first.strip()[:40] or "New chat"
        _save(_chat_path(chat_id), {
            "title": title,
            "updated": datetime.now().isoformat(timespec="seconds"),
            "messages": clean,
        })


def list_chats() -> list[dict]:
    chats = []
    for p in CHATS_DIR.glob("*.json"):
        data = _load(p, {})
        chats.append({"id": p.stem, "title": data.get("title", "Chat"), "updated": data.get("updated", "")})
    return sorted(chats, key=lambda c: c["updated"], reverse=True)


def delete_chat(chat_id: str) -> bool:
    if not valid_chat_id(chat_id):
        return False
    with _lock:
        try:
            _chat_path(chat_id).unlink()
            return True
        except FileNotFoundError:
            return False


def _migrate_old_history() -> None:
    """Older versions kept one conversation in history.json; turn it into a chat."""
    old = _load(HISTORY_FILE, None)
    if old:
        save_chat(new_chat_id(), old)
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()


_migrate_old_history()
