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
| Voice commands | Alt+Shift+V, then say “next”, “previous”, “click”, “click Sign in”, “go to search”, “go to main”, “scroll down”, “landmarks”, “stop listening”. English commands; it listens only in the tab in front and stops if the microphone is blocked |
| Check this page | Counts controls Tab skips, click-only elements and unnamed controls, and says whether there is a skip link or main landmark and whether the focus outline was removed |

## Install (developer mode)

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Choose **Load unpacked** and select this `extension` folder.
3. Pin **AccessPath Assist** and open its popup to choose the features. Shortcuts can be
   changed at `chrome://extensions/shortcuts`.

## Privacy

The extension asks only for `storage` (your settings) and `activeTab`, and it sends
nothing anywhere itself: the fixes and the page check run in the page on your computer.
Voice commands (off by default) use Chrome's built-in speech recognition, which asks for
the microphone on each site the first time and may process speech on Google's servers;
leave voice off if that is a concern.

## Tests

`tests/test_extension.py` loads the real extension in Chromium and checks the fixes (and
what they leave alone), undoing them, new content, the page check, voice command handling
and the landmarks dialog.
