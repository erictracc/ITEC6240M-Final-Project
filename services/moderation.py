from services.ollama_service import query_model
from concurrent.futures import ThreadPoolExecutor
import json

MODELS = [
    "llama3.1:latest",
    "phi3:latest",
    "llama3-ft",
    "phi-ft"
]


# =========================
# PROMPT BUILDER
# =========================
def build_prompt(text, is_finetuned):

    # SAME FORMAT FOR ALL
    return f"""
You are a STRICT classifier.

Return ONLY ONE label:
- hate speech
- offensive language
- neither

Rules:
- ONLY output the label
- NO explanation
- NO JSON
- NO extra words

Text: "{text}"

Answer:
"""


# =========================
# OUTPUT CLEANER
# =========================
def extract_label(response):
    if not response:
        return "unknown"

    text = response.strip().lower()

    # Handle JSON safely
    if "{" in text:
        try:
            parsed = json.loads(text)
            text = parsed.get("label") or parsed.get("sentiment") or ""
        except:
            pass

    # Hard normalization
    if "hate" in text:
        return "hate speech"

    if "offensive" in text:
        return "offensive language"

    if "neither" in text or "not" in text:
        return "neither"

    return "unknown"


# =========================
# MAIN FUNCTION (PARALLEL)
# =========================
def classify_text(text):

    results = {}

    def run_model(model):
        try:
            is_ft = "-ft" in model
            prompt = build_prompt(text, is_ft)

            raw = query_model(model, prompt)
            clean = extract_label(raw)

            return model, {
                "label": clean,
                "raw": raw,
                "is_finetuned": is_ft
            }

        except Exception as e:
            return model, {
                "label": "error",
                "error": str(e),
                "is_finetuned": "-ft" in model
            }

    # PARALLEL EXECUTION
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_model, m) for m in MODELS]

        for f in futures:
            model, result = f.result()
            results[model] = result

    return results