import requests
import os

OLLAMA_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")

def query_model(model, prompt):
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        data = response.json()
        return data.get("response", "").strip()

    except Exception as e:
        return f"error: {str(e)}"