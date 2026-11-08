import ollama
from datetime import datetime

MODEL = "qwen3.5:4b"

# Say any of these phrases and Jarvis switches to slow, careful mode.
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

while True:
    user = input("You: ").strip()
    if user.lower() in ("exit", "quit"):
        break

    think = wants_thinking(user)
    if think:
        print("Jarvis: (thinking it over, this may take a minute...)")

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
            print("Jarvis:", msg.content)
            break

        for call in msg.tool_calls:
            fn = TOOLS.get(call.function.name)
            result = fn(**call.function.arguments) if fn else "Unknown tool"
            messages.append({
                "role": "tool",
                "tool_name": call.function.name,
                "content": str(result),
            })
