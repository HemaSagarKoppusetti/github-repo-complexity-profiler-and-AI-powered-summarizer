import requests
import networkx
import radon
import streamlit
from dotenv import load_dotenv
import os

load_dotenv()

key = os.getenv("OPENROUTER_API_KEY")
model = os.getenv("OPENROUTER_MODEL")

print(f"Key loaded: {repr(key[:15])}...")  # only print first 15 chars for safety
print(f"Model: {repr(model)}")

assert key and key.startswith("sk-or-"), "❌ API key missing or wrong format"

response = requests.post(
    url="https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "GitHub Repo Profiler"
    },
    json={
        "model": model,
        "messages": [{"role": "user", "content": "Say exactly: setup works"}],
        "max_tokens": 20
    }
)

data = response.json()

if "error" in data:
    print(f"❌ API error: {data['error']}")
else:
    reply = data["choices"][0]["message"]["content"]
    actual_model = data.get("model", "unknown")
    print(f"✅ OpenRouter API: {reply}")
    print(f"✅ Routed to model: {actual_model}")
    print("✅ All packages imported successfully")
    print("✅ Environment is ready — let's build!")