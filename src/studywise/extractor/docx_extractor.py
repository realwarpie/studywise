from docx import Document


def extract_text_from_docx(docx_path: str) -> str:
    document = Document(docx_path)
    parts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            parts.append(text)

    return "\n".join(parts).strip()
