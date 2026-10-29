"""Keyboard accessibility checks that run while a journey is evaluated.

Focus checks run each time keyboard focus lands on a new control; page checks run
once per page the journey visits. Each check records whether its rule applied, so a
report can tell "passed" from "not checked". Static scans that cannot prove a
problem on their own report it as ``needs_review``, never as a confirmed barrier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

from .contracts import FindingConfirmationV1, FindingV1
from .dom import script
from .findings import FindingCollector, element_signature
from .probes import TabWalk, tab_walk

_FOCUS_GEOMETRY = script(
    """
    const element = document.activeElement;
    if (!element || element === document.body || element.tagName === 'IFRAME') return null;
    const rect = element.getBoundingClientRect();
    const width = window.innerWidth, height = window.innerHeight;
    const inView = rect.bottom > 0 && rect.right > 0 && rect.top < height && rect.left < width;
    const insetX = Math.min(4, rect.width / 4), insetY = Math.min(4, rect.height / 4);
    const points = [
      [rect.left + rect.width / 2, rect.top + rect.height / 2],
      [rect.left + insetX, rect.top + insetY], [rect.right - insetX, rect.top + insetY],
      [rect.left + insetX, rect.bottom - insetY], [rect.right - insetX, rect.bottom - insetY],
    ].filter(([x, y]) => x >= 0 && y >= 0 && x < width && y < height);
    let covered = 0, coverer = null;
    for (const [x, y] of points) {
      const hit = document.elementFromPoint(x, y);
      if (!hit || hit === element || element.contains(hit) || hit.contains(element)) continue;
      let node = hit, pinned = false;
      while (node && node !== document.body) {
        const position = window.getComputedStyle(node).position;
        if (position === 'fixed' || position === 'sticky') { pinned = true; break; }
        node = node.parentElement;
      }
      if (pinned) { covered += 1; coverer = coverer || node; }
    }
    const style = window.getComputedStyle(element);
    const outlineWidth = parseFloat(style.outlineWidth) || 0;
    return {
      details: __details(element),
      in_view: inView,
      points: points.length,
      covered,
      coverer: coverer ? __details(coverer) : null,
      clip: {x: rect.left + window.scrollX - 6, y: rect.top + window.scrollY - 6,
        width: rect.width + 12, height: rect.height + 12},
      outline: style.outlineStyle !== 'none' && outlineWidth >= 2,
      box_shadow: style.boxShadow && style.boxShadow !== 'none',
    };
    """
)

_BLUR_ACTIVE = """() => {
    const element = document.activeElement;
    if (!element || element === document.body) return false;
    element.setAttribute('data-accesspath-refocus', '1');
    element.blur();
    return true;
}"""

_REFOCUS = """() => {
    const element = document.querySelector('[data-accesspath-refocus]');
    if (!element) return false;
    element.removeAttribute('data-accesspath-refocus');
    element.focus({preventScroll: true});
    return document.activeElement === element;
}"""

_SCAN_PAGE = script(
    """
    document.querySelectorAll('[data-accesspath-scan]')
      .forEach((element) => element.removeAttribute('data-accesspath-scan'));
    const composite = '[role=toolbar],[role=menubar],[role=menu],[role=tablist],[role=radiogroup],' +
      '[role=listbox],[role=grid],[role=tree],[role=treegrid],[aria-activedescendant]';
    const all = Array.from(document.querySelectorAll('*'));
    const focusable = all.filter(__isSequentiallyFocusable);
    const unnamed = [];
    focusable.forEach((element) => {
      const role = __roleOf(element);
      if (!role || !__interactiveRoles.includes(role)) return;
      if (__accName(element)) return;
      element.setAttribute('data-accesspath-scan', String(unnamed.length));
      unnamed.push({index: unnamed.length, details: __details(element)});
    });
    const unreachable = [];
    const clickOnly = [];
    for (const element of all) {
      if (unreachable.length >= 20 && clickOnly.length >= 20) break;
      if (!__isVisible(element) || element.tabIndex >= 0 || element.matches(':disabled')) continue;
      if (element.closest(composite)) continue;
      const role = __roleOf(element);
      const tag = element.tagName.toLowerCase();
      const nativeControl = ['button', 'a', 'input', 'select', 'textarea', 'summary'].includes(tag) &&
        role !== null;
      const ariaControl = element.hasAttribute('role') &&
        ['button', 'link', 'checkbox', 'switch', 'slider', 'spinbutton', 'combobox', 'textbox',
         'searchbox'].includes(role);
      if ((nativeControl || ariaControl) && unreachable.length < 20) {
        unreachable.push(__details(element));
      } else if (!role && element.hasAttribute('onclick') && __norm(element.textContent) &&
                 !element.querySelector('a[href],button,input,select,textarea,[tabindex]') &&
                 clickOnly.length < 20) {
        clickOnly.push(__details(element));
      }
    }
    const positive = all.filter((element) => element.tabIndex > 0 && __isVisible(element))
      .slice(0, 10).map(__details);
    const main = document.querySelector('main,[role=main]');
    const headings = document.querySelectorAll('h1,h2,[role=heading]').length;
    const repeated = document.querySelectorAll('nav a[href], header a[href], [role=navigation] a[href]')
      .length;
    return {unnamed, unreachable, click_only: clickOnly, positive, has_main: Boolean(main),
      main_path: main ? __cssPath(main) : null, headings, repeated_links: repeated,
      focusable_count: focusable.length};
    """
)

_SKIP_TARGET = """(href) => {
    const id = decodeURIComponent((href.split('#')[1] || ''));
    if (!id) return false;
    return Boolean(document.getElementById(id) || document.getElementsByName(id).length);
}"""

_CLEAR_SCAN = """() => {
    document.querySelectorAll('[data-accesspath-scan]')
      .forEach((element) => element.removeAttribute('data-accesspath-scan'));
    return true;
}"""

_NAME_FROM_SNAPSHOT = re.compile(r'^- [\w-]+ "(.+)"')
AXE_NAME_RULES = {
    "button-name",
    "link-name",
    "label",
    "input-button-name",
    "aria-toggle-field-name",
    "select-name",
    "aria-command-name",
    "aria-input-field-name",
}
_AXE_CRITERION = re.compile(r"^wcag(\d)(\d)(\d{1,2})$")


def page_key(url: str) -> str:
    return url.split("#", 1)[0]


@dataclass
class CheckRunner:
    """Runs the focus and page checks for one journey and feeds the collector."""

    collector: FindingCollector
    axe_source: str | None = None
    axe_tags: list[str] = field(default_factory=list)
    checked_pages: set[str] = field(default_factory=set)
    checked_focus: set[str] = field(default_factory=set)
    axe_status: dict[str, Any] = field(default_factory=lambda: {"status": "not_run", "pages": 0})
    walks: dict[str, TabWalk] = field(default_factory=dict)

    # Focus checks -------------------------------------------------------------

    def check_focus(self, page: Page, step_number: int) -> None:
        """Check the control that has just received keyboard focus."""
        geometry = page.evaluate(_FOCUS_GEOMETRY)
        if geometry is None:
            return
        details = geometry["details"]
        key = f"{page_key(page.url)}|{details.get('css_path')}"
        if key in self.checked_focus:
            return
        self.checked_focus.add(key)
        name = details.get("name") or details.get("role") or details.get("tag")
        url = page.url

        if not geometry["in_view"] or geometry["points"] == 0:
            self.collector.add(
                "focus-visible",
                summary=(
                    f"Keyboard focus moved to “{name}”, which is outside the visible "
                    "page, so a sighted keyboard user cannot see where focus is."
                ),
                url=url,
                method="point_sample",
                detail="The focused element's box lies outside the viewport.",
                element=details,
                step_number=step_number,
            )
            return

        obscured = geometry["covered"] == geometry["points"]
        self.collector.checked("focus-not-obscured", applicable=True)
        if obscured:
            coverer = geometry.get("coverer") or {}
            self.collector.add(
                "focus-not-obscured",
                summary=(
                    f"“{name}” has keyboard focus but is completely hidden behind "
                    f"a fixed or sticky element ({coverer.get('css_path') or 'unknown'})."
                ),
                url=url,
                method="point_sample",
                detail=f"All {geometry['points']} sampled points of the control are covered.",
                element=details,
                step_number=step_number,
            )
        else:
            self._check_indicator(page, geometry, details, name, url, step_number)

        if self.collector.is_active("focus-appearance") and not obscured:
            self.collector.checked("focus-appearance", applicable=True)
            if not geometry["outline"] and not geometry["box_shadow"]:
                self.collector.add(
                    "focus-appearance",
                    summary=(
                        f"The focus indicator on “{name}” is not a 2px or thicker "
                        "outline or a shadow; check it is large and clear enough."
                    ),
                    url=url,
                    method="focus_diff",
                    confirmed=False,
                    element=details,
                    step_number=step_number,
                    merge_key="focus-appearance-style",
                )

    def _check_indicator(self, page, geometry, details, name, url, step_number) -> None:
        if not self.collector.is_active("focus-visible"):
            return
        clip = {key: max(0.0, float(value)) for key, value in geometry["clip"].items()}
        if clip["width"] < 1 or clip["height"] < 1:
            return
        options = {"clip": clip, "full_page": True, "animations": "disabled", "caret": "hide"}
        focused = page.screenshot(**options)
        if not page.evaluate(_BLUR_ACTIVE):
            return
        try:
            unfocused = page.screenshot(**options)
        finally:
            page.evaluate(_REFOCUS)
        self.collector.checked("focus-visible", applicable=True)
        if focused == unfocused:
            self.collector.add(
                "focus-visible",
                summary=(
                    f"“{name}” looks exactly the same with and without keyboard "
                    "focus, so there is no visible focus indicator."
                ),
                url=url,
                method="focus_diff",
                detail="Screenshots of the control focused and unfocused are identical.",
                element=details,
                step_number=step_number,
            )

    # Page checks ---------------------------------------------------------------

    def check_page(self, page: Page, step_number: int | None) -> TabWalk | None:
        """Run the once-per-page checks; returns the Tab walk it made."""
        key = page_key(page.url)
        if key in self.checked_pages:
            return None
        self.checked_pages.add(key)
        url = page.url
        scan = page.evaluate(_SCAN_PAGE)
        try:
            self._report_unnamed(page, scan, url, step_number)
        finally:
            page.evaluate(_CLEAR_SCAN)
        self._report_unreachable(scan, url, step_number)
        walk = tab_walk(page, max_stops=60, settle_ms=15)
        self.walks[key] = walk
        self.record_walk(walk, url, step_number)
        self._report_bypass(page, scan, walk, url, step_number)
        self._report_focus_order(scan, walk, url, step_number)
        self._run_axe(page, url, step_number)
        return walk

    def record_walk(self, walk: TabWalk, url: str, step_number: int | None = None) -> None:
        """A Tab walk also tests the on-focus and keyboard-trap rules for its page."""
        if walk.navigated_to:
            stop = walk.navigation_stop or {}
            name = stop.get("name") or "a control"
            summary = (
                f"Moving focus onto “{name}” with Tab opened another page "
                f"({walk.navigated_to}). Focus alone must not change the page."
            )
            self.collector.add(
                "on-focus",
                summary=summary,
                url=url,
                method="tab_walk",
                detail=summary,
                element=stop or None,
                step_number=step_number,
            )
        elif walk.stops:
            self.collector.checked("on-focus", applicable=True)
        if walk.completed and not walk.cycle_paths:
            self.collector.checked("no-keyboard-trap", applicable=bool(walk.stops))

    def _report_unnamed(self, page, scan, url, step_number) -> None:
        self.collector.checked("name-role-value", applicable=scan["focusable_count"] > 0)
        for item in scan["unnamed"][:30]:
            locator = page.locator(f'[data-accesspath-scan="{item["index"]}"]').first
            try:
                snapshot = locator.aria_snapshot(timeout=2000)
            except Exception:
                continue
            if _NAME_FROM_SNAPSHOT.match(snapshot.strip().splitlines()[0] if snapshot else ""):
                continue  # Chromium computes a name our quick check missed.
            details = item["details"]
            role = details.get("role") or details.get("tag")
            signature = f"{details.get('tag')}|{role}|{'.'.join(details.get('classes') or [])}"
            self.collector.add(
                "name-role-value",
                summary=(
                    f"A focusable {role} has no accessible name, so a screen reader announces "
                    f"only “{role}”. Example: {details.get('html_snippet', '')[:160]}"
                ),
                url=url,
                method="dom_scan",
                detail="Chromium's accessibility tree gives this control no name.",
                element=details,
                step_number=step_number,
                merge_key=signature,
            )

    def _report_unreachable(self, scan, url, step_number) -> None:
        self.collector.checked("keyboard-operable", applicable=scan["focusable_count"] > 0)
        for details in scan["unreachable"]:
            name = details.get("name") or details.get("tag")
            self.collector.add(
                "keyboard-operable",
                summary=(
                    f"“{name}” is a visible control that Tab skips "
                    f"(tabindex=“{details.get('tabindex')}”). If the task needs it, "
                    "keyboard users cannot reach it."
                ),
                url=url,
                method="dom_scan",
                confirmed=False,
                element=details,
                step_number=step_number,
                merge_key=element_signature("unreachable", details),
            )
        for details in scan["click_only"]:
            name = details.get("name") or details.get("tag")
            self.collector.add(
                "keyboard-operable",
                summary=(
                    f"“{name[:80]}” has a click handler but is not a button or link "
                    "and is not focusable, so keyboard users may not be able to use it."
                ),
                url=url,
                method="dom_scan",
                confirmed=False,
                element=details,
                step_number=step_number,
                merge_key=element_signature("unreachable", details),
            )

    def _report_bypass(self, page, scan, walk: TabWalk, url, step_number) -> None:
        if not self.collector.is_active("bypass-blocks"):
            return
        before_main = len(walk.stops)
        if scan["main_path"]:
            before_main = next(
                (
                    index
                    for index, stop in enumerate(walk.stops)
                    if stop.get("css_path", "").startswith(scan["main_path"])
                ),
                len(walk.stops),
            )
        applicable = scan["repeated_links"] >= 3 and before_main >= 3
        if not applicable:
            self.collector.checked("bypass-blocks", applicable=False)
            return
        first = walk.stops[0] if walk.stops else {}
        href = (first.get("html_snippet") or "")
        skip_href = re.search(r'href="(#[^"]+)"', href)
        has_skip = bool(skip_href and page.evaluate(_SKIP_TARGET, skip_href.group(1)))
        if has_skip or scan["has_main"] or scan["headings"]:
            how = "a working skip link" if has_skip else "a main landmark" if scan["has_main"] else "headings"
            self.collector.checked("bypass-blocks", applicable=True, detail=f"Passed via {how}.")
            return
        self.collector.add(
            "bypass-blocks",
            summary=(
                f"Keyboard users must Tab through {before_main} navigation controls before the "
                "page content, and there is no skip link, main landmark or heading to jump past them."
            ),
            url=url,
            method="tab_walk",
            detail=f"{scan['repeated_links']} repeated navigation links, no bypass mechanism.",
            step_number=step_number,
            merge_key="bypass",
        )

    def _report_focus_order(self, scan, walk: TabWalk, url, step_number) -> None:
        self.collector.checked("focus-order", applicable=len(walk.stops) >= 3)
        for details in scan["positive"][:3]:
            self.collector.add(
                "focus-order",
                summary=(
                    f"“{details.get('name') or details.get('tag')}” has "
                    f"tabindex=“{details.get('tabindex')}”, which moves it ahead of the "
                    "page's natural Tab order. Check the order still makes sense."
                ),
                url=url,
                method="dom_scan",
                confirmed=False,
                element=details,
                step_number=step_number,
                merge_key="positive-tabindex",
            )
        jumps = 0
        example = None
        for previous, current in zip(walk.stops, walk.stops[1:], strict=False):
            before, after = previous.get("rect") or {}, current.get("rect") or {}
            if before and after and after.get("y", 0) < before.get("y", 0) - 300:
                jumps += 1
                example = example or (previous, current)
        if jumps >= 2 and example:
            self.collector.add(
                "focus-order",
                summary=(
                    f"Tab moves focus back up the page {jumps} times, for example from "
                    f"“{example[0].get('name')}” to “{example[1].get('name')}”. "
                    "Check the Tab order follows the reading order."
                ),
                url=url,
                method="tab_walk",
                confirmed=False,
                element=example[1],
                step_number=step_number,
                merge_key="order-jumps",
            )

    def _run_axe(self, page: Page, url: str, step_number: int | None) -> None:
        if not self.axe_source or not self.axe_tags:
            if self.axe_status["status"] == "not_run":
                self.axe_status = {
                    "status": "not_installed" if not self.axe_source else "not_in_preset",
                    "pages": 0,
                }
            return
        try:
            page.evaluate("(source) => { (0, eval)(source); return true; }", self.axe_source)
            report = page.evaluate(
                """async (tags) => {
                    const result = await axe.run(document, {
                      runOnly: {type: 'tag', values: tags}, resultTypes: ['violations']});
                    return {version: axe.version, violations: result.violations};
                }""",
                self.axe_tags,
            )
        except Exception as error:
            self.axe_status = {"status": "failed", "error": type(error).__name__, "pages": 0}
            return
        self.axe_status = {
            "status": "ran",
            "version": report.get("version", ""),
            "pages": int(self.axe_status.get("pages", 0)) + 1,
        }
        have_names = any(
            item.rule_id == "name-role-value" and page_key(item.url) == page_key(url)
            for item in self.collector.findings
        )
        for violation in report.get("violations", [])[:40]:
            if have_names and violation.get("id") in AXE_NAME_RULES:
                continue
            self.collector.add_external(axe_finding(violation, url, step_number))


def axe_finding(violation: dict[str, Any], url: str, step_number: int | None) -> FindingV1:
    """Turn one axe-core violation into a finding with its WCAG criterion and level."""
    import hashlib

    tags = violation.get("tags") or []
    criterion = ""
    for tag in tags:
        match = _AXE_CRITERION.match(tag)
        if match:
            criterion = ".".join(match.groups())
            break
    level = "AAA" if "wcag2aaa" in tags else "AA" if any(t.endswith("aa") for t in tags) else (
        "A" if any(t in {"wcag2a", "wcag21a", "wcag22a"} for t in tags) else ""
    )
    nodes = violation.get("nodes") or []
    first = nodes[0] if nodes else {}
    html = re.sub(r'\svalue="[^"]*"', "", str(first.get("html", "")))[:400]
    target = first.get("target") or []
    selector = " ".join(str(part) for part in target)[:512] if isinstance(target, list) else ""
    impact = violation.get("impact") or "moderate"
    if impact not in {"critical", "serious", "moderate", "minor"}:
        impact = "moderate"
    rule_id = f"axe/{violation.get('id', 'unknown')}"[:96]
    digest = hashlib.sha256(f"{rule_id}|{page_key(url)}".encode()).hexdigest()[:16]
    return FindingV1(
        id=digest,
        rule_id=rule_id,
        wcag_criterion=criterion,
        wcag_level=level,
        severity=impact,  # type: ignore[arg-type]
        status="confirmed",
        source="axe",
        title=str(violation.get("help", violation.get("id", "axe-core rule")))[:200],
        summary=(
            f"{violation.get('description', '')} {len(nodes)} element"
            f"{'' if len(nodes) == 1 else 's'} on this page. "
            f"{str(first.get('failureSummary', ''))[:300]}"
        ).strip()[:800],
        step_number=step_number,
        url=url[:1000],
        element={"css_path": selector, "html_snippet": html} if selector or html else None,
        occurrences=max(1, len(nodes)),
        confirmation=FindingConfirmationV1(
            method="axe", confirmed=True, detail=f"axe-core rule {violation.get('id')}"
        ),
        help_url=str(violation.get("helpUrl", ""))[:500] or None,
    )
