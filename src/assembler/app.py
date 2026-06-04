"""PyQt6 UI for the AMB assembler simulator."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import textwrap
import traceback
import faulthandler
from dataclasses import dataclass
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

try:
    from PyQt6 import QtWebEngineWidgets
except Exception:  # pragma: no cover - optional runtime dependency fallback
    QtWebEngineWidgets = None

if __package__ in (None, ""):
    pkg_root = Path(__file__).resolve().parents[1]
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
    from assembler.assembler import AsmError, assemble, parse_number
    from assembler.cpu import CPU
    from assembler.resources import bundled_oss_root, docs_index_path, resource_path, rtl_run_root
    from assembler.isa import (
        ADDR_MASK,
        GEN_OPCODES,
        IMM_OPCODES,
        JUMP_OPCODES,
        MEM_OPCODES,
        REG_NAMES,
        RR_OPCODES,
        WORD_MASK,
    )
else:
    from .assembler import AsmError, assemble, parse_number
    from .cpu import CPU
    from .resources import bundled_oss_root, docs_index_path, resource_path, rtl_run_root
    from .isa import (
        ADDR_MASK,
        GEN_OPCODES,
        IMM_OPCODES,
        JUMP_OPCODES,
        MEM_OPCODES,
        REG_NAMES,
        RR_OPCODES,
        WORD_MASK,
    )

from rtl.testbench import run_rtl_sim as rtl_runner

@dataclass(frozen=True)
class SampleDefinition:
    name: str
    data_hex_path: Path
    mem_view_start: int = 0
    source_text: str | None = None
    source_path: Path | None = None
    rtl_check_result: str = "0"
    rtl_expected: str = "25"
    rtl_result_addr: str = "0000200"
    rtl_data_source: str = "Sample data image"

    def source(self) -> str:
        if self.source_text is not None:
            return textwrap.dedent(self.source_text).strip() + "\n"
        if self.source_path is not None:
            return self.source_path.read_text(encoding="utf-8").strip() + "\n"
        raise ValueError(f"Sample {self.name!r} is missing assembly source.")


EMPTY_DATA_HEX = resource_path("src", "rtl", "testbench", "empty_data.hex")
ARRAY_SUM_SOURCE = resource_path("src", "rtl", "testbench", "array_sum.s")
ARRAY_SUM_DATA_HEX = resource_path("src", "rtl", "testbench", "array_sum_data.hex")

SAMPLE_DEFINITIONS: list[SampleDefinition] = [
    SampleDefinition(
        name="Counter Loop",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Count down from 5 to 0 and halt.
        LIL 5
        MOV R0, IMR
        LIL 1
        MOV R1, IMR

        loop:
        SUB R0, R1
        MOV CMPA, R0
        MOV CMPB, R1
        JPBLW done
        JMP loop

        done:
        HLT
        """,
    ),
    SampleDefinition(
        name="Shift + Store",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Build a value, shift it, and store to memory.
        LIL 10
        MOV R0, IMR
        LIL 2
        MOV R1, IMR
        LIL 32
        MOV R3, IMR
        SHL R0, R1
        STOR R0, R3
        LOAD R2, R3
        HLT
        """,
    ),
    SampleDefinition(
        name="Bitwise Demo",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Basic boolean ops.
        LIL 15
        MOV R0, IMR
        LIL 9
        MOV R1, IMR
        AND R0, R1
        XOR R1, R0
        OR R0, R1
        HLT
        """,
    ),
    SampleDefinition(
        name="Addition Chain",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Build R0 = 1 + 2 + 3.
        LIL 1
        MOV R0, IMR
        LIL 2
        MOV R1, IMR
        LIL 3
        MOV R2, IMR
        ADD R0, R1
        ADD R0, R2
        HLT
        """,
    ),
    SampleDefinition(
        name="Shift Register",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Demonstrate register-controlled left/right shifts.
        LIL 12
        MOV R0, IMR
        LIL 1
        MOV R2, IMR
        MOV R1, R0
        SHL R1, R2
        SHR R1, R2
        SAR R1, R2
        HLT
        """,
    ),
    SampleDefinition(
        name="Loop Until Zero",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Repeatedly decrement R0 until it drops below 1.
        LIL 6
        MOV R0, IMR
        LIL 1
        MOV R1, IMR

        check:
        MOV CMPA, R0
        MOV CMPB, R1
        JPBLW done
        SUB R0, R1
        JMP check

        done:
        HLT
        """,
    ),
    SampleDefinition(
        name="Store 16-bit Value",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Compose a 16-bit literal into IMR, then copy it to R0.
        LIL 0x34
        LIH 0x12
        MOV R0, IMR
        HLT
        """,
    ),
    SampleDefinition(
        name="Store a 28-bit Immediate",
        data_hex_path=EMPTY_DATA_HEX,
        source_text="""\
        // Store a full 28-bit number in R0 = 0xEABCDFE
        LIL 0xFE
        LIH 0xCD
        LILL 0xAB
        LIHH 0x0E
        MOV R0, IMR
        HLT
        """,
    ),
    SampleDefinition(
        name="Array Sum Benchmark",
        source_path=ARRAY_SUM_SOURCE,
        data_hex_path=ARRAY_SUM_DATA_HEX,
        mem_view_start=0x0100,
        rtl_check_result="1",
        rtl_expected="25",
        rtl_result_addr="0000200",
        rtl_data_source="Array Sum Benchmark data",
    ),
]

SAMPLE_DEFINITIONS_BY_NAME = {
    sample.name: sample for sample in SAMPLE_DEFINITIONS
}


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setObjectName("lineNumberArea")

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        self.editor.lineNumberAreaPaintEvent(event)


class LintHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document: QtGui.QTextDocument) -> None:
        super().__init__(document)
        self._error_spans: dict[int, tuple[int, int]] = {}
        self._comment_markers = ("//", ";", "#")
        self._mnemonics = {
            *RR_OPCODES.keys(),
            *GEN_OPCODES.keys(),
            *IMM_OPCODES.keys(),
            *MEM_OPCODES.keys(),
            *JUMP_OPCODES.keys(),
        }
        self._comment_format = QtGui.QTextCharFormat()
        self._comment_format.setForeground(QtGui.QColor("#ffffff"))
        self._mnemonic_format = QtGui.QTextCharFormat()
        self._mnemonic_format.setForeground(QtGui.QColor("#4dff8a"))
        self._mnemonic_format.setFontWeight(QtGui.QFont.Weight.DemiBold)
        self._error_format = QtGui.QTextCharFormat()
        self._error_format.setUnderlineStyle(
            QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline
        )
        self._error_format.setUnderlineColor(QtGui.QColor("#ff5a70"))

    def set_error_spans(self, error_spans: dict[int, tuple[int, int]]) -> None:
        self._error_spans = error_spans
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        comment_start: int | None = None
        for marker in self._comment_markers:
            idx = text.find(marker)
            if idx != -1 and (comment_start is None or idx < comment_start):
                comment_start = idx

        code_text = text if comment_start is None else text[:comment_start]
        if code_text.strip():
            label_prefix = r"(?:\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*)*"
            match = re.match(rf"^\s*{label_prefix}([A-Za-z_][A-Za-z0-9_]*)", code_text)
            if match:
                mnemonic = match.group(1).upper()
                if mnemonic in self._mnemonics:
                    self.setFormat(
                        match.start(1),
                        len(match.group(1)),
                        self._mnemonic_format,
                    )

        if comment_start is not None:
            self.setFormat(comment_start, len(text) - comment_start, self._comment_format)

        line_no = self.currentBlock().blockNumber() + 1
        span = self._error_spans.get(line_no)
        if span is None:
            return
        if not text:
            return
        start, length = span
        if start < 0:
            start = 0
        if length <= 0:
            length = len(text)
        max_len = max(0, len(text) - start)
        if max_len <= 0:
            return
        length = min(length, max_len)
        self.setFormat(start, length, self._error_format)


