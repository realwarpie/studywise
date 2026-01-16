import re
from typing import List, Tuple


def parse_flashcards(text: str) -> List[Tuple[str, str]]:
    """
    Parse flashcards from 'Q: ... A: ...' format.
    
    Args:
        text: Text containing flashcards in format:
              Q: question text
              A: answer text
              
    Returns:
        List of (question, answer) tuples
    """
    cards = []
    lines = text.split('\n')
    current_q = None
    current_a = None
    
    for line in lines:
        line = line.strip()
        
        # Match Q: pattern
        if line.startswith('Q:') or line.startswith('Question:'):
            if current_q and current_a:
                cards.append((current_q, current_a))
            current_q = re.sub(r'^(Q:|Question:)\s*', '', line).strip()
            current_a = None
        
        # Match A: pattern
        elif line.startswith('A:') or line.startswith('Answer:'):
            current_a = re.sub(r'^(A:|Answer:)\s*', '', line).strip()
        
        # Continue multi-line answer
        elif current_q and current_a is not None and line and not line.startswith(('Q:', 'A:', 'Question:', 'Answer:')):
            current_a += ' ' + line
    
    # Add last card
    if current_q and current_a:
        cards.append((current_q, current_a))
    
    return cards


def export_anki(flashcards: List[Tuple[str, str]], deck_name: str = "StudyWise", output_dir: str = ".") -> str:
    """
    Create Anki deck file from flashcards using genanki.
    
    Args:
        flashcards: List of (question, answer) tuples
        deck_name: Name for the Anki deck
        output_dir: Directory to save the .apkg file
        
    Returns:
        Path to created .apkg file
        
    Raises:
        ImportError: If genanki is not installed
        Exception: If deck creation fails
    """
    try:
        import genanki  # type: ignore
    except ImportError:
        raise ImportError(
            "genanki library is required for Anki export. "
            "Install it with: pip install genanki"
        )
    
    if not flashcards:
        raise ValueError("No flashcards to export")
    
    import os
    
    # Create note model (basic Anki flashcard format)
    model_id = 1607392319  # Standard Anki model ID
    model = genanki.Model(
        model_id,
        'StudyWise Flashcard',
        fields=[
            {'name': 'Front'},
            {'name': 'Back'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Front}}',
                'afmt': '{{FrontSide}}<hr id=answer>{{Back}}',
            },
        ],
    )
    
    # Create deck
    deck_id = int(deck_name.encode().hex()[:16], 16) % (2**31)  # Generate consistent ID
    deck = genanki.Deck(deck_id, deck_name)
    
    # Add notes
    for question, answer in flashcards:
        note = genanki.Note(
            model=model,
            fields=[question, answer],
            tags=['studywise']
        )
        deck.add_note(note)
    
    # Create output path
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{deck_name}.apkg")
    
    # Save deck
    genanki.Package(deck).write_to_file(output_file)
    
    return output_file


def export_flashcards_from_text(text: str, deck_name: str = "StudyWise", output_dir: str = ".") -> str:
    """
    Parse flashcards from text and export to Anki format.
    
    Args:
        text: Text containing flashcards
        deck_name: Name for the Anki deck
        output_dir: Directory to save the .apkg file
        
    Returns:
        Path to created .apkg file
    """
    cards = parse_flashcards(text)
    return export_anki(cards, deck_name, output_dir)
