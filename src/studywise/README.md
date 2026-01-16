# StudyWise

StudyWise is a **local-first Windows application** that helps students turn their study material into **exam-ready questions and revision content** using language models of their choice.

It is built for real academic workflows — lecture notes, handouts, and documents — with a strong focus on **privacy, control, and clarity**.

---

## What StudyWise Does

StudyWise ingests study material (PDF, DOCX, or text), extracts and cleans the content, and then uses a **user-connected LLM** (cloud or local) to generate **useful study outputs** such as exam-style questions.

The application runs locally on Windows.
No accounts. No forced models. No data upload.

---

## Core Features

* **Windows desktop application** (offline-first)
* Supports:

  * Text-based PDFs
  * Scanned PDFs (OCR fallback)
  * DOCX
  * Plain text
* Automatic detection of scanned pages
* OCR using Tesseract (local)
* Clean text normalization and chunking
* **LLM-agnostic design**

  * Cloud providers (OpenAI, Gemini, Anthropic, etc.)
  * Local models (Ollama, LM Studio, llama.cpp)
* Exam-style question generation:

  * MCQs
  * Short-answer questions
  * Long-answer questions
* Simple, distraction-free UI
* Privacy-first: all processing stays on the user’s machine

---

## What StudyWise Is *Not*

* Not a hosted SaaS
* Not a “magic AI tutor”
* Not locked to a single model
* Not dependent on GPUs or paid APIs

StudyWise is intentionally **boring, predictable, and controllable** - by design.

---

## Architecture Overview

1. **Input Layer**

   * PDF / DOCX / TXT ingestion
   * Page-wise processing for PDFs

2. **Text Extraction**

   * Direct extraction for text-based documents
   * OCR fallback for scanned pages (Tesseract + optional OpenCV preprocessing)

3. **Text Processing**

   * Normalization
   * Noise reduction
   * Chunking (LLM-safe sizes)

4. **LLM Adapter Layer**

   * Unified interface for:

     * Cloud APIs (API key based)
     * Local models (HTTP endpoints)
   * No SDK lock-in

5. **Prompt Engine**

   * Exam-focused prompt templates
   * Deterministic output formatting

6. **UI Layer**

   * Native Windows UI
   * File selection
   * LLM configuration
   * Output viewer

---

## Design Decisions

* **Local-first by default**
  Users control their data and models.

* **LLM-agnostic architecture**
  Avoids vendor lock-in and future-proofs the app.

* **Exam-oriented outputs**
  Prioritizes practical revision over generic summaries.

* **Minimal feature surface**
  Fewer features, higher reliability.

---

## Limitations

* OCR quality depends on scan quality
* Output quality depends on the selected LLM
* Large documents may take longer to process

These trade-offs are intentional to keep the system understandable and robust.

---

## Website

The project website is hosted via **GitHub Pages** and is used to:

* Explain the product
* Showcase screenshots
* Provide Windows downloads
* Link the source repository

No backend services are used.

---

## Demo

Demo screenshots and a short walkthrough will be added soon.

---

## Author

**Ashwin**
Built for **DUHacks 5.0**

---
