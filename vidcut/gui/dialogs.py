"""The export dialog: it only asks for the name of the file."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.formats import OUTPUT_EXTS, extension
from . import icons


class ExportDialog(QDialog):
    """Asks only for the name of the file to write. Quality is set in the Settings tab."""

    def __init__(self, parent: QWidget, default_path: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(520)

        self.path_edit = QLineEdit(default_path)
        self.path_edit.setClearButtonEnabled(True)
        browse = QPushButton("Browse")
        browse.setIcon(icons.icon("folder"))
        browse.setAutoDefault(False)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.path_edit, 1)
        row.addWidget(browse)

        label = QLabel("File name")
        label.setObjectName("muted")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        export_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        export_button.setText("Export")
        export_button.setIcon(icons.icon("export"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(label)
        layout.addLayout(row)
        layout.addSpacing(6)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save as",
            self.path_edit.text(),
            "Video (*.mp4 *.mkv *.mov)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if path:
            self.path_edit.setText(path)

    def _accept(self) -> None:
        path = os.path.abspath(self.path_edit.text().strip())
        if extension(path) not in OUTPUT_EXTS:
            QMessageBox.warning(self, "Export", "The file name must end in .mp4, .mkv or .mov.")
            return
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            QMessageBox.warning(self, "Export", f"This folder does not exist:\n{folder}")
            return
        if os.path.isdir(path):
            QMessageBox.warning(self, "Export", f"This is a folder, not a file:\n{path}")
            return
        if os.path.exists(path):
            answer = QMessageBox.question(self, "Export", f"This file already exists:\n{path}\n\nReplace it?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.path_edit.setText(path)
        self.accept()

    def output_path(self) -> str:
        return self.path_edit.text()
