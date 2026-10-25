"""Keyboard-only Playwright executor with safety checks and evidence capture."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from playwright.sync_api import BrowserContext, Download, Page, Route, sync_playwright

from .artifacts import LocalArtifactStore, StoredArtifact
from .contracts import (
    ActionKind,
    ActionResultV1,
    ElementEvidenceV1,
    PlannerHistoryEntryV1,
    PlannerInteractiveElementV1,
    PlannerObservationV1,
    ProposedActionV1,
    StepEvidenceV1,
    TargetPolicyV1,
)
from .planner import Planner
from .policy import KeyboardActionPolicy
from .target_policy import TargetPolicy

StepCallback = Callable[[StepEvidenceV1, list[StoredArtifact]], None]


@dataclass(frozen=True)
class EvaluationResult:
    outcome: str
    terminal_reason: str
    steps_completed: int
    detail: str = ""


class KeyboardExecutor:
    """Executes only approved keyboard actions against an approved origin."""

    _key_map = {
        ActionKind.TAB: "Tab",
        ActionKind.SHIFT_TAB: "Shift+Tab",
        ActionKind.ENTER: "Enter",
        ActionKind.SPACE: "Space",
        ActionKind.ARROW_UP: "ArrowUp",
        ActionKind.ARROW_DOWN: "ArrowDown",
        ActionKind.ARROW_LEFT: "ArrowLeft",
        ActionKind.ARROW_RIGHT: "ArrowRight",
        ActionKind.ESCAPE: "Escape",
    }

    def __init__(
        self,
        *,
        run_id: UUID,
        start_url: str,
        allowed_origins: list[str],
        target_policy: dict[str, Any] | None = None,
        completion_policy: dict[str, Any],
        barrier_check: dict[str, Any] | None,
        max_steps: int,
        action_timeout_ms: int,
        headless: bool,
        browser_executable_path: str | None = None,
        artifact_store: LocalArtifactStore,
        on_step: StepCallback,
    ) -> None:
        self.run_id = run_id
        self.start_url = start_url
        self.allowed_origins = set(allowed_origins)
        policy_config = target_policy or {
            "navigation_origins": allowed_origins,
            "resource_origins": allowed_origins,
            "navigation_path_prefixes": ["/"],
        }
        self.target_policy = TargetPolicy(TargetPolicyV1.model_validate(policy_config))
        self.completion_policy = completion_policy
        self.barrier_check = barrier_check or {}
        self.max_steps = min(max_steps, self.target_policy.config.max_actions)
        self.action_timeout_ms = action_timeout_ms
        self.headless = headless
        self.browser_executable_path = browser_executable_path
        self.artifact_store = artifact_store
        self.on_step = on_step
        self.policy = KeyboardActionPolicy()
        self._required_focus_seen = False
        self._safety_violation_code = ""
        self._safety_violation_detail = ""
        self._pending_policy_events: list[str] = []
        self._pending_evidence_events: list[str] = []
        self.runtime_metadata: dict[str, object] = {}
        self._started_monotonic = 0.0

    def run(self, actions: Iterable[ProposedActionV1]) -> EvaluationResult:
        self._assert_safe_start_url()
        self._reset_run_state()
        with sync_playwright() as playwright:
            if self.browser_executable_path:
                browser = playwright.chromium.launch(
                    headless=self.headless,
                    executable_path=self.browser_executable_path,
                )
            else:
                browser = playwright.chromium.launch(headless=self.headless)
            context: BrowserContext | None = None
            try:
                self._record_browser_metadata(browser)
                context = self._new_context(browser)
                page = context.new_page()
                self._configure_page_events(context, page)
                page.set_default_timeout(self.action_timeout_ms)
                page.goto(self.start_url, wait_until="domcontentloaded")
                return self._execute_actions(page, actions)
            finally:
                if context is not None:
                    with suppress(Exception):
                        context.close()
                browser.close()

    def run_with_planner(self, planner: Planner, *, goal: str) -> EvaluationResult:
        """Execute a bounded observe-propose-authorize keyboard loop."""
        self._assert_safe_start_url()
        self._reset_run_state()
        with sync_playwright() as playwright:
            if self.browser_executable_path:
                browser = playwright.chromium.launch(
                    headless=self.headless,
                    executable_path=self.browser_executable_path,
                )
            else:
                browser = playwright.chromium.launch(headless=self.headless)
            context: BrowserContext | None = None
            try:
                self._record_browser_metadata(browser)
                context = self._new_context(browser)
                page = context.new_page()
                self._configure_page_events(context, page)
                page.set_default_timeout(self.action_timeout_ms)
                page.goto(self.start_url, wait_until="domcontentloaded")
                return self._execute_actions(page, None, planner=planner, goal=goal)
            finally:
                if context is not None:
                    with suppress(Exception):
                        context.close()
                browser.close()

    def _reset_run_state(self) -> None:
        self._safety_violation_code = ""
        self._safety_violation_detail = ""
        self._pending_policy_events = []
        self._pending_evidence_events = []

    def _record_browser_metadata(self, browser) -> None:
        self.runtime_metadata = {
            "engine": "keyboard_executor.v2",
            "browser_engine": "chromium",
            "browser_version": browser.version,
            "target_policy_version": self.target_policy.config.schema_version,
            "user_agent": self.target_policy.config.user_agent,
        }
        self._started_monotonic = time.monotonic()

    def _new_context(self, browser) -> BrowserContext:
        service_workers = (
            "block" if self.target_policy.config.block_service_workers else "allow"
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="UTC",
            user_agent=self.target_policy.config.user_agent,
            service_workers=service_workers,
            accept_downloads=False,
        )
        context.route("**/*", self._route_request)
        return context

    def _configure_page_events(self, context: BrowserContext, page: Page) -> None:
        context.on("page", self._handle_popup)
        page.on("download", self._handle_download)

    def _route_request(self, route: Route) -> None:
        request = route.request
        decision = self.target_policy.decide_request(
            request.url,
            method=request.method,
            is_navigation=request.is_navigation_request(),
        )
        if decision.allowed:
            route.continue_()
            return
        self._record_policy_event(decision.code, request.method, request.url)
        if decision.fatal:
            self._record_safety_violation(decision.code, request.url)
        route.abort("blockedbyclient")

    def _handle_popup(self, page: Page) -> None:
        decision = self.target_policy.decide_popup()
        if not decision.allowed:
            self._record_policy_event(decision.code, "POPUP", page.url)
            self._record_safety_violation(decision.code, page.url)
            page.close()
            return
        if len(page.context.pages) > self.target_policy.config.max_pages:
            self._record_safety_violation("PAGE_BUDGET_EXCEEDED", page.url)
            page.close()

    def _handle_download(self, download: Download) -> None:
        decision = self.target_policy.decide_download()
        if not decision.allowed:
            self._record_policy_event(decision.code, "DOWNLOAD", download.url)
            self._record_safety_violation(decision.code, download.url)
            download.cancel()

    def _record_safety_violation(self, code: str, detail: str = "") -> None:
        if not self._safety_violation_code:
            self._safety_violation_code = code
            self._safety_violation_detail = detail[:1000]

    def _record_policy_event(self, code: str, method: str, url: str) -> None:
        if len(self._pending_policy_events) < 20:
            self._pending_policy_events.append(f"{code} {method} {url}"[:512])

    def _consume_policy_events(self) -> list[str]:
        events = self._pending_policy_events
        self._pending_policy_events = []
        return events

    def _capture_screenshot(
        self, page: Page, step_number: int, moment: str
    ) -> StoredArtifact | None:
        path = self.artifact_store.screenshot_path(step_number, moment)
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                page.screenshot(path=str(path), full_page=True)
                return self.artifact_store.describe(path, f"screenshot_{moment}")
            except Exception as error:
                last_error = error
        if len(self._pending_evidence_events) < 20:
            error_name = type(last_error).__name__.upper()
            self._pending_evidence_events.append(
                f"SCREENSHOT_CAPTURE_FAILED {moment} {error_name}"[:512]
            )
        return None

    def _consume_evidence_events(self) -> list[str]:
        events = self._pending_evidence_events
        self._pending_evidence_events = []
        return events

    def _execute_actions(
        self,
        page: Page,
        actions: Iterable[ProposedActionV1] | None,
        *,
        planner: Planner | None = None,
        goal: str = "",
    ) -> EvaluationResult:
        rejection_counts: dict[str, int] = {}
        steps_run = 0
        history: list[PlannerHistoryEntryV1] = []
        state_visit_counts: dict[str, int] = {}
        action_iterator = iter(actions) if actions is not None else None
        while True:
            elapsed_ms = int((time.monotonic() - self._started_monotonic) * 1000)
            if elapsed_ms >= self.target_policy.config.total_timeout_ms:
                return EvaluationResult("environment_blocked", "RUN_TIMEOUT", steps_run)
            observation: PlannerObservationV1 | None = None
            if planner is not None:
                if steps_run >= self.max_steps:
                    return EvaluationResult(
                        "agent_error", "MAX_STEP_BUDGET_EXCEEDED", steps_run
                    )
                observation = self._planner_observation(
                    page,
                    goal=goal,
                    history=history,
                    remaining_steps=self.max_steps - steps_run,
                )
                action = planner.propose_next_action(observation)
                if action is None:
                    break
                consume_reset = getattr(planner, "consume_reset_request", None)
                if callable(consume_reset) and consume_reset():
                    page.goto(self.start_url, wait_until="domcontentloaded")
            else:
                try:
                    action = next(action_iterator)  # type: ignore[arg-type]
                except StopIteration:
                    break

            step_number = steps_run + 1
            steps_run = step_number
            if step_number > self.max_steps:
                return EvaluationResult("agent_error", "MAX_STEP_BUDGET_EXCEEDED", step_number - 1)

            before_url = page.url
            before_focus = self._focus_evidence(page)
            before_fingerprint = self._state_fingerprint(page, before_focus)
            decision = self.policy.decide(
                action,
                before_focus,
                rejection_counts.get("TYPE_TARGET_NOT_EDITABLE", 0),
            )
            artifacts: list[StoredArtifact] = []
            before_artifact = self._capture_screenshot(page, step_number, "before")
            if before_artifact is not None:
                artifacts.append(before_artifact)

            started_at = datetime.now(UTC)
            executed_action: ProposedActionV1 | None = None
            if decision.outcome == "approved":
                try:
                    self._perform_action(page, action)
                    executed_action = action
                    self._wait_for_stability(page)
                    meaningful_progress = self._state_changed(
                        page, before_url, before_fingerprint
                    )
                    action_result = ActionResultV1(
                        status="effect_observed" if meaningful_progress else "no_effect",
                        meaningful_progress=meaningful_progress,
                    )
                # Browser errors become evidence rather than web-request errors.
                except Exception as error:
                    action_result = ActionResultV1(
                        status="execution_error",
                        meaningful_progress=False,
                        error_code=type(error).__name__.upper()[:64],
                    )
            else:
                rejection_counts[decision.code] = rejection_counts.get(decision.code, 0) + 1
                action_result = ActionResultV1(
                    status="rejected",
                    meaningful_progress=False,
                    error_code=decision.code,
                )

            after_focus = self._focus_evidence(page)
            after_url = page.url
            after_fingerprint = self._state_fingerprint(page, after_focus)
            state_visit_counts[after_fingerprint] = (
                state_visit_counts.get(after_fingerprint, 0) + 1
            )
            repeated_focus_cycle = (
                state_visit_counts[after_fingerprint]
                >= self.target_policy.config.no_progress_limit
            )
            if decision.outcome == "approved" and self._safety_violation_code:
                action_result = ActionResultV1(
                    status="navigation_blocked",
                    meaningful_progress=False,
                    error_code=self._safety_violation_code,
                )
            elif decision.outcome == "approved" and repeated_focus_cycle:
                action_result = ActionResultV1(
                    status="repeated_focus_cycle",
                    meaningful_progress=False,
                    error_code="REPEATED_FOCUS_CYCLE",
                )
            elif (
                decision.outcome == "approved"
                and before_focus is not None
                and after_focus is None
                and after_url == before_url
            ):
                action_result = ActionResultV1(
                    status="focus_lost",
                    meaningful_progress=False,
                    error_code="FOCUS_LOST",
                )
            after_artifact = self._capture_screenshot(page, step_number, "after")
            if after_artifact is not None:
                artifacts.append(after_artifact)
            duration_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
            evidence = StepEvidenceV1(
                run_id=self.run_id,
                step_number=step_number,
                observed_at=started_at,
                url_before=before_url,  # pyright: ignore[reportArgumentType]
                url_after=(
                    after_url
                    if urlparse(after_url).scheme in {"http", "https"}
                    else before_url
                ),  # pyright: ignore[reportArgumentType]
                focus_before=before_focus,
                focus_after=after_focus,
                proposed_action=action,
                policy_decision=decision,
                executed_action=executed_action,
                action_result=action_result,
                state_fingerprint_before=before_fingerprint,
                state_fingerprint_after=after_fingerprint,
                duration_ms=duration_ms,
                policy_events=self._consume_policy_events(),
                evidence_events=self._consume_evidence_events(),
                completion_signals=self._completion_evaluations(page),
            )
            self.on_step(evidence, artifacts)
            if planner is not None and observation is not None:
                planner.record_outcome(observation, action, decision, action_result)
            history.append(
                PlannerHistoryEntryV1(
                    action=action.action,
                    policy_code=decision.code,
                    result_status=action_result.status,
                    meaningful_progress=action_result.meaningful_progress,
                )
            )
            barrier = self.barrier_check
            required_test_id = barrier.get("required_focus_test_id")
            if required_test_id and after_focus and after_focus.test_id == required_test_id:
                self._required_focus_seen = True

            if decision.outcome == "rejected" and rejection_counts.get(decision.code, 0) >= 2:
                return EvaluationResult("agent_error", decision.code, step_number)
            if self._safety_violation_code:
                return EvaluationResult(
                    "safety_stopped",
                    self._safety_violation_code,
                    step_number,
                    self._safety_violation_detail,
                )
            if repeated_focus_cycle:
                return EvaluationResult(
                    "agent_error", "REPEATED_FOCUS_CYCLE", step_number
                )
            if not self._origin_is_allowed(page.url):
                return EvaluationResult(
                    "safety_stopped", "NAVIGATION_ORIGIN_NOT_ALLOWED", step_number
                )
            if self._completion_is_stable(page):
                return EvaluationResult("completed", "COMPLETION_POLICY_SATISFIED", step_number)
            if self._barrier_budget_exhausted(page, steps_run):
                return EvaluationResult("blocked", "KEYBOARD_TARGET_NOT_REACHABLE", steps_run)

        if self._barrier_was_observed(page):
            return EvaluationResult("blocked", "KEYBOARD_TARGET_NOT_REACHABLE", steps_run)
        return EvaluationResult(
            "inconclusive", "PLAN_COMPLETED_WITHOUT_VERIFIED_COMPLETION", steps_run
        )

    def _assert_safe_start_url(self) -> None:
        self.target_policy.validate_start_url(self.start_url)

    def _origin_is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return parsed.scheme in {"http", "https"} and origin in self.allowed_origins

    def _planner_observation(
        self,
        page: Page,
        *,
        goal: str,
        history: list[PlannerHistoryEntryV1],
        remaining_steps: int,
    ) -> PlannerObservationV1:
        data = page.evaluate(
            """() => {
                const selector = [
                  'a[href]', 'button', 'input:not([type=hidden])', 'textarea', 'select',
                  '[contenteditable=true]', '[tabindex]:not([tabindex="-1"])'
                ].join(',');
                const isVisible = (element) => {
                  const style = window.getComputedStyle(element);
                  const rect = element.getBoundingClientRect();
                  return style.visibility !== 'hidden' && style.display !== 'none' &&
                    rect.width > 0 && rect.height > 0;
                };
                const all = Array.from(document.querySelectorAll(selector)).filter(isVisible);
                const active = document.activeElement;
                if (active && all.includes(active)) {
                  all.splice(all.indexOf(active), 1);
                  all.unshift(active);
                }
                const accessibleName = (element) => {
                  const labelledBy = (element.getAttribute('aria-labelledby') || '')
                    .split(/\\s+/).filter(Boolean)
                    .map((id) => document.getElementById(id)?.textContent?.trim() || '')
                    .filter(Boolean).join(' ');
                  return element.getAttribute('aria-label') || labelledBy ||
                    Array.from(element.labels || []).map((label) => label.textContent?.trim() || '')
                      .filter(Boolean).join(' ') ||
                    element.getAttribute('alt') || element.textContent?.trim() ||
                    element.getAttribute('title') || element.getAttribute('name') || '';
                };
                const roleFor = (element, tag) => {
                  const explicit = element.getAttribute('role');
                  if (explicit) return explicit;
                  if (tag === 'a' && element.hasAttribute('href')) return 'link';
                  if (tag === 'button') return 'button';
                  if (tag === 'textarea') return 'textbox';
                  if (tag === 'select') return 'combobox';
                  if (tag === 'input') {
                    const type = (element.getAttribute('type') || 'text').toLowerCase();
                    if (type === 'search') return 'searchbox';
                    if (type === 'checkbox') return 'checkbox';
                    if (type === 'radio') return 'radio';
                    if (['button', 'submit', 'reset'].includes(type)) return 'button';
                    return 'textbox';
                  }
                  return null;
                };
                const boolAttr = (element, name) => element.hasAttribute(name)
                  ? element.getAttribute(name) === 'true' : null;
                const isEditable = (element, tag) => {
                  if (tag === 'textarea' || element.matches('[contenteditable=true]')) return true;
                  if (tag !== 'input' || element.hasAttribute('readonly')) return false;
                  const type = (element.getAttribute('type') || 'text').toLowerCase();
                  return ![
                    'button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image',
                    'hidden', 'range', 'color'
                  ].includes(type);
                };
                const describe = (element) => {
                  const tag = element.tagName.toLowerCase();
                  const name = accessibleName(element);
                  return {
                    role: roleFor(element, tag),
                    name: name.replace(/\\s+/g, ' ').slice(0, 120),
                    test_id: element.getAttribute('data-testid'),
                    tag,
                    control_type: element.getAttribute('type'),
                    label: Array.from(element.labels || [])
                      .map((label) => label.textContent?.trim() || '')
                      .filter(Boolean).join(' ').slice(0, 120) || null,
                    editable: isEditable(element, tag),
                    enabled: !element.matches(':disabled'),
                    expanded: boolAttr(element, 'aria-expanded'),
                    checked: 'checked' in element ? Boolean(element.checked) :
                      boolAttr(element, 'aria-checked'),
                    selected: 'selected' in element ? Boolean(element.selected) :
                      boolAttr(element, 'aria-selected'),
                    required: Boolean(element.required ||
                      element.getAttribute('aria-required') === 'true'),
                    active_descendant: element.getAttribute('aria-activedescendant'),
                    href: element.href || null,
                    frame: window === window.top ? 'main' : 'child'
                  };
                };
                const visibleText = (document.body?.innerText || '').replace(/\\s+/g, ' ').trim();
                return {
                  elements: all.slice(0, 40).map(describe),
                  elements_truncated: all.length > 40,
                  visible_text: visibleText.slice(0, 4000),
                  visible_text_truncated: visibleText.length > 4000
                };
            }"""
        )
        bounded_history = history[-8:]
        return PlannerObservationV1(
            goal=goal,
            url=page.url,  # pyright: ignore[reportArgumentType]
            focused_element=self._focus_evidence(page),
            interactive_elements=[
                PlannerInteractiveElementV1.model_validate(item) for item in data["elements"]
            ],
            visible_text=data["visible_text"],
            history=bounded_history,
            remaining_steps=remaining_steps,
            elements_truncated=data["elements_truncated"],
            visible_text_truncated=data["visible_text_truncated"],
            history_truncated=len(history) > len(bounded_history),
        )

    def _perform_action(self, page: Page, action: ProposedActionV1) -> None:
        if action.action == ActionKind.TYPE:
            page.keyboard.press("Control+A")
            page.keyboard.type(action.value or "")
            return
        page.keyboard.press(self._key_map[action.action])

    def _wait_for_stability(self, page: Page) -> None:
        """Wait for two matching browser-state samples inside a bounded window."""
        deadline = time.monotonic() + min(self.action_timeout_ms, 2000) / 1000
        last_fingerprint = ""
        stable_samples = 0
        while time.monotonic() < deadline:
            page.wait_for_timeout(100)
            try:
                fingerprint = self._state_fingerprint(page, self._focus_evidence(page))
            except Exception:
                stable_samples = 0
                continue
            if fingerprint == last_fingerprint:
                stable_samples += 1
                if stable_samples >= 2:
                    return
            else:
                last_fingerprint = fingerprint
                stable_samples = 0

    def _focus_evidence(self, page: Page) -> ElementEvidenceV1 | None:
        data = page.evaluate(
            """() => {
                const element = document.activeElement;
                if (!element || element === document.body) return null;
                const tag = element.tagName.toLowerCase();
                const labelledBy = (element.getAttribute('aria-labelledby') || '')
                  .split(/\\s+/).filter(Boolean)
                  .map((id) => document.getElementById(id)?.textContent?.trim() || '')
                  .filter(Boolean).join(' ');
                const label = Array.from(element.labels || [])
                  .map((item) => item.textContent?.trim() || '').filter(Boolean).join(' ');
                const name = element.getAttribute('aria-label') || labelledBy || label ||
                  element.getAttribute('alt') || element.textContent?.trim() ||
                  element.getAttribute('title') || element.getAttribute('name') || element.id || '';
                const type = (element.getAttribute('type') || '').toLowerCase();
                const role = element.getAttribute('role') ||
                  (tag === 'a' && element.hasAttribute('href') ? 'link' :
                  tag === 'button' ? 'button' : tag === 'textarea' ? 'textbox' :
                  tag === 'select' ? 'combobox' : tag === 'input' && type === 'search' ?
                  'searchbox' : tag === 'input' && type === 'checkbox' ? 'checkbox' :
                  tag === 'input' && type === 'radio' ? 'radio' :
                  tag === 'input' ? 'textbox' : null);
                const boolAttr = (name) => element.hasAttribute(name)
                  ? element.getAttribute(name) === 'true' : null;
                const editable = tag === 'textarea' || element.matches('[contenteditable=true]') ||
                  (tag === 'input' && !element.hasAttribute('readonly') && ![
                    'button', 'submit', 'reset', 'checkbox', 'radio', 'file', 'image',
                    'hidden', 'range', 'color'
                  ].includes(type || 'text'));
                return {
                    fingerprint: `${tag}#${element.id}.${element.className}`.slice(0, 256),
                    role,
                    name: name.slice(0, 256),
                    test_id: element.getAttribute('data-testid'),
                    tag,
                    control_type: element.getAttribute('type'),
                    label: label.slice(0, 256) || null,
                    editable,
                    enabled: !element.matches(':disabled'),
                    expanded: boolAttr('aria-expanded'),
                    checked: 'checked' in element ? Boolean(element.checked) :
                      boolAttr('aria-checked'),
                    selected: 'selected' in element ? Boolean(element.selected) :
                      boolAttr('aria-selected'),
                    required: Boolean(element.required ||
                      element.getAttribute('aria-required') === 'true'),
                    active_descendant: element.getAttribute('aria-activedescendant'),
                    href: element.href || null,
                    frame: window === window.top ? 'main' : 'child'
                };
            }"""
        )
        return ElementEvidenceV1.model_validate(data) if data else None

    def _state_fingerprint(self, page: Page, focus: ElementEvidenceV1 | None) -> str:
        text = page.locator("body").inner_text(timeout=self.action_timeout_ms)[:2048]
        form_state = page.evaluate(
            """() => JSON.stringify(Array.from(
                document.querySelectorAll('input, textarea, select')
            ).map((element) => ({
                tag: element.tagName.toLowerCase(),
                name: element.getAttribute('name') || '',
                type: element.getAttribute('type') || '',
                value: element.value || '',
                checked: Boolean(element.checked),
                selectedIndex: Number.isInteger(element.selectedIndex)
                  ? element.selectedIndex : null
            })))"""
        )
        raw = (
            f"{page.url}|{focus.model_dump_json() if focus else ''}|{text}|{form_state}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _state_changed(self, page: Page, before_url: str, before_fingerprint: str) -> bool:
        return (
            page.url != before_url
            or self._state_fingerprint(page, self._focus_evidence(page)) != before_fingerprint
        )

    def _completion_is_stable(self, page: Page) -> bool:
        if not self._completion_matches(page):
            return False
        stability = self.completion_policy.get("stability", {})
        observations = stability.get("consecutive_observations", 2)
        interval_ms = stability.get("interval_ms", 500)
        for _ in range(observations - 1):
            page.wait_for_timeout(interval_ms)
            if not self._completion_matches(page):
                return False
        return True

    def _completion_matches(self, page: Page) -> bool:
        evaluations = self._completion_evaluations(page)
        return bool(evaluations) and all(evaluations.values())

    def _completion_evaluations(self, page: Page) -> dict[str, bool]:
        evaluations: dict[str, bool] = {}
        for signal in self.completion_policy.get("signals", []):
            signal_id = signal.get("id") or f"signal_{len(evaluations) + 1}"
            evaluations[signal_id] = self._completion_signal_matches(page, signal)
        return evaluations

    def _completion_signal_matches(self, page: Page, signal: dict[str, Any]) -> bool:
        try:
            signal_type = signal["type"]
            if signal_type == "url_path_equals":
                return urlparse(page.url).path == signal.get("expected")
            locator = signal.get("locator") or {}
            locator_by = locator.get("by")
            if locator_by == "test_id":
                element = page.get_by_test_id(locator.get("value", ""))
            elif locator_by == "role":
                role_options: dict[str, Any] = {"exact": True}
                if locator.get("name"):
                    role_options["name"] = locator["name"]
                element = page.get_by_role(locator.get("value", ""), **role_options)
            elif locator_by == "heading":
                element = page.get_by_role(
                    "heading",
                    name=locator.get("value", ""),
                    exact=True,
                    level=locator.get("level"),
                )
            else:
                return False
            if element.count() < 1:
                return False
            if signal_type == "element_present":
                return True
            if signal_type == "element_text_equals":
                actual = element.first.inner_text().strip()
                expected = signal.get("expected", "")
                if not signal.get("case_sensitive", True):
                    actual, expected = actual.lower(), expected.lower()
                return actual == expected
            if signal_type == "element_attribute_equals":
                return element.first.get_attribute(signal.get("attribute", "")) == signal.get(
                    "expected"
                )
            return False
        except Exception:
            return False

    def _barrier_was_observed(self, page: Page) -> bool:
        if not self.barrier_check:
            return False
        target_test_id = self.barrier_check.get("required_focus_test_id")
        if not target_test_id:
            return False
        return page.get_by_test_id(target_test_id).count() > 0 and not self._required_focus_seen

    def _barrier_budget_exhausted(self, page: Page, steps_run: int) -> bool:
        """Apply a journey-owned, bounded keyboard-barrier observation window."""
        action_budget = self.barrier_check.get("max_keyboard_actions")
        if not isinstance(action_budget, int) or action_budget < 1:
            return False
        return steps_run >= action_budget and self._barrier_was_observed(page)
