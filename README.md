# StudyWise

StudyWise is a privacy-first desktop application that converts raw academic material into clean study notes, flashcards, and quizzes through a modern graphical interface built with PySide6.

It is designed to be fast, offline-capable, and free from accounts, tracking, or vendor lock-in.

---

## Overview

StudyWise takes unstructured learning material such as lecture PDFs, scanned notes, or documents and transforms it into structured study resources that are ready to use.

The application runs locally by default and gives users full control over how and where AI models are used.

---

## Features

### Document Processing

* Import PDF files (text-based or scanned)
* Extract text from PNG and JPG images using OCR
* Support for DOCX documents
* Automatic text cleaning and normalization
* Batch file handling with file-size display and progress tracking

### Study Material Generation

* Generate structured study notes from raw content
* Automatically create flashcards from generated notes
* Convert flashcards into an interactive quiz mode

### AI Integration

* Local model support via Ollama for offline usage
* Optional cloud model support (e.g. Google Gemini)
* Configurable model and provider settings inside the app
* No forced APIs or subscriptions

### Quiz Mode

* Interactive flashcard practice
* Progressive answer reveal
* Correct and incorrect marking
* Score and progress tracking

### Export Options

* Export notes as Markdown or plain text
* Export flashcards as native Anki (.apkg) decks
* Copy notes and flashcards directly to the clipboard

---

## User Interface

* Desktop GUI built with PySide6
* Multi-tab workspace for:

  * Original text
  * Cleaned text
  * Study notes
  * Flashcards
  * Quiz mode
* Drag-and-drop file support
* Keyboard shortcuts for common actions
* Real-time status updates and progress indicators
* Dark theme with accent-based styling

---

## Privacy

StudyWise is designed with a local-first approach.

* All files remain on the user’s machine by default
* No telemetry, analytics, or user accounts
* Internet access is only required if a cloud-based AI model is explicitly selected
* Fully functional offline workflow with local models

---

## Download

### Windows (x64)

Direct download:

[https://github.com/realwarpie/studywise/releases/download/v0.1.0/StudyWise.exe](https://github.com/realwarpie/studywise/releases/download/v0.1.0/StudyWise.exe)

The application can be downloaded and run directly without an installer.

---

## Technology Stack

* Python
* PySide6 (Qt for Python)
* OCR for scanned document processing
* Local and cloud large language model support

---

## Intended Users

* Students working with large volumes of lecture material
* Exam preparation workflows that require fast summarization
* Users who prefer offline tools and data privacy
* Learners who use external tools such as Anki, Notion, or Obsidian

---

## Project Status

* Early release (v0.1.0)
* Actively developed
* Built for DUHacks 5.0

---

## Author

Ashwin

---

Better notes. Better grades.
