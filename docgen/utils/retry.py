import time

def call_gemini_with_retry(client, model, prompt, retries=5):
    for i in range(retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt
            )
        except Exception as e:
            msg = str(e)
            if "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg:
                wait = 2 ** i
                print(f"Model overloaded. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise e
    raise RuntimeError("Gemini unavailable after retries")
