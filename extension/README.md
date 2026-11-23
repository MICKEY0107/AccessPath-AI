# AccessPath Assist (Chrome extension)

Helps people who use a keyboard or their voice to use any website. It is the user-side
companion to AccessPath AI: AccessPath finds keyboard barriers for the people who build a
site; Assist works around the most common ones for the people who visit it.

## What it does

| Feature | How |
|---|---|
| Strong focus ring | A thick, high-contrast outline on whatever has keyboard focus, even where the site removed it |
| Skip to main content | Alt+Shift+M, or say “go to main” |
| Landmarks and headings | Alt+Shift+L opens a list; choose one to jump there (Escape closes) |
| Keyboard fixes | Click-only elements (a `div` with a click handler, or a small element with a pointer cursor) get Tab and Enter/Space. Visible, named buttons and links hidden from Tab with `tabindex="-1"` are put back, except where sites do this on purpose: tabs, menus and toolbars with arrow keys, a second link to the same page, content behind an open dialog, and hidden or inert content. Content added later (single-page apps) is fixed too, and turning a fix off puts the page back as it was |
| Names for unnamed buttons | Icon buttons with no name get one from their tooltip, icon or id, so screen readers can announce them |
| Voice commands | Understands short commands and natural requests such as “please take me to the search box”, “click on the Sign in button”, “search for accessible travel”, “go to main”, “scroll down”, “what can I say?” and “stop listening”. It checks up to three speech-recognition alternatives and acts only in the visible tab. A search request fills the search field but does not submit it automatically. |
| Check this page | Counts controls Tab skips, click-only elements and unnamed controls, and says whether there is a skip link or main landmark and whether the focus outline was removed |

## Install (developer mode)

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Choose **Load unpacked** and select this `extension` folder.
3. Pin **AccessPath Assist** and open its popup.
4. Choose the English variant closest to your accent. English (India) is the default.
5. Select **Start listening**, allow microphone access when Chrome asks, and wait for the
   dark listening message on the page.

Shortcuts can be changed at `chrome://extensions/shortcuts`. `Alt+Shift+V` starts or stops
voice control without opening the popup.

## Voice check

Use a normal `http` or `https` page; Chrome does not allow content scripts on pages such as
`chrome://extensions` or the Chrome Web Store. Test these in order:

1. Say “go to main”. Focus should move to the page's main content.
2. Say “please take me to the search box”. Focus should move to the search field.
3. Say “search for web accessibility”. The words should appear in the field, but the form
   should not be submitted.
4. Say “click Sign in” on a page with a clearly named Sign in control.
5. Say “what can I say?” to open the accessible command help panel.
6. Say “stop listening”.

The page message shows both what Chrome heard and what the extension did. If it says that
microphone access was not allowed, enable the microphone for that site in Chrome, reload the
page and choose **Start listening** again. Check that the correct microphone is selected in
Chrome if the extension reports that no microphone was found.

## Privacy

The extension asks for `storage` (your settings) and `activeTab`. Its content script runs
on every http and https page so the fixes can apply, which Chrome shows at install as
access to the sites you visit. It sends nothing anywhere itself: the fixes and the page
check run in the page on your computer.
Voice commands (off by default) use Chrome's built-in speech recognition, which asks for
the microphone on a site the first time and may process speech on Google's servers. The
extension itself does not save transcripts or send page content to AccessPath AI. Leave
voice off if browser speech processing is not acceptable for the situation.

## Tests

`tests/test_extension.py` loads the real extension in Chromium and checks the fixes (and
what they leave alone), undoing them, new content, the page check, natural voice phrasing,
language selection, recognition alternatives, permission errors and the landmarks dialog.
