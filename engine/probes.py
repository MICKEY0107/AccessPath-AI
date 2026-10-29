"""Deterministic keyboard probes used to confirm a barrier before reporting it.

The planner is an AI and can fail on its own. Before a run blames the website,
these probes re-check the suspected control with plain keyboard actions:

* a Tab walk from the top of the page lists every control Tab reaches;
* a target probe finds the control the run was aiming for and tests whether Tab
  reaches it and whether Enter or Space operates it (a mouse click is used only as
  a comparison, to show the control works for pointer users);
* a trap probe tests whether Tab, Shift+Tab or Escape can move focus out of a loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

from .dom import ACTIVE_DETAILS, script

WALK_START_ID = "__accesspath_walk_start"
STOPWORDS = {
    "the", "and", "for", "with", "button", "link", "field", "input", "control", "focus",
    "next", "element", "item", "select", "choose", "open", "press", "click", "tab", "page",
    "this", "that", "into", "onto", "from", "then", "area", "box", "text",
}

_PREPARE_WALK = script(
    f"""
    const active = document.activeElement;
    if (active && active !== document.body) active.setAttribute('data-accesspath-restore', '1');
    document.getElementById('{WALK_START_ID}')?.remove();
    const start = document.createElement('span');
    start.id = '{WALK_START_ID}';
    start.tabIndex = -1;
    start.setAttribute('aria-hidden', 'true');
    start.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:1px;overflow:hidden;';
    document.body.prepend(start);
    start.focus({{preventScroll: true}});
    return true;
    """
)

_RESTORE_WALK = script(
    f"""
    const target = document.querySelector('[data-accesspath-restore]');
    target?.removeAttribute('data-accesspath-restore');
    let start = document.getElementById('{WALK_START_ID}');
    if (target) {{
      start?.remove();
      target.focus({{preventScroll: true}});
      return 'restored';
    }}
    // Nothing was focused: put the Tab starting point back at the top of the page.
    if (!start) {{
      start = document.createElement('span');
      start.id = '{WALK_START_ID}';
      start.tabIndex = -1;
      document.body.prepend(start);
    }}
    start.focus({{preventScroll: true}});
    start.blur();
    start.remove();
    return 'top';
    """
)

_FOCUSABLE_COUNT = script(
    "return Array.from(document.querySelectorAll('*')).filter(__isSequentiallyFocusable).length;"
)

_FIND_CANDIDATES = script(
    """
    document.querySelectorAll('[data-accesspath-candidate]')
      .forEach((element) => element.removeAttribute('data-accesspath-candidate'));
    let found = [];
    if (arg.test_id) {
      found = Array.from(document.querySelectorAll('[data-testid]'))
        .filter((element) => element.getAttribute('data-testid') === arg.test_id)
        .map((element) => ({element, score: 1}));
    } else if (arg.tokens.length) {
      const pool = Array.from(document.querySelectorAll(
        'a,button,input,select,textarea,summary,[role],[onclick],[tabindex],label,li,div,span'
      )).slice(0, 3000).filter(__isVisible);
      for (const element of pool) {
        const hay = [__accName(element), element.id, element.getAttribute('data-testid'),
          element.getAttribute('aria-label'), element.getAttribute('placeholder')]
          .join(' ').toLowerCase();
        const hits = arg.tokens.filter((token) => hay.includes(token)).length;
        const score = hits / arg.tokens.length;
        if (score >= 0.6) found.push({element, score});
      }
      // Keep the innermost element: drop any candidate that contains another one.
      found = found.filter((item) => !found.some((other) => other !== item &&
        item.element.contains(other.element) && other.score >= item.score));
      const interactive = (element) => __interactiveRoles.includes(__roleOf(element)) ? 1 : 0;
      found.sort((a, b) => b.score - a.score || interactive(b.element) - interactive(a.element));
    }
    return found.filter((item) => __isVisible(item.element)).slice(0, 3).map((item, index) => {
      item.element.setAttribute('data-accesspath-candidate', String(index));
      const style = window.getComputedStyle(item.element);
      return {
        index,
        score: item.score,
        details: __details(item.element),
        focusable: __isSequentiallyFocusable(item.element),
        disabled: item.element.matches(':disabled') ||
          item.element.getAttribute('aria-disabled') === 'true',
        interactive: __interactiveRoles.includes(__roleOf(item.element)) ||
          item.element.hasAttribute('onclick') || style.cursor === 'pointer',
      };
    });
    """,
    "arg",
)

_CLEAR_CANDIDATES = script(
    """
    document.querySelectorAll('[data-accesspath-candidate]')
      .forEach((element) => element.removeAttribute('data-accesspath-candidate'));
    return true;
    """
)

_WATCH_MUTATIONS = """() => {
    window.__accesspathMutations = 0;
    window.__accesspathObserver?.disconnect();
    window.__accesspathObserver = new MutationObserver((records) => {
      window.__accesspathMutations += records.length;
    });
    window.__accesspathObserver.observe(document.documentElement,
      {subtree: true, childList: true, attributes: true, characterData: true});
    return true;
}"""

_READ_MUTATIONS = """() => {
    const count = window.__accesspathMutations || 0;
    window.__accesspathObserver?.disconnect();
    delete window.__accesspathObserver;
    delete window.__accesspathMutations;
    return count;
}"""


@dataclass
class TabWalk:
    """The controls that Tab reaches, in order, starting from the top of the page."""

    stops: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False
    cycle_paths: list[str] = field(default_factory=list)
    navigated_to: str | None = None
    navigation_stop: dict[str, Any] | None = None
    focusable_count: int = 0
    restored: str = ""

    def position_of(self, css_path: str) -> int | None:
        for index, stop in enumerate(self.stops):
            if stop.get("css_path") == css_path:
                return index
        return None


@dataclass
class TargetProbe:
    """What the probe learned about the control the run was trying to reach."""

    found: bool
    confirmed_barrier: bool
    rule_id: str = "keyboard-operable"
    method: str = "tab_walk"
    element: dict[str, Any] | None = None
    detail: str = ""
    diagnosis: str = ""


@dataclass
class TrapProbe:
    confirmed_trap: bool
    element: dict[str, Any] | None = None
    detail: str = ""
    diagnosis: str = ""


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def hint_tokens(hint: str) -> list[str]:
    words = re.findall(r"[a-z0-9:]{3,}", hint.lower())
    return [word for word in dict.fromkeys(words) if word not in STOPWORDS][:8]


def tab_walk(page: Page, *, max_stops: int = 80, settle_ms: int = 30) -> TabWalk:
    """Press Tab from the top of the page and record each focus stop, then restore focus."""
    walk = TabWalk()
    before_url = page.url
    page.evaluate(_PREPARE_WALK)
    seen: dict[str, int] = {}
    frame_repeats = 0
    try:
        for _ in range(max_stops):
            page.keyboard.press("Tab")
            if settle_ms:
                page.wait_for_timeout(settle_ms)
            if page.url != before_url:
                walk.navigated_to = page.url
                walk.navigation_stop = walk.stops[-1] if walk.stops else None
                break
            info = page.evaluate(ACTIVE_DETAILS)
            if info is None:
                walk.completed = True
                break
            path = info.get("css_path", "")
            if path.endswith(WALK_START_ID):
                walk.completed = True
                break
            if path in seen:
                if info.get("tag") == "iframe" and frame_repeats < 30:
                    frame_repeats += 1
                    continue
                if seen[path] == 0:
                    walk.completed = True
                else:
                    walk.cycle_paths = [stop["css_path"] for stop in walk.stops[seen[path] :]]
                break
            frame_repeats = 0
            seen[path] = len(walk.stops)
            walk.stops.append(info)
        walk.focusable_count = int(page.evaluate(_FOCUSABLE_COUNT))
    finally:
        if walk.navigated_to:
            page.goto(before_url, wait_until="domcontentloaded")
            walk.restored = "reloaded"
        else:
            walk.restored = page.evaluate(_RESTORE_WALK)
    return walk


def _activation_changes(page: Page, locator, key: str | None, request_count) -> bool:
    """Press a key (or click when key is None) and report whether the page reacted."""
    before_url = page.url
    before_requests = request_count()
    page.evaluate(_WATCH_MUTATIONS)
    if key is None:
        locator.click(timeout=2000)
    else:
        page.keyboard.press(key)
    page.wait_for_timeout(400)
    if page.url != before_url:
        return True
    mutations = page.evaluate(_READ_MUTATIONS)
    return bool(mutations) or request_count() > before_requests


def probe_target(
    page: Page,
    walk: TabWalk,
    *,
    test_id: str | None = None,
    hint: str = "",
    request_count=lambda: 0,
    check_activation: bool = True,
) -> TargetProbe:
    """Decide whether the control a run was aiming for is a real keyboard barrier."""
    tokens = hint_tokens(hint)
    if not test_id and not tokens:
        return TargetProbe(
            found=False,
            confirmed_barrier=False,
            diagnosis="The run gave no target to re-check, so no barrier is reported.",
        )
    candidates = page.evaluate(_FIND_CANDIDATES, {"test_id": test_id, "tokens": tokens})
    label = f"test id “{test_id}”" if test_id else f"“{hint[:80]}”"
    if not candidates:
        return TargetProbe(
            found=False,
            confirmed_barrier=False,
            diagnosis=(
                f"No visible control matching {label} was found on the page, so AccessPath "
                "cannot say the site blocked the task. Treat this as an agent failure."
            ),
        )
    try:
        unreachable = [
            item
            for item in candidates
            if item["interactive"] and not item["disabled"] and not item["focusable"]
        ]
        if unreachable and not any(item["focusable"] for item in candidates):
            item = unreachable[0]
            name = item["details"].get("name") or item["details"].get("tag")
            tabindex = item["details"].get("tabindex")
            why = (
                f'it has tabindex="{tabindex}"'
                if tabindex is not None and tabindex.startswith("-")
                else "it is not focusable"
            )
            return TargetProbe(
                found=True,
                confirmed_barrier=True,
                element=item["details"],
                detail=(
                    f"“{name}” is visible and looks operable, but {why}, so Tab "
                    f"never reaches it. A Tab walk from the top of the page visited "
                    f"{_count(len(walk.stops), 'control')} and skipped it."
                ),
            )
        reachable = [item for item in candidates if item["focusable"]]
        if not reachable:
            return TargetProbe(
                found=True,
                confirmed_barrier=False,
                element=candidates[0]["details"],
                diagnosis=(
                    f"The element matching {label} is not an operable control (or is "
                    "disabled), so AccessPath does not report a barrier."
                ),
            )
        item = reachable[0]
        details = item["details"]
        name = details.get("name") or details.get("tag")
        position = walk.position_of(details.get("css_path", ""))
        where = (
            f"after {position + 1} Tab press{'' if position == 0 else 'es'} from the top of the page"
            if position is not None
            else "with Tab"
        )
        if not check_activation:
            return TargetProbe(
                found=True,
                confirmed_barrier=False,
                element=details,
                diagnosis=f"“{name}” is reachable {where}; the planner did not get there.",
            )
        locator = page.locator(f'[data-accesspath-candidate="{item["index"]}"]').first
        locator.focus(timeout=2000)
        keys = ["Enter"]
        if details.get("role") in {"button", "checkbox", "radio", "switch", "menuitemcheckbox"}:
            keys.append("Space")
        for key in keys:
            if _activation_changes(page, locator, key, request_count):
                return TargetProbe(
                    found=True,
                    confirmed_barrier=False,
                    method="activation_probe",
                    element=details,
                    diagnosis=(
                        f"Not a site barrier: “{name}” is reachable {where} and "
                        f"responds to {key}. The planner did not complete the task, so this is "
                        "an agent failure."
                    ),
                )
        locator.focus(timeout=2000)
        if _activation_changes(page, locator, None, request_count):
            return TargetProbe(
                found=True,
                confirmed_barrier=True,
                method="activation_probe",
                element=details,
                detail=(
                    f"“{name}” is reachable {where}, but Enter and Space do nothing; "
                    "a mouse click on the same control does change the page. Keyboard users "
                    "cannot operate it."
                ),
            )
        return TargetProbe(
            found=True,
            confirmed_barrier=False,
            method="activation_probe",
            element=details,
            diagnosis=(
                f"“{name}” is reachable {where}, but neither keys nor a click changed "
                "the page in this state, so no barrier is reported."
            ),
        )
    finally:
        page.evaluate(_CLEAR_CANDIDATES)


def probe_trap(page: Page, walk: TabWalk) -> TrapProbe:
    """Confirm a keyboard trap: focus loops and no standard key gets it out."""
    if not walk.cycle_paths:
        reached = len(walk.stops)
        return TrapProbe(
            confirmed_trap=False,
            diagnosis=(
                f"Not a keyboard trap: Tab moved freely through {_count(reached, 'control')}"
                f"{' and wrapped back to the start' if walk.completed else ''}. The run "
                "repeated itself, so this is an agent failure."
            ),
        )
    cycle = set(walk.cycle_paths)
    first = next(stop for stop in walk.stops if stop["css_path"] == walk.cycle_paths[0])
    page.evaluate(
        script(
            "const target = Array.from(document.querySelectorAll('*'))"
            ".find((element) => __cssPath(element) === arg);"
            " target?.focus(); return Boolean(target);",
            "arg",
        ),
        walk.cycle_paths[0],
    )
    for key, presses in (("Shift+Tab", len(cycle) + 2), ("Escape", 1), ("Tab", len(cycle) + 2)):
        for _ in range(presses):
            page.keyboard.press(key)
            page.wait_for_timeout(30)
            info = page.evaluate(ACTIVE_DETAILS)
            if info is None or info.get("css_path") not in cycle:
                return TrapProbe(
                    confirmed_trap=False,
                    element=first,
                    diagnosis=(
                        f"Focus looped through {len(cycle)} controls, but {key} moved it out, "
                        "so this is not a keyboard trap."
                    ),
                )
    return TrapProbe(
        confirmed_trap=True,
        element=first,
        detail=(
            f"Focus is trapped in a loop of {len(cycle)} controls starting at "
            f"“{first.get('name') or first.get('tag')}”. Tab, Shift+Tab and Escape "
            f"never move it out, although the page has {walk.focusable_count} focusable "
            "controls."
        ),
    )
