"""Index a front-end codebase so findings can be mapped to files and lines.

The index is built by reading files as text with regular expressions; nothing is
parsed by a JavaScript engine and nothing is executed. It records, per file, the
ids, test ids, ARIA labels and classes the markup renders, a few accessibility
code patterns tied to catalog rules, and which components render which.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .secret_scan import is_blocked_path, redact

INDEX_VERSION = "code_index.v1"
SOURCE_EXTENSIONS = {
    ".html",
    ".htm",
    ".jsx",
    ".tsx",
    ".js",
    ".mjs",
    ".ts",
    ".vue",
    ".svelte",
    ".astro",
    ".erb",
    ".php",
    ".twig",
    ".hbs",
    ".handlebars",
    ".ejs",
    ".jinja",
    ".j2",
    ".njk",
    ".liquid",
    ".cshtml",
    ".razor",
    ".css",
    ".scss",
    ".sass",
    ".less",
}
STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less"}
MAX_FILE_BYTES = 512 * 1024
MAX_VALUES_PER_KEY = 20

ATTRIBUTE_PATTERNS = {
    "ids": re.compile(r"""\bid\s*=\s*\{?\s*["'`]([^"'`{}$<>\s]{1,128})["'`]"""),
    "test_ids": re.compile(r"""\bdata-testid\s*=\s*\{?\s*["'`]([^"'`{}$<>]{1,128})["'`]"""),
    "aria_labels": re.compile(r"""\baria-label\s*=\s*\{?\s*["'`]([^"'`{}$<>]{1,160})["'`]"""),
    "classes": re.compile(r"""\bclass(?:Name)?\s*=\s*\{?\s*["'`]([^"'`{}$<>]{1,300})["'`]"""),
}
CONTROL_TAG = re.compile(r"<(button|a\s|input|select|textarea|summary)\b", re.IGNORECASE)
ROLE_CONTROL = re.compile(r"""\brole\s*=\s*["'](button|link|checkbox|switch|tab|menuitem)["']""")
# Composite widgets (tabs, menus, listboxes) correctly use tabindex="-1" on all but one item.
ROVING_ROLE = re.compile(
    r"""\brole\s*=\s*["'](tab|option|menuitem\w*|treeitem|radio|gridcell)["']"""
)
TABINDEX = re.compile(r"""\btab[iI]ndex\s*=\s*\{?\s*["']?\s*(-?\d+)""")
CLICK_ON_NON_CONTROL = re.compile(
    r"""<(div|span|li|td|tr|img|p|section|article)\b[^>]*?\s"""
    r"""(onclick|onClick|@click|v-on:click|\(click\)|on:click)\s*=""",
    re.IGNORECASE,
)
FOCUS_NAVIGATION = re.compile(
    r"""\bon[Ff]ocus\s*=\s*[^>]*(location|navigate|router\.push|submit)"""
)
TAB_PREVENT = re.compile(r"""key\s*===?\s*["']Tab["'][^\n]{0,120}preventDefault""")
INPUT_TAG = re.compile(
    r"""<input\b(?![^>]*type\s*=\s*["']?(hidden|submit|button|reset|image))[^>]*>""", re.IGNORECASE
)
COMPONENT_DEFINITION = re.compile(
    r"""(?:export\s+(?:default\s+)?)?(?:function|const|class)\s+([A-Z][A-Za-z0-9]{1,60})\b"""
)
COMPONENT_USE = re.compile(r"""<([A-Z][A-Za-z0-9]{1,60})[\s/>]""")
STYLE_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
OUTLINE_REMOVED = re.compile(r"outline\s*:\s*(none|0)\b|outline-style\s*:\s*none", re.IGNORECASE)


@dataclass
class CodeIndex:
    files: list[dict[str, Any]] = field(default_factory=list)
    values: dict[str, dict[str, list[list[Any]]]] = field(
        default_factory=lambda: {key: {} for key in ATTRIBUTE_PATTERNS}
    )
    patterns: list[dict[str, Any]] = field(default_factory=list)
    components: dict[str, dict[str, Any]] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    controls: int = 0

    def summary(self) -> dict[str, int]:
        return {
            "files": len(self.files),
            "components": len(self.components),
            "controls": self.controls,
            "ids": len(self.values["ids"]),
            "test_ids": len(self.values["test_ids"]),
            "aria_labels": len(self.values["aria_labels"]),
            "patterns": len(self.patterns),
            "skipped_blocked": self.skipped.get("blocked", 0),
            "skipped_large": self.skipped.get("large", 0),
        }

    def to_json(self) -> dict[str, Any]:
        return {
            "version": INDEX_VERSION,
            "summary": self.summary(),
            "files": self.files,
            "values": self.values,
            "patterns": self.patterns,
            "components": self.components,
        }


def _add(store: dict[str, list[list[Any]]], value: str, path: str, line: int) -> None:
    locations = store.setdefault(value, [])
    if len(locations) < MAX_VALUES_PER_KEY:
        locations.append([path, line])


def _pattern(index: CodeIndex, kind: str, path: str, line: int, text: str) -> None:
    if len(index.patterns) < 2000:
        snippet = redact(text.strip()[:240])[0]
        index.patterns.append({"kind": kind, "path": path, "line": line, "snippet": snippet})


def _index_markup(index: CodeIndex, path: str, lines: list[str]) -> None:
    for number, line in enumerate(lines, start=1):
        for key, pattern in ATTRIBUTE_PATTERNS.items():
            for match in pattern.finditer(line):
                if key == "classes":
                    for name in match.group(1).split()[:12]:
                        _add(index.values[key], name, path, number)
                else:
                    _add(index.values[key], match.group(1).strip(), path, number)
        control = bool(CONTROL_TAG.search(line) or ROLE_CONTROL.search(line))
        if control:
            index.controls += 1
        for match in TABINDEX.finditer(line):
            value = int(match.group(1))
            if value < 0 and control and not ROVING_ROLE.search(line):
                _pattern(index, "tabindex_negative_on_control", path, number, line)
            elif value > 0:
                _pattern(index, "tabindex_positive", path, number, line)
        if CLICK_ON_NON_CONTROL.search(line) and not ROLE_CONTROL.search(line):
            _pattern(index, "click_handler_on_non_control", path, number, line)
        if FOCUS_NAVIGATION.search(line):
            _pattern(index, "navigation_on_focus", path, number, line)
        if TAB_PREVENT.search(line):
            _pattern(index, "tab_keydown_prevent_default", path, number, line)
        for match in INPUT_TAG.finditer(line):
            tag = match.group(0)
            wrapped = "<label" in line[: match.start()]
            if not wrapped and not any(
                attribute in tag
                for attribute in ("aria-label", "aria-labelledby", " id=", "title=")
            ):
                _pattern(index, "unlabelled_input", path, number, line)
        for match in COMPONENT_DEFINITION.finditer(line):
            entry = index.components.setdefault(match.group(1), {"defined_in": [], "used_in": []})
            if [path, number] not in entry["defined_in"] and len(entry["defined_in"]) < 5:
                entry["defined_in"].append([path, number])
        for match in COMPONENT_USE.finditer(line):
            entry = index.components.setdefault(match.group(1), {"defined_in": [], "used_in": []})
            if [path, number] not in entry["used_in"] and len(entry["used_in"]) < 40:
                entry["used_in"].append([path, number])


def _index_styles(index: CodeIndex, path: str, text: str) -> None:
    for match in STYLE_RULE.finditer(text):
        selector, body = match.group(1), match.group(2)
        if ":focus" in selector and OUTLINE_REMOVED.search(body) and "box-shadow" not in body:
            line = text.count("\n", 0, match.start(2)) + 1
            snippet = (
                selector.strip()[-80:].split(">")[-1].strip() + " { " + body.strip()[:120] + " }"
            )
            _pattern(index, "outline_removed_on_focus", path, line, snippet)


def build_index(root: Path) -> CodeIndex:
    """Index every readable front-end source file under ``root``."""
    index = CodeIndex()
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue  # Outside the snapshot: never read.
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if is_blocked_path(relative):
            index.skipped["blocked"] += 1
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            index.skipped["large"] += 1
            continue
        text = redact(path.read_text(encoding="utf-8", errors="replace"))[0]
        lines = text.splitlines()
        index.files.append(
            {
                "path": relative,
                "lines": len(lines),
                "sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16],
            }
        )
        if path.suffix.lower() in STYLE_EXTENSIONS:
            _index_styles(index, relative, text)
        else:
            _index_markup(index, relative, lines)
            if "<style" in text:
                _index_styles(index, relative, text)
        if path.suffix.lower() in {".vue", ".svelte", ".astro"}:
            name = path.stem[:1].upper() + path.stem[1:]
            entry = index.components.setdefault(name, {"defined_in": [], "used_in": []})
            entry["defined_in"].append([relative, 1])
    # Keep only components that are actually defined in this codebase.
    index.components = {
        name: entry for name, entry in index.components.items() if entry["defined_in"]
    }
    return index


def save_index(index: CodeIndex, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index.to_json()), encoding="utf-8")


def load_index(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
