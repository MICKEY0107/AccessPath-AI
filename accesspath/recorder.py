"""Record a person's own keyboard journey, and save a signed-in session.

``accesspath record URL`` opens a browser window; every key the person presses (Tab,
Shift+Tab, Enter, Space, Escape, arrows, and typed text) is captured as a scripted
plan. Closing the window ends the recording, and the journey file it writes can be
replayed anywhere with ``accesspath run`` (no AI), in CI or on the web app.

``accesspath login URL`` opens a window to sign in by hand and saves the session
(cookies and storage) for journeys behind a login. The password is never seen or
stored; the session file is as sensitive as one, so keep it out of the repository.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from .journey_file import SCHEMA, JourneyFileV1, PlanStepV1

_KEYS = {
    "Tab": "tab",
    "Enter": "enter",
    " ": "space",
    "Escape": "escape",
    "ArrowUp": "arrow_up",
    "ArrowDown": "arrow_down",
    "ArrowLeft": "arrow_left",
    "ArrowRight": "arrow_right",
}

_LISTENER = """() => {
  if (window.__accesspathRecording) return;
  window.__accesspathRecording = true;
  const fields = new WeakMap();
  let nextField = 1;
  const fieldId = (el) => {
    if (!fields.has(el)) fields.set(el, nextField++);
    return fields.get(el);
  };
  const textLike = (el) => el && (el.isContentEditable || el.tagName === 'TEXTAREA' ||
    (el.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'reset', 'range',
      'color', 'file', 'image'].includes((el.type || 'text').toLowerCase())));
  const sensitive = (el) => el && el.tagName === 'INPUT' && (
    (el.type || '').toLowerCase() === 'password' ||
    /^(cc-|one-time-code)/.test((el.getAttribute('autocomplete') || '').toLowerCase()));
  const nameOf = (el) => (el && (el.getAttribute('aria-label') || el.textContent ||
    el.getAttribute('placeholder') || el.getAttribute('name') || '') || '').trim().slice(0, 80);
  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const text = textLike(target);
    const key = event.key;
    const modified = event.ctrlKey || event.metaKey;
    // Text, deletions and caret moves inside a text field arrive as its final value
    // through the input event below, so they replay exactly.
    if (text && (key.length === 1 || ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight',
        'Home', 'End'].includes(key) || (target.tagName === 'TEXTAREA' &&
        ['ArrowUp', 'ArrowDown'].includes(key)))) return;
    window.__accesspathKey({kind: 'key', key, shift: event.shiftKey, ctrl: modified,
      editable: Boolean(text), name: nameOf(target)});
  }, true);
  document.addEventListener('input', (event) => {
    const target = event.target;
    if (!textLike(target)) return;
    if (sensitive(target)) {
      window.__accesspathKey({kind: 'sensitive', field: fieldId(target)});
      return;
    }
    const value = target.isContentEditable ? target.textContent : target.value;
    window.__accesspathKey({kind: 'input', field: fieldId(target),
      value: String(value || '').slice(0, 500)});
  }, true);
  document.addEventListener('focusin', (event) => {
    window.__accesspathKey({kind: 'focus', name: nameOf(event.target)});
  }, true);
}"""


def steps_from_keys(events: list[dict[str, Any]]) -> list[PlanStepV1]:
    """Turn recorded events into plan steps.

    Typing in a field becomes one TYPE step with the field's final value (the replay
    selects the field and types it, so edits, deletions and caret moves come out right).
    Password and card fields are never recorded. Each Tab step is labelled with the
    control it reached.
    """
    steps: list[PlanStepV1] = []
    typing: str | None = None
    typing_field: Any = None

    def flush() -> None:
        nonlocal typing, typing_field
        if typing:
            steps.append(PlanStepV1(action="type", value=typing[:500], purpose="type text"))
        typing = None
        typing_field = None

    for event in events:
        kind = event.get("kind", "key")
        if kind == "sensitive":
            continue
        if kind == "input":
            if typing_field is not None and event.get("field") != typing_field:
                flush()
            typing = str(event.get("value") or "")
            typing_field = event.get("field")
            continue
        if kind == "focus":
            if steps and steps[-1].action in {"tab", "shift_tab"} and typing is None:
                hint = str(event.get("name") or "")[:120]
                steps[-1] = steps[-1].model_copy(
                    update={"target_hint": hint, "purpose": f"{steps[-1].action} to {hint}"[:200]}
                )
            continue
        key = str(event.get("key", ""))
        # Older recordings (and tests) send typed characters as keys.
        if event.get("editable") and len(key) == 1 and key != " " and not event.get("ctrl"):
            typing = (typing or "") + key
            continue
        if event.get("editable") and key == "Backspace" and typing:
            typing = typing[:-1]
            continue
        action = _KEYS.get(key)
        if action is None:
            continue  # Shift, Control, function keys and the like are not plan steps.
        if action == "space" and event.get("editable"):
            typing = (typing or "") + " "
            continue
        flush()
        if action == "tab" and event.get("shift"):
            action = "shift_tab"
        hint = str(event.get("name") or "")[:120]
        steps.append(
            PlanStepV1(action=action, target_hint=hint, purpose=f"{action} on {hint}"[:200])
        )
    flush()
    return steps


def _attach(page: Page, events: list[dict[str, Any]]) -> None:
    page.expose_binding("__accesspathKey", lambda source, event: events.append(event))
    page.add_init_script(f"({_LISTENER})()")
    page.evaluate(_LISTENER)


def record_journey(
    url: str,
    out: Path,
    *,
    name: str,
    goal: str,
    headless: bool = False,
    drive: Callable[[Page], None] | None = None,
    success_url: str | None = None,
    success_text: str | None = None,
) -> Path:
    """Record until the window closes (or ``drive`` returns, in tests); write a journey."""
    events: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        last_url = [url]
        page.on(
            "framenavigated",
            lambda frame: last_url.__setitem__(0, frame.url) if frame == page.main_frame else None,
        )
        page.goto(url, wait_until="domcontentloaded")
        _attach(page, events)
        if drive is not None:
            drive(page)
        else:
            print("Recording: use only the keyboard in the browser window, then close it.")
            page.wait_for_event("close", timeout=0)
        final_url = last_url[0]
        context.close()
        browser.close()
    steps = steps_from_keys(events)
    if any(event.get("kind") == "sensitive" for event in events):
        print(
            "Typing in password and card fields was not recorded. For pages behind a "
            "login, use `accesspath login` and run with --session."
        )
    if not steps:
        raise ValueError("No keyboard steps were recorded.")
    if not (success_url or success_text):
        if final_url.split("#")[0] == url.split("#")[0]:
            raise ValueError(
                "The recording ended on the start page; say how to tell the journey "
                "succeeded with --success-text or --success-url."
            )
        success_url = urlparse(final_url).path or "/"
    journey = JourneyFileV1(
        name=name,
        goal=goal,
        start_url=url,
        success={"url_contains": success_url, "text_present": success_text},
        plan=steps,
    )
    data = {"schema_version": SCHEMA, **journey.model_dump(mode="json", exclude_defaults=True)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def capture_session(
    url: str, out: Path, *, headless: bool = False, wait: Callable[[Page], None] | None = None
) -> Path:
    """Open a window to sign in by hand; save cookies and storage when it closes."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        if wait is not None:
            wait(page)
        else:
            print("Sign in in the browser window. Press Enter here when you are signed in.")
            input()
        state = context.storage_state()
        context.close()
        browser.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    # A session is as sensitive as a password: create the file owner-only from the start.
    with suppress(FileNotFoundError):
        out.unlink()
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    return out
