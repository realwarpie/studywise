import subprocess
import shutil
import os
import json
import urllib.request

DEFAULT_MODEL = "llama3"


def _find_ollama_cli() -> str | None:
    """Locate the Ollama CLI, falling back to typical Windows install paths."""
    path = shutil.which("ollama")
    if path:
        return path
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _ollama_http_models() -> list[str]:
    """Return available model names via REST API, or empty list if unreachable."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            models = data.get("models", [])
            names = []
            for m in models:
                # Recent tags API returns name like "llama3:latest"
                name = m.get("name") or m.get("model")
                if name:
                    # Strip tag suffix if present
                    names.append(str(name).split(":")[0])
            return names
    except Exception:
        return []


def ollama_has_model() -> bool:
    """Check if any Ollama model is available via CLI or REST API."""
    cli = _find_ollama_cli()
    if cli:
        try:
            result = subprocess.run(
                [cli, "list"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass

    # Fallback: REST API
    return bool(_ollama_http_models())


def ollama_summarize(prompt: str) -> str:
    """Summarize via Ollama using CLI if available, otherwise REST API."""
    cli = _find_ollama_cli()
    if cli:
        try:
            result = subprocess.run(
                [cli, "run", DEFAULT_MODEL],
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

    # REST fallback
    models = _ollama_http_models()
    model = DEFAULT_MODEL if DEFAULT_MODEL in models else (models[0] if models else DEFAULT_MODEL)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            if "error" in data:
                raise RuntimeError(f"Ollama error: {data['error']}")
            out = data.get("response", "").strip()
            if not out:
                raise RuntimeError("Ollama returned empty response")
            return out
    except Exception as e:
        raise RuntimeError(f"Ollama REST call failed: {e}")
