from services.ollama_service import query_model

def classify_text(text):

    prompt = f"""
Classify this text into ONE of the following:
- hate speech
- offensive language
- neither

Text: "{text}"

Return ONLY the label.
"""

    llama_result = query_model("llama3.1:latest", prompt)
    phi_result = query_model("phi3:latest", prompt)

    return {
        "llama": llama_result.lower(),
        "phi": phi_result.lower()
    }