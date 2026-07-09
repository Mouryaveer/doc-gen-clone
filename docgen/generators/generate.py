from schema import DOCUMENT_SCHEMAS

def build_prompt(doc_type, extracted_text, user_inputs):
    fields = "\n".join(f"{k}: {v}" for k, v in user_inputs.items())

    return f"""
You are generating a company owned template of {doc_type.replace('_',' ')}.

Reference document:
{extracted_text}

Use these inputs:
{fields}

STRICT RULES:
- Do NOT change any company-related text.
- Do NOT change company name, mission, address, platform, services, or signatory.
- ONLY replace employee-specific fields.
- Keep same length, structure, and formatting.
- Do NOT rewrite or summarize.
"""
