import os
from dotenv import load_dotenv
import threading
import ollama
from datetime import datetime
from flask import Flask, request, jsonify

load_dotenv() 

MODEL = "qwen3.5:4b"
PASSWORD = os.environ.get("JARVIS_PASSWORD")

THINK_TRIGGERS = ("think about", "think hard", "think carefully", "think deeply")

def wants_thinking(text: str) -> bool:
    text = text.lower()
    return any(phrase in text for phrase in THINK_TRIGGERS)

def get_time() -> str:
    """Get the current date and time."""
    return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

TOOLS = {"get_time": get_time}

SYSTEM = (
    "You are Jarvis, a polite, dry-witted personal assistant. "
    "Address me as 'Thisen'. "
    "Keep replies short and conversational. "
    "Use the tools provided when they help; never guess the time. "
    "If you are unsure, say so instead of guessing."
)

messages = [{"role": "system", "content": SYSTEM}]
lock = threading.Lock()   # one request at a time

def ask_jarvis(user: str) -> str:
    think = wants_thinking(user)
    messages.append({"role": "user", "content": user})

    while True:
        resp = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=list(TOOLS.values()),
            think=think,
        )
        msg = resp.message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for call in msg.tool_calls:
            fn = TOOLS.get(call.function.name)
            result = fn(**call.function.arguments) if fn else "Unknown tool"
            messages.append({
                "role": "tool",
                "tool_name": call.function.name,
                "content": str(result),
            })

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jarvis</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden; }
  body { font-family: system-ui, sans-serif; background: #111; color: #eee;
         display: flex; flex-direction: column;
         height: 100vh; height: 100dvh; }
  #log { flex: 1; min-height: 0; overflow-y: auto; padding: 16px; }
  .msg { margin: 8px 0; padding: 10px 14px; border-radius: 12px; max-width: 80%;
         white-space: pre-wrap; overflow-wrap: anywhere; }
  .you { background: #2b5cff; margin-left: auto; }
  .jarvis { background: #262626; }
  #bar { display: flex; gap: 8px; padding: 12px; background: #1a1a1a;
         flex-shrink: 0; }
  #box { flex: 1; min-width: 0; padding: 12px; font-size: 16px; border-radius: 8px; border: 0; }
  button { padding: 12px 18px; font-size: 16px; border-radius: 8px; border: 0; }
</style>
</head>
<body>
<div id="log"></div>
<div id="bar">
  <input id="box" placeholder="Talk to Jarvis..." autocomplete="off">
  <button id="send">Send</button>
</div>
<script>
  let password = prompt("Password:");
  const log = document.getElementById("log");
  const box = document.getElementById("box");

  function add(text, who) {
    const d = document.createElement("div");
    d.className = "msg " + who;
    d.textContent = text;
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }

  async function send() {
    const text = box.value.trim();
    if (!text) return;
    box.value = "";
    add(text, "you");
    const wait = add("...", "jarvis");
    try {
      const r = await fetch("/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message: text, password: password})
      });
      const data = await r.json();
      if (r.status === 401) { password = prompt("Wrong password, try again:"); }
      wait.textContent = data.reply || data.error || "Something went wrong.";
    } catch (e) {
      wait.textContent = "Could not reach Jarvis.";
    }
  }

  document.getElementById("send").onclick = send;
  box.addEventListener("keydown", e => { if (e.key === "Enter") send(); });
</script>
</body>
</html>"""

app = Flask(__name__)

@app.route("/")
def index():
    return PAGE

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    if data.get("password") != PASSWORD:
        return jsonify(error="Wrong password."), 401
    user = (data.get("message") or "").strip()
    if not user:
        return jsonify(error="Empty message."), 400
    with lock:
        reply = ask_jarvis(user)
    return jsonify(reply=reply)

if __name__ == "__main__":
    # 0.0.0.0 = reachable from other devices on your network
    app.run(host="0.0.0.0", port=5000)
