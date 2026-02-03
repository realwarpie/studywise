import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io

def extract_text_from_pdf(pdf_path: str) -> str:
    full_text = ""

    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text().strip()

            # If selectable text exists, use it
            if text:
                full_text += text + "\n"
            else:
                # OCR fallback
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_bytes))
                ocr_text = pytesseract.image_to_string(image)
                full_text += ocr_text + "\n"

    return full_text.strip()
