"""Map a finding to the files and lines that need to change, and suggest a fix.

Three columns, as on the report:

* exact   - rule-based: the element's test id, id, ARIA label or framework source
            hint found in the index, or a known code pattern on a line that also
            carries the element's own attributes. High confidence.
* likely  - the control's visible text or class names found in the code (rule-based),
            or the AI search agent's answer when one is allowed to read the code.
* related - components that render the matched file, and the same pattern in
            other files.

Every snippet passes the secret scanner first. A fix is a unified diff for people
to review; it is never applied to the repository.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .secret_scan import redact

MAX_PER_COLUMN = 5
SNIPPET_CONTEXT = 2


@dataclass
class CodeLocation:
    path: str
    line: int
    confidence: str
    reason: str
    snippet: str = ""
    source: str = "index"


@dataclass
class FixSuggestion:
    path: str
    line: int
    title: str
    steps: list[str]
    patch: str = ""
    # Line number -> replacement text, for the reviewable patch and fixture verification.
    edits: dict[int, str] = field(default_factory=dict)


@dataclass
class LocatorResult:
    exact: list[CodeLocation] = field(default_factory=list)
    likely: list[CodeLocation] = field(default_factory=list)
    related: list[CodeLocation] = field(default_factory=list)
    fix: FixSuggestion | None = None
    notes: list[str] = field(default_factory=list)
    ai_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "exact": [asdict(item) for item in self.exact],
            "likely": [asdict(item) for item in self.likely],
            "related": [asdict(item) for item in self.related],
            "fix": asdict(self.fix) if self.fix else None,
            "notes": self.notes,
            "ai_used": self.ai_used,
        }


class SourceReader:
    """Read lines from the snapshot, only for files the index lists."""

    def __init__(self, root: Path, index: dict[str, Any]) -> None:
        self.root = root.resolve()
        self.files = {item["path"]: item for item in index.get("files", [])}
        self._cache: dict[str, list[str]] = {}

    def lines(self, path: str) -> list[str]:
        if path not in self.files:
            return []
        if path not in self._cache:
            target = (self.root / path).resolve()
            try:
                target.relative_to(self.root)
            except ValueError:
                return []
            if target.is_symlink() or not target.is_file():
                return []
            text = target.read_text(encoding="utf-8", errors="replace")
            # Redact the whole file first, so secrets spanning lines (PEM keys) never leak.
            self._cache[path] = redact(text)[0].splitlines()
        return self._cache[path]

    def snippet(self, path: str, line: int, context: int = SNIPPET_CONTEXT) -> str:
        lines = self.lines(path)
        if not lines:
            return ""
        start, end = max(1, line - context), min(len(lines), line + context)
        text = "\n".join(
            f"{number:>4}  {lines[number - 1][:200]}" for number in range(start, end + 1)
        )
        return redact(text)[0]

    def search(self, needle: str, limit: int = 10) -> list[tuple[str, int, str]]:
        hits = []
        for path in self.files:
            for number, text in enumerate(self.lines(path), start=1):
                if needle in text:
                    hits.append((path, number, redact(text.strip()[:200])[0]))
                    if len(hits) >= limit:
                        return hits
        return hits


def _attribute_tokens(element: dict[str, Any]) -> list[str]:
    tokens = []
    if element.get("test_id"):
        tokens.append(element["test_id"])
    if element.get("dom_id"):
        tokens.append(element["dom_id"])
    tokens.extend(name for name in element.get("classes") or [] if len(name) >= 3)
    return tokens


def _add(column: list[CodeLocation], location: CodeLocation) -> None:
    if len(column) >= MAX_PER_COLUMN:
        return
    if any(item.path == location.path and item.line == location.line for item in column):
        return
    column.append(location)


def _match_source_hint(element: dict[str, Any], reader: SourceReader) -> CodeLocation | None:
    hint = element.get("source_file")
    if not hint:
        return None
    hint = hint.replace("\\", "/")
    for path in reader.files:
        if hint.endswith(path) or path.endswith(hint.split("/src/", 1)[-1]):
            try:
                line = int(element.get("source_line") or 1)
            except (TypeError, ValueError):
                line = 1
            line = min(max(line, 1), max(len(reader.lines(path)), 1))
            return CodeLocation(
                path,
                line,
                "high",
                f"{element.get('framework', 'Framework')} source hint from the page",
            )
    return None


def locate_rule_based(
    finding: dict[str, Any],
    index: dict[str, Any],
    reader: SourceReader,
    *,
    rule_patterns: list[str],
) -> LocatorResult:
    result = LocatorResult()
    element = finding.get("element") or {}
    values = index.get("values", {})
    seen_paths: set[str] = set()

    page_path = urlparse(finding.get("url", "")).path.strip("/")
    pattern_lines = {
        (item["path"], item["line"]): item["kind"]
        for item in index.get("patterns", [])
        if item["kind"] in rule_patterns
    }
    candidates: list[tuple[int, CodeLocation]] = []

    def score(path: str, line: int) -> int:
        value = 0
        if (path, line) in pattern_lines:
            value += 3  # The rule's own code pattern sits on this line.
        if page_path and (path.endswith(page_path) or page_path.endswith(path)):
            value += 2  # The file is the page the finding happened on.
        elif page_path and Path(path).stem == Path(page_path).stem:
            value += 1
        return value

    hinted = _match_source_hint(element, reader)
    if hinted:
        candidates.append((10, hinted))

    lookups = (
        ("test_ids", element.get("test_id"), "data-testid=\u201c{}\u201d"),
        ("ids", element.get("dom_id"), "id=\u201c{}\u201d"),
        ("aria_labels", element.get("name"), "aria-label=\u201c{}\u201d"),
    )
    for key, value, label in lookups:
        if not value:
            continue
        for path, line in values.get(key, {}).get(value, [])[:20]:
            reason = f"Renders {label.format(value)}"
            if (path, line) in pattern_lines:
                reason += f" with {pattern_lines[(path, line)].replace('_', ' ')}"
            candidates.append((score(path, line), CodeLocation(path, line, "high", reason)))

    tokens = _attribute_tokens(element)
    name_text = (element.get("name") or "").strip()
    if len(name_text) >= 3:
        tokens.append(f">{name_text}<")
    for (path, line), kind in pattern_lines.items():
        snippet = next(
            (
                item["snippet"]
                for item in index.get("patterns", [])
                if item["path"] == path and item["line"] == line
            ),
            "",
        )
        on_line = [token for token in tokens if token in snippet]
        if on_line:
            candidates.append(
                (
                    score(path, line),
                    CodeLocation(
                        path,
                        line,
                        "high",
                        f"{kind.replace('_', ' ')} on the line that renders {on_line[0]}",
                        source="pattern",
                    ),
                )
            )

    ranked = sorted(candidates, key=lambda item: -item[0])
    best = ranked[0][0] if ranked else 0
    for value, location in ranked:
        if best >= 2 and value < best:
            # The same attribute on a page other than the one tested: weaker evidence.
            location.confidence = "medium"
            location.reason += " (on a different page from the one tested)"
        location.snippet = location.snippet or reader.snippet(location.path, location.line)
        _add(result.exact, location)
        seen_paths.add(location.path)

    if not result.exact:
        name = (element.get("name") or "").strip()
        if len(name) >= 3:
            hits = reader.search(f">{name}<", limit=20) + reader.search(name, limit=20)

            def text_score(item: tuple[str, int]) -> int:
                tag_content = f">{name}<" in reader.lines(item[0])[item[1] - 1]
                return score(*item) + (2 if tag_content else 0)

            ranked = sorted(
                dict.fromkeys((path, line) for path, line, _text in hits),
                key=lambda item: -text_score(item),
            )
            for path, line in ranked[:MAX_PER_COLUMN]:
                _add(
                    result.likely,
                    CodeLocation(
                        path,
                        line,
                        "medium",
                        f"Contains the control's text “{name[:60]}”",
                        reader.snippet(path, line),
                        "text",
                    ),
                )
        classes = [name for name in element.get("classes") or [] if len(name) >= 3]
        if classes and len(result.likely) < MAX_PER_COLUMN:
            for path, line, _text in reader.search(classes[0], limit=MAX_PER_COLUMN):
                text = reader.lines(path)[line - 1]
                if all(name in text for name in classes):
                    _add(
                        result.likely,
                        CodeLocation(
                            path,
                            line,
                            "medium",
                            f"Uses the classes {' '.join(classes)}",
                            reader.snippet(path, line),
                            "text",
                        ),
                    )
        if not result.likely:
            for item in index.get("patterns", []):
                if item["kind"] in rule_patterns:
                    _add(
                        result.likely,
                        CodeLocation(
                            item["path"],
                            item["line"],
                            "low",
                            f"A {item['kind'].replace('_', ' ')} pattern this rule often "
                            f"comes from",
                            reader.snippet(item["path"], item["line"]),
                            "pattern",
                        ),
                    )

    anchor_paths = [item.path for item in result.exact] or [item.path for item in result.likely[:1]]
    components = index.get("components", {})
    for name, entry in components.items():
        if any(defined[0] in anchor_paths for defined in entry.get("defined_in", [])):
            for path, line in entry.get("used_in", [])[:MAX_PER_COLUMN]:
                if path not in anchor_paths:
                    _add(
                        result.related,
                        CodeLocation(
                            path,
                            line,
                            "medium",
                            f"Renders the <{name}> component",
                            reader.snippet(path, line, 0),
                            "component",
                        ),
                    )
    for item in index.get("patterns", []):
        if item["kind"] in rule_patterns and item["path"] not in anchor_paths:
            _add(
                result.related,
                CodeLocation(
                    item["path"],
                    item["line"],
                    "low",
                    f"Same {item['kind'].replace('_', ' ')} pattern",
                    reader.snippet(item["path"], item["line"], 0),
                    "pattern",
                ),
            )
    return result


# Fixes ---------------------------------------------------------------------------

_TABINDEX_NEGATIVE = re.compile(r"""\s+tab[iI]ndex\s*=\s*(?:"-\d+"|'-\d+'|\{\s*-\d+\s*\})""")
_ONFOCUS = re.compile(r"""\s+on[Ff]ocus\s*=\s*(?:"[^"]*"|'[^']*'|\{[^}]*\})""")
_OUTLINE = re.compile(r"outline\s*:\s*(none|0)\s*;?", re.IGNORECASE)
_CLICKABLE_TAG = re.compile(r"<(div|span|li|p)\b", re.IGNORECASE)


