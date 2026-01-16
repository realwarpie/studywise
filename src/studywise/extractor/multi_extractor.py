import os
from studywise.extractor.pdf_extractor import extract_text_from_pdf
from studywise.extractor.image_extractor import extract_text_from_image
from studywise.extractor.docx_extractor import extract_text_from_docx


def extract_and_merge(files: list[str]) -> str:
    """
    Extracts text from multiple files and merges them with clear separators.
    Supports: PDF, PNG, JPG, JPEG, DOCX
    """
    combined = []

    for path in files:
        name = os.path.basename(path)
        combined.append(f"\n\n===== FILE: {name} =====\n\n")

        ext = path.lower()
        if ext.endswith(".pdf"):
            text = extract_text_from_pdf(path)
        elif ext.endswith((".png", ".jpg", ".jpeg")):
            text = extract_text_from_image(path)
        elif ext.endswith(".docx"):
            text = extract_text_from_docx(path)
        else:
            text = ""

        combined.append(text)

    return "\n".join(combined).strip()