class CodeEditor(QtWidgets.QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self._completer: QtWidgets.QCompleter | None = None
        self._completion_model = QtGui.QStandardItemModel(self)
        self._completion_signature: tuple[tuple[str, str], ...] = ()
        self._lint_errors: dict[int, str] = {}
        self._lint_highlighter = LintHighlighter(self.document())
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self._apply_caret_palette()

    def _log_nonfatal(self, context: str, exc: Exception) -> None:
        print(f"[CodeEditor] {context}: {exc}")

    def _apply_caret_palette(self) -> None:
        palette = self.palette()
        green = QtGui.QColor("#00ff6a")
        dark = QtGui.QColor("#001")
        for group in (
            QtGui.QPalette.ColorGroup.Active,
            QtGui.QPalette.ColorGroup.Inactive,
        ):
            palette.setColor(group, QtGui.QPalette.ColorRole.Text, green)
            palette.setColor(group, QtGui.QPalette.ColorRole.WindowText, green)
            palette.setColor(group, QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#0b2b0b"))
            palette.setColor(group, QtGui.QPalette.ColorRole.HighlightedText, green)
        palette.setColor(
            QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor("#0a3")
        )
        palette.setColor(
            QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor("#0a3")
        )
        self.setPalette(palette)

    def lineNumberAreaWidth(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        space = 8 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, _: int) -> None:
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect: QtCore.QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QtCore.QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QtGui.QColor("#020b02"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QtGui.QColor("#00ff6a"))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    QtCore.Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlightCurrentLine(self) -> None:
        if self.isReadOnly():
            self.setExtraSelections([])
            return
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.format.setBackground(QtGui.QColor("#071507"))
        selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def set_completion_words(self, entries: dict[str, str] | list[str]) -> None:
        try:
            if isinstance(entries, dict):
                normalized_entries = {
                    str(token): str(kind)
                    for token, kind in entries.items()
                    if str(token).strip()
                }
            else:
                normalized_entries = {
                    str(token): "SYMBOL" for token in entries if str(token).strip()
                }

            signature = tuple(
                sorted(
                    ((token, kind) for token, kind in normalized_entries.items()),
                    key=lambda pair: pair[0].upper(),
                )
            )
            if signature == self._completion_signature and self._completer is not None:
                return

            if self._completer is not None and self._completer.popup().isVisible():
                self._completer.popup().hide()

            self._completion_signature = signature
            self._completion_model.clear()
            self._completion_model.setHorizontalHeaderLabels(["Token", "Type"])
            for token, kind in signature:
                token_item = QtGui.QStandardItem(token)
                type_item = QtGui.QStandardItem(kind)
                token_item.setEditable(False)
                type_item.setEditable(False)
                type_item.setTextAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                self._completion_model.appendRow([token_item, type_item])

            if self._completer is None:
                self._completer = QtWidgets.QCompleter(self._completion_model, self)
                self._completer.setWidget(self)
                self._completer.setCompletionColumn(0)
                self._completer.setCompletionRole(QtCore.Qt.ItemDataRole.DisplayRole)
                self._completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
                self._completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
                self._completer.setFilterMode(QtCore.Qt.MatchFlag.MatchStartsWith)
                self._completer.setMaxVisibleItems(24)
                # Explicit QString overload avoids QModelIndex payload mismatches.
                self._completer.activated[str].connect(self._insert_completion)

                popup = QtWidgets.QTreeView(self)
                popup.setObjectName("completionPopup")
                popup.setRootIsDecorated(False)
                popup.setItemsExpandable(False)
                popup.setAllColumnsShowFocus(True)
                popup.setUniformRowHeights(True)
                popup.setAlternatingRowColors(False)
                popup.setSortingEnabled(False)
                popup.setIndentation(0)
                popup.setHorizontalScrollBarPolicy(
                    QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                popup.setVerticalScrollMode(
                    QtWidgets.QAbstractItemView.ScrollMode.ScrollPerItem
                )
                popup.setMinimumWidth(220)
                popup_font = QtGui.QFont(self.font())
                popup_font.setPointSizeF(max(8.5, popup_font.pointSizeF() - 0.5))
                popup.setFont(popup_font)
                popup.setHeaderHidden(True)
                popup.header().setStretchLastSection(False)
                popup.header().setSectionResizeMode(
                    0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
                )
                popup.header().setSectionResizeMode(
                    1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
                )
                # Popup styling is set directly here because completer popups can
                # be top-level and may not always inherit the main-window stylesheet.
                popup.setStyleSheet(
                    """
                    QTreeView {
                        background: rgba(2, 2, 2, 242);
                        color: #8dffd0;
                        border: 2px solid #18d77f;
                        border-radius: 0px;
                        outline: none;
                    }
                    QTreeView::item {
                        padding: 1px 6px;
                        border: none;
                    }
                    QTreeView::item:selected {
                        background: rgba(10, 56, 30, 220);
                        color: #e9fff5;
                    }
                    """
                )
                self._completer.setPopup(popup)
        except Exception as exc:
            self._completion_signature = ()
            self._log_nonfatal("set_completion_words", exc)

    def set_lint_errors(self, errors: dict[int, str], spans: dict[int, tuple[int, int]] | None = None) -> None:
        try:
            self._lint_errors = errors
            self._lint_highlighter.set_error_spans(spans or {})
        except Exception as exc:
            self._log_nonfatal("set_lint_errors", exc)

    def _completion_prefix(self) -> str:
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def _show_completion_popup(self, force: bool = False) -> None:
        try:
            if self._completer is None:
                return
            prefix = "" if force else self._completion_prefix()
            if not force and len(prefix) < 1:
                self._completer.popup().hide()
                return

            self._completer.setCompletionPrefix(prefix)
            if self._completer.completionCount() == 0:
                self._completer.popup().hide()
                return

            popup = self._completer.popup()
            completion_model = self._completer.completionModel()
            if completion_model is None:
                popup.hide()
                return

            popup.resizeColumnToContents(0)
            popup.resizeColumnToContents(1)

            top_index = completion_model.index(0, 0)
            if top_index.isValid():
                popup.setCurrentIndex(top_index)

            row_count = max(1, self._completer.completionCount())
            row_height = popup.sizeHintForRow(0)
            if row_height <= 0:
                row_height = popup.fontMetrics().height() + 6
            screen = QtGui.QGuiApplication.screenAt(self.mapToGlobal(self.cursorRect().bottomRight()))
            if screen is None:
                screen = QtGui.QGuiApplication.primaryScreen()
            available_height = 500
            available_width = 900
            if screen is not None:
                available = screen.availableGeometry()
                available_height = max(220, int(available.height() * 0.45))
                available_width = max(360, int(available.width() * 0.52))
            header_height = 0
            max_rows_by_screen = max(8, (available_height - header_height - 20) // row_height)
            visible_rows = min(max_rows_by_screen, row_count)
            self._completer.setMaxVisibleItems(visible_rows)

            cursor_rect = self.cursorRect()
            font_metrics = popup.fontMetrics()
            max_token_width = 0
            max_kind_width = 0
            for row in range(row_count):
                token_text = str(completion_model.index(row, 0).data() or "")
                kind_text = str(completion_model.index(row, 1).data() or "")
                max_token_width = max(max_token_width, font_metrics.horizontalAdvance(token_text))
                max_kind_width = max(max_kind_width, font_metrics.horizontalAdvance(kind_text))
            side_padding = 22
            inter_column_gap = 20
            popup_width = (
                max_token_width
                + max_kind_width
                + (2 * side_padding)
                + inter_column_gap
                + (popup.frameWidth() * 2)
            )
            if row_count > visible_rows:
                popup_width += popup.style().pixelMetric(
                    QtWidgets.QStyle.PixelMetric.PM_ScrollBarExtent
                ) + 4
            popup_width = min(max(260, popup_width), available_width)
            cursor_rect.setWidth(popup_width)
            self._completer.complete(cursor_rect)
        except Exception as exc:
            self._log_nonfatal("show_completion_popup", exc)

    def _accept_current_completion(self) -> bool:
        if self._completer is None:
            return False
        popup = self._completer.popup()
        index = popup.currentIndex()
        if not index.isValid():
            model = popup.model()
            if model is None:
                return False
            index = model.index(0, 0)
            if not index.isValid():
                return False
        self._insert_completion(index)
        popup.hide()
        return True

    def _insert_completion(self, completion: object) -> None:
        try:
            if self._completer is None:
                return
            if (
                hasattr(completion, "row")
                and hasattr(completion, "column")
                and hasattr(completion, "sibling")
                and hasattr(completion, "data")
            ):
                # QModelIndex payload from popup: always read token from column 0.
                completion_text = str(completion.sibling(completion.row(), 0).data() or "")
            elif hasattr(completion, "data"):
                completion_text = str(completion.data() or "")
            else:
                completion_text = str(completion)
            if not completion_text:
                return
            prefix = self._completer.completionPrefix()
            cursor = self.textCursor()
            if prefix:
                cursor.movePosition(
                    QtGui.QTextCursor.MoveOperation.Left,
                    QtGui.QTextCursor.MoveMode.KeepAnchor,
                    len(prefix),
                )
            cursor.insertText(completion_text)
            self.setTextCursor(cursor)
        except Exception as exc:
            self._log_nonfatal("insert_completion", exc)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        try:
            if self._completer is not None and self._completer.popup().isVisible():
                if event.key() in (
                    QtCore.Qt.Key.Key_Return,
                    QtCore.Qt.Key.Key_Enter,
                    QtCore.Qt.Key.Key_Tab,
                ):
                    self._accept_current_completion()
                    return
                if event.key() in (QtCore.Qt.Key.Key_Backtab, QtCore.Qt.Key.Key_Escape):
                    self._completer.popup().hide()
                    return

            ctrl_space = (
                event.key() == QtCore.Qt.Key.Key_Space
                and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
            )
            if ctrl_space:
                self._show_completion_popup(force=True)
                return

            super().keyPressEvent(event)

            if self._completer is None:
                return

            typed = event.text()
            if typed and (typed[-1].isalnum() or typed[-1] == "_"):
                self._show_completion_popup(force=False)
                return
            if event.key() == QtCore.Qt.Key.Key_Backspace:
                self._show_completion_popup(force=False)
                return
            if self._completer.popup().isVisible():
                self._completer.popup().hide()
        except Exception as exc:
            self._log_nonfatal("keyPressEvent", exc)
            super().keyPressEvent(event)

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        try:
            if self._completer is not None:
                self._completer.setWidget(self)
        except Exception as exc:
            self._log_nonfatal("focusInEvent", exc)
        super().focusInEvent(event)


class TitleBar(QtWidgets.QWidget):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        *,
        title: str | None = None,
        button_labels: tuple[str, str, str] = ("MIN", "MAX", "X"),
        button_widths: tuple[int, int, int] = (40, 40, 30),
        height: int = 34,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAutoFillBackground(True)
        self.setFixedHeight(height)
        self._drag_pos: QtCore.QPoint | None = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(6)

        self.title_label = QtWidgets.QLabel(title or parent.windowTitle())
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.min_btn = QtWidgets.QPushButton(button_labels[0])
        self.min_btn.setObjectName("titleButton")
        self.max_btn = QtWidgets.QPushButton(button_labels[1])
        self.max_btn.setObjectName("titleButton")
        self.close_btn = QtWidgets.QPushButton(button_labels[2])
        self.close_btn.setObjectName("titleClose")

        for btn, min_w in zip((self.min_btn, self.max_btn, self.close_btn), button_widths):
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(min_w)
            btn.setFixedHeight(22)

        self.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self.max_btn.clicked.connect(self._toggle_max_restore)
        self.close_btn.clicked.connect(lambda: self.window().close())

        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def _toggle_max_restore(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            )
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if (
            self._drag_pos is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._toggle_max_restore()
        super().mouseDoubleClickEvent(event)


class AssemblerWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AMB Assembler Simulator")
        self.setWindowFlags(
            self.windowFlags() | QtCore.Qt.WindowType.FramelessWindowHint
        )
        self.resize(1200, 700)
        self.setMinimumSize(900, 540)
        self.setMouseTracking(True)
        self._resize_margin = 6
        self._resizing = False
        self._resize_edge: str | None = None
        self._resize_start_pos = QtCore.QPoint()
        self._resize_start_geom = QtCore.QRect()

        self.cpu = CPU()
        self.program = None
        self.addr_to_line = {}
        self.settings = QtCore.QSettings("AMBProcessor", "AMBAssembler")
        self.current_file: str | None = None
        self.current_sample: SampleDefinition | None = None
        self.last_rtl_result: dict[str, object] | None = None
        self.html_windows: dict[Path, QtWidgets.QMainWindow] = {}
        self.rtl_data_hex_override: Path | None = None
        self.waveform_viewer = str(self.settings.value("rtl/waveform_viewer", "surfer"))
        if self.waveform_viewer not in {"surfer", "gtkwave"}:
            self.waveform_viewer = "surfer"
        self._last_reg_changes: set[int] = set()
        self._last_mem_changes: set[int] = set()
        self._highlight_bg = QtGui.QBrush(QtGui.QColor("#00ff6a"))
        self._highlight_fg = QtGui.QBrush(QtGui.QColor("#001"))
        self._default_bg = QtGui.QBrush(QtGui.QColor("#020b02"))
        self._default_fg = QtGui.QBrush(QtGui.QColor("#00ff6a"))
        self._pulse_phase = 0.0
        self._pulse_timer = QtCore.QTimer(self)
        self._pulse_timer.setInterval(120)
        self._pulse_timer.timeout.connect(self._advance_pulse)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.step)
        self._lint_timer = QtCore.QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(250)
        self._lint_timer.timeout.connect(self._lint_source)
        self._base_completion_entries: dict[str, str] = {}

        self._build_ui()
        self.update_register_view()
        self.update_memory_view()

    def _log_nonfatal(self, context: str, exc: Exception) -> None:
        print(f"[AssemblerWindow] {context}: {exc}")

    def _build_ui(self) -> None:
        self._apply_style()
        self._build_titlebar()
        self._build_toolbar()
        self._build_help_dock()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)

        self.editor = CodeEditor()
        self.editor.setTabStopDistance(4 * QtGui.QFontMetrics(self.editor.font()).horizontalAdvance(" "))
        self.editor.setPlaceholderText("Write AMB assembly here...")
        editor_panel = self._wrap_panel("Editor", self.editor)

        self.reg_table = QtWidgets.QTableWidget()
        self.reg_table.setColumnCount(2)
        self.reg_table.setHorizontalHeaderLabels(["Register", "Value"])
        self.reg_table.verticalHeader().setVisible(False)
        self.reg_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.reg_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.reg_table.horizontalHeader().setStretchLastSection(True)
        reg_panel = self._wrap_panel("Registers", self.reg_table)
        reg_panel.setMinimumWidth(300)

        mem_panel = QtWidgets.QWidget()
        mem_layout = QtWidgets.QVBoxLayout(mem_panel)
        mem_layout.setContentsMargins(0, 0, 0, 0)
        mem_layout.setSpacing(6)

        mem_header = QtWidgets.QHBoxLayout()
        self.mem_start = QtWidgets.QLineEdit("0x0000000")
        self.mem_start.setPlaceholderText("Start address (hex or dec)")
        self.mem_count = QtWidgets.QSpinBox()
        self.mem_count.setRange(1, 1024)
        self.mem_count.setValue(64)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_memory_view)
        mem_header.addWidget(QtWidgets.QLabel("Start"))
        mem_header.addWidget(self.mem_start)
        mem_header.addWidget(QtWidgets.QLabel("Rows"))
        mem_header.addWidget(self.mem_count)
        mem_header.addWidget(refresh_btn)
        mem_header.addStretch(1)

        self.mem_table = QtWidgets.QTableWidget()
        self.mem_table.setColumnCount(2)
        self.mem_table.setHorizontalHeaderLabels(["Address", "Byte"])
        self.mem_table.verticalHeader().setVisible(False)
        self.mem_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mem_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.mem_table.horizontalHeader().setStretchLastSection(True)

        mem_layout.addLayout(mem_header)
        mem_layout.addWidget(self.mem_table)

        mem_panel_wrapped = self._wrap_panel("Data Memory", mem_panel)

        splitter.addWidget(editor_panel)
        splitter.addWidget(reg_panel)
        splitter.addWidget(mem_panel_wrapped)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        central = QtWidgets.QWidget()
        central_layout = QtWidgets.QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.toolbar_scroll)
        central_layout.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QtWidgets.QStatusBar())
        self.statusBar().setSizeGripEnabled(True)
        self._install_resize_filters()

        mono = QtGui.QFont("Cascadia Mono", 10)
        if not mono.exactMatch():
            mono = QtGui.QFont("Consolas", 10)
        self.editor.setFont(mono)
        self.editor.setCursorWidth(2)
        palette = self.editor.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#00ff6a"))
        self.editor.setPalette(palette)
        self.reg_table.setFont(mono)
        self.mem_table.setFont(mono)
        self._setup_editor_assist()

    def _setup_editor_assist(self) -> None:
        entries: dict[str, str] = {}
        entries.update({mnem: "FUNCTION" for mnem in RR_OPCODES})
        entries.update({mnem: "CONTROL" for mnem in GEN_OPCODES})
        entries.update({mnem: "IMMEDIATE" for mnem in IMM_OPCODES})
        entries.update({mnem: "MEMORY" for mnem in MEM_OPCODES})
        entries.update({mnem: "JUMP" for mnem in JUMP_OPCODES})
        entries.update({name: "REGISTER" for name in REG_NAMES})
        self._base_completion_entries = entries
        self.editor.set_completion_words(self._base_completion_entries)
        self.editor.textChanged.connect(self._schedule_lint)
        self._lint_source()

    def _schedule_lint(self) -> None:
        self._lint_timer.start()

    @staticmethod
    def _strip_comment(text: str) -> str:
        earliest: int | None = None
        for marker in ("//", ";", "#"):
            idx = text.find(marker)
            if idx != -1 and (earliest is None or idx < earliest):
                earliest = idx
        if earliest is None:
            return text
        return text[:earliest]

    @staticmethod
    def _first_non_space_span(text: str) -> tuple[int, int]:
        match = re.search(r"\S+", text)
        if not match:
            return (0, 0)
        return (match.start(), match.end() - match.start())

    @staticmethod
    def _find_token_span(text: str, token: str) -> tuple[int, int]:
        if not token:
            return AssemblerWindow._first_non_space_span(text)
        match = re.search(rf"\b{re.escape(token)}\b", text, flags=re.IGNORECASE)
        if match:
            return (match.start(), match.end() - match.start())
        idx = text.find(token)
        if idx != -1:
            return (idx, len(token))
        return AssemblerWindow._first_non_space_span(text)

    @staticmethod
    def _is_register_token(token: str) -> bool:
        token_u = token.strip().upper()
        if not token_u:
            return False
        if token_u in {name.upper() for name in REG_NAMES}:
            return True
        if token_u.startswith("R") and token_u[1:].isdigit():
            idx = int(token_u[1:])
            return 0 <= idx < len(REG_NAMES)
        return False

    @staticmethod
    def _parse_operands_from_line(line: str) -> list[str]:
        return [part.strip() for part in line.split(",") if part.strip()]

    def _lint_structure(
        self, source: str
    ) -> tuple[dict[int, str], dict[int, tuple[int, int]], set[str]]:
        errors: dict[int, str] = {}
        spans: dict[int, tuple[int, int]] = {}
        label_names: set[str] = set()

        lines = source.splitlines()
        for line_no, raw in enumerate(lines, start=1):
            line = self._strip_comment(raw).rstrip()
            if not line.strip():
                continue

            working = line.strip()
            while True:
                colon = working.find(":")
                if colon < 0:
                    break
                label = working[:colon].strip()
                if not label:
                    break
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", label):
                    errors[line_no] = f"Invalid label '{label}'"
                    spans[line_no] = self._find_token_span(line, label)
                    break
                label_u = label.upper()
                if label_u in label_names:
                    errors[line_no] = f"Duplicate label '{label}'"
                    spans[line_no] = self._find_token_span(line, label)
                    break
                label_names.add(label_u)
                working = working[colon + 1 :].strip()
                if not working:
                    break
            if line_no in errors:
                continue
            if not working:
                continue

            parts = working.split(None, 1)
            mnem = parts[0].upper()
            op_text = parts[1] if len(parts) > 1 else ""
            operands = self._parse_operands_from_line(op_text)

            if mnem in RR_OPCODES:
                unary_rr = {"NOT"}
                expected = 1 if mnem in unary_rr else 2
                if len(operands) != expected:
                    errors[line_no] = f"{mnem} expects {expected} register{'s' if expected == 2 else ''}"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                bad_reg = next((op for op in operands if not self._is_register_token(op)), None)
                if bad_reg:
                    errors[line_no] = f"Unknown register '{bad_reg}'"
                    spans[line_no] = self._find_token_span(line, bad_reg)
                    continue
                continue

            if mnem in GEN_OPCODES:
                if operands:
                    errors[line_no] = f"{mnem} expects no operands"
                    spans[line_no] = self._find_token_span(line, operands[0])
                continue

            if mnem in IMM_OPCODES:
                if len(operands) != 1:
                    errors[line_no] = f"{mnem} expects an imm8 operand"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                imm = operands[0]
                try:
                    imm_val = parse_number(imm)
                except Exception:
                    errors[line_no] = f"Invalid immediate '{imm}'"
                    spans[line_no] = self._find_token_span(line, imm)
                    continue
                if not (-128 <= imm_val <= 255):
                    errors[line_no] = f"Immediate out of range for {mnem}: {imm_val}"
                    spans[line_no] = self._find_token_span(line, imm)
                continue

            if mnem in MEM_OPCODES:
                if len(operands) != 2:
                    errors[line_no] = f"{mnem} expects 2 registers"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                bad_reg = next((op for op in operands if not self._is_register_token(op)), None)
                if bad_reg:
                    errors[line_no] = f"Unknown register '{bad_reg}'"
                    spans[line_no] = self._find_token_span(line, bad_reg)
                    continue
                continue

            if mnem in JUMP_OPCODES:
                if len(operands) != 1:
                    errors[line_no] = f"{mnem} expects an immediate or label"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                jump_arg = operands[0]
                try:
                    imm_val = parse_number(jump_arg)
                    if not (-128 <= imm_val <= 127):
                        errors[line_no] = f"Jump offset out of range: {imm_val}"
                        spans[line_no] = self._find_token_span(line, jump_arg)
                except Exception:
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", jump_arg):
                        errors[line_no] = f"Invalid immediate '{jump_arg}'"
                        spans[line_no] = self._find_token_span(line, jump_arg)
                continue

            errors[line_no] = f"Unknown instruction '{mnem}'"
            spans[line_no] = self._find_token_span(line, mnem)

        return errors, spans, label_names

    def _infer_span_from_asm_error(self, source: str, line_no: int, message: str) -> tuple[int, int]:
        lines = source.splitlines()
        if line_no <= 0 or line_no > len(lines):
            return (0, 0)
        line = lines[line_no - 1]
        quoted = re.search(r"'([^']+)'", message)
        if quoted:
            return self._find_token_span(line, quoted.group(1))
        return self._first_non_space_span(line)

    def _lint_source(self) -> None:
        source = self.editor.toPlainText()
        if not source.strip():
            self.editor.set_lint_errors({}, {})
            return

        try:
            errors, spans, labels = self._lint_structure(source)
            completion_entries = dict(self._base_completion_entries)
            for label in labels:
                if label not in completion_entries:
                    completion_entries[label] = "LABEL"
            self.editor.set_completion_words(completion_entries)
            if errors:
                self.editor.set_lint_errors(errors, spans)
                return

            assemble(source)
            self.editor.set_lint_errors({}, {})
        except AsmError as exc:
            line_no = exc.line_no if exc.line_no is not None else 1
            span = self._infer_span_from_asm_error(source, line_no, str(exc))
            self.editor.set_lint_errors({line_no: str(exc)}, {line_no: span})
        except Exception as exc:
            self._log_nonfatal("lint_source", exc)
            self.editor.set_lint_errors({}, {})

    def _build_toolbar(self) -> None:
        self.toolbar_scroll = QtWidgets.QScrollArea(self)
        self.toolbar_scroll.setObjectName("mainToolbarScroll")
        self.toolbar_scroll.setWidgetResizable(False)
        self.toolbar_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.toolbar_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.toolbar_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.toolbar_scroll.viewport().installEventFilter(self)

        strip = QtWidgets.QWidget()
        strip.setObjectName("mainToolbarStrip")
        strip.installEventFilter(self)
        layout = QtWidgets.QHBoxLayout(strip)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)

        def add_button(label: str, slot) -> QtWidgets.QPushButton:
            button = QtWidgets.QPushButton(label, strip)
            button.setObjectName("toolbarButton")
            button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
            button.installEventFilter(self)
            button.clicked.connect(slot)
            layout.addWidget(button)
            return button

        def add_separator() -> None:
            separator = QtWidgets.QFrame(strip)
            separator.setObjectName("toolbarSeparator")
            separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
            separator.setFixedHeight(26)
            separator.installEventFilter(self)
            layout.addWidget(separator)

        add_button("New", self.new_file)
        add_button("Open", self.open_file)
        add_button("Save", self.save_file)
        add_button("Save As", self.save_file_as)

        add_separator()

        self.sample_codes_combo = QtWidgets.QComboBox(self)
        self.sample_codes_combo.setObjectName("sampleCodesCombo")
        self.sample_codes_combo.setMinimumWidth(170)
        self.sample_codes_combo.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.sample_codes_combo.setMaxVisibleItems(12)
        self.sample_codes_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.sample_codes_combo.installEventFilter(self)
        self.sample_codes_combo.addItem(" Sample Code")
        for sample in SAMPLE_DEFINITIONS:
            self.sample_codes_combo.addItem(sample.name)
        self.sample_codes_combo.activated.connect(self.load_sample_code)
        layout.addWidget(self.sample_codes_combo)
        add_separator()

        add_button("Assemble", self.assemble_source)
        add_button("Step", self.step)
        add_button("Run", self.run)
        add_button("Stop", self.stop)
        add_button("Reset", self.reset_cpu)
        add_separator()
        add_button("CPU Blueprint", self.open_cpu_blueprint)
        add_button("Run RTL Sim", self.run_rtl_sim)
        rtl_options_btn = add_button("RTL Options", lambda _checked=False: self.show_rtl_options_menu(rtl_options_btn))
        add_button("Open Waveform", self.open_latest_waveform)
        add_separator()
        add_button("Authors", self.show_authors)
        add_button("Help", self.show_help)
        layout.addStretch(1)

        strip.adjustSize()
        strip.setMinimumWidth(strip.sizeHint().width())
        self.toolbar_scroll.setWidget(strip)
        self.toolbar_scroll.setFixedHeight(strip.sizeHint().height() + 18)

    def _build_titlebar(self) -> None:
        self.title_bar = TitleBar(self)
        self.setMenuWidget(self.title_bar)

    def _build_help_dock(self) -> None:
        self.help_dock = QtWidgets.QDockWidget("AMB Assembly Help", self)
        self.help_dock.setObjectName("helpDock")
        self.help_dock.setMinimumWidth(380)
        self.help_dock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.help_dock.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
        )

        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QtWidgets.QLabel("AMB Instruction Set Reference")
        title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(title)

        browser = QtWidgets.QTextBrowser()
        browser.setObjectName("helpBrowser")
        browser.setOpenExternalLinks(False)
        browser.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        browser.setWordWrapMode(QtGui.QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        browser.document().setDocumentMargin(8)
        browser.setHtml(self._build_help_html())
        layout.addWidget(browser, 1)

        self.help_dock.setWidget(panel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.help_dock)
        self.help_dock.hide()

    def _build_help_html(self) -> str:
        def build_table(rows: list[tuple[str, str, str]]) -> str:
            body = "\n".join(
                "<tr>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px; white-space: normal; overflow-wrap: anywhere;'>{mnem}</td>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px; white-space: normal; overflow-wrap: anywhere;'><code style='white-space: normal; overflow-wrap: anywhere;'>{syntax}</code></td>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px; white-space: normal; overflow-wrap: anywhere;'>{note}</td>"
                "</tr>"
                for mnem, syntax, note in rows
            )
            return (
                "<table style='width: 100%; table-layout: fixed; border-collapse: collapse; border: 1px solid #0a3; margin: 4px 0 10px 0;'>"
                "<colgroup>"
                "<col style='width: 16%;'>"
                "<col style='width: 26%;'>"
                "<col style='width: 58%;'>"
                "</colgroup>"
                "<tr>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Mnemonic</th>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Syntax</th>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Notes</th>"
                "</tr>"
                f"{body}</table>"
            )

        rr_syntax = {mnem: f"{mnem} Ra, Rb" for mnem in RR_OPCODES}
        rr_syntax.update(
            {
                "NOT": "NOT Ra",
            }
        )
        rr_notes = {
            "NOT": "Ra = ~Ra",
            "OR": "Ra = Ra | Rb",
            "AND": "Ra = Ra & Rb",
            "XOR": "Ra = Ra ^ Rb",
            "SHL": "Ra = Ra << Rb",
            "SHR": "Ra = Ra >> Rb",
            "SAR": "Ra = arithmetic_shift_right(Ra, Rb)",
            "ADD": "Ra = Ra + Rb",
            "SUB": "Ra = Ra - Rb",
            "MOV": "Ra = Rb",
        }
        rr_rows = [(mnem, rr_syntax[mnem], rr_notes.get(mnem, "")) for mnem in RR_OPCODES]

        gen_notes = {
            "HLT": "Halts the CPU",
            "NOP": "No operation",
        }
        gen_rows = [(mnem, mnem, gen_notes.get(mnem, "No operands")) for mnem in GEN_OPCODES]

        imm_syntax = {
            "LIL": "LIL imm8",
            "LIH": "LIH imm8",
            "LILL": "LILL imm8",
            "LIHH": "LIHH imm8",
        }
        imm_notes = {
            "LIL": "Set IMR[7:0] to imm8",
            "LIH": "Set IMR[15:8] to imm8",
            "LILL": "Set IMR[23:16] to imm8",
            "LIHH": "Set IMR[27:24] to imm8[3:0]",
        }
        imm_rows = [
            (mnem, imm_syntax.get(mnem, mnem), imm_notes.get(mnem, ""))
            for mnem in IMM_OPCODES
        ]

        mem_syntax = {mnem: f"{mnem} Ra, Rb" for mnem in MEM_OPCODES}
        mem_notes = {
            "LOAD": "Ra = DMEM[Rb + MEMOFF], byte address, 28-bit little-endian word",
            "STOR": "DMEM[Rb + MEMOFF] = Ra, byte address, 28-bit little-endian word",
        }
        mem_rows = [
            (mnem, mem_syntax.get(mnem, mnem), mem_notes.get(mnem, ""))
            for mnem in MEM_OPCODES
        ]

        jump_syntax = {mnem: f"{mnem} imm8" for mnem in JUMP_OPCODES}
        jump_notes = {
            "JMP": "IC += signed imm8 word offset",
            "JMPL": "IC += signed (imm8 + JMPOFF) word offset",
            "JPEQ": "If CMPA == CMPB, do JMPL",
            "JPBLW": "If CMPA < CMPB (unsigned for now), do JMPL",
        }
        jump_rows = [
            (mnem, jump_syntax.get(mnem, mnem), jump_notes.get(mnem, ""))
            for mnem in JUMP_OPCODES
        ]

        toolbar_rows = [
            ("Assemble", "Current editor", "Parse the source and load the simulator instruction memory."),
            ("Step", "One instruction", "Execute one simulator instruction and highlight changed state."),
            ("Run", "Timed stepping", "Run the Python simulator until Stop or HLT."),
            ("Stop", "Timed stepping", "Stop the Python simulator timer without resetting state."),
            ("Reset", "Simulator state", "Reset registers and reload the assembled program."),
            ("CPU Blueprint", "Docs and latest RTL run", "Open architecture docs, diagrams, authors, and the latest RTL run summary."),
            ("Run RTL Sim", "Verilog testbench", "Export program.hex, run the RTL bench, and generate report/wave files."),
            ("RTL Options", "Data image + viewer", "Choose/clear an optional data.hex file and select Surfer or GTKWave."),
            ("Open Waveform", "Latest VCD/FST", "Open the latest RTL waveform with the selected viewer. Surfer is the default; GTKWave can use the curated .gtkw layout."),
            ("Sample Code", "Samples", "Load a predefined .ambasm example; the array-sum benchmark selects its matching RTL data image."),
        ]

        reg_names = ", ".join(REG_NAMES)

        return textwrap.dedent(
            f"""
        <div style="font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px; line-height: 1.35;">
        <h3>AMB ISA v1 Quick Reference</h3>
        <ul>
            <li>Instruction width: 15 bits (stored in 2 bytes, 1 unused bit)</li>
            <li>Word size: 28 bits</li>
            <li>Address width: 28 bits (byte-addressable)</li>
            <li>PC/IC increments by 2 after each instruction fetch</li>
            <li>Assembly syntax is <code>OP Ra, Rb</code>: <code>Ra</code> is destination and <code>Rb</code> is source.</li>
            <li>RTL simulation uses split instruction memory (<code>imem</code>) and byte-addressed data memory (<code>dmem</code>).</li>
        </ul>
        <h4>Registers</h4>
        <p>General: R0-R7.</p>
        <p>Special: IC, SP, LC, IMR, JMPOFF, MEMOFF, CMPA, CMPB. <code>IMR</code> is the multi-step immediate assembly register.</p>
        <p>Full register list (case-insensitive): {reg_names}</p>
        <h4>Encoding Forms</h4>
        <div style="white-space: pre-wrap; border: 1px solid #0a3; background: #021002; padding: 6px;">
RR/MEM: opcode7 | Rb | Ra
GEN:    opcode7 only
IMM:    opcode7 | imm8
JMP:    opcode7 | imm8
        </div>
        <h4>Register-to-Register (RR)</h4>
        <p>Format: <code>MNEMONIC Ra, Rb</code>. <code>Ra</code> is destination, <code>Rb</code> is source. <code>NOT</code> is unary.</p>
        {build_table(rr_rows)}
        <h4>General (GEN)</h4>
        {build_table(gen_rows)}
        <h4>Immediate (IMM)</h4>
        <p><code>imm8</code> accepts -128..255 and is encoded as 8 bits. Immediate loads write <code>IMR</code>; labels are not allowed.</p>
        {build_table(imm_rows)}
        <h4>Memory (MEM)</h4>
        <p>Instruction memory and data memory are split. Program loading writes instruction memory; <code>LOAD</code> and <code>STOR</code> use byte-addressed data memory at <code>Rb + MEMOFF</code>. Store data comes from <code>Ra</code>.</p>
        {build_table(mem_rows)}
        <h4>Jump (JMP)</h4>
        <p><code>imm8</code> accepts -128..127 (word offset). Labels are allowed and resolve to a PC-relative offset; labels must be 2-byte aligned.</p>
        <p><code>JPEQ</code> and <code>JPBLW</code> compare only <code>CMPA</code> and <code>CMPB</code>. <code>JPBLW</code> is modeled unsigned until the RTL signedness TODO is resolved.</p>
        {build_table(jump_rows)}
        <h4>Toolbar Buttons</h4>
        <p>The top strip scrolls horizontally when the window is narrow. Use the sample dropdown to load ready-to-run examples; the array-sum benchmark also selects the matching RTL data image. Arbitrary RTL runs are inspection traces, not pass/fail tests. Use <code>RTL Options</code> to choose a custom <code>data.hex</code> file and to select the waveform viewer.</p>
        {build_table(toolbar_rows)}
        <h4>Labels & Comments</h4>
        <div style="white-space: pre-wrap; border: 1px solid #0a3; background: #021002; padding: 6px;">
label: ADD R0, R1
       JMP label

Comments: // ; #
        </div>
        </div>
        """
        ).strip()

    def _wrap_panel(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("panelBox")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        label = QtWidgets.QLabel(title)
        label.setObjectName("panelTitle")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)
        layout.addWidget(widget)
        return panel

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #030d04; color: #8dffd1; border: 1px solid #16a865; }
            QWidget { color: #79ffc4; background: transparent; }
            QWidget#panelBox {
                background: #031405;
                border: 2px solid #38f3a5;
            }
            QLabel#panelTitle {
                color: #e4fff4;
                font-weight: 700;
                padding: 0 0 4px 0;
                border-bottom: 1px solid #2fe596;
            }
            QPlainTextEdit, QTableWidget, QLineEdit, QComboBox, QTreeView, QTextBrowser {
                background: #031305; color: #90ffd0; border: 1px solid #15a967;
            }
            QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QTextBrowser:focus {
                border: 1px solid #4af6ad;
            }
            QPlainTextEdit {
                selection-background-color: #15522d;
                selection-color: #e2fff3;
            }
            QTableWidget { gridline-color: #15a967; }
            QTableWidget::item { padding: 1px 4px; }
            QTableWidget::item:selected { background: #166335; color: #edfff8; }
            QTableCornerButton::section { background: #0d4329; border: 1px solid #15a967; }
            QHeaderView::section {
                background: #0f4a2d; color: #d5ffec; border: 1px solid #15a967; padding: 5px 6px;
            }

            QLabel { color: #b2ffe0; font-weight: 600; padding: 1px 0; }

            QPushButton {
                background: #073016; color: #95ffd4; border: 1px solid #1fc97c; padding: 4px 10px; margin: 0;
            }
            QPushButton:hover { background: #0f4b2a; border: 1px solid #35e796; }
            QPushButton:pressed {
                background: #1a7442;
                color: #f3fffa;
                border: 1px solid #63ffc2;
                padding-top: 5px;
                padding-left: 11px;
                padding-bottom: 3px;
                padding-right: 9px;
            }
            QPushButton:disabled {
                color: #3f8f67; border-color: #2a6d4a; background: #062010;
            }

            QScrollArea#mainToolbarScroll {
                background: #062311;
                border: 1px solid #39f5a7;
                margin: 5px 8px 3px 8px;
            }
            QScrollArea#mainToolbarScroll QWidget#qt_scrollarea_viewport {
                background: #062311;
            }
            QWidget#mainToolbarStrip {
                background: #062311;
            }
            QPushButton#toolbarButton {
                min-height: 26px;
                padding: 4px 12px;
                background: #052312;
                color: #defff0;
                border: 1px solid #19d17d;
            }
            QPushButton#toolbarButton:hover {
                background: #08311b;
                border: 1px solid #2ee792;
            }
            QPushButton#toolbarButton:pressed {
                background: #0f5732;
                color: #f2fff9;
                border: 1px solid #54f5ab;
                padding-top: 5px;
                padding-left: 13px;
                padding-bottom: 3px;
                padding-right: 11px;
            }
            QFrame#toolbarSeparator { background: #2ad88b; width: 1px; margin: 2px 8px; }
            QLabel#sampleCodesLabel {
                color: #d6ffed;
                font-weight: 700;
                padding: 0 6px 0 2px;
            }
            QComboBox#sampleCodesCombo {
                min-height: 26px;
                background: #052312;
                color: #defff0;
                border: 1px solid #19d17d;
                min-width: 170px;
            }
            QComboBox#sampleCodesCombo:hover {
                border: 1px solid #2ee792;
                background: #08311b;
            }
            QComboBox#sampleCodesCombo:focus {
                border: 1px solid #54f5ab;
            }
            QComboBox#sampleCodesCombo QAbstractItemView {
                background: #031003;
                color: #d9ffef;
                border: 1px solid #15ca76;
                selection-background-color: #0d4a2a;
                selection-color: #effff8;
                outline: none;
            }

            QWidget#titleBar { background: #062513; border-bottom: 1px solid #1bbb71; }
            QLabel#titleLabel { color: #defff0; font-weight: 700; letter-spacing: 0.5px; }
            QPushButton#titleButton {
                background: #073317; color: #b3ffe1; border: 1px solid #1ec97b; padding: 1px 8px;
            }
            QPushButton#titleButton:hover { background: #15502e; }
            QPushButton#titleClose {
                background: #2a0f14; color: #ffbdca; border: 1px solid #8f2f40; padding: 1px 8px;
            }
            QPushButton#titleClose:hover { background: #561825; color: #ffe0e6; }

            QSplitter::handle:horizontal { background: #22cf84; width: 3px; margin: 0 1px; }
            QSplitter::handle:vertical { background: #22cf84; height: 3px; margin: 1px 0; }
            QMainWindow::separator { background: #22cf84; width: 3px; height: 3px; }

            QScrollBar:vertical, QScrollBar:horizontal {
                background: #031305; border: 1px solid #15a967; margin: 0px; width: 10px; height: 10px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #33f5a6; border-radius: 5px; min-width: 8px; min-height: 20px;
            }
            QScrollBar::add-line, QScrollBar::sub-line { background: transparent; border: none; height: 0px; width: 0px; }
            QScrollBar::add-page, QScrollBar::sub-page { background: #031305; }

            QStatusBar { background: #062311; color: #97ffd5; border-top: 1px solid #1bbb71; }
            QStatusBar::item { border: 1px solid #15a967; }
            QSizeGrip { background: #062311; border: 1px solid #15a967; }
            #lineNumberArea { background: #062311; border-right: 1px solid #15a967; }

            QLineEdit { min-height: 22px; padding: 0 6px; }
            QSpinBox {
                min-height: 22px;
                padding: 0 6px;
                background: #031305;
                color: #90ffd0;
                border: 1px solid #15a967;
                selection-background-color: #15522d;
                selection-color: #e2fff3;
            }
            QSpinBox:focus {
                border: 1px solid #4af6ad;
            }

            QMenu { background: #031305; color: #90ffd0; border: 1px solid #15a967; }
            QMenu::item:selected { background: #15522d; }
            QTreeView#completionPopup {
                background: rgba(3, 16, 3, 232);
                color: #8dffd0;
                border: 2px solid #2de493;
                border-radius: 0px;
                outline: none;
            }
            QTreeView#completionPopup::item {
                padding: 2px 6px;
                border: none;
            }
            QTreeView#completionPopup::item:selected {
                background: rgba(15, 76, 43, 220);
                color: #e9fff5;
            }
            QHeaderView#completionPopupHeader::section {
                background: rgba(7, 34, 18, 230);
                color: #9dffd9;
                border: 1px solid #1dbf73;
                border-left: none;
                border-top: none;
                padding: 2px 6px;
                font-size: 9pt;
            }
            QToolTip { background: #031305; color: #d6ffed; border: 1px solid #15a967; }
            QDialog { background: #030d04; color: #90ffd0; border: 2px solid #1bbb71; }
            QFileDialog {
                background: #020a04;
                color: #d6ffed;
                border: 2px solid #31f3a2;
            }
            QFileDialog QLabel {
                color: #d6ffed;
                font-weight: 700;
            }
            QFileDialog QLineEdit,
            QFileDialog QComboBox {
                background: #031305;
                color: #d6ffed;
                border: 1px solid #2fe596;
                min-height: 24px;
                selection-background-color: #15522d;
                selection-color: #effff8;
            }
            QFileDialog QComboBox QAbstractItemView,
            QFileDialog QTreeView,
            QFileDialog QListView {
                background: #010703;
                color: #8dffd0;
                border: 1px solid #1bbb71;
                selection-background-color: #0d4a2a;
                selection-color: #effff8;
                outline: none;
            }
            QFileDialog QHeaderView::section {
                background: #07301b;
                color: #d6ffed;
                border: 1px solid #0d8f54;
                padding: 4px 6px;
            }
            QFileDialog QPushButton,
            QFileDialog QToolButton {
                background: #06210d;
                color: #bfffe0;
                border: 1px solid #18d77f;
                padding: 4px 8px;
            }
            QFileDialog QPushButton:hover,
            QFileDialog QToolButton:hover {
                background: #0b3a20;
                color: #eafff4;
            }
            QFileDialog QPushButton:pressed,
            QFileDialog QToolButton:pressed {
                background: #10522e;
            }

            QDockWidget#helpDock { background: #030d04; color: #90ffd0; border: 1px solid #15a967; }
            QDockWidget#helpDock::title {
                background: #073317; border-bottom: 1px solid #1bbb71; color: #d6ffed; padding: 7px 8px;
            }
            QDockWidget#helpDock::close-button, QDockWidget#helpDock::float-button {
                border: 1px solid #15a967; background: #062513; width: 14px; height: 14px;
            }
            QDockWidget#helpDock::close-button:hover, QDockWidget#helpDock::float-button:hover { background: #165230; }
            QTextBrowser#helpBrowser { background: #031305; color: #90ffd0; }
            """
        )

    @staticmethod
    def _same_local_html_document(left: QtCore.QUrl, right: QtCore.QUrl) -> bool:
        left_copy = QtCore.QUrl(left)
        right_copy = QtCore.QUrl(right)
        left_copy.setFragment("")
        right_copy.setFragment("")
        return left_copy == right_copy

    @staticmethod
    def _run_html_script_after_load(view: QtWebEngineWidgets.QWebEngineView, script: str) -> None:
        def run_script(ok: bool) -> None:
            try:
                view.loadFinished.disconnect(run_script)
            except TypeError:
                pass
            if ok:
                view.page().runJavaScript(script)

        view.loadFinished.connect(run_script)

    def _open_local_html(
        self,
        path: Path,
        title: str,
        fragment: str | None = None,
        after_load_script: str | None = None,
    ) -> None:
        path = path.resolve()
        if not path.exists():
            self.statusBar().showMessage(f"Missing file: {path}", 5000)
            return
        url = QtCore.QUrl.fromLocalFile(str(path))
        if fragment:
            url.setFragment(fragment)
        if QtWebEngineWidgets is None:
            QtGui.QDesktopServices.openUrl(url)
            return

        existing = self.html_windows.get(path)
        if existing is not None:
            existing.setWindowTitle(title)
            view = existing.findChild(QtWebEngineWidgets.QWebEngineView)
            if isinstance(view, QtWebEngineWidgets.QWebEngineView):
                same_document = self._same_local_html_document(view.url(), url)
                if after_load_script and not same_document:
                    self._run_html_script_after_load(view, after_load_script)
                view.setUrl(url)
                if after_load_script and same_document:
                    QtCore.QTimer.singleShot(
                        0,
                        lambda view=view, script=after_load_script: view.page().runJavaScript(script),
                    )
            if existing.isMinimized():
                existing.setWindowState(
                    existing.windowState() & ~QtCore.Qt.WindowState.WindowMinimized
                )
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return

        window = QtWidgets.QMainWindow()
        window.setObjectName("htmlViewerWindow")
        window.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint, True)
        window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.setWindowTitle(title)
        window.setWindowIcon(self.windowIcon())
        window.resize(1200, 800)
        light_palette = window.palette()
        light_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#f6f9fb"))
        light_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#14212a"))
        light_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#ffffff"))
        light_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#14212a"))
        light_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#edf4f8"))
        light_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#14212a"))
        light_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#0b84d8"))
        light_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#ffffff"))
        window.setPalette(light_palette)
        window.setStyleSheet(
            """
            QMainWindow#htmlViewerWindow {
                background: #f6f9fb;
                color: #14212a;
                border: none;
            }
            QWidget#htmlViewerShell {
                background: #f6f9fb;
                color: #14212a;
                border: 1px solid #9fb5c4;
            }
            QWidget#htmlTitleBar {
                background: #e9edf0;
                color: #14212a;
                border-bottom: 1px solid #c4d2dc;
            }
            QLabel#htmlTitleLabel {
                color: #14212a;
                font-weight: 700;
                letter-spacing: 0.2px;
            }
            QPushButton#htmlTitleButton {
                background: #e9edf0;
                color: #14212a;
                border: 1px solid transparent;
                padding: 1px 8px;
            }
            QPushButton#htmlTitleButton:hover {
                background: #d9e7ef;
                border-color: #9fb5c4;
            }
            QPushButton#htmlTitleClose {
                background: #e9edf0;
                color: #14212a;
                border: 1px solid transparent;
                padding: 1px 8px;
            }
            QPushButton#htmlTitleClose:hover {
                background: #f2d3d8;
                border-color: #b55d6c;
                color: #601522;
            }
            QFrame#htmlGripBar {
                background: #f6f9fb;
                border: none;
            }
            QSizeGrip#htmlSizeGrip {
                background: #f6f9fb;
            }
            QMainWindow#htmlViewerWindow QToolTip {
                background: #ffffff;
                color: #14212a;
                border: 1px solid #b9cedb;
            }
            QMainWindow#htmlViewerWindow QScrollBar:vertical,
            QMainWindow#htmlViewerWindow QScrollBar:horizontal {
                background: #edf4f8;
                border: 1px solid #b9cedb;
                margin: 0px;
                width: 10px;
                height: 10px;
            }
            QMainWindow#htmlViewerWindow QScrollBar::handle:vertical,
            QMainWindow#htmlViewerWindow QScrollBar::handle:horizontal {
                background: #8fb1c5;
                border-radius: 5px;
                min-width: 8px;
                min-height: 20px;
            }
            QMainWindow#htmlViewerWindow QScrollBar::add-line,
            QMainWindow#htmlViewerWindow QScrollBar::sub-line {
                background: transparent;
                border: none;
                height: 0px;
                width: 0px;
            }
            QMainWindow#htmlViewerWindow QScrollBar::add-page,
            QMainWindow#htmlViewerWindow QScrollBar::sub-page {
                background: #edf4f8;
            }
            """
        )
        shell = QtWidgets.QWidget(window)
        shell.setObjectName("htmlViewerShell")
        shell_layout = QtWidgets.QVBoxLayout(shell)
        shell_layout.setContentsMargins(1, 1, 1, 1)
        shell_layout.setSpacing(0)

        title_bar = TitleBar(
            window,
            title=title,
            button_labels=("-", "□", "×"),
            button_widths=(30, 30, 30),
        )
        title_bar.setObjectName("htmlTitleBar")
        title_bar.title_label.setObjectName("htmlTitleLabel")
        title_bar.min_btn.setObjectName("htmlTitleButton")
        title_bar.max_btn.setObjectName("htmlTitleButton")
        title_bar.close_btn.setObjectName("htmlTitleClose")
        shell_layout.addWidget(title_bar)

        view = QtWebEngineWidgets.QWebEngineView(shell)
        if after_load_script:
            self._run_html_script_after_load(view, after_load_script)
        view.setUrl(url)
        shell_layout.addWidget(view, 1)

        grip_bar = QtWidgets.QFrame(shell)
        grip_bar.setObjectName("htmlGripBar")
        grip_bar.setFixedHeight(12)
        grip_layout = QtWidgets.QHBoxLayout(grip_bar)
        grip_layout.setContentsMargins(0, 0, 2, 2)
        grip_layout.addStretch(1)
        size_grip = QtWidgets.QSizeGrip(grip_bar)
        size_grip.setObjectName("htmlSizeGrip")
        grip_layout.addWidget(size_grip)
        shell_layout.addWidget(grip_bar)

        window.setCentralWidget(shell)
        window.destroyed.connect(
            lambda _obj=None, key=path: self.html_windows.pop(key, None)
        )
        self.html_windows[path] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def open_cpu_blueprint(self, fragment: str | None = None) -> None:
        after_load_script = self._latest_rtl_injection_script()
        self._open_local_html(docs_index_path(), "AMB CPU Blueprint", fragment, after_load_script)

    def open_cpu_docs(self) -> None:
        self.open_cpu_blueprint()

    def _load_rtl_runner(self):
        return rtl_runner

    @staticmethod
    def _write_program_hex(words: list[int], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for word in words:
                handle.write(f"{(word >> 8) & 0xFF:02x}\n")
                handle.write(f"{word & 0xFF:02x}\n")

    @staticmethod
    def _write_default_data_hex(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("@0000\n00\n@0200\n00\n00\n00\n00\n", encoding="utf-8")

    def _current_sample_data_hex(self) -> Path | None:
        if self.current_sample is None:
            return None
        return self.current_sample.data_hex_path

    def _prime_memory_view_for_sample(self) -> None:
        if self.current_sample is None:
            self.mem_start.setText("0x0000000")
            return
        self.mem_start.setText(f"0x{self.current_sample.mem_view_start:07X}")

    def _load_current_sample_dmem(self) -> None:
        data_hex = self._current_sample_data_hex()
        if data_hex is None:
            return
        self.cpu.load_data_hex(data_hex)

    def _rtl_data_source_label(self, data_hex: Path) -> str:
        if self.rtl_data_hex_override is not None and data_hex == self.rtl_data_hex_override:
            return "Custom data.hex"
        if self.current_sample is not None and data_hex == self.current_sample.data_hex_path:
            return self.current_sample.rtl_data_source
        return "Generated default data.hex"

    def _select_rtl_data_hex(self, out_dir: Path) -> tuple[Path, str, str]:
        if self.rtl_data_hex_override is not None and self.rtl_data_hex_override.exists():
            expected = self.current_sample.rtl_expected if self.current_sample is not None else "25"
            return self.rtl_data_hex_override, "0", expected

        if self.current_sample is not None and self.current_sample.data_hex_path.exists():
            return (
                self.current_sample.data_hex_path,
                self.current_sample.rtl_check_result,
                self.current_sample.rtl_expected,
            )

        data_hex = out_dir / "data.hex"
        self._write_default_data_hex(data_hex)
        return data_hex, "0", "25"

    def show_rtl_options_menu(self, anchor: QtWidgets.QWidget) -> None:
        menu = QtWidgets.QMenu(self)
        current_data_hex = self.rtl_data_hex_override or self._current_sample_data_hex()
        current_text = f"Data image: {current_data_hex}" if current_data_hex is not None else "Data image: generated default"
        current_action = menu.addAction(current_text)
        current_action.setEnabled(False)
        viewer_action = menu.addAction(f"Waveform viewer: {self.waveform_viewer_title()}")
        viewer_action.setEnabled(False)
        menu.addSeparator()
        choose_action = menu.addAction("Choose data.hex...")
        clear_action = menu.addAction("Clear data image")
        clear_action.setEnabled(self.rtl_data_hex_override is not None)
        menu.addSeparator()
        viewer_group = QtGui.QActionGroup(menu)
        viewer_group.setExclusive(True)
        surfer_action = menu.addAction("Use Surfer")
        surfer_action.setCheckable(True)
        surfer_action.setChecked(self.waveform_viewer == "surfer")
        viewer_group.addAction(surfer_action)
        gtkwave_action = menu.addAction("Use GTKWave")
        gtkwave_action.setCheckable(True)
        gtkwave_action.setChecked(self.waveform_viewer == "gtkwave")
        viewer_group.addAction(gtkwave_action)

        selected = menu.exec(anchor.mapToGlobal(QtCore.QPoint(0, anchor.height())))
        if selected == choose_action:
            self.choose_rtl_data_hex()
        elif selected == clear_action:
            self.clear_rtl_data_hex()
        elif selected == surfer_action:
            self.set_waveform_viewer("surfer")
        elif selected == gtkwave_action:
            self.set_waveform_viewer("gtkwave")

    def waveform_viewer_title(self) -> str:
        return "Surfer" if self.waveform_viewer == "surfer" else "GTKWave"

    def set_waveform_viewer(self, viewer: str) -> None:
        if viewer not in {"surfer", "gtkwave"}:
            return
        self.waveform_viewer = viewer
        self.settings.setValue("rtl/waveform_viewer", viewer)
        self.statusBar().showMessage(f"Waveform viewer: {self.waveform_viewer_title()}", 4000)

    @staticmethod
    def _dark_file_dialog_stylesheet() -> str:
        return (
            """
            QDialog#darkFileDialogShell {
                background: #020a04;
                color: #d6ffed;
                border: 2px solid #31f3a2;
            }
            QWidget#darkDialogTitleBar {
                background: #031305;
                color: #d6ffed;
                border-bottom: 1px solid #31f3a2;
            }
            QLabel#darkDialogTitleLabel {
                color: #d6ffed;
                font-weight: 800;
                letter-spacing: 0.2px;
            }
            QPushButton#darkDialogTitleButton {
                background: #06210d;
                color: #bfffe0;
                border: 1px solid #18d77f;
                padding: 1px 8px;
            }
            QPushButton#darkDialogTitleButton:hover {
                background: #0b3a20;
            }
            QPushButton#darkDialogTitleClose {
                background: #2a0f14;
                color: #ffbdca;
                border: 1px solid #8f2f40;
                padding: 1px 8px;
            }
            QPushButton#darkDialogTitleClose:hover {
                background: #5a1b2b;
                color: #ffe0e6;
            }
            QFileDialog#darkFileDialogPanel {
                background: #020a04;
                color: #d6ffed;
                border: none;
            }
            QFileDialog#darkFileDialogPanel QLabel {
                color: #d6ffed;
                font-weight: 700;
            }
            QFileDialog#darkFileDialogPanel QLineEdit,
            QFileDialog#darkFileDialogPanel QComboBox {
                background: #031305;
                color: #d6ffed;
                border: 1px solid #2fe596;
                min-height: 24px;
                selection-background-color: #15522d;
                selection-color: #effff8;
            }
            QFileDialog#darkFileDialogPanel QComboBox QAbstractItemView,
            QFileDialog#darkFileDialogPanel QTreeView,
            QFileDialog#darkFileDialogPanel QListView {
                background: #010703;
                color: #8dffd0;
                border: 1px solid #1bbb71;
                selection-background-color: #0d4a2a;
                selection-color: #effff8;
                outline: none;
            }
            QFileDialog#darkFileDialogPanel QHeaderView::section {
                background: #07301b;
                color: #d6ffed;
                border: 1px solid #0d8f54;
                padding: 4px 6px;
            }
            QFileDialog#darkFileDialogPanel QPushButton,
            QFileDialog#darkFileDialogPanel QToolButton {
                background: #06210d;
                color: #bfffe0;
                border: 1px solid #18d77f;
                padding: 4px 8px;
            }
            QFileDialog#darkFileDialogPanel QPushButton:hover,
            QFileDialog#darkFileDialogPanel QToolButton:hover {
                background: #0b3a20;
                color: #eafff4;
            }
            QFileDialog#darkFileDialogPanel QPushButton:pressed,
            QFileDialog#darkFileDialogPanel QToolButton:pressed {
                background: #10522e;
            }
            """
        )

    def _run_dark_file_dialog(
        self,
        title: str,
        start_dir: str,
        file_filter: str,
        accept_mode: QtWidgets.QFileDialog.AcceptMode,
        file_mode: QtWidgets.QFileDialog.FileMode,
    ) -> str:
        shell = QtWidgets.QDialog(self)
        shell.setObjectName("darkFileDialogShell")
        shell.setWindowTitle(title)
        shell.setWindowFlags(
            QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.FramelessWindowHint
        )
        shell.setModal(True)
        shell.resize(760, 520)
        shell.setStyleSheet(self._dark_file_dialog_stylesheet())

        layout = QtWidgets.QVBoxLayout(shell)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        title_bar = TitleBar(
            shell,
            title=title,
            button_labels=("-", "□", "×"),
            button_widths=(30, 30, 30),
        )
        title_bar.setObjectName("darkDialogTitleBar")
        title_bar.title_label.setObjectName("darkDialogTitleLabel")
        title_bar.min_btn.setObjectName("darkDialogTitleButton")
        title_bar.max_btn.setObjectName("darkDialogTitleButton")
        title_bar.close_btn.setObjectName("darkDialogTitleClose")
        layout.addWidget(title_bar)

        dialog = QtWidgets.QFileDialog(shell, title, start_dir, file_filter)
        dialog.setObjectName("darkFileDialogPanel")
        dialog.setWindowFlags(QtCore.Qt.WindowType.Widget)
        dialog.setOption(QtWidgets.QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setAcceptMode(accept_mode)
        dialog.setFileMode(file_mode)
        dialog.accepted.connect(shell.accept)
        dialog.rejected.connect(shell.reject)
        layout.addWidget(dialog, 1)

        if shell.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return ""
        selected = dialog.selectedFiles()
        return selected[0] if selected else ""

    def _get_open_filename(self, title: str, start_dir: str, file_filter: str) -> str:
        return self._run_dark_file_dialog(
            title,
            start_dir,
            file_filter,
            QtWidgets.QFileDialog.AcceptMode.AcceptOpen,
            QtWidgets.QFileDialog.FileMode.ExistingFile,
        )

    def _get_save_filename(self, title: str, start_dir: str, file_filter: str) -> str:
        return self._run_dark_file_dialog(
            title,
            start_dir,
            file_filter,
            QtWidgets.QFileDialog.AcceptMode.AcceptSave,
            QtWidgets.QFileDialog.FileMode.AnyFile,
        )

    def choose_rtl_data_hex(self) -> None:
        start_dir = Path(self.current_file).parent if self.current_file else Path.home()
        if self.rtl_data_hex_override is not None:
            start_dir = self.rtl_data_hex_override.parent
        elif self.current_sample is not None:
            start_dir = self.current_sample.data_hex_path.parent
        filename = self._get_open_filename(
            "Choose RTL data image",
            str(start_dir),
            "Hex files (*.hex);;All files (*)",
        )
        if not filename:
            return
        self.rtl_data_hex_override = Path(filename).resolve()
        self.statusBar().showMessage(f"RTL data image: {self.rtl_data_hex_override}", 5000)

    def clear_rtl_data_hex(self) -> None:
        self.rtl_data_hex_override = None
        fallback = self._current_sample_data_hex()
        if fallback is not None:
            self.statusBar().showMessage(f"RTL data image cleared; using sample image {fallback}.", 5000)
        else:
            self.statusBar().showMessage("RTL data image cleared; using generated default.", 5000)

    @staticmethod
    def _rtl_status_text(result: dict[str, object]) -> str:
        report = result.get("testbench")
        report_data = report if isinstance(report, dict) else {}
        mode = str(result.get("run_mode", "inspection"))
        status_kind = str(result.get("status_kind", ""))
        cycles = report_data.get("cycles", "-")
        halt = report_data.get("halt", "-")
        if mode == "validation":
            actual = report_data.get("actual", "-")
            expected = report_data.get("expected", "-")
            if status_kind == "pass":
                return f"RTL benchmark pass: actual {actual} == expected {expected}"
            return f"RTL benchmark fail: actual {actual} != expected {expected}"
        if result.get("returncode") != 0:
            return f"RTL run failed: exit {result.get('returncode')}"
        return f"RTL trace complete: cycles {cycles}, halt {halt}"

    def run_rtl_sim(self) -> None:
        if not self.program:
            self.assemble_source()
            if not self.program:
                return

        try:
            runner = self._load_rtl_runner()
            out_dir = rtl_run_root() / "gui_current"
            program_hex = out_dir / "program.hex"
            self._write_program_hex(self.program.words, program_hex)
            data_hex, check_result, expected = self._select_rtl_data_hex(out_dir)

            oss_root = bundled_oss_root()
            result = runner.run_simulation(
                run_name="gui_current",
                program=program_hex,
                data=data_hex,
                out_dir=out_dir,
                oss_root=oss_root if oss_root.exists() else None,
                check_result=check_result,
                expected=expected,
                schematic=False,
                data_source=self._rtl_data_source_label(data_hex),
            )
            self.last_rtl_result = result
            self.statusBar().showMessage(self._rtl_status_text(result), 7000)
            self.open_cpu_blueprint("latest-rtl-run")
        except Exception as exc:
            self._log_nonfatal("run_rtl_sim", exc)
            self.statusBar().showMessage(f"RTL sim failed: {exc}", 8000)

    def _load_latest_rtl_result(self) -> dict[str, object] | None:
        if isinstance(self.last_rtl_result, dict):
            return self.last_rtl_result

        candidate = rtl_run_root() / "gui_current" / "summary.json"
        if candidate.exists():
            try:
                self.last_rtl_result = json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                self.last_rtl_result = None
        return self.last_rtl_result

    @staticmethod
    def _artifact_file_url(value: object) -> str | None:
        if not value:
            return None
        return QtCore.QUrl.fromLocalFile(str(Path(str(value)))).toString()

    def _latest_rtl_payload(self) -> dict[str, object] | None:
        summary = self._load_latest_rtl_result()
        if not isinstance(summary, dict):
            return None

        try:
            summary_payload = json.loads(json.dumps(summary))
        except TypeError:
            summary_payload = {str(key): str(value) for key, value in summary.items()}

        artifacts = summary_payload.get("artifacts")
        artifact_paths = artifacts if isinstance(artifacts, dict) else {}
        summary_path = rtl_run_root() / "gui_current" / "summary.json"
        report_path = summary_payload.get("report") or artifact_paths.get("result_json")
        result_payload = summary_payload.get("testbench")

        if report_path:
            candidate = Path(str(report_path))
            if candidate.exists():
                try:
                    result_payload = json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    result_payload = summary_payload.get("testbench")

        artifact_sources = {
            "html": summary_payload.get("html") or artifact_paths.get("html"),
            "result_json": report_path,
            "summary_json": artifact_paths.get("summary_json") or summary_path,
            "run_log": summary_payload.get("log") or artifact_paths.get("run_log"),
            "vcd": summary_payload.get("vcd") or artifact_paths.get("vcd"),
            "fst": summary_payload.get("fst") or artifact_paths.get("fst"),
            "gtkw": summary_payload.get("gtkw") or artifact_paths.get("gtkw"),
        }
        artifact_urls = {
            key: url
            for key, value in artifact_sources.items()
            if (url := self._artifact_file_url(value)) is not None
        }

        return {
            "summary": summary_payload,
            "result": result_payload if isinstance(result_payload, dict) else None,
            "artifact_urls": artifact_urls,
        }

    def _latest_rtl_injection_script(self) -> str | None:
        payload = self._latest_rtl_payload()
        if payload is None:
            return None

        encoded = json.dumps(payload).replace("</", "<\\/")
        return (
            f"window.__AMB_LATEST_RTL_RUN__ = {encoded};"
            "if (window.__AMB_RENDER_LATEST_RTL_RUN__) {"
            "window.__AMB_RENDER_LATEST_RTL_RUN__();"
            "}"
        )

    def _latest_artifact(self, *keys: str) -> Path | None:
        result = self._load_latest_rtl_result()
        if not result:
            return None
        artifacts = result.get("artifacts")
        artifact_paths = artifacts if isinstance(artifacts, dict) else {}
        for key in keys:
            value = result.get(key) or artifact_paths.get(key)
            if value:
                path = Path(str(value))
                if path.exists():
                    return path
        return None

    def open_latest_rtl_report(self) -> None:
        report = self._latest_artifact("html")
        if report is None:
            self.open_cpu_blueprint("latest-rtl-run")
            return
        self._open_local_html(report, "AMB RTL Run")

    @staticmethod
    def _tool_is_unresolved(tool: str, name: str) -> bool:
        tool_path = Path(tool)
        normalized = tool_path.name.lower()
        expected = {name.lower(), f"{name.lower()}.exe"}
        return normalized in expected and not tool_path.exists() and shutil.which(tool) is None

    def open_latest_waveform(self) -> None:
        wave_path = self._latest_artifact("fst", "vcd")
        if wave_path is None:
            self.statusBar().showMessage("No waveform yet. Run RTL Sim first.", 5000)
            return
        gtkw_path = self._latest_artifact("gtkw")
        try:
            runner = self._load_rtl_runner()
            oss_root = bundled_oss_root()
            oss_root_arg = oss_root if oss_root.exists() else None
            fallback_used = False

            if self.waveform_viewer == "surfer":
                viewer = runner.tool_path("surfer", oss_root_arg)
                if self._tool_is_unresolved(viewer, "surfer"):
                    viewer = runner.tool_path("gtkwave", oss_root_arg)
                    fallback_used = True
                    args = ["-a", str(gtkw_path), str(wave_path)] if gtkw_path is not None else [str(wave_path)]
                else:
                    args = [str(wave_path)]
            else:
                viewer = runner.tool_path("gtkwave", oss_root_arg)
                if self._tool_is_unresolved(viewer, "gtkwave"):
                    viewer = runner.tool_path("surfer", oss_root_arg)
                    fallback_used = True
                    args = [str(wave_path)]
                elif gtkw_path is not None:
                    args = ["-a", str(gtkw_path), str(wave_path)]
                else:
                    args = [str(wave_path)]

            if self._tool_is_unresolved(viewer, "surfer") or self._tool_is_unresolved(viewer, "gtkwave"):
                raise FileNotFoundError("No waveform viewer found. Install Surfer or GTKWave, or install the repo-local OSS CAD Suite.")

            if Path(viewer).name.lower().startswith("gtkwave") and gtkw_path is not None and args == [str(wave_path)]:
                args = ["-a", str(gtkw_path), str(wave_path)]

            runner.popen_tool(viewer, args, runner.REPO_ROOT, oss_root_arg, hide_console=True)
            viewer_name = Path(viewer).name
            if fallback_used:
                self.statusBar().showMessage(f"Opened waveform with fallback {viewer_name}: {wave_path}", 5000)
            else:
                self.statusBar().showMessage(f"Opened waveform with {viewer_name}: {wave_path}", 3000)
        except Exception as exc:
            self._log_nonfatal("open_latest_waveform", exc)
            self.statusBar().showMessage(f"Could not open waveform: {exc}", 8000)

    def new_file(self) -> None:
        self.editor.clear()
        self.current_file = None
        self.current_sample = None
        self.program = None
        self.addr_to_line = {}
        self.cpu.reset()
        self._last_reg_changes = set()
        self._last_mem_changes = set()
        self.mem_start.setText("0x0000000")
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        self.highlight_line(None)
        self.statusBar().showMessage("New file", 2000)

    def load_sample_code(self, index: int) -> None:
        if index <= 0:
            return
        sample_name = self.sample_codes_combo.itemText(index)
        sample = SAMPLE_DEFINITIONS_BY_NAME.get(sample_name)
        if sample is None:
            return
        if self.timer.isActive():
            self.timer.stop()
        self.editor.setPlainText(sample.source())
        self.current_file = None
        self.current_sample = sample
        self.program = None
        self.addr_to_line = {}
        self.cpu.reset()
        self._load_current_sample_dmem()
        self._last_reg_changes = set()
        self._last_mem_changes = set()
        self._prime_memory_view_for_sample()
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        self.highlight_line(None)
        self.statusBar().showMessage(f"Loaded sample: {sample.name}", 3000)
        self.sample_codes_combo.setCurrentIndex(0)

    def open_file(self) -> None:
        path = self._get_open_filename(
            "Open Assembly",
            "",
            "AMB Assembly (*.ambasm)",
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as handle:
            self.editor.setPlainText(handle.read())
        self.current_file = path
        self.current_sample = None
        self.program = None
        self.addr_to_line = {}
        self.cpu.reset()
        self._last_reg_changes = set()
        self._last_mem_changes = set()
        self.mem_start.setText("0x0000000")
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        self.highlight_line(None)
        self.statusBar().showMessage(f"Opened {path}", 3000)

    def save_file(self) -> None:
        if not self.current_file:
            self.save_file_as()
            return
        with open(self.current_file, "w", encoding="utf-8") as handle:
            handle.write(self.editor.toPlainText())
        self.statusBar().showMessage(f"Saved {self.current_file}", 3000)

    def save_file_as(self) -> None:
        path = self._get_save_filename(
            "Save Assembly",
            "",
            "AMB Assembly (*.ambasm)",
        )
        if not path:
            return
        if not path.lower().endswith(".ambasm"):
            path = f"{path}.ambasm"
        self.current_file = path
        self.save_file()

    def _install_resize_filters(self) -> None:
        self.installEventFilter(self)
        for widget in self.findChildren(QtWidgets.QWidget):
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _hit_test_edges(self, pos: QtCore.QPoint) -> str | None:
        if self.isMaximized():
            return None
        margin = self._resize_margin
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        left = x <= margin
        right = x >= w - margin
        top = y <= margin
        bottom = y >= h - margin

        if top and left:
            return "top_left"
        if top and right:
            return "top_right"
        if bottom and left:
            return "bottom_left"
        if bottom and right:
            return "bottom_right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _update_cursor(self, edge: str | None) -> None:
        if self._resizing:
            return
        if edge == "left" or edge == "right":
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif edge == "top" or edge == "bottom":
            self.setCursor(QtCore.Qt.CursorShape.SizeVerCursor)
        elif edge == "top_left" or edge == "bottom_right":
            self.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
        elif edge == "top_right" or edge == "bottom_left":
            self.setCursor(QtCore.Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def _start_resize(self, edge: str, global_pos: QtCore.QPoint) -> None:
        self._resizing = True
        self._resize_edge = edge
        self._resize_start_pos = global_pos
        self._resize_start_geom = self.geometry()

    def _perform_resize(self, global_pos: QtCore.QPoint) -> None:
        if not self._resize_edge:
            return
        dx = global_pos.x() - self._resize_start_pos.x()
        dy = global_pos.y() - self._resize_start_pos.y()

        geom = self._resize_start_geom
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
        min_w = self.minimumWidth()
        min_h = self.minimumHeight()

        if "left" in self._resize_edge:
            x += dx
            w -= dx
        if "right" in self._resize_edge:
            w += dx
        if "top" in self._resize_edge:
            y += dy
            h -= dy
        if "bottom" in self._resize_edge:
            h += dy

        if w < min_w:
            if "left" in self._resize_edge:
                x = geom.x() + (geom.width() - min_w)
            w = min_w
        if h < min_h:
            if "top" in self._resize_edge:
                y = geom.y() + (geom.height() - min_h)
            h = min_h

        self.setGeometry(x, y, w, h)

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if (
            hasattr(self, "toolbar_scroll")
            and isinstance(obj, QtWidgets.QWidget)
            and event.type() == QtCore.QEvent.Type.Wheel
            and (
                obj is self.toolbar_scroll
                or obj is self.toolbar_scroll.viewport()
                or self.toolbar_scroll.isAncestorOf(obj)
            )
        ):
            wheel_event = event
            pixel_delta = wheel_event.pixelDelta()
            angle_delta = wheel_event.angleDelta()
            delta = (
                pixel_delta.x()
                or pixel_delta.y()
                or angle_delta.x()
                or angle_delta.y()
            )
            bar = self.toolbar_scroll.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            wheel_event.accept()
            return True

        if isinstance(event, QtGui.QMouseEvent):
            if event.type() == QtCore.QEvent.Type.MouseMove:
                if self._resizing:
                    self._perform_resize(event.globalPosition().toPoint())
                    return True
                if isinstance(obj, QtWidgets.QWidget):
                    local_pos = obj.mapTo(self, event.position().toPoint())
                    edge = self._hit_test_edges(local_pos)
                    self._update_cursor(edge)
                return False
            if event.type() == QtCore.QEvent.Type.MouseButtonPress:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    if isinstance(obj, QtWidgets.QWidget):
                        local_pos = obj.mapTo(self, event.position().toPoint())
                        edge = self._hit_test_edges(local_pos)
                        if edge:
                            self._start_resize(edge, event.globalPosition().toPoint())
                            return True
                return False
            if event.type() == QtCore.QEvent.Type.MouseButtonRelease:
                if self._resizing:
                    self._resizing = False
                    self._resize_edge = None
                    return True
        if event.type() == QtCore.QEvent.Type.Leave and not self._resizing:
            self.unsetCursor()
        return super().eventFilter(obj, event)

    def assemble_source(self) -> None:
        source = self.editor.toPlainText()
        try:
            program = assemble(source)
        except AsmError as exc:
            line_no = exc.line_no if exc.line_no is not None else 1
            span = self._infer_span_from_asm_error(source, line_no, str(exc))
            self.editor.set_lint_errors({line_no: str(exc)}, {line_no: span})
            self.statusBar().showMessage(str(exc), 5000)
            self.highlight_line(exc.line_no)
            return
        except Exception as exc:
            self._log_nonfatal("assemble_source", exc)
            self.statusBar().showMessage(f"Internal error: {exc}", 5000)
            return

        self.editor.set_lint_errors({}, {})
        self.program = program
        self.addr_to_line = program.addr_to_line
        self.cpu.reset()
        self.cpu.load_program(program.words)
        self._load_current_sample_dmem()
        self._last_reg_changes = set()
        self._last_mem_changes = set()
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        self.highlight_line(self.addr_to_line.get(0))
        self.statusBar().showMessage("Assembled successfully", 3000)

    def run(self) -> None:
        if self.timer.isActive():
            return
        if not self.program:
            self.assemble_source()
            if not self.program:
                return
        self.timer.start()
        self.statusBar().showMessage("Running", 2000)

    def stop(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.statusBar().showMessage("Stopped", 2000)

    def reset_cpu(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        if self.program:
            self.cpu.reset()
            self.cpu.load_program(self.program.words)
        else:
            self.cpu.reset()
        self._load_current_sample_dmem()
        self._last_reg_changes = set()
        self._last_mem_changes = set()
        if self.current_sample is not None:
            self._prime_memory_view_for_sample()
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        self.highlight_line(self.addr_to_line.get(0))
        self.statusBar().showMessage("Reset", 2000)

    def step(self) -> None:
        if not self.program:
            self.assemble_source()
            if not self.program:
                return
        result = self.cpu.step()
        self._last_reg_changes = result.changed_registers
        self._last_mem_changes = result.changed_memory
        self.update_register_view()
        self.update_memory_view()
        self._sync_pulse()
        line_no = self.addr_to_line.get(result.ic)
        if line_no:
            self.highlight_line(line_no)
        if result.message:
            self.statusBar().showMessage(result.message, 3000)
        if result.halted:
            self.timer.stop()

    def highlight_line(self, line_no: int | None) -> None:
        if line_no is None:
            self.editor.setExtraSelections([])
            return
        block = self.editor.document().findBlockByNumber(line_no - 1)
        if not block.isValid():
            return
        cursor = QtGui.QTextCursor(block)
        selection = QtWidgets.QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(QtGui.QColor("#0b2b0b"))
        selection.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
        self.editor.setExtraSelections([selection])

    def _apply_cell_style(self, item: QtWidgets.QTableWidgetItem, highlight: bool) -> None:
        if highlight:
            item.setBackground(self._highlight_bg)
            item.setForeground(self._highlight_fg)
        else:
            item.setBackground(self._default_bg)
            item.setForeground(self._default_fg)

    def _update_pulse_brush(self) -> None:
        bright = QtGui.QColor("#00ff6a")
        dark = QtGui.QColor("#007a3a")
        t = 0.5 + 0.5 * math.sin(self._pulse_phase)
        r = int(dark.red() + (bright.red() - dark.red()) * t)
        g = int(dark.green() + (bright.green() - dark.green()) * t)
        b = int(dark.blue() + (bright.blue() - dark.blue()) * t)
        self._highlight_bg = QtGui.QBrush(QtGui.QColor(r, g, b))

    def _refresh_highlights(self) -> None:
        for row in range(self.reg_table.rowCount()):
            highlight = row in self._last_reg_changes
            for col in range(self.reg_table.columnCount()):
                item = self.reg_table.item(row, col)
                if item is not None:
                    self._apply_cell_style(item, highlight)

        start = self._parse_address(self.mem_start.text())
        if start is None:
            return
        for i in range(self.mem_table.rowCount()):
            addr = (start + i) & ADDR_MASK
            highlight = addr in self._last_mem_changes
            for col in range(self.mem_table.columnCount()):
                item = self.mem_table.item(i, col)
                if item is not None:
                    self._apply_cell_style(item, highlight)

    def _advance_pulse(self) -> None:
        if not (self._last_reg_changes or self._last_mem_changes):
            self._pulse_timer.stop()
            return
        self._pulse_phase += 0.35
        self._update_pulse_brush()
        self._refresh_highlights()

    def _sync_pulse(self) -> None:
        if self._last_reg_changes or self._last_mem_changes:
            self._pulse_phase = 0.0
            self._update_pulse_brush()
            if not self._pulse_timer.isActive():
                self._pulse_timer.start()
            self._refresh_highlights()
        else:
            if self._pulse_timer.isActive():
                self._pulse_timer.stop()
            self._refresh_highlights()

    def _adjust_memory_range_for_changes(self, start: int, count: int) -> tuple[int, int]:
        if not self._last_mem_changes:
            return start, count
        min_addr = min(self._last_mem_changes)
        max_addr = max(self._last_mem_changes)
        range_len = max_addr - min_addr + 1
        new_count = count
        if range_len > new_count:
            new_count = min(range_len, self.mem_count.maximum())
        if min_addr < start or max_addr >= start + new_count:
            start = min_addr
        return start, new_count

    def update_register_view(self) -> None:
        self.reg_table.setRowCount(len(REG_NAMES))
        for row, name in enumerate(REG_NAMES):
            val = self.cpu.registers[row] & WORD_MASK
            highlight = row in self._last_reg_changes
            name_item = QtWidgets.QTableWidgetItem(name)
            value_item = QtWidgets.QTableWidgetItem(f"0x{val:07X}")
            self._apply_cell_style(name_item, highlight)
            self._apply_cell_style(value_item, highlight)
            self.reg_table.setItem(row, 0, name_item)
            self.reg_table.setItem(row, 1, value_item)

    def _parse_address(self, text: str) -> int | None:
        try:
            value = parse_number(text.strip())
        except Exception:
            return None
        return value & ADDR_MASK

    def update_memory_view(self) -> None:
        start = self._parse_address(self.mem_start.text())
        if start is None:
            self.statusBar().showMessage("Invalid memory start address", 3000)
            return
        count = self.mem_count.value()
        start, count = self._adjust_memory_range_for_changes(start, count)
        if count != self.mem_count.value():
            self.mem_count.setValue(count)
        if start != self._parse_address(self.mem_start.text()):
            self.mem_start.setText(f"0x{start:07X}")
        self.mem_table.setRowCount(count)
        for i in range(count):
            addr = (start + i) & ADDR_MASK
            val = self.cpu.dmem.read_byte(addr)
            highlight = addr in self._last_mem_changes
            addr_item = QtWidgets.QTableWidgetItem(f"0x{addr:07X}")
            val_item = QtWidgets.QTableWidgetItem(f"0x{val:02X}")
            self._apply_cell_style(addr_item, highlight)
            self._apply_cell_style(val_item, highlight)
            self.mem_table.setItem(i, 0, addr_item)
            self.mem_table.setItem(i, 1, val_item)

    def show_help(self) -> None:
        if self.help_dock.isVisible():
            self.help_dock.hide()
        else:
            self.help_dock.show()
            self.help_dock.raise_()

    def show_authors(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setObjectName("authorsDialog")
        dialog.setWindowTitle("Project Authors")
        dialog.setModal(True)
        dialog.setWindowFlags(
            QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.FramelessWindowHint
        )
        dialog.resize(700, 320)
        dialog.setStyleSheet(
            """
            QDialog#authorsDialog {
                background: #020a04;
                border: 2px solid #18d77f;
                border-radius: 0px;
            }
            QDialog#authorsDialog QLabel {
                color: #8dffd0;
            }
            QDialog#authorsDialog QTableWidget {
                background: #010703;
                color: #8dffd0;
                border: 1px solid #0d8f54;
                gridline-color: #0d8f54;
            }
            QDialog#authorsDialog QHeaderView::section {
                background: #07301b;
                color: #d5ffee;
                border: 1px solid #0d8f54;
                padding: 6px 8px;
            }
            QDialog#authorsDialog QPushButton {
                background: #06210d;
                color: #8dffd0;
                border: 1px solid #18d77f;
                padding: 5px 14px;
                min-width: 90px;
            }
            QDialog#authorsDialog QPushButton:hover {
                background: #0b3a20;
                color: #e8fff5;
            }
            QDialog#authorsDialog QPushButton:pressed {
                background: #10522e;
            }
            QDialog#authorsDialog QPushButton#authorsTopClose {
                min-width: 0px;
                padding: 0px;
                background: #2a0f14;
                color: #ffc7d3;
                border: 1px solid #8f2f40;
            }
            QDialog#authorsDialog QPushButton#authorsTopClose:hover {
                background: #5a1b2b;
                color: #ffe4ea;
            }
            """
        )

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        title = QtWidgets.QLabel("AMB Processor Group Project", dialog)
        title.setStyleSheet("font-size: 14pt; font-weight: 700; color: #bfffe0;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(title, 1)
        top_close_btn = QtWidgets.QPushButton("X", dialog)
        top_close_btn.setObjectName("authorsTopClose")
        top_close_btn.setFixedSize(28, 24)
        top_close_btn.clicked.connect(dialog.reject)
        top_row.addWidget(top_close_btn, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top_row)

        course = QtWidgets.QLabel(
            "<b>Course:</b> ELEC 462 -- Computer Architecture and Organization", dialog
        )
        course.setTextFormat(QtCore.Qt.TextFormat.RichText)
        course.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(course)

        instructor = QtWidgets.QLabel("<b>Instructor:</b> Dr Abulhalim Jallad", dialog)
        instructor.setTextFormat(QtCore.Qt.TextFormat.RichText)
        instructor.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(instructor)

        table = QtWidgets.QTableWidget(dialog)
        table.setColumnCount(2)
        table.setRowCount(3)
        table.setHorizontalHeaderLabels(["Student Name", "Student ID"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        table.setAlternatingRowColors(False)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        rows = [
            ("Alrida Ismail", "ALRIDAS_UNIVERSITY_ID"),
            ("Muddathir Yousif", "MUDDATHIRS_UNIVERSITY_ID"),
            ("Basel Alhomsi", "BASELS_UNIVERSITY_ID"),
        ]
        for r, (name, sid) in enumerate(rows):
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(r, 1, QtWidgets.QTableWidgetItem(sid))

        # Subtle highlight for your row without extra role labels.
        for c in range(2):
            item = table.item(0, c)
            if item is not None:
                item.setBackground(QtGui.QColor("#0a3320"))

        table.resizeRowsToContents()
        total_rows_height = sum(table.rowHeight(r) for r in range(table.rowCount()))
        exact_height = (
            table.horizontalHeader().height()
            + total_rows_height
            + (table.frameWidth() * 2)
        )
        table.setFixedHeight(exact_height)
        layout.addWidget(table)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close", dialog)
        close_btn.clicked.connect(dialog.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        QtGui.QShortcut(QtGui.QKeySequence("Esc"), dialog, activated=dialog.reject)

        dialog.exec()


SELF_TEST_REQUIRED_OSS_TOOLS = ("yosys", "iverilog", "vvp", "vcd2fst", "dot")
SELF_TEST_WAVE_TOOLS = ("surfer", "gtkwave")


def _oss_executable(root: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return root / "bin" / f"{name}{suffix}"


def _validate_oss_tools(root: Path, *, require_wave_viewer: bool = True) -> dict[str, object]:
    if not root.exists():
        raise FileNotFoundError(f"OSS CAD Suite root not found: {root}")

    found: dict[str, str] = {}
    missing: list[str] = []
    for name in SELF_TEST_REQUIRED_OSS_TOOLS:
        candidate = _oss_executable(root, name)
        if candidate.exists():
            found[name] = str(candidate)
        else:
            missing.append(name)

    wave = next((name for name in SELF_TEST_WAVE_TOOLS if _oss_executable(root, name).exists()), None)
    if wave is not None:
        found[wave] = str(_oss_executable(root, wave))
    elif require_wave_viewer:
        missing.append("surfer_or_gtkwave")

    if missing:
        raise FileNotFoundError(f"OSS CAD Suite missing required tools: {', '.join(missing)}")

    return {
        "root": str(root),
        "tools": found,
    }


def _existing_resource(label: str, path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return str(path)


def run_self_test(*, require_oss: bool = False) -> dict[str, object]:
    source = "\n".join(
        (
            "LIL 5",
            "MOV R0, IMR",
            "HLT",
            "",
        )
    )
    program = assemble(source)
    if len(program.words) != 3:
        raise RuntimeError(f"Assembler smoke expected 3 instructions, got {len(program.words)}")

    resources = {
        "docs_index": _existing_resource("CPU docs index", docs_index_path()),
        "app_icon": _existing_resource("App icon", resource_path("assets", "amb.ico")),
        "rtl_testbench": _existing_resource("RTL testbench", resource_path("src", "rtl", "testbench", "tb.v")),
        "array_sum_program": _existing_resource(
            "Array-sum program image",
            resource_path("src", "rtl", "testbench", "array_sum_program.hex"),
        ),
        "array_sum_data": _existing_resource(
            "Array-sum data image",
            resource_path("src", "rtl", "testbench", "array_sum_data.hex"),
        ),
    }

    oss_root = bundled_oss_root()
    if oss_root.exists():
        oss_payload: dict[str, object] = _validate_oss_tools(oss_root)
        oss_payload["exists"] = True
    elif require_oss:
        raise FileNotFoundError(f"OSS CAD Suite root not found: {oss_root}")
    else:
        oss_payload = {
            "root": str(oss_root),
            "exists": False,
        }

    return {
        "status": "pass",
        "mode": "self-test",
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_root": str(resource_path()),
        "assembler_words": [f"{word:04x}" for word in program.words],
        "resources": resources,
        "oss_cad_suite": oss_payload,
    }


def run_self_test_rtl() -> dict[str, object]:
    payload = run_self_test(require_oss=True)
    oss_root = bundled_oss_root()
    _validate_oss_tools(oss_root)

    out_dir = rtl_run_root() / "self_test"
    result = rtl_runner.run_simulation(
        run_name="self_test",
        program=resource_path("src", "rtl", "testbench", "array_sum_program.hex"),
        data=resource_path("src", "rtl", "testbench", "array_sum_data.hex"),
        out_dir=out_dir,
        oss_root=oss_root,
        check_result="1",
        expected="25",
        schematic=False,
        data_source="Self-test array_sum_data.hex",
    )
    if result.get("returncode") != 0 or result.get("status_kind") != "pass":
        raise RuntimeError(
            "RTL self-test failed: "
            f"returncode={result.get('returncode')} status={result.get('status_kind')}"
        )

    payload["mode"] = "self-test-rtl"
    payload["rtl_simulation"] = {
        "returncode": result.get("returncode"),
        "status_kind": result.get("status_kind"),
        "status_label": result.get("status_label"),
        "oss_root": result.get("oss_root"),
        "summary_json": result.get("artifacts", {}).get("summary_json")
        if isinstance(result.get("artifacts"), dict)
        else None,
    }
    return payload


def _handle_self_test_args(argv: list[str]) -> bool:
    if "--self-test-rtl" in argv:
        runner = run_self_test_rtl
    elif "--self-test" in argv:
        runner = run_self_test
    else:
        return False

    try:
        print(json.dumps(runner(), indent=2))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return True


def main() -> None:
    def _global_excepthook(exc_type, exc_value, exc_tb) -> None:
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(msg)
        try:
            with open("assembler_crash.log", "a", encoding="utf-8") as handle:
                handle.write(msg)
                handle.write("\n")
        except Exception:
            pass

    sys.excepthook = _global_excepthook
    if _handle_self_test_args(sys.argv[1:]):
        return

    try:
        fh_stream = open("assembler_faulthandler.log", "a", encoding="utf-8")
        faulthandler.enable(fh_stream)
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)
    icon_path = resource_path("assets", "amb.ico")
    icon = QtGui.QIcon(str(icon_path))
    app.setWindowIcon(icon)
    app_palette = app.palette()
    green = QtGui.QColor("#00ff6a")
    for group in (
        QtGui.QPalette.ColorGroup.Active,
        QtGui.QPalette.ColorGroup.Inactive,
    ):
        app_palette.setColor(group, QtGui.QPalette.ColorRole.Text, green)
        app_palette.setColor(group, QtGui.QPalette.ColorRole.WindowText, green)
    app.setPalette(app_palette)
    window = AssemblerWindow()
    window.setWindowIcon(icon)
    window.show()
    app.exec()