def _diff(path: str, before: list[str], edits: dict[int, str]) -> str:
    """A reviewable unified diff for the edited lines; never applied automatically."""
    after = list(before)
    for number, replacement in edits.items():
        after[number - 1] = replacement
    return "".join(
        difflib.unified_diff(
            [line + "\n" for line in before],
            [line + "\n" for line in after],
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=2,
        )
    )


def suggest_fix(
    rule_id: str, element: dict[str, Any], result: LocatorResult, reader: SourceReader
) -> FixSuggestion | None:
    target = (result.exact or result.likely or [None])[0]
    if target is None:
        return None
    lines = reader.lines(target.path)
    if not lines or not 1 <= target.line <= len(lines):
        return None
    original = lines[target.line - 1]
    path, number = target.path, target.line
    name = element.get("name") or "this control"

    if rule_id == "keyboard-operable" and _TABINDEX_NEGATIVE.search(original):
        # Fix every copy in the same file (three identical slot buttons need three edits).
        numbers = sorted(
            {number}
            | {
                item.line
                for item in result.exact + result.related
                if item.path == path and _TABINDEX_NEGATIVE.search(lines[item.line - 1])
            }
        )
        edits = {item: _TABINDEX_NEGATIVE.sub("", lines[item - 1], count=1) for item in numbers}
        return FixSuggestion(
            path,
            number,
            "Put the control back in the Tab order",
            [
                'Remove tabindex="-1" so Tab reaches the control again.',
                f"The patch changes {len(edits)} line{'s' if len(edits) != 1 else ''}; check "
                f"other files in Also affected.",
            ],
            _diff(path, lines, edits),
            edits,
        )
    if (
        rule_id == "keyboard-operable"
        and _CLICKABLE_TAG.search(original)
        and re.search(r"on[Cc]lick|@click|\(click\)", original)
    ):
        tag = _CLICKABLE_TAG.search(original).group(1)
        new = _CLICKABLE_TAG.sub('<button type="button"', original, count=1)
        new = re.sub(rf"</{tag}>", "</button>", new, count=1)
        new = re.sub(r"""\s+role\s*=\s*["']button["']""", "", new, count=1)
        new = re.sub(r"""\s+tab[iI]ndex\s*=\s*["']?0["']?""", "", new, count=1)
        return FixSuggestion(
            path,
            number,
            "Use a real button",
            [
                f'Replace the <{tag}> with <button type="button"> so it is focusable and '
                f'works with Enter and Space.',
                "Move any visual styling onto the button; browsers give it focus and "
                "keyboard support for free.",
            ],
            _diff(path, lines, {number: new}),
            {number: new},
        )
    if rule_id == "keyboard-operable":
        return FixSuggestion(
            path,
            number,
            "Make the control work with Enter and Space",
            [
                "Prefer a native <button> or <a href>; they handle Enter and Space automatically.",
                'If it must stay custom: add tabindex="0", the right role, and a keydown '
                'handler for Enter and Space.',
            ],
        )
    if rule_id == "focus-visible" and _OUTLINE.search(original):
        new = _OUTLINE.sub(
            "outline: 3px solid currentColor; outline-offset: 2px;", original, count=1
        )
        return FixSuggestion(
            path,
            number,
            "Bring back a visible focus indicator",
            [
                "Replace outline: none with a clear outline on :focus-visible.",
                "Check the colour contrasts with both the control and the page background.",
            ],
            _diff(path, lines, {number: new}),
            {number: new},
        )
    if rule_id == "on-focus" and _ONFOCUS.search(original):
        new = _ONFOCUS.sub("", original, count=1)
        return FixSuggestion(
            path,
            number,
            "Do not navigate when focus arrives",
            [
                "Remove the focus handler that changes the page.",
                "Navigate from a click or Enter instead (a normal link already does this).",
            ],
            _diff(path, lines, {number: new}),
            {number: new},
        )
    if rule_id == "name-role-value":
        tag_match = re.search(r"<(input|button|a)\b", original)
        if tag_match and "aria-label" not in original:
            new = (
                original[: tag_match.end()]
                + ' aria-label="Describe what this does"'
                + original[tag_match.end() :]
            )
            return FixSuggestion(
                path,
                number,
                "Give the control an accessible name",
                [
                    "Add an aria-label (or a <label>) that says what the control does, e.g. "
                    "“Mark Buy milk as complete”.",
                    "Replace the placeholder text in the patch with a real description.",
                ],
                _diff(path, lines, {number: new}),
                {number: new},
            )
    if rule_id == "no-keyboard-trap":
        return FixSuggestion(
            path,
            number,
            "Let Tab leave the component",
            [
                "Remove the keydown handler that cancels Tab or moves focus back.",
                "In a modal dialog, let Escape close it and return focus to the control that "
                "opened it.",
            ],
        )
    if rule_id == "focus-not-obscured":
        return FixSuggestion(
            path,
            number,
            "Stop the fixed header covering focus",
            [
                "Add html { scroll-padding-top: <header height>; } so focused controls "
                "scroll clear of it.",
                f"Check “{name}” is fully visible when it has focus.",
            ],
        )
    if rule_id == "bypass-blocks":
        return FixSuggestion(
            path,
            number,
            "Add a way to skip the navigation",
            [
                'Add <a href="#main">Skip to main content</a> as the first focusable element.',
                'Wrap the page content in <main id="main">.',
            ],
        )
    return None


