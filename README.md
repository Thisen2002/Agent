# Jarvis

A local personal assistant with a web chat interface, powered by Ollama (`qwen3.5:4b`, which also does vision).

## Features
- Chat with tools: time, weather
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

Say "think about", "think hard", "think carefully" or "think deeply" for slow, careful mode.
The Menu button lists saved chats and documents: open or delete them, or start a new chat. Saved facts carry over to every chat.

Set `JARVIS_DATA_DIR` to keep data somewhere other than `memory/` (useful for testing).
