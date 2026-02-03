import re

def clean_text(text: str) -> str:
    # Remove broken encoding artifacts
    text = text.replace("ï¿½", "")
    text = text.replace("â€“", "-")
    text = text.replace("â€™", "'")

    # Normalize spacing while preserving paragraph breaks
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)


    # Restore newlines around file separators
    text = text.replace("=====", "\n\n=====\n\n")

    return text.strip()
