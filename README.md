# Jarvis

A local personal assistant with a web chat interface, powered by Ollama (`qwen3.5:4b`, which also does vision).

## Features
- Chat with tools: time, weather
- **Web search**: Jarvis searches the internet with [Tavily](https://tavily.com) for current information and can read a page in full; it says which site it used. Needs a free `TAVILY_API_KEY` in `.env` (1,000 searches a month, no card).
- **Google Calendar**: say "add this event" and paste the message about it. Jarvis adds it and reads back what it added. It can also list upcoming events and delete one ("remove the tech talk").
- **Memory**: saves lasting facts (`remember` / `recall` / `forget`) and keeps every chat across restarts. Stored in `memory/` (git-ignored).
- **PDFs**: upload with the paperclip. Text is extracted per page, scanned pages are read by the vision model, and passages are searched with embeddings. Jarvis cites page numbers.
- **Images**: attach or paste an image, then ask about it.

## Setup
1. Install [Ollama](https://ollama.com), then:
   ```
   ollama pull qwen3.5:4b
   ollama pull nomic-embed-text
   ```
2. Create the Python environment:
   ```
   conda create -n jarvis python=3.11
   conda activate jarvis
   pip install -r requirements.txt
   ```
3. Create `.env` from the example, then set your own password:
   ```
   cp .env.example .env
   ```
4. For a 4 GB GPU, start Ollama with:
   ```
   OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
   ```
5. `python web.py`, then open `http://<host>:5000`.

### Google Calendar (optional)
1. In [Google Cloud Console](https://console.cloud.google.com), create a project and enable the **Google Calendar API**.
2. Under **Google Auth Platform**, set up the consent screen (External), and add your own Google account as a **test user**.
3. Under **Clients**, create an OAuth client of type **Desktop app**. Download its JSON and save it as `credentials.json` in this folder (it is git-ignored).
4. Run `python gcal.py` once. A browser opens; sign in and allow access. The token is saved to `memory/google_token.json`.
   If Jarvis runs on a machine without a browser, run this step over `ssh -L 8765:localhost:8765 <host>` and open the printed link on your own computer.

While the consent screen is in "Testing" mode, Google expires the sign-in after 7 days; run `python gcal.py` again when Jarvis says the calendar is not connected, or publish the app (it stays unverified, which is fine for personal use).

Say "think about", "think hard", "think carefully" or "think deeply" for slow, careful mode.
The Menu button lists saved chats and documents: open or delete them, or start a new chat. Saved facts carry over to every chat.

Set `JARVIS_DATA_DIR` to keep data somewhere other than `memory/` (useful for testing).
