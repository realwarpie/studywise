import sys
if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import os
import re
from datetime import datetime
from pathlib import Path
import time

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QTextEdit,
    QVBoxLayout, QHBoxLayout, QFileDialog, QProgressBar,
    QSplitter, QTabWidget, QMessageBox, QListWidget, QListWidgetItem,
    QFrame, QScrollArea, QLineEdit, QComboBox, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QPropertyAnimation, QSize, QTimer, QEasingCurve, QSequentialAnimationGroup
from PySide6.QtGui import QPalette, QColor, QFont, QIcon, QPixmap, QTextCursor, QTextCharFormat, QShortcut

from studywise.ai.ollama_client import ollama_has_model
from studywise.cleaner.text_cleaner import clean_text
from studywise.ai.summarizer import summarize_text, generate_flashcards
from studywise.extractor.multi_extractor import extract_and_merge
from studywise.config import load_config
from studywise.ui.settings_dialog import SettingsDialog
from studywise.export.markdown_exporter import to_markdown
from studywise.export.anki_exporter import parse_flashcards, export_anki


# -------------------- THEME --------------------
ACCENT = "#6C5CE7"
ACCENT_HOVER = "#7C6CFF"
ACCENT_DARK = "#5A4BB8"
BG = "#0A0E17"
BG_SECONDARY = "#0F1219"
PANEL = "#151B28"
CARD = "#0D1117"
TEXT = "#E8EAED"
TEXT_SECONDARY = "#A8ADB5"
MUTED = "#6B7280"
SUCCESS = "#34D399"
ERROR = "#EF4444"
WARNING = "#F59E0B"


# -------------------- UTILITIES --------------------
class ToastNotification:
    """Simple toast notification system"""
    def __init__(self, parent, message: str, duration: int = 2000):
        self.parent = parent
        self.message = message
        self.duration = duration
        self.show()
    
    def show(self):
        """Show toast-style notification"""
        QMessageBox.information(self.parent, "Success", self.message)


class AnimatedSpinner:
    """Animated loading spinner using text"""
    def __init__(self):
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0
    
    def get_frame(self) -> str:
        frame = self.frames[self.current]
        self.current = (self.current + 1) % len(self.frames)
        return frame


# -------------------- HELPERS --------------------
def safe_filename(name: str) -> str:
    name = os.path.splitext(name)[0]
    name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
    return name.strip("_").lower()


