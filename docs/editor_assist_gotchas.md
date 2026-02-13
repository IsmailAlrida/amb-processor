# Editor Assist Gotchas (Autocomplete + Lint)

This document tracks the practical issues we hit while adding editor assist to
the AMB assembler UI and how each one was fixed.

## 1) Autocomplete signal payload mismatch

Gotcha:
- `QCompleter.activated` can emit different payload types depending on the
  binding/overload.
- If a slot expects `str` but receives `QModelIndex`, the editor can fail while
  typing/selecting completions.

Fix:
- Connect explicit overload: `activated[str]`.
- Defensive insert path still supports `QModelIndex` payload by reading column 0.

## 2) Completer not explicitly bound to editor widget

Gotcha:
- Popup completion can behave unpredictably if the completer is not explicitly
  attached to the active text widget.

Fix:
- Call `self._completer.setWidget(self)` on setup and in `focusInEvent`.

## 3) Updating completion model while popup is visible

Gotcha:
- Live model updates while the popup is open can cause unstable popup state.

Fix:
- Hide popup before model updates.
- Rebuild model safely and re-open completion only through controlled paths.

## 4) Autocomplete UX needed type metadata

Gotcha:
- Single-column suggestions are ambiguous for assembly where tokens are short.

Fix:
- Switched to a two-column completion model:
  - Column 1: token
  - Column 2: type/category
- Category labels currently include:
  - `FUNCTION` (RR ops)
  - `CONTROL` (GEN ops)
  - `IMMEDIATE` (IMM ops)
  - `JUMP` (jump ops)
  - `REGISTER` (register names)
  - `LABEL` (labels discovered in the current source)

## 5) Tab/Enter behavior for popup acceptance

Gotcha:
- Key handling that only ignores events when popup is visible can leave
  acceptance behavior inconsistent.

Fix:
- `Tab`, `Enter`, and `Return` now accept the currently highlighted completion.
- `Esc` and `Backtab` close the popup.

## 6) Linter should not crash editor on typing

Gotcha:
- Running `assemble()` on each text change can surface parse exceptions while
  the user is mid-typing.
- Any unhandled exception in lint/autocomplete code can terminate the app loop.

Fix:
- Linting is structure-first (mnemonic/operand checks) with deterministic rules.
- Full `assemble()` is used only as a secondary validation stage.
- All lint/completion handlers catch non-fatal exceptions and print diagnostics
  instead of propagating into the main UI loop.

## 7) Red squiggles should be token-level, not whole line

Gotcha:
- Whole-line underlines are noisy and hide the true syntax problem location.

Fix:
- `QSyntaxHighlighter` now stores and applies `(start, length)` spans per line.
- Wave underline is applied only to the offending token.

## 8) Crash observability

Gotcha:
- GUI app exits can appear "silent" if exception output is not captured.

Fix:
- Added global exception hook and fault handler logging:
  - `assembler_crash.log` (Python exceptions)
  - `assembler_faulthandler.log` (native faults)

## 9) Completion popup readability / UX density

Gotcha:
- A narrow popup with default sizing can clip token/type information and force
  unnecessary horizontal or constant vertical scrolling.

Fix:
- Popup width is now computed dynamically from both columns with a larger floor.
- Visible-row count is scaled against available screen height.
- Popup style tuned for terminal theme:
  - stronger green outline
  - slight transparency
  - square corners
  - slightly smaller popup font for denser lists

## Operational note

Assembler parse issues are treated as editor diagnostics, not fatal runtime
errors. They should render squiggles/status feedback and keep the editor alive.
