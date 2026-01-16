# StudyWise

StudyWise is a local-first application that converts **normal and scanned PDFs** into structured summaries, generated quizzes, and a short study plan.

It is designed for real academic material - including scanned lecture notes and handouts - where most summarization tools fail.

---

## Overview

StudyWise accepts a PDF, automatically detects whether it contains selectable text or scanned images, applies OCR when required, and processes the content page-by-page using a local language model.

Each page is summarized independently to preserve structure and context. The generated notes are then used to create quiz questions and a simple adaptive study plan.

---

## Key Features

- Supports **both text-based and scanned PDFs**
- Automatic scanned-page detection
- OCR-based text extraction using Tesseract
- Page-wise summarization for better structure
- Quiz generation from extracted notes
- Simple adaptive study plan
- Local LLM support (privacy-first)
- Clean Streamlit-based interface

---

## Architecture

1. PDF ingestion and page analysis  
2. Text extraction  
   - Direct text extraction for normal PDFs  
   - OCR fallback for scanned pages  
3. Text chunking with size limits  
4. Page-level summarization using a local LLM  
5. Downstream quiz and study plan generation  
6. Presentation through a lightweight UI

---

## Design Decisions

- **Local-first LLM usage** to avoid unnecessary data sharing
- **Page-level summaries** instead of whole-document summaries to maintain structure
- **Explicit OCR fallback** rather than assuming clean input
- Minimal but reliable feature set, optimized for correctness and clarity

---

## Limitations

- OCR accuracy depends on scan quality
- Large PDFs may require more processing time
- Output quality depends on the selected local language model

These trade-offs were made intentionally to keep the system robust and understandable within a limited development window.

---

## Future Work

- Layout-aware OCR and table handling
- Section-level semantic grouping
- Export integrations (Markdown, Notion)
- Multi-language OCR support
- User progress tracking

---

## Demo

will be up shortly
---

## Author

Ashwin  
Built for DUHacks 5.0
