from pathlib import Path
import re


def to_markdown(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r'^\s*Q:\s*(.+)$', r'#### Q: \1', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*A:\s*(.+)$', r'> A: \1', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*[•*]\s+', r'- ', t, flags=re.MULTILINE)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def export_markdown(content: str, out_path: str) -> Path:
    md = to_markdown(content)
    out = Path(out_path)
    if out.suffix.lower() != ".md":
        out = out.with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out
