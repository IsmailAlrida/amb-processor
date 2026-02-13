"""PyQt6 UI for the AMB assembler simulator."""

from __future__ import annotations

import re
import sys
import textwrap
import traceback
import faulthandler
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from .assembler import AsmError, assemble, parse_number
from .cpu import CPU
from .isa import (
    ADDR_MASK,
    GEN_OPCODES,
    IMM_OPCODES,
    JUMP_OPCODES,
    REG_NAMES,
    RR_OPCODES,
    WORD_MASK,
)


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
        self._error_format = QtGui.QTextCharFormat()
        self._error_format.setUnderlineStyle(
            QtGui.QTextCharFormat.UnderlineStyle.WaveUnderline
        )
        self._error_format.setUnderlineColor(QtGui.QColor("#ff5a70"))

    def set_error_spans(self, error_spans: dict[int, tuple[int, int]]) -> None:
        self._error_spans = error_spans
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
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
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAutoFillBackground(True)
        self.setFixedHeight(34)
        self._drag_pos: QtCore.QPoint | None = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(6)

        self.title_label = QtWidgets.QLabel(parent.windowTitle())
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.min_btn = QtWidgets.QPushButton("MIN")
        self.min_btn.setObjectName("titleButton")
        self.max_btn = QtWidgets.QPushButton("MAX")
        self.max_btn.setObjectName("titleButton")
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setObjectName("titleClose")

        for btn, min_w in (
            (self.min_btn, 40),
            (self.max_btn, 40),
            (self.close_btn, 30),
        ):
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
        self.current_file: str | None = None

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

        mem_panel_wrapped = self._wrap_panel("Memory", mem_panel)

        splitter.addWidget(editor_panel)
        splitter.addWidget(reg_panel)
        splitter.addWidget(mem_panel_wrapped)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        self.setCentralWidget(splitter)
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
                unary_rr = {"NOT", "SHL", "SHR", "SAR"}
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
                if len(operands) != 2:
                    errors[line_no] = f"{mnem} expects register and immediate"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                ra, imm = operands
                if not self._is_register_token(ra):
                    errors[line_no] = f"Unknown register '{ra}'"
                    spans[line_no] = self._find_token_span(line, ra)
                    continue
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

            if mnem in JUMP_OPCODES:
                if len(operands) != 1:
                    errors[line_no] = f"{mnem} expects an immediate or label"
                    spans[line_no] = self._find_token_span(line, mnem)
                    continue
                jump_arg = operands[0]
                try:
                    imm_val = parse_number(jump_arg)
                    if not (-1024 <= imm_val <= 1023):
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
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setObjectName("mainToolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        def add_action(label: str, slot) -> None:
            action = QtGui.QAction(label, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        add_action("New", self.new_file)
        add_action("Open", self.open_file)
        add_action("Save", self.save_file)
        add_action("Save As", self.save_file_as)
        toolbar.addSeparator()
        add_action("Assemble", self.assemble_source)
        add_action("Step", self.step)
        add_action("Run", self.run)
        add_action("Stop", self.stop)
        add_action("Reset", self.reset_cpu)
        toolbar.addSeparator()
        add_action("Authors", self.show_authors)
        add_action("Help", self.show_help)

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
                "SHL": "SHL Ra",
                "SHR": "SHR Ra",
                "SAR": "SAR Ra",
            }
        )
        rr_notes = {
            "NOT": "Ra = ~Ra",
            "OR": "Ra = Ra | Rb",
            "AND": "Ra = Ra & Rb",
            "XOR": "Ra = Ra ^ Rb",
            "SHL": "Ra = Ra << SHC",
            "SHR": "Ra = Ra >> SHC",
            "SAR": "Ra = arithmetic_shift_right(Ra, SHC)",
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
            "LIL": "LIL Ra, imm8",
            "LIH": "LIH Ra, imm8",
            "LOAD": "LOAD Ra, imm8",
            "STOR": "STOR Ra, imm8",
        }
        imm_notes = {
            "LIL": "Set bits 7..0 of Ra to imm8",
            "LIH": "Set bits 15..8 of Ra to imm8",
            "LOAD": "Ra = MEM[imm8 + MEMOFF] (28-bit word)",
            "STOR": "MEM[imm8 + MEMOFF] = Ra (28-bit word)",
        }
        imm_rows = [
            (mnem, imm_syntax.get(mnem, mnem), imm_notes.get(mnem, ""))
            for mnem in IMM_OPCODES
        ]

        jump_syntax = {mnem: f"{mnem} imm11" for mnem in JUMP_OPCODES}
        jump_notes = {
            "JMP": "PC += (imm11 << 1)",
            "JMPL": "PC += (imm11 << 1) + JMPOFF",
            "JPEQ": "If CMPA == CMPB, PC += (imm11 << 1) + JMPOFF",
            "JPBLW": "If CMPA < CMPB (unsigned), PC += (imm11 << 1) + JMPOFF",
        }
        jump_rows = [
            (mnem, jump_syntax.get(mnem, mnem), jump_notes.get(mnem, ""))
            for mnem in JUMP_OPCODES
        ]

        reg_names = ", ".join(REG_NAMES)

        return textwrap.dedent(
            f"""
        <div style="font-family: 'Cascadia Mono', Consolas, monospace; font-size: 11px; line-height: 1.35;">
        <h3>Instruction Set Reference</h3>
        <ul>
            <li>Instruction width: 15 bits (stored in 2 bytes, 1 unused bit)</li>
            <li>Word size: 28 bits</li>
            <li>Address width: 28 bits (byte-addressable)</li>
            <li>PC/IC increments by 2 after each instruction fetch</li>
        </ul>
        <h4>Registers</h4>
        <p>General: R0-R7.</p>
        <p>Special: IC, SP, LC, SHC, JMPOFF, MEMOFF, CMPA, CMPB.</p>
        <p>Full register list (case-insensitive): {reg_names}</p>
        <h4>Encoding Forms</h4>
        <div style="white-space: pre-wrap; border: 1px solid #0a3; background: #021002; padding: 6px;">
RR:  opcode7 | Ra | Rb
GEN: opcode7 only
IMM: opcode3 | Ra | imm8
JMP: opcode4 | imm11
        </div>
        <h4>Register-to-Register (RR)</h4>
        <p>Format: <code>MNEMONIC Ra, Rb</code>. If only one register is provided, the assembler uses <code>Rb = Ra</code>.</p>
        {build_table(rr_rows)}
        <h4>General (GEN)</h4>
        {build_table(gen_rows)}
        <h4>Immediate (IMM)</h4>
        <p><code>imm8</code> accepts -128..255 and is encoded as 8 bits. Labels are not allowed for IMM.</p>
        {build_table(imm_rows)}
        <h4>Jump (JMP)</h4>
        <p><code>imm11</code> accepts -1024..1023 (word offset). Labels are allowed and resolve to a PC-relative offset; labels must be 2-byte aligned.</p>
        <p><code>JPEQ</code> and <code>JPBLW</code> compare only <code>CMPA</code> and <code>CMPB</code>.</p>
        {build_table(jump_rows)}
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
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        label = QtWidgets.QLabel(title)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label)
        layout.addWidget(widget)
        return panel

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #030a03; color: #7affbf; border: 1px solid #0d8f54; }
            QWidget { color: #68ffb3; background: transparent; }
            QPlainTextEdit, QTableWidget, QLineEdit, QSpinBox, QComboBox, QTreeView, QTextBrowser {
                background: #031003; color: #80ffc6; border: 1px solid #0b7c49;
            }
            QPlainTextEdit:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextBrowser:focus {
                border: 1px solid #26d684;
            }
            QPlainTextEdit {
                selection-background-color: #0f3b1f;
                selection-color: #c8ffe5;
            }
            QTableWidget { gridline-color: #0b7c49; }
            QTableWidget::item { background: #031003; color: #80ffc6; }
            QTableWidget::item:selected { background: #104528; color: #d6ffec; }
            QTableCornerButton::section { background: #0a3520; border: 1px solid #0b7c49; }
            QHeaderView::section {
                background: #0a3520; color: #bfffe0; border: 1px solid #0b7c49; padding: 5px 6px;
            }

            QLabel { color: #9effd3; font-weight: 600; padding: 1px 0; }

            QPushButton, QToolButton {
                background: #06210d; color: #77ffc1; border: 1px solid #0d8f54; padding: 4px 10px; margin: 0;
            }
            QPushButton:hover, QToolButton:hover { background: #0d3a21; }
            QPushButton:pressed, QToolButton:pressed { background: #0f4c2b; color: #d7ffee; }
            QPushButton:disabled, QToolButton:disabled {
                color: #2f7f58; border-color: #1f5b3d; background: #041108;
            }

            QToolBar#mainToolbar {
                background: #041508; border-top: 1px solid #0d8f54; border-bottom: 1px solid #0d8f54;
                spacing: 2px; padding: 4px 6px;
            }
            QToolBar#mainToolbar QToolButton {
                min-height: 24px; padding: 4px 10px;
            }
            QToolBar#mainToolbar::separator { background: #0d8f54; width: 1px; margin: 2px 8px; }

            QWidget#titleBar { background: #041909; border-bottom: 1px solid #0d8f54; }
            QLabel#titleLabel { color: #c9ffe5; font-weight: 700; letter-spacing: 0.5px; }
            QPushButton#titleButton {
                background: #06250f; color: #92ffcd; border: 1px solid #0d8f54; padding: 1px 8px;
            }
            QPushButton#titleButton:hover { background: #0f3f24; }
            QPushButton#titleClose {
                background: #2a0f14; color: #ffbdca; border: 1px solid #8f2f40; padding: 1px 8px;
            }
            QPushButton#titleClose:hover { background: #561825; color: #ffe0e6; }

            QSplitter::handle:horizontal { background: #0d8f54; width: 3px; margin: 0 1px; }
            QSplitter::handle:vertical { background: #0d8f54; height: 3px; margin: 1px 0; }
            QMainWindow::separator { background: #0d8f54; width: 3px; height: 3px; }

            QScrollBar:vertical, QScrollBar:horizontal {
                background: #021002; border: 1px solid #0b7c49; margin: 0px; width: 10px; height: 10px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #1ce08c; border-radius: 5px; min-width: 8px; min-height: 20px;
            }
            QScrollBar::add-line, QScrollBar::sub-line { background: transparent; border: none; height: 0px; width: 0px; }
            QScrollBar::add-page, QScrollBar::sub-page { background: #021002; }

            QStatusBar { background: #041508; color: #7affbf; border-top: 1px solid #0d8f54; }
            QStatusBar::item { border: 1px solid #0b7c49; }
            QSizeGrip { background: #041508; border: 1px solid #0b7c49; }
            #lineNumberArea { background: #041508; border-right: 1px solid #0b7c49; }

            QLineEdit, QSpinBox { min-height: 22px; padding: 0 6px; }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: padding; width: 14px; background: #041909; border-left: 1px solid #0b7c49;
            }
            QSpinBox::up-button { border-bottom: 1px solid #0b7c49; }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #0d3a21; }
            QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; width: 0px; height: 0px; }
            QSpinBox::up-arrow {
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-bottom: 6px solid #8affcb; margin-top: 1px;
            }
            QSpinBox::down-arrow {
                border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 6px solid #8affcb; margin-bottom: 1px;
            }
            QComboBox::drop-down { border: 1px solid #0b7c49; background: #041909; }
            QComboBox::down-arrow {
                image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 6px solid #8affcb;
            }

            QMenu { background: #031003; color: #80ffc6; border: 1px solid #0b7c49; }
            QMenu::item:selected { background: #0f3b1f; }
            QTreeView#completionPopup {
                background: rgba(3, 16, 3, 232);
                color: #8dffd0;
                border: 2px solid #18d77f;
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
                border: 1px solid #0d8f54;
                border-left: none;
                border-top: none;
                padding: 2px 6px;
                font-size: 9pt;
            }
            QToolTip { background: #031003; color: #bfffe0; border: 1px solid #0b7c49; }
            QDialog { background: #030a03; color: #80ffc6; border: 1px solid #0d8f54; }

            QDockWidget#helpDock { background: #030a03; color: #80ffc6; border: 1px solid #0b7c49; }
            QDockWidget#helpDock::title {
                background: #06210d; border-bottom: 1px solid #0d8f54; color: #bfffe0; padding: 7px 8px;
            }
            QDockWidget#helpDock::close-button, QDockWidget#helpDock::float-button {
                border: 1px solid #0b7c49; background: #041909; width: 14px; height: 14px;
            }
            QDockWidget#helpDock::close-button:hover, QDockWidget#helpDock::float-button:hover { background: #0d3a21; }
            QTextBrowser#helpBrowser { background: #021002; color: #8dffd0; }
            """
        )

    def new_file(self) -> None:
        self.editor.clear()
        self.current_file = None
        self.statusBar().showMessage("New file", 2000)

    def open_file(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Assembly",
            "",
            "AMB Assembly (*.ambasm)",
        )
        if not path:
            return
        with open(path, "r", encoding="utf-8") as handle:
            self.editor.setPlainText(handle.read())
        self.current_file = path
        self.statusBar().showMessage(f"Opened {path}", 3000)

    def save_file(self) -> None:
        if not self.current_file:
            self.save_file_as()
            return
        with open(self.current_file, "w", encoding="utf-8") as handle:
            handle.write(self.editor.toPlainText())
        self.statusBar().showMessage(f"Saved {self.current_file}", 3000)

    def save_file_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
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
        self.update_register_view()
        self.update_memory_view()
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
        self.update_register_view()
        self.update_memory_view()
        self.highlight_line(self.addr_to_line.get(0))
        self.statusBar().showMessage("Reset", 2000)

    def step(self) -> None:
        if not self.program:
            self.assemble_source()
            if not self.program:
                return
        result = self.cpu.step()
        self.update_register_view()
        self.update_memory_view()
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

    def update_register_view(self) -> None:
        self.reg_table.setRowCount(len(REG_NAMES))
        for row, name in enumerate(REG_NAMES):
            val = self.cpu.registers[row] & WORD_MASK
            self.reg_table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            self.reg_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"0x{val:07X}"))

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
        self.mem_table.setRowCount(count)
        for i in range(count):
            addr = (start + i) & ADDR_MASK
            val = self.cpu.memory.read_byte(addr)
            self.mem_table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"0x{addr:07X}"))
            self.mem_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"0x{val:02X}"))

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
    try:
        fh_stream = open("assembler_faulthandler.log", "a", encoding="utf-8")
        faulthandler.enable(fh_stream)
    except Exception:
        pass

    app = QtWidgets.QApplication([])
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "amb.ico"
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
