import google.generativeai as genai
import time


def gemini_summarize(prompt: str, api_key: str, max_retries: int = 3) -> str:
    if not api_key:
        raise RuntimeError("Gemini API key not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)

            if not response or not response.text:
                raise RuntimeError("Gemini returned empty response")

            return response.text.strip()

        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limit errors (429)
            if "429" in error_msg or "quota" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"Rate limit hit. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(
                        "Gemini API quota exceeded. Free tier limit reached.\n\n"
                        "Options:\n"
                        "1. Wait and try again later\n"
                        "2. Upgrade to a paid Gemini API plan\n"
                        "3. Switch to Ollama in Settings (free, local AI)"
                    )
            
            # For other errors, fail immediately
            raise
