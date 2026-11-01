"""AccessPath Assist, the Chrome extension for keyboard and voice users."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from page_server import serve_pages
from playwright.sync_api import sync_playwright

EXTENSION = Path(__file__).resolve().parents[1] / "extension"

PAGE = """<!doctype html><html lang="en"><head><title>Shop</title>
<style>button:focus { outline: none }</style></head><body>
<nav><a href="/a">Deals</a> <a href="/b">Help</a></nav>
<main><h1>Basket</h1>
<div class="checkout" onclick="document.title='Checked out'">Check out</div>
<button tabindex="-1" onclick="document.title='Saved'">Save for later</button>
<button data-tooltip="remove-item"><svg aria-hidden="true" width="10" height="10"></svg></button>
<input type="search" aria-label="Search products">
<div role="tablist"><button role="tab" aria-selected="true">One</button>
<button role="tab" tabindex="-1">Two</button></div>
</main></body></html>"""


def test_manifest_is_a_valid_mv3_extension() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    assert manifest["manifest_version"] == 3
    assert set(manifest["permissions"]) <= {"storage", "activeTab"}  # nothing broader
    for path in [
        manifest["background"]["service_worker"],
        manifest["action"]["default_popup"],
        *manifest["content_scripts"][0]["js"],
        *manifest["content_scripts"][0]["css"],
        *manifest["icons"].values(),
    ]:
        assert (EXTENSION / path).is_file(), path
    assert {"skip-to-main", "show-landmarks", "toggle-voice", "check-page"} <= set(
        manifest["commands"]
    )
    popup = (EXTENSION / "popup.html").read_text()
    for control in ("focusRing", "keyboardFixes", "nameControls", "voice"):
        assert f'<label><input type="checkbox" id="{control}">' in popup  # labelled controls


def _with_script(page) -> None:
    page.add_script_tag(path=str(EXTENSION / "content.js"))


def test_content_script_fixes_and_checks_a_page() -> None:
    with serve_pages({"/": PAGE}) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(origin + "/")
        before = page.evaluate("() => null")
        _with_script(page)
        result = page.evaluate("() => window.__accesspathAssist.checkPage()")
        assert before is None
        assert result["fixed"] == {"madeOperable": 1, "unskipped": 1, "named": 1}
        assert result["clickOnly"] == 0 and result["skipped"] == 0
        assert result["outlineRemoved"] is True and result["hasMain"] is True
        assert page.evaluate("document.documentElement.classList.contains('ap-focus-ring')")
        checkout = page.locator(".checkout")
        assert (
            checkout.get_attribute("tabindex") == "0" and checkout.get_attribute("role") == "button"
        )
        checkout.focus()
        page.keyboard.press("Enter")
        assert page.title() == "Checked out"
        assert page.locator("button[data-tooltip]").get_attribute("aria-label") == "Remove item"
        # The inactive tab keeps tabindex=-1: tab lists use arrow keys, not Tab.
        assert page.locator("[role=tab]").nth(1).get_attribute("tabindex") == "-1"
        browser.close()


CAREFUL = """<!doctype html><html lang="en"><head><title>Cards</title></head><body><main>
<div class="card"><a href="/p/1" tabindex="-1"><img alt="Mug" width="20" height="20"></a>
<a href="/p/1">Blue mug</a></div>
<div class="toolbar"><button tabindex="0">Bold</button><button tabindex="-1">Italic</button></div>
<button tabindex="-1" id="lost">Save for later</button>
<span class="react-click" style="cursor:pointer">Remove</span>
<a href="#%E0%A4%A">Broken skip link</a>
<div id="later"></div>
</main></body></html>"""


def test_fixes_leave_deliberate_patterns_alone_undo_and_follow_new_content() -> None:
    with serve_pages({"/": CAREFUL}) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(origin + "/")
        _with_script(page)
        result = page.evaluate("() => window.__accesspathAssist.checkPage()")  # no URI error
        assert result["fixed"] == {"madeOperable": 1, "unskipped": 1, "named": 0}
        assert page.locator(".card a").first.get_attribute("tabindex") == "-1"  # duplicate link
        assert page.locator(".toolbar button").nth(1).get_attribute("tabindex") == "-1"  # roving
        assert page.locator("#lost").get_attribute("tabindex") == "0"
        assert page.locator(".react-click").get_attribute("role") == "button"
        # Content added later is fixed too.
        page.evaluate(
            "document.getElementById('later').innerHTML = "
            "'<button tabindex=\\'-1\\' id=\\'late\\'>Apply coupon</button>'"
        )
        page.wait_for_function("document.getElementById('late').getAttribute('tabindex') === '0'")
        # Turning the fixes off puts every attribute back.
        page.evaluate(
            "() => window.__accesspathAssist.handle({type: 'settings', settings: "
            "{keyboardFixes: false, nameControls: false, focusRing: false, voice: false}})"
        )
        assert page.locator("#lost").get_attribute("tabindex") == "-1"
        assert page.locator(".react-click").get_attribute("role") is None
        assert page.locator(".react-click").get_attribute("tabindex") is None
        assert page.locator("[data-ap-fixed]").count() == 0
        browser.close()


def test_voice_commands_and_landmarks() -> None:
    with serve_pages({"/": PAGE}) as origin, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(origin + "/")
        _with_script(page)
        run = "(text) => window.__accesspathAssist.runVoiceCommand(text)"
        assert page.evaluate(run, "go to main") == "Main content"
        assert page.evaluate("document.activeElement.tagName") == "MAIN"
        assert page.evaluate(run, "go to search") == "Search box"
        assert page.evaluate(run, "click save for later") == "Pressed Save for later"
        assert page.title() == "Saved"
        assert page.evaluate(run, "next").startswith("Next")
        assert page.evaluate(run, "open the moon").startswith("No control named")
        assert page.evaluate(run, "sing a song").startswith("Not a command")
        page.evaluate(
            "() => window.__accesspathAssist.handle({type: 'command', command: 'show-landmarks'})"
        )
        dialog = page.locator(".ap-assist-panel[role=dialog]")
        assert dialog.count() == 1 and "Main" in dialog.inner_text()
        assert page.evaluate("document.activeElement.closest('.ap-assist-panel') !== null")
        page.keyboard.press("Escape")
        assert dialog.count() == 0
        browser.close()


def test_the_real_extension_loads_and_answers_the_popup() -> None:
    with serve_pages({"/": PAGE}) as origin, sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                tempfile.mkdtemp(),
                headless=True,
                channel="chromium",
                args=[f"--disable-extensions-except={EXTENSION}", f"--load-extension={EXTENSION}"],
            )
        except Exception as error:  # Extension support depends on the local Chromium build.
            pytest.skip(f"Chromium cannot load extensions here: {error}")
        page = context.new_page()
        page.goto(origin + "/")
        page.wait_for_function("document.documentElement.classList.contains('ap-focus-ring')")
        assert page.locator(".checkout").get_attribute("tabindex") == "0"
        worker = (
            context.service_workers[0]
            if context.service_workers
            else context.wait_for_event("serviceworker")
        )
        result = worker.evaluate(
            """async () => {
                for (const tab of await chrome.tabs.query({})) {
                    try {
                        const answer = await chrome.tabs.sendMessage(tab.id, {type: 'check'});
                        if (answer) return answer;
                    } catch (error) {}
                }
                return null;
            }"""
        )
        assert result["unnamed"] == 0 and result["fixed"]["madeOperable"] == 1
        context.close()
