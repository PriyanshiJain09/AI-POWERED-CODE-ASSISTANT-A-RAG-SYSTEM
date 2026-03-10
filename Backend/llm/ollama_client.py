# llm/ollama_client.py — Groq cloud LLM (drop-in replacement for Ollama)

import os
from groq import Groq

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")  # read fresh, not at import time
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=api_key)
    return _client


async def ask_ollama(prompt: str) -> str:
    """Same function name — drop-in replacement for Ollama."""
    try:
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        client = get_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are RepoMind, an expert code assistant. Answer questions about codebases clearly and concisely. Always cite file names when referencing code."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        error = str(e)
        if "api_key" in error.lower() or "invalid" in error.lower():
            return "⚠️ Invalid Groq API key. Check your .env file."
        if "rate_limit" in error.lower():
            return "⚠️ Groq rate limit hit. Wait a moment and try again."
        return f"⚠️ LLM error: {error}"


async def check_ollama_health() -> dict:
    """Check if Groq is reachable and API key is valid."""
    try:
        model = os.getenv("GROQ_MODEL", "llama3-70b-8192")
        client = get_client()
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return {"running": True, "model_ready": True, "models": [model]}
    except Exception as e:
        return {"running": False, "model_ready": False, "models": [], "error": str(e)}