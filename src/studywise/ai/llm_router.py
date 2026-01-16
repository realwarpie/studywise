from studywise.ai.gemini_client import gemini_summarize
from studywise.ai.ollama_client import ollama_summarize


def summarize(
    prompt: str,
    mode: str = "ollama",
    gemini_key: str | None = None
) -> str:


    if mode == "gemini":
        if not gemini_key:
            raise RuntimeError("Gemini API key not set.")
        return gemini_summarize(prompt, gemini_key)

    if mode == "ollama":
        return ollama_summarize(prompt)

    raise ValueError(f"Invalid LLM mode: {mode}")
