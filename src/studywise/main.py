import sys
import os

from studywise.extractor.pdf_extractor import extract_text_from_pdf
from studywise.extractor.image_extractor import extract_text_from_image
from studywise.cleaner.text_cleaner import clean_text
from studywise.ai.summarizer import summarize_text


def run(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError("File not found")

    # 1. Extract
    if file_path.lower().endswith(".pdf"):
        raw_text = extract_text_from_pdf(file_path)
    elif file_path.lower().endswith((".png", ".jpg", ".jpeg")):
        raw_text = extract_text_from_image(file_path)
    else:
        raise ValueError("Unsupported file type")

    if not raw_text.strip():
        raise ValueError("No text extracted")

    # 2. Clean
    cleaned_text = clean_text(raw_text)

    # 3. Summarize
    final_notes = summarize_text(cleaned_text)

    return final_notes


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m studywise.main <file>")
        sys.exit(1)

    output = run(sys.argv[1])

    with open("studywise_notes.md", "w", encoding="utf-8") as f:
        f.write(output)

    print("✅ Notes saved to studywise_notes.md")
