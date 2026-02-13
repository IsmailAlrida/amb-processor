"""PyQt6 UI for the AMB assembler simulator."""

from __future__ import annotations

import textwrap

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


class CodeEditor(QtWidgets.QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        self._apply_caret_palette()

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


class TitleBar(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self._drag_pos: QtCore.QPoint | None = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.title_label = QtWidgets.QLabel(parent.windowTitle())
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.min_btn = QtWidgets.QPushButton("-")
        self.min_btn.setObjectName("titleButton")
        self.max_btn = QtWidgets.QPushButton("MAX")
        self.max_btn.setObjectName("titleButton")
        self.close_btn = QtWidgets.QPushButton("X")
        self.close_btn.setObjectName("titleClose")

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

        self._build_ui()
        self.update_register_view()
        self.update_memory_view()

    def _build_ui(self) -> None:
        self._apply_style()
        self._build_titlebar()
        self._build_toolbar()
        self._build_help_dock()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

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

    def _build_toolbar(self) -> None:
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setMovable(False)
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
        add_action("Help", self.show_help)

    def _build_titlebar(self) -> None:
        self.title_bar = TitleBar(self)
        self.setMenuWidget(self.title_bar)

    def _build_help_dock(self) -> None:
        self.help_dock = QtWidgets.QDockWidget("AMB Assembly Help", self)
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
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_help_html())
        layout.addWidget(browser, 1)

        self.help_dock.setWidget(panel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.help_dock)
        self.help_dock.hide()

    def _build_help_html(self) -> str:
        def build_table(rows: list[tuple[str, str, str]]) -> str:
            body = "\n".join(
                "<tr>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px;'>{mnem}</td>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px;'><code>{syntax}</code></td>"
                f"<td style='border: 1px solid #0a3; padding: 4px 6px;'>{note}</td>"
                "</tr>"
                for mnem, syntax, note in rows
            )
            return (
                "<table style='width: 100%; border-collapse: collapse; border: 1px solid #0a3;'>"
                "<tr>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Mnemonic</th>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Syntax</th>"
                "<th style='border: 1px solid #0a3; background: #041; color: #7CFFAA; padding: 4px 6px;'>Notes</th>"
                "</tr>"
                f"{body}</table>"
            )

        rr_syntax = {mnem: f"{mnem} Ra, Rb" for mnem in RR_OPCODES}
        rr_notes = {
            "NOT": "Ra = ~Ra (Rb ignored)",
            "OR": "Ra = Ra | Rb",
            "AND": "Ra = Ra & Rb",
            "XOR": "Ra = Ra ^ Rb",
            "SHL": "Ra = Ra << (Rb[4:0]); SHC = shift count",
            "SHR": "Ra = Ra >> (Rb[4:0]); SHC = shift count",
            "SAR": "Ra = arithmetic_shift_right(Ra, Rb[4:0]); SHC = shift count",
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
        <div style="font-family: 'Cascadia Mono', Consolas, monospace; font-size: 12px;">
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
        <pre>
RR:  opcode7 | Ra | Rb
GEN: opcode7 only
IMM: opcode3 | Ra | imm8
JMP: opcode4 | imm11
        </pre>
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
        <pre>
label: ADD R0, R1
       JMP label

Comments: // ; #
        </pre>
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
            QMainWindow { background: #050805; color: #00ff6a; border: 1px solid #0a3; }
            QWidget { color: #00ff6a; }
            QPlainTextEdit, QTableWidget, QLineEdit, QSpinBox, QComboBox, QTreeView, QTextBrowser {
                background: #020b02; color: #00ff6a; border: 1px solid #0a3;
            }
            QPlainTextEdit:focus, QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #7CFFAA;
            }
            QPlainTextEdit {
                selection-background-color: #0b2b0b;
                selection-color: #7CFFAA;
            }
            QTableWidget::item { background: #020b02; color: #00ff6a; }
            QTableWidget::item:selected { background: #0b2b0b; color: #7CFFAA; }
            QTableCornerButton::section { background: #041; border: 1px solid #0a3; }
            QHeaderView::section {
                background: #041; color: #7CFFAA; border: 1px solid #0a3; padding: 4px;
            }
            #titleBar { background: #00ff6a; border-bottom: 1px solid #0a3; }
            #titleLabel { color: #001; font-weight: 700; }
            QPushButton#titleButton {
                background: #00ff6a; color: #001; border: 1px solid #0a3; padding: 2px 8px;
            }
            QPushButton#titleButton:hover { background: #7CFFAA; }
            QPushButton#titleClose {
                background: #00ff6a; color: #001; border: 1px solid #0a3; padding: 2px 8px;
            }
            QPushButton#titleClose:hover { background: #0a3; color: #001; }
            QLabel { color: #7CFFAA; font-weight: 600; }
            QPushButton {
                background: #020b02; color: #00ff6a; border: 1px solid #0a3; padding: 4px 10px;
            }
            QPushButton:hover { background: #033; }
            QPushButton:pressed { background: #0a3; color: #001; }
            QToolBar { background: #020b02; border-bottom: 1px solid #0a3; }
            QToolButton {
                background: #020b02; color: #00ff6a; padding: 4px 8px; border: 1px solid #0a3;
            }
            QToolButton:hover { background: #033; }
            QToolBar::separator { background: #0a3; width: 1px; margin: 4px; }
            QSplitter::handle { background: #0a3; }
            QMainWindow::separator { background: #0a3; width: 6px; height: 6px; }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: transparent; border: none; margin: 0px; width: 6px; height: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #00ff6a; border-radius: 6px; min-width: 6px; min-height: 16px;
            }
            QScrollBar::add-line, QScrollBar::sub-line { background: #020b02; border: none; }
            QScrollBar::add-page, QScrollBar::sub-page { background: #020b02; }
            QStatusBar { background: #020b02; color: #00ff6a; }
            QStatusBar::item { border: 1px solid #0a3; }
            QSizeGrip { background: #020b02; border: 1px solid #0a3; }
            #lineNumberArea { background: #020b02; border-right: 1px solid #0a3; }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: border; width: 16px; background: #020b02; border: 1px solid #0a3;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #033; }
            QSpinBox::up-arrow, QSpinBox::down-arrow { width: 7px; height: 7px; }
            QSpinBox::up-arrow { image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-bottom: 5px solid #00ff6a; }
            QSpinBox::down-arrow { image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 5px solid #00ff6a; }
            QComboBox::drop-down { border: 1px solid #0a3; background: #020b02; }
            QComboBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 6px solid #00ff6a; }
            QMenu { background: #020b02; color: #00ff6a; border: 1px solid #0a3; }
            QMenu::item:selected { background: #0b2b0b; }
            QToolTip { background: #020b02; color: #7CFFAA; border: 1px solid #0a3; }
            QDialog { background: #050805; color: #00ff6a; border: 1px solid #0a3; }
            QDockWidget { background: #050805; color: #00ff6a; border: 1px solid #0a3; }
            QDockWidget::title {
                background: #020b02; border-bottom: 1px solid #0a3; padding: 6px;
            }
            QDockWidget::close-button, QDockWidget::float-button {
                border: 1px solid #0a3; background: #020b02; width: 14px; height: 14px;
            }
            QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: #033; }
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
            self.statusBar().showMessage(str(exc), 5000)
            self.highlight_line(exc.line_no)
            return

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


def main() -> None:
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon("assets/amb.ico"))
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
    window.show()
    app.exec()
