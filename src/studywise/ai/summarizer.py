from studywise.ai.llm_router import summarize as llm_summarize


def chunk_text(text: str, max_chars: int = 3500) -> list[str]:
    """
    Splits text by FILE boundaries first, then by size.
    This prevents mixing multiple documents.
    """
    chunks = []

    has_file_markers = "===== FILE:" in text
    for block in text.split("===== FILE:"):
        block = block.strip()
        if not block:
            continue

        if has_file_markers:
            block = "===== FILE:" + block

        if len(block) <= max_chars:
            chunks.append(block)
        else:
            # If a single file is too large, chunk it internally
            for i in range(0, len(block), max_chars):
                chunks.append(block[i:i + max_chars])

    return chunks

def strip_thinking(text: str) -> str:
    """
    Removes any model 'thinking' or meta commentary.
    Keeps only the final notes.
    """
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        lower = line.lower().strip()

        # Skip obvious reasoning/meta lines
        if lower.startswith(("thinking", "analysis", "we need to", "maybe", "given unclear", "ok.", "...")):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()



def build_prompt(chunk: str) -> str:
    return f"""
You are a study assistant.

IMPORTANT RULES (STRICT):
- DO NOT show your thinking, analysis, or reasoning.
- DO NOT include words like "Thinking", "Analysis", or explanations of what you are doing.
- DO NOT apologize.
- DO NOT mention OCR, errors, guesses, or uncertainty.
- OUTPUT ONLY the final study notes.

The content may come from MULTIPLE DOCUMENTS.
Each document starts with:
===== FILE: filename =====

TASK:
- Create CLEAN, EXAM-READY STUDY NOTES.
- Separate notes by document.
- Use the filename as the section heading.
- Reconstruct broken words ONLY when obvious.
- Ignore corrupted or meaningless fragments.

STYLE:
- Clear headings
- Bullet points
- Short factual lines
- No repetition
- No extra information

CONTENT:
{chunk}
"""

def build_flashcard_prompt(notes: str) -> str:
    return f"""
You are creating exam flashcards.

RULES:
- Create concise QUESTION to ANSWER pairs
- One concept per card
- No explanations outside the answer
- No meta commentary
- No apologies
- Output format EXACTLY:

Q: question text
A: answer text

CONTENT:
{notes}
"""



def summarize_text(
    text: str,
    mode: str = "ollama",        # "ollama" or "gemini"
    gemini_key: str | None = None
) -> str:
    """
    Summarizes text using the selected LLM backend.
    Chunking is handled automatically.
    """

    chunks = chunk_text(text)
    summaries = []

    for i, chunk in enumerate(chunks, start=1):
        print(f"[AI] Summarizing chunk {i}/{len(chunks)}...")

        prompt = build_prompt(chunk)
        summary = llm_summarize(
            prompt=prompt,
            mode=mode,
            gemini_key=gemini_key
        )

        summary = strip_thinking(summary)
        summaries.append(summary)


    return "\n\n".join(summaries)

def generate_flashcards(
    notes: str,
    mode: str = "ollama",
    gemini_key: str | None = None
) -> list[tuple[str, str]]:
    prompt = build_flashcard_prompt(notes)

    raw = llm_summarize(
        prompt=prompt,
        mode=mode,
        gemini_key=gemini_key
    )

    cards = []
    q = None

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("Q:"):
            q = line[2:].strip()
        elif line.startswith("A:") and q:
            a = line[2:].strip()
            cards.append((q, a))
            q = None

    return cards
