from google import genai
from config import GEMINI_API_KEY, MODEL_NAME
from utils.retry import call_gemini_with_retry

client = genai.Client(api_key=GEMINI_API_KEY)
ALLOWED_TYPES = (
    "NDA",
    "Offer_Letter",
    "Contract",
    "MOU",
    "IP_Agreement",
    "Onboarding_Letter",
)


def _normalize_doc_type(raw_text):
    candidate = (raw_text or "").strip()
    if candidate in ALLOWED_TYPES:
        return candidate

    candidate_lower = candidate.lower()
    for doc_type in ALLOWED_TYPES:
        if doc_type.lower() in candidate_lower:
            return doc_type

    raise ValueError(f"Unsupported classification output: {candidate!r}")

def classify_document(text):
    prompt = f"""
Classify this document into exactly one of:
{", ".join(ALLOWED_TYPES)}.

Do NOT return Other.
Choose the closest match.
Return only the label.

Document:
{text[:3000]}
"""
    response = call_gemini_with_retry(client, MODEL_NAME, prompt)
    return _normalize_doc_type(response.text)
