from docx import Document


def extract_text_from_docx(docx_path: str) -> str:
    """
    Extract text from DOCX files while preserving paragraph structure.
    
    Args:
        docx_path: Path to the DOCX file
        
    Returns:
        Extracted text with preserved paragraphs
        
    Raises:
        Exception: If file cannot be read
    """
    try:
        doc = Document(docx_path)
        full_text = []
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                full_text.append(text)
        
        # Extract text from tables if present
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        row_text.append(cell_text)
                if row_text:
                    full_text.append(" | ".join(row_text))
        
        return "\n".join(full_text).strip()
    
    except Exception as e:
        raise RuntimeError(f"Failed to extract from DOCX: {str(e)}")
