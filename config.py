import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
# git-ignored; facts, chats, documents. JARVIS_DATA_DIR lets tests use a throwaway folder.
DATA_DIR = Path(os.environ.get("JARVIS_DATA_DIR") or BASE_DIR / "memory")
DOCS_DIR = DATA_DIR / "docs"

MODEL = "qwen3.5:4b"                    # chat + vision
EMBED_MODEL = "nomic-embed-text"        # run `ollama pull nomic-embed-text`
NUM_CTX = 8192                          # keeps the KV cache small enough for 4 GB VRAM

PASSWORD = os.environ.get("JARVIS_PASSWORD")
DEFAULT_CITY = os.environ.get("JARVIS_CITY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")   # web search; free key at tavily.com

# Google Calendar: OAuth client from Google Cloud Console, and the token saved by `python gcal.py`
GOOGLE_CREDENTIALS = BASE_DIR / "credentials.json"
GOOGLE_TOKEN = DATA_DIR / "google_token.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)
