from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QHBoxLayout
)
from studywise.config import load_config, save_config


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        cfg = load_config()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["ollama", "gemini"])
        self.mode_combo.setCurrentText(cfg.get("llm_mode", "ollama"))

        self.gemini_input = QLineEdit()
        self.gemini_input.setPlaceholderText("Gemini API Key")
        self.gemini_input.setText(cfg.get("gemini_api_key", ""))
        self.gemini_input.setEchoMode(QLineEdit.Password)

        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.save)
        cancel_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("LLM Mode"))
        layout.addWidget(self.mode_combo)
        layout.addWidget(QLabel("Gemini API Key (optional)"))
        layout.addWidget(self.gemini_input)

        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def save(self):
        cfg = {
            "llm_mode": self.mode_combo.currentText(),
            "gemini_api_key": self.gemini_input.text().strip()
        }
        save_config(cfg)
        self.accept()
