import subprocess


def ollama_has_model() -> bool:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=5
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def ollama_summarize(prompt: str) -> str:
    """
    Runs a prompt against the default local Ollama model.
    """

    try:
        result = subprocess.run(
            ["ollama", "run", "llama3"],
            input=prompt,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=90
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Ollama model timed out")

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Ollama failed")

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("Ollama returned empty response")

    return output