def locate(
    finding: dict[str, Any],
    index: dict[str, Any],
    root: Path,
    *,
    rule_patterns: list[str],
    ai_search=None,
) -> LocatorResult:
    """Run the rule-based locator, then the AI search when nothing exact was found."""
    reader = SourceReader(root, index)
    result = locate_rule_based(finding, index, reader, rule_patterns=rule_patterns)
    if not result.exact and ai_search is not None:
        try:
            answers, note = ai_search(finding, reader)
        except Exception as error:  # The AI is optional; never lose the rule-based answer.
            result.notes.append(f"The AI search stopped ({type(error).__name__}).")
        else:
            if answers:
                result.ai_used = True
                result.likely = answers + result.likely
                result.likely = result.likely[:MAX_PER_COLUMN]
            if note:
                result.notes.append(note)
    if not (result.exact or result.likely):
        result.notes.append(
            "No matching code was found; the element may come from a library or a CMS."
        )
    result.fix = suggest_fix(
        finding.get("rule_id", ""), finding.get("element") or {}, result, reader
    )
    if result.fix is not None:
        result.fix.patch, _found = redact(result.fix.patch)
        clean_edits = {number: redact(text)[0] for number, text in result.fix.edits.items()}
        if clean_edits != result.fix.edits:
            # Never store a secret; without the exact line the fix can only be shown, not verified.
            result.fix.edits = {}
    return result