# -------------------- PROCESSING STATS --------------------
class ProcessingStats:
    """Track processing metrics"""
    def __init__(self):
        self.start_time = None
        self.files_count = 0
        self.raw_chars = 0
        self.cleaned_chars = 0
        self.notes_chars = 0
        self.flashcards_count = 0
        
    def start(self, files_count: int):
        self.start_time = time.time()
        self.files_count = files_count
        
    def get_elapsed(self) -> str:
        if not self.start_time:
            return "0s"
        elapsed = time.time() - self.start_time
        if elapsed < 60:
            return f"{int(elapsed)}s"
        return f"{elapsed/60:.1f}m"
    
    def get_summary(self) -> str:
        stats = []
        stats.append(f"Files: {self.files_count}")
        if self.raw_chars:
            stats.append(f"Raw: {self.raw_chars:,} chars")
        if self.cleaned_chars:
            stats.append(f"Cleaned: {self.cleaned_chars:,} chars")
        if self.notes_chars:
            stats.append(f"Notes: {self.notes_chars:,} chars")
        if self.flashcards_count:
            stats.append(f"Flashcards: {self.flashcards_count} cards")
        stats.append(f"Time: {self.get_elapsed()}")
        return " | ".join(stats)
    
    @staticmethod
    def estimate_time(total_chars: int) -> str:
        """Estimate processing time based on character count"""
        # Rough estimate: ~5000 chars per minute
        minutes = max(1, total_chars // 5000)
        if minutes < 1:
            return "< 1 min"
        elif minutes < 60:
            return f"{minutes} min"
        else:
            return f"{minutes/60:.1f} hrs"


# -------------------- WORKER --------------------
class Worker(QObject):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(str, dict)
    error = Signal(str)

    def __init__(self, files, llm_mode, gemini_key):
        super().__init__()
        self.files = files
        self.llm_mode = llm_mode
        self.gemini_key = gemini_key
        self.cancelled = False
        self.stats = ProcessingStats()

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            self.stats.start(len(self.files))
            self.status.emit(f"Processing {len(self.files)} file(s)…")
            self.progress.emit(10)

            if self.cancelled:
                return

            raw = extract_and_merge(self.files)
            if not raw.strip():
                raise RuntimeError("No text extracted")

            self.stats.raw_chars = len(raw)
            self.status.emit("Cleaning content…")
            self.progress.emit(35)
            cleaned = clean_text(raw)

            if self.cancelled:
                return

            self.stats.cleaned_chars = len(cleaned)
            self.status.emit("Generating study notes…")
            self.progress.emit(65)
            notes = summarize_text(cleaned, self.llm_mode, self.gemini_key)

            if self.cancelled:
                return

            self.stats.notes_chars = len(notes)
            self.status.emit("Generating flashcards…")
            cards = generate_flashcards(notes, self.llm_mode, self.gemini_key)
            self.stats.flashcards_count = len(cards)

            self.progress.emit(100)
            self.finished.emit(notes, {
                "raw": raw,
                "cleaned": cleaned,
                "flashcards": cards,
                "stats": self.stats
            })

        except Exception as e:
            self.error.emit(str(e))


# -------------------- UI --------------------
class StudyWiseApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StudyWise - Study Notes Generator")
        self.setMinimumSize(1400, 850)
        self.setGeometry(100, 100, 1400, 850)

        self.files = []
        self.worker = None
        self.worker_thread = None
        self.last_save_dir = os.getcwd()
        self.is_dragging = False

        # Initialize quiz state early
        self.quiz_cards = []
        self.quiz_index = 0
        self.quiz_correct = 0
        self.quiz_total_answered = 0
        self.quiz_completed = False

        # ===== BUILD UI =====
        self.build_ui()
        self.apply_theme()
        self.setAcceptDrops(True)
        self.update_file_placeholder()
        
        # ===== KEYBOARD SHORTCUTS =====
        QShortcut("Return", self).activated.connect(self.generate)
        QShortcut("Escape", self).activated.connect(self.stop_generation)
        QShortcut("Ctrl+O", self).activated.connect(self.open_files)
        QShortcut("Ctrl+H", self).activated.connect(self.show_help)
        
        # Add animation timer for idle state
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self.update_idle_state)
        self.idle_timer.start(500)

    def build_ui(self):
        """Construct the complete UI layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== HEADER SECTION =====
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_frame.setFixedHeight(110)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 16, 24, 16)
        header_layout.setSpacing(12)

        # Title + Subtitle
        title_container = QHBoxLayout()
        title = QLabel("StudyWise")
        title.setFont(QFont("Segoe UI", 32, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT_HOVER}; background: none;")

        subtitle = QLabel("Professional Study Notes Generator")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; background: none;")

        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        title_container.addLayout(title_col)
        title_container.addStretch()

        # Header buttons
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedSize(120, 36)
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setToolTip("Configure AI model and API settings")

        self.help_btn = QPushButton("Help")
        self.help_btn.setFixedSize(80, 36)
        self.help_btn.clicked.connect(self.show_help)
        self.help_btn.setToolTip("View keyboard shortcuts and help")

        self.theme_btn = QPushButton("Theme")
        self.theme_btn.setFixedSize(80, 36)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.theme_btn.setToolTip("Toggle dark/light theme")

        self.add_btn = QPushButton("Add Files")
        self.add_btn.setFixedSize(130, 36)
        self.add_btn.clicked.connect(self.open_files)
        self.add_btn.setObjectName("PrimaryButton")
        self.add_btn.setToolTip("Add PDF or image files to process")

        title_container.addWidget(self.settings_btn, alignment=Qt.AlignRight)
        title_container.addWidget(self.theme_btn, alignment=Qt.AlignRight)
        title_container.addWidget(self.help_btn, alignment=Qt.AlignRight)
        title_container.addWidget(self.add_btn, alignment=Qt.AlignRight)

        # Status info
        self.status = QLabel("Ready to process documents")
        self.status.setFont(QFont("Segoe UI", 9))
        self.status.setStyleSheet(f"color: {TEXT_SECONDARY}; background: none;")

        header_layout.addLayout(title_container)
        header_layout.addWidget(self.status)

        # ===== CONTENT SECTION =====
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        # Left Sidebar - File List
        sidebar = self.create_sidebar()
        content_layout.addWidget(sidebar, stretch=0)

        # Right Workspace - Editors
        workspace = self.create_workspace()
        content_layout.addWidget(workspace, stretch=1)

        # ===== ACTION BAR =====
        action_frame = QFrame()
        action_frame.setObjectName("ActionBar")
        action_frame.setFixedHeight(70)
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(24, 12, 24, 12)
        action_layout.setSpacing(8)

        # Progress section
        progress_row = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_label.setFont(QFont("Segoe UI", 9))
        self.progress_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        
        self.progress = QProgressBar()
        self.progress.setFixedHeight(5)
        self.progress.setMaximumWidth(400)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {CARD};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: linear-gradient(to right, {ACCENT_HOVER}, {ACCENT});
                border-radius: 3px;
            }}
        """)

        progress_row.addWidget(self.progress_label)
        progress_row.addWidget(self.progress)
        progress_row.addStretch()

        # Button row
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        
        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.setFixedSize(140, 38)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setToolTip("Cancel the current processing (Esc)")

        self.generate_btn = QPushButton("Generate Notes")
        self.generate_btn.setFixedSize(160, 38)
        self.generate_btn.setEnabled(False)
        self.generate_btn.setObjectName("PrimaryButton")
        self.generate_btn.clicked.connect(self.generate)
        self.generate_btn.setToolTip("Process selected files and generate study notes (Enter)")

        button_row.addStretch()
        button_row.addWidget(self.stop_btn)
        button_row.addWidget(self.generate_btn)

        action_layout.addLayout(progress_row)
        action_layout.addLayout(button_row)

        # ===== ASSEMBLE MAIN LAYOUT =====
        main_layout.addWidget(header_frame)
        main_layout.addWidget(content_frame, stretch=1)
        main_layout.addWidget(action_frame)

        # Setup keyboard shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        self.generate_btn.setShortcut("Return")
        self.stop_btn.setShortcut("Escape")
        
        # Create action for Ctrl+O
        import weakref
        from PySide6.QtGui import QAction
        open_action = QAction(self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_files)
        self.addAction(open_action)

    def create_sidebar(self) -> QFrame:
        """Create the left sidebar with file list and controls"""
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(340)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        # Files section header
        files_header = QLabel("FILE QUEUE")
        files_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        files_header.setStyleSheet(f"color: {MUTED}; background: none; letter-spacing: 1px;")
        sidebar_layout.addWidget(files_header)

        # File list with search
        search_layout = QHBoxLayout()
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("Search files...")
        self.file_search.setMaximumHeight(28)
        self.file_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {PANEL};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT_HOVER};
            }}
        """)
        self.file_search.textChanged.connect(self.filter_files)
        search_layout.addWidget(self.file_search)
        sidebar_layout.addLayout(search_layout)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(220)
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)
        self.file_list.setStyleSheet(f"""
            QListWidget {{
                border-radius: 6px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-radius: 4px;
                margin: 2px 0px;
            }}
            QListWidget::item:hover {{
                background-color: rgba(124, 108, 255, 0.1);
            }}
        """)
        sidebar_layout.addWidget(self.file_list, stretch=1)

        # File info
        self.file_info = QLabel()
        self.file_info.setFont(QFont("Segoe UI", 9))
        self.file_info.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: none;
            padding: 4px 0px;
        """)
        sidebar_layout.addWidget(self.file_info)

        # Control buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setMinimumHeight(32)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setToolTip("Remove selected file from queue")

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setMinimumHeight(32)
        self.clear_btn.clicked.connect(self.clear_files)
        self.clear_btn.setToolTip("Clear all files from queue")

        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        sidebar_layout.addLayout(btn_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {PANEL};")
        sidebar_layout.addWidget(divider)

        # Model section
        model_label = QLabel("AI MODEL")
        model_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        model_label.setStyleSheet(f"color: {MUTED}; background: none; letter-spacing: 1px;")
        sidebar_layout.addWidget(model_label)

        cfg = load_config()
        llm_mode = cfg.get("llm_mode", "ollama")
        
        # Model indicator
        self.model_indicator = QLabel(llm_mode.upper())
        self.model_indicator.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.model_indicator.setStyleSheet(f"""
            color: {SUCCESS};
            background-color: rgba(52, 211, 153, 0.1);
            padding: 10px;
            border-radius: 6px;
            border-left: 4px solid {SUCCESS};
        """)
        sidebar_layout.addWidget(self.model_indicator)

        # Status indicator
        self.status_indicator = QLabel("Status: Connected")
        self.status_indicator.setFont(QFont("Segoe UI", 8))
        self.status_indicator.setStyleSheet(f"color: {TEXT_SECONDARY}; background: none;")
        sidebar_layout.addWidget(self.status_indicator)

        # Statistics section
        sidebar_layout.addSpacing(12)
        stats_label = QLabel("PROCESSING STATS")
        stats_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        stats_label.setStyleSheet(f"color: {MUTED}; background: none; letter-spacing: 1px;")
        sidebar_layout.addWidget(stats_label)

        self.stats_display = QLabel("Waiting for input...")
        self.stats_display.setFont(QFont("Segoe UI", 8))
        self.stats_display.setWordWrap(True)
        self.stats_display.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background-color: rgba(124, 108, 255, 0.05);
            padding: 8px;
            border-radius: 4px;
            border-left: 3px solid {ACCENT_HOVER};
        """)
        sidebar_layout.addWidget(self.stats_display)

        return sidebar

    def create_workspace(self) -> QFrame:
        """Create the main workspace with tabs"""
        workspace = QFrame()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        # Create tabs
        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("MainTabs")

        # ===== INPUT TABS (Left side) =====
        input_tabs = QTabWidget()
        input_tabs.setObjectName("InputTabs")

        # Raw view with copy button
        raw_container = QFrame()
        raw_layout = QVBoxLayout(raw_container)
        raw_layout.setContentsMargins(8, 8, 8, 8)
        raw_layout.setSpacing(8)
        
        raw_button_row = QHBoxLayout()
        raw_copy_btn = QPushButton("Copy")
        raw_copy_btn.setFixedWidth(70)
        raw_copy_btn.setFixedHeight(28)
        raw_copy_btn.setToolTip("Copy to clipboard")
        raw_button_row.addStretch()
        raw_button_row.addWidget(raw_copy_btn)
        
        self.raw_view = QTextEdit(readOnly=True)
        self.raw_view.setPlaceholderText("Original extracted content will appear here...\n\nDrag and drop files or use the 'Add Files' button to get started.")
        
        raw_copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.raw_view, "Raw content"))
        
        raw_layout.addLayout(raw_button_row)
        raw_layout.addWidget(self.raw_view)
        input_tabs.addTab(raw_container, "Original")

        # Cleaned view with copy button
        cleaned_container = QFrame()
        cleaned_layout = QVBoxLayout(cleaned_container)
        cleaned_layout.setContentsMargins(8, 8, 8, 8)
        cleaned_layout.setSpacing(8)
        
        cleaned_button_row = QHBoxLayout()
        cleaned_copy_btn = QPushButton("Copy")
        cleaned_copy_btn.setFixedWidth(70)
        cleaned_copy_btn.setFixedHeight(28)
        cleaned_button_row.addStretch()
        cleaned_button_row.addWidget(cleaned_copy_btn)
        
        self.cleaned_view = QTextEdit(readOnly=True)
        self.cleaned_view.setPlaceholderText("Cleaned and normalized text will appear here...\n\nThis shows the text after removing artifacts and normalizing formatting.")
        
        cleaned_copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.cleaned_view, "Cleaned content"))
        
        cleaned_layout.addLayout(cleaned_button_row)
        cleaned_layout.addWidget(self.cleaned_view)
        input_tabs.addTab(cleaned_container, "Cleaned")

        # ===== OUTPUT TABS (Right side) =====
        output_tabs = QTabWidget()
        output_tabs.setObjectName("OutputTabs")
        # keep a reference for enabling/disabling tabs later (Quiz Mode)
        self.output_tabs = output_tabs

        # Notes view with copy and export buttons
        notes_container = QFrame()
        notes_layout = QVBoxLayout(notes_container)
        notes_layout.setContentsMargins(8, 8, 8, 8)
        notes_layout.setSpacing(8)
        
        notes_button_row = QHBoxLayout()
        notes_search = QLineEdit()
        notes_search.setPlaceholderText("Search notes...")
        notes_search.setMaximumWidth(150)
        notes_search.setFixedHeight(28)
        
        notes_button_row.addWidget(notes_search)
        notes_button_row.addStretch()
        
        notes_copy_btn = QPushButton("Copy")
        notes_copy_btn.setFixedWidth(70)
        notes_copy_btn.setFixedHeight(28)
        notes_export_btn = QPushButton("Export")
        notes_export_btn.setFixedWidth(70)
        notes_export_btn.setFixedHeight(28)
        
        notes_button_row.addWidget(notes_copy_btn)
        notes_button_row.addWidget(notes_export_btn)
        
        self.notes_view = QTextEdit(readOnly=True)
        self.notes_view.setPlaceholderText("AI-generated study notes will appear here...\n\nThe AI will transform the content into clean, exam-ready notes.")
        
        notes_copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.notes_view, "Study notes"))
        notes_export_btn.clicked.connect(lambda: self.export_content(self.notes_view, "study_notes"))
        notes_search.textChanged.connect(lambda text: self.search_in_text(self.notes_view, text))
        
        notes_layout.addLayout(notes_button_row)
        notes_layout.addWidget(self.notes_view)
        output_tabs.addTab(notes_container, "Study Notes")

        # Flashcards view with copy and export buttons
        cards_container = QFrame()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(8, 8, 8, 8)
        cards_layout.setSpacing(8)
        
        cards_button_row = QHBoxLayout()
        cards_search = QLineEdit()
        cards_search.setPlaceholderText("Search cards...")
        cards_search.setMaximumWidth(150)
        cards_search.setFixedHeight(28)
        
        cards_button_row.addWidget(cards_search)
        cards_button_row.addStretch()
        
        cards_copy_btn = QPushButton("Copy")
        cards_copy_btn.setFixedWidth(70)
        cards_copy_btn.setFixedHeight(28)
        cards_export_btn = QPushButton("Export")
        cards_export_btn.setFixedWidth(70)
        cards_export_btn.setFixedHeight(28)
        
        cards_button_row.addWidget(cards_copy_btn)
        cards_button_row.addWidget(cards_export_btn)
        
        self.flashcards_view = QTextEdit(readOnly=True)
        self.flashcards_view.setPlaceholderText("AI-generated flashcards will appear here...\n\nPerfect for quick review and memorization.")
        
        cards_copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.flashcards_view, "Flashcards"))
        cards_export_btn.clicked.connect(lambda: self.export_content(self.flashcards_view, "flashcards"))
        cards_search.textChanged.connect(lambda text: self.search_in_text(self.flashcards_view, text))
        
        cards_layout.addLayout(cards_button_row)
        cards_layout.addWidget(self.flashcards_view)
        output_tabs.addTab(cards_container, "Flashcards")

        # Quiz Mode tab
        quiz_container = QFrame()
        quiz_layout = QVBoxLayout(quiz_container)
        quiz_layout.setContentsMargins(12, 12, 12, 12)
        quiz_layout.setSpacing(12)

        # Progress/score row
        quiz_top_row = QHBoxLayout()
        self.quiz_progress_label = QLabel("No quiz yet")
        self.quiz_progress_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        quiz_top_row.addWidget(self.quiz_progress_label)
        quiz_top_row.addStretch()

        # Question label
        self.quiz_question_label = QLabel("Generate flashcards to start Quiz Mode")
        self.quiz_question_label.setWordWrap(True)
        self.quiz_question_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.quiz_question_label.setStyleSheet("font-size: 14pt; font-weight: 600;")

        # Answer label (initially hidden)
        self.quiz_answer_label = QLabel("")
        self.quiz_answer_label.setWordWrap(True)
        self.quiz_answer_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.quiz_answer_label.setStyleSheet("font-size: 12pt; color: #A8ADB5;")
        self.quiz_answer_label.setVisible(False)

        # Controls row
        quiz_controls = QHBoxLayout()
        self.quiz_reveal_btn = QPushButton("Reveal Answer")
        self.quiz_correct_btn = QPushButton("Correct")
        self.quiz_incorrect_btn = QPushButton("Incorrect")
        self.quiz_prev_btn = QPushButton("Prev")
        self.quiz_next_btn = QPushButton("Next")
        for b in [self.quiz_reveal_btn, self.quiz_correct_btn, self.quiz_incorrect_btn, self.quiz_prev_btn, self.quiz_next_btn]:
            b.setFixedHeight(32)
        quiz_controls.addWidget(self.quiz_reveal_btn)
        quiz_controls.addStretch()
        quiz_controls.addWidget(self.quiz_correct_btn)
        quiz_controls.addWidget(self.quiz_incorrect_btn)
        quiz_controls.addWidget(self.quiz_prev_btn)
        quiz_controls.addWidget(self.quiz_next_btn)

        # Wire quiz actions
        self.quiz_reveal_btn.clicked.connect(self.reveal_answer)
        self.quiz_correct_btn.clicked.connect(self.mark_correct)
        self.quiz_incorrect_btn.clicked.connect(self.mark_incorrect)
        self.quiz_prev_btn.clicked.connect(self.prev_card)
        self.quiz_next_btn.clicked.connect(self.next_card)

        # Assemble quiz layout
        quiz_layout.addLayout(quiz_top_row)
        quiz_layout.addWidget(self.quiz_question_label)
        quiz_layout.addWidget(self.quiz_answer_label)
        quiz_layout.addLayout(quiz_controls)

        self.quiz_tab_index = output_tabs.addTab(quiz_container, "Quiz Mode")
        # Initially disabled until cards exist
        self.output_tabs.setTabEnabled(self.quiz_tab_index, False)

        # Splitter to divide input/output
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(input_tabs)
        splitter.addWidget(output_tabs)
        splitter.setSizes([600, 700])
        splitter.setHandleWidth(8)

        workspace_layout.addWidget(splitter)

        return workspace

    # ---------- FILE LIST MANAGEMENT ----------
    def update_file_placeholder(self):
        self.file_list.clear()
        if not self.files:
            item = QListWidgetItem("No files added yet")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(MUTED))
            self.file_list.addItem(item)
            self.file_info.setText("0 files in queue")
        else:
            self.display_files(self.files)
            count = len(self.files)
            plural = "file" if count == 1 else "files"
            size_info = self.get_total_size()
            self.file_info.setText(f"{count} {plural} • {size_info}")

    def display_files(self, files_to_show):
        """Display files in the list with file type indicators and sizes"""
        self.file_list.clear()
        for idx, f in enumerate(files_to_show, 1):
            name = os.path.basename(f)
            ext = os.path.splitext(name)[1].lower()
            
            # File type indicator
            if ext == ".pdf":
                type_icon = "▪"
            elif ext in [".png", ".jpg", ".jpeg"]:
                type_icon = "▢"
            else:
                type_icon = "•"
            
            # Get file size
            try:
                size = os.path.getsize(f)
                size_str = self.format_size(size)
                display_text = f"{type_icon} {name}  [{size_str}]"
            except:
                display_text = f"{type_icon} {name}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, f)  # Store full path
            item.setData(Qt.DisplayRole, display_text)
            self.file_list.addItem(item)

    def filter_files(self):
        """Filter files based on search text"""
        search_text = self.file_search.text().lower()
        if not search_text.strip():
            # No filter, show all files
            if self.files:
                self.display_files(self.files)
            return
        
        filtered_files = [
            f for f in self.files 
            if search_text in os.path.basename(f).lower()
        ]
        if filtered_files:
            self.display_files(filtered_files)
            self.file_info.setText(f"{len(filtered_files)} matching file(s)")
        else:
            self.file_list.clear()
            item = QListWidgetItem("No matching files")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor(MUTED))
            self.file_list.addItem(item)
            self.file_info.setText("0 matching files")

    def get_total_size(self) -> str:
        """Calculate and format total file size"""
        total = sum(os.path.getsize(f) for f in self.files if os.path.exists(f))
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total < 1024:
                return f"{total:.1f} {unit}"
            total /= 1024
        return f"{total:.1f} TB"

    def on_file_selected(self):
        """Handle file selection"""
        item = self.file_list.currentItem()
        if item:
            file_path = item.data(Qt.UserRole)
            if file_path and os.path.exists(file_path):
                size = os.path.getsize(file_path)
                size_str = self.format_size(size)
                self.file_info.setText(f"Selected: {size_str}")
            else:
                # Fall back to showing queue info
                if self.files:
                    self.file_info.setText(f"{len(self.files)} files in queue")
        else:
            if self.files:
                self.file_info.setText(f"{len(self.files)} files in queue")

    @staticmethod
    def format_size(bytes_size: int) -> str:
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} GB"

    # ---------- UI STATE ----------
    def lock_ui(self):
        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_btn.setEnabled(False)
        self.settings_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def unlock_ui(self):
        self.generate_btn.setEnabled(bool(self.files))
        self.stop_btn.setEnabled(False)
        self.add_btn.setEnabled(True)
        self.settings_btn.setEnabled(True)
        self.remove_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    # ---------- SETTINGS ----------
    def open_settings(self):
        SettingsDialog(self).exec()
        cfg = load_config()
        llm_mode = cfg.get("llm_mode", "ollama")
        self.model_indicator.setText(llm_mode.upper())

    def show_help(self):
        """Display keyboard shortcuts and help information"""
        help_text = """
KEYBOARD SHORTCUTS & HELP

SHORTCUTS:
  Enter          - Generate study notes from selected files
  Escape         - Stop current processing
  Ctrl+O         - Open file dialog
  
WORKFLOW:
    1. Click "Add Files" or drag & drop PDF/images/DOCX
  2. Adjust settings if needed (Ollama vs Gemini)
  3. Press Enter or click "Generate Notes"
  4. Review results in tabs (Original, Cleaned, Study Notes, Flashcards)
  5. Save your study notes when satisfied

FEATURES:
  • Real-time file search in queue
  • File size display for each document
  • Processing statistics and time tracking
    • Support for PDF (with OCR), images, and DOCX
  • AI-powered study notes generation
  • Automatic flashcard creation
    • Multiple export formats (Markdown, Text, Anki .apkg)
    • Quiz Mode to practice generated flashcards

TIPS:
  • Use smaller documents for faster processing
  • Ensure Ollama is running if using local AI
  • Processing time depends on file size and AI model
  • Flashcards are extracted from generated notes

SETTINGS:
  • Switch between Ollama (local) and Gemini (cloud)
  • Configure API key for Gemini in Settings
        """
        QMessageBox.information(self, "Help & Shortcuts", help_text.strip())

    def toggle_theme(self):
        """Toggle between dark and light theme"""
        # For now, show a toast - full light mode would require extensive CSS updates
        self.show_toast("Light theme coming in next update", "info")

    # ---------- FILES ----------
    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Files to Process", "", "Documents (*.pdf *.png *.jpg *.jpeg *.docx)"
        )
        self.add_files(paths)

    # ---------- STATUS UPDATES ----------
    def update_status(self, msg: str):
        """Update status with proper formatting"""
        self.status.setText(msg)
        self.progress_label.setText(msg)

    def add_files(self, paths):
        if not paths:
            return
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self.file_search.clear()
        self.file_list.clearSelection()
        self.update_file_placeholder()
        if self.files:
            self.generate_btn.setEnabled(True)
            count = len(self.files)
            plural = "file" if count == 1 else "files"
            self.update_status(f"{count} {plural} ready to process")

    def remove_selected(self):
        item = self.file_list.currentItem()
        if item:
            file_path = item.data(Qt.UserRole)
            if file_path and file_path in self.files:
                self.files.remove(file_path)
                self.file_search.clear()
                self.file_list.clearSelection()
        
        self.update_file_placeholder()
        self.generate_btn.setEnabled(bool(self.files))
        
        if self.files:
            count = len(self.files)
            plural = "file" if count == 1 else "files"
            self.update_status(f"{count} {plural} ready to process")
        else:
            self.update_status("Ready to process documents")

    def clear_files(self):
        self.files.clear()
        self.file_search.clear()
        self.file_list.clearSelection()
        self.progress.setValue(0)
        self.progress_label.setText("Ready")
        self.update_file_placeholder()
        self.generate_btn.setEnabled(False)
        self.update_status("Ready to process documents")

    # ---------- DRAG & DROP ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self.is_dragging = True
            # Highlight the entire window
            self.setStyleSheet(self.styleSheet() + f"""
                StudyWiseApp {{
                    border: 2px dashed {ACCENT_HOVER};
                    background-color: rgba(124, 108, 255, 0.05);
                }}
            """)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.is_dragging = False
        self.apply_theme()

    def dropEvent(self, e):
        self.is_dragging = False
        self.apply_theme()
        self.add_files([u.toLocalFile() for u in e.mimeData().urls()])

    def update_idle_state(self):
        """Subtle animation for idle state"""
        if not self.files and not self.is_dragging:
            # Subtle pulsing effect could go here if needed
            pass

    # ---------- GENERATION ----------
    def generate(self):
        if not self.files:
            return

        cfg = load_config()
        llm_mode = cfg.get("llm_mode", "ollama")

        if llm_mode == "ollama" and not ollama_has_model():
            QMessageBox.warning(
                self,
                "⚠ Local AI Model Not Found",
                "Ollama is not set up with a model.\n\n"
                "Run this command in terminal:\n  ollama pull llama3\n\n"
                "Or switch to Gemini in Settings."
            )
            return

        self.lock_ui()
        self.progress.setValue(0)
        self.progress_label.setText("Starting...")
        self.notes_view.clear()
        self.flashcards_view.clear()
        self.raw_view.clear()
        self.cleaned_view.clear()

        self.worker = Worker(self.files, llm_mode, cfg.get("gemini_api_key", ""))
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress_with_step)
        self.worker.status.connect(self.update_status)
        self.worker.finished.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.error.connect(self.worker_thread.quit)

        self.worker_thread.start()

    def update_progress_with_step(self, value: int):
        """Update progress with step indicator"""
        self.progress.setValue(value)
        
        # Show which step we're on
        if value < 20:
            step = "Extracting..."
        elif value < 40:
            step = "Cleaning..."
        elif value < 70:
            step = "Analyzing..."
        elif value < 100:
            step = "Generating flashcards..."
        else:
            step = "Complete"
        
        self.progress_label.setText(step)

    def stop_generation(self):
        if self.worker:
            self.worker.cancel()
        if self.worker_thread:
            self.worker_thread.quit()
        self.update_status("Processing cancelled")
        self.unlock_ui()

    def on_done(self, notes, data):
        self.progress.setValue(100)
        self.progress_label.setText("Complete")
        
        self.notes_view.setPlainText(notes)
        self.raw_view.setPlainText(data["raw"])
        self.cleaned_view.setPlainText(data["cleaned"])

        cards = data.get("flashcards", [])
        cards_text = (
            "\n\n---\n\n".join([f"Question: {q}\n\nAnswer: {a}" for q, a in cards])
            if cards
            else "No flashcards generated."
        )
        self.flashcards_view.setPlainText(cards_text)

        # Initialize Quiz Mode from generated cards
        try:
            self.init_quiz(cards)
        except Exception:
            # Fail silently; quiz is optional
            pass

        # Display statistics
        stats = data.get("stats")
        if stats:
            self.stats_display.setText(stats.get_summary())

        # Save file with error handling
        if not self.files:
            self.update_status("No files to save from")
            self.unlock_ui()
            return

        try:
            base = safe_filename(os.path.basename(self.files[0]))
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default = f"{base}_notes_{ts}.md"

            path, _ = QFileDialog.getSaveFileName(
                self, "Save Study Notes",
                os.path.join(self.last_save_dir, default),
                "Markdown (*.md);;Text (*.txt);;All Files (*.*)"
            )

            if path:
                self.last_save_dir = os.path.dirname(path)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(notes)
                self.update_status(f"Study notes saved: {os.path.basename(path)}")
            else:
                self.update_status("Processing complete (file not saved)")
        except Exception as e:
            self.update_status(f"Error saving file: {str(e)[:50]}")

        self.unlock_ui()

    def on_error(self, err):
        error_short = err[:200] + "..." if len(err) > 200 else err
        
        if "timeout" in err.lower():
            title = "Processing Timeout"
            msg = "The AI model took too long to respond.\n\nTry again with fewer files or a shorter document."
        elif "quota" in err.lower():
            title = "API Quota Exceeded"
            msg = error_short
        elif "no text extracted" in err.lower():
            title = "No Content Found"
            msg = "No readable content could be extracted from the selected files."
        else:
            title = "Processing Error"
            msg = error_short

        QMessageBox.critical(self, title, msg)
        self.progress.setValue(0)
        self.progress_label.setText("Error occurred")
        self.unlock_ui()
        self.update_status("Error during processing - try again")


    # ---------- HELPER METHODS ----------
    def copy_to_clipboard(self, text_widget: QTextEdit, item_name: str) -> None:
        """Copy text widget content to clipboard with toast notification"""
        text = text_widget.toPlainText()
        if not text or text.strip().startswith("AI-generated") or text.strip().startswith("Original"):
            self.show_toast("Nothing to copy", "info")
            return
        
        QApplication.clipboard().setText(text)
        self.show_toast(f"Copied {item_name}!", "success")

    def search_in_text(self, text_widget: QTextEdit, search_text: str) -> None:
        """Search for text and highlight matches in QTextEdit"""
        document = text_widget.document()
        cursor = QTextCursor(document)
        
        # Clear previous formatting
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        
        if not search_text:
            return
        
        # Find and highlight matches
        format = QTextCharFormat()
        format.setBackground(QColor(ACCENT_HOVER))
        format.setForeground(QColor(TEXT))
        
        cursor = QTextCursor(document)
        while not cursor.isNull():
            cursor = document.find(search_text, cursor)
            if not cursor.isNull():
                cursor.mergeCharFormat(format)

    def export_content(self, text_widget: QTextEdit, export_type: str) -> None:
        """Export content to file"""
        text = text_widget.toPlainText()
        if not text or text.strip().startswith("AI-generated") or text.strip().startswith("Original"):
            self.show_toast("Nothing to export", "info")
            return
        
        # Create export dialog
        desktop = str(Path.home() / "Desktop")
        # Different filters based on export type
        if export_type == "flashcards":
            filters = "Anki Decks (*.apkg);;Markdown (*.md);;Text Files (*.txt);;All Files (*)"
            default_name = f"{desktop}/flashcards"
        else:
            filters = "Markdown (*.md);;Text Files (*.txt);;All Files (*)"
            default_name = f"{desktop}/{export_type}"
        
        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Content",
            default_name,
            filters
        )
        
        if filename:
            try:
                # Determine format from filter or extension
                if "Anki" in selected_filter or filename.endswith(".apkg"):
                    self._export_anki(text, filename)
                elif "Markdown" in selected_filter or filename.endswith(".md"):
                    self._export_markdown(text, filename)
                else:
                    # Export as plain text
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(text)
                self.show_toast(f"Exported to {Path(filename).name}", "success")
            except Exception as e:
                self.show_toast(f"Export failed: {str(e)}", "error")

    def _export_markdown(self, text: str, filename: str) -> None:
        """Export given text as Markdown using markdown exporter."""
        # Ensure .md extension
        if not filename.lower().endswith(".md"):
            filename = f"{filename}.md"
        md = to_markdown(text)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(md)

    def _export_anki(self, text: str, filename: str) -> None:
        """Export given flashcards text to Anki .apkg deck."""
        # Parse Q/A blocks
        cards = parse_flashcards(text)
        if not cards:
            raise ValueError("No flashcards found to export")

        # Compute deck name and output directory from filename
        out_path = Path(filename)
        if out_path.suffix.lower() != ".apkg":
            out_path = out_path.with_suffix(".apkg")
        deck_name = safe_filename(out_path.stem) or "studywise_deck"
        output_dir = str(out_path.parent)

        try:
            result_path = export_anki(cards, deck_name=deck_name, output_dir=output_dir)
            # If exporter returns a path different than requested, copy/move if needed
            # Ensure final path matches user selection
            if Path(result_path) != out_path:
                # Move/rename to desired path
                Path(result_path).replace(out_path)
        except ImportError as ie:
            raise ImportError("genanki not installed. Run: pip install genanki") from ie

    def show_toast(self, message: str, toast_type: str = "info") -> None:
        """Show temporary toast notification"""
        # Update status label with toast message
        colors = {
            "success": "#4CAF50",
            "error": "#f44336",
            "info": ACCENT_HOVER
        }
        
        self.status.setText(message)
        self.status.setStyleSheet(f"""
            color: white;
            background-color: {colors.get(toast_type, ACCENT_HOVER)};
            padding: 8px 12px;
            border-radius: 4px;
            font-weight: bold;
        """)
        
        # Auto-hide after 3 seconds
        QTimer.singleShot(3000, self.hide_toast)

    def hide_toast(self) -> None:
        """Hide toast notification"""
        self.status.setText("Ready to process documents")
        self.status.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            background: none;
            padding: 0px;
        """)

    # ---------- QUIZ MODE ----------
    def init_quiz(self, cards):
        """Initialize quiz state from list of (question, answer) tuples."""
        self.quiz_cards = cards or []
        self.quiz_index = 0
        self.quiz_correct = 0
        self.quiz_total_answered = 0
        self.quiz_completed = False

        has_cards = len(self.quiz_cards) > 0
        if hasattr(self, 'output_tabs') and hasattr(self, 'quiz_tab_index'):
            self.output_tabs.setTabEnabled(self.quiz_tab_index, has_cards)

        if has_cards:
            self.show_quiz_card(0)
            self.status.setText("Quiz ready. Use Reveal/Next to practice")
        else:
            self.quiz_question_label.setText("No flashcards available. Generate content first.")
            self.quiz_answer_label.setText("")
            self.quiz_answer_label.setVisible(False)
            self.quiz_progress_label.setText("No quiz yet")
            # Disable controls
            self.quiz_reveal_btn.setEnabled(False)
            self.quiz_correct_btn.setEnabled(False)
            self.quiz_incorrect_btn.setEnabled(False)
            self.quiz_prev_btn.setEnabled(False)
            self.quiz_next_btn.setEnabled(False)

    def show_quiz_card(self, index: int):
        if not self.quiz_cards:
            return
        self.quiz_index = max(0, min(index, len(self.quiz_cards) - 1))
        q, a = self.quiz_cards[self.quiz_index]
        self.quiz_question_label.setText(q)
        self.quiz_answer_label.setText(a)
        self.quiz_answer_label.setVisible(False)
        self.update_quiz_progress()
        # Enable/disable buttons appropriately
        self.quiz_reveal_btn.setEnabled(True)
        self.quiz_correct_btn.setEnabled(False)
        self.quiz_incorrect_btn.setEnabled(False)
        self.quiz_prev_btn.setEnabled(self.quiz_index > 0)
        self.quiz_next_btn.setEnabled(self.quiz_index < len(self.quiz_cards) - 1)

    def update_quiz_progress(self):
        total = len(self.quiz_cards)
        current = self.quiz_index + 1 if total else 0
        self.quiz_progress_label.setText(
            f"Card {current}/{total} • Correct: {self.quiz_correct}/{self.quiz_total_answered}"
        )

    def reveal_answer(self):
        if not self.quiz_cards:
            return
        self.quiz_answer_label.setVisible(True)
        self.quiz_correct_btn.setEnabled(True)
        self.quiz_incorrect_btn.setEnabled(True)
        self.quiz_reveal_btn.setEnabled(False)

    def mark_correct(self):
        if not self.quiz_cards:
            return
        self.quiz_correct += 1
        self.quiz_total_answered += 1
        self.update_quiz_progress()
        self.next_card()

    def mark_incorrect(self):
        if not self.quiz_cards:
            return
        self.quiz_total_answered += 1
        self.update_quiz_progress()
        self.next_card()

    def next_card(self):
        if not self.quiz_cards:
            return
        if self.quiz_index < len(self.quiz_cards) - 1:
            self.show_quiz_card(self.quiz_index + 1)
        else:
            self.quiz_completed = True
            self.status.setText("Quiz completed! Great job.")
            # Disable controls at end
            self.quiz_reveal_btn.setEnabled(False)
            self.quiz_correct_btn.setEnabled(False)
            self.quiz_incorrect_btn.setEnabled(False)
            self.quiz_prev_btn.setEnabled(len(self.quiz_cards) > 1)
            self.quiz_next_btn.setEnabled(False)

    def prev_card(self):
        if not self.quiz_cards:
            return
        if self.quiz_index > 0:
            self.show_quiz_card(self.quiz_index - 1)

    # ---------- THEME & STYLING ----------
    def apply_theme(self):
        app = QApplication.instance()
        pal = QPalette()
        pal.setColor(QPalette.Window, QColor(BG))
        pal.setColor(QPalette.Base, QColor(CARD))
        pal.setColor(QPalette.AlternateBase, QColor(PANEL))
        pal.setColor(QPalette.Text, QColor(TEXT))
        pal.setColor(QPalette.Button, QColor(PANEL))
        pal.setColor(QPalette.ButtonText, QColor(TEXT))
        pal.setColor(QPalette.ToolTipBase, QColor(PANEL))
        pal.setColor(QPalette.ToolTipText, QColor(TEXT))
        app.setPalette(pal)

        self.setStyleSheet(f"""
            /* Main Window & Base */
            QWidget {{ 
                background-color: {BG}; 
                color: {TEXT}; 
                font-family: "Segoe UI", "Source Sans Pro", Arial, sans-serif;
                font-size: 10pt;
            }}

            /* Tooltips */
            QToolTip {{
                background-color: {PANEL};
                color: {TEXT};
                border: 1px solid {ACCENT_HOVER};
                border-radius: 4px;
                padding: 4px 8px;
            }}

            /* Header */
            #HeaderFrame {{
                background-color: {BG_SECONDARY};
                border-bottom: 2px solid {PANEL};
            }}

            /* Sidebar */
            #Sidebar {{
                background-color: {PANEL};
                border-radius: 8px;
                border: 1px solid rgba(124, 108, 255, 0.08);
            }}

            /* Tabs */
            #MainTabs::pane, #InputTabs::pane, #OutputTabs::pane {{
                border: 1px solid {PANEL};
                background-color: {BG};
            }}
            QTabBar::tab {{
                background-color: {CARD};
                color: {TEXT_SECONDARY};
                padding: 10px 16px;
                margin-right: 2px;
                border-bottom: 2px solid transparent;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background-color: {PANEL};
                color: {ACCENT_HOVER};
                border-bottom: 2px solid {ACCENT_HOVER};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: rgba(124, 108, 255, 0.08);
                color: {TEXT};
            }}

            /* Text Edits */
            QTextEdit {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {PANEL};
                border-radius: 6px;
                padding: 12px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 9pt;
                line-height: 1.5;
            }}
            QTextEdit:focus {{
                border: 1px solid {ACCENT_HOVER};
                background-color: rgba(12, 17, 23, 0.8);
            }}
            QTextEdit::placeholder-text {{
                color: {MUTED};
            }}

            /* List Widget */
            QListWidget {{
                background-color: {CARD};
                border: 1px solid {PANEL};
                border-radius: 6px;
                outline: none;
                show-decoration-selected: 1;
            }}
            QListWidget::item {{
                padding: 8px 10px;
                background-color: transparent;
                margin: 2px 0px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(124, 108, 255, 0.15);
                border-radius: 4px;
                color: {ACCENT_HOVER};
                font-weight: 500;
            }}
            QListWidget::item:hover:!selected {{
                background-color: rgba(124, 108, 255, 0.08);
            }}

            /* Buttons - Normal */
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.08);
                color: {TEXT};
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: rgba(124, 108, 255, 0.12);
                border: 1px solid {ACCENT_HOVER};
                color: {ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: rgba(124, 108, 255, 0.2);
            }}
            QPushButton:disabled {{
                color: {MUTED};
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid {MUTED};
            }}

            /* Buttons - Primary */
            QPushButton#PrimaryButton {{
                background: linear-gradient(135deg, {ACCENT_HOVER}, {ACCENT});
                color: white;
                border: none;
                font-weight: 600;
            }}
            QPushButton#PrimaryButton:hover {{
                background: linear-gradient(135deg, {ACCENT}, {ACCENT_HOVER});
                color: white;
            }}
            QPushButton#PrimaryButton:pressed {{
                background-color: {ACCENT_DARK};
            }}
            QPushButton#PrimaryButton:disabled {{
                background-color: {MUTED};
                color: {PANEL};
            }}

            /* Line Edit */
            QLineEdit {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {PANEL};
                border-radius: 4px;
                padding: 6px 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {ACCENT_HOVER};
                background-color: rgba(12, 17, 23, 0.9);
            }}

            /* Progress Bar */
            QProgressBar {{
                background-color: {CARD};
                border: none;
                border-radius: 3px;
                text-align: center;
                color: {TEXT_SECONDARY};
                height: 5px;
            }}
            QProgressBar::chunk {{
                background: linear-gradient(90deg, {ACCENT}, {ACCENT_HOVER});
                border-radius: 3px;
            }}

            /* Action Bar */
            #ActionBar {{
                background-color: {BG_SECONDARY};
                border-top: 2px solid {PANEL};
            }}

            /* Splitter */
            QSplitter::handle {{
                background-color: {PANEL};
                width: 1px;
            }}
            QSplitter::handle:hover {{
                background-color: {ACCENT_HOVER};
            }}

            /* Scrollbars */
            QScrollBar:vertical {{
                background-color: {CARD};
                width: 10px;
                border-radius: 5px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {PANEL};
                border-radius: 5px;
                min-height: 20px;
                margin: 2px 2px 2px 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {ACCENT_HOVER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}

            QScrollBar:horizontal {{
                background-color: {CARD};
                height: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {PANEL};
                border-radius: 5px;
                min-width: 20px;
                margin: 2px 2px 2px 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {ACCENT_HOVER};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: none;
            }}

            /* Frame */
            QFrame {{
                background-color: transparent;
            }}
        """)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = StudyWiseApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
