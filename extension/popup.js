// The AccessPath Assist popup: settings, a quick page check, and navigation helpers.
const DEFAULTS = { focusRing: true, keyboardFixes: true, nameControls: true, voice: false };
const KEYS = Object.keys(DEFAULTS);

const send = async (message) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || tab.id === undefined) return null;
  try {
    return await chrome.tabs.sendMessage(tab.id, message);
  } catch (error) {
    return null; // chrome:// pages and the Web Store do not allow extensions.
  }
};

const line = (ok, text) => {
  const item = document.createElement("li");
  item.className = ok ? "ok" : "problem";
  item.textContent = `${ok ? "OK" : "Problem"}: ${text}`;
  return item;
};

const show = (result) => {
  const box = document.getElementById("result");
  box.replaceChildren();
  if (!result) {
    box.textContent = "This page does not allow extensions.";
    return;
  }
  const heading = document.createElement("strong");
  heading.textContent = "This page";
  const list = document.createElement("ul");
  list.append(
    line(result.skipped === 0, `${result.skipped} visible controls skipped by Tab`),
    line(result.clickOnly === 0, `${result.clickOnly} click-only elements`),
    line(result.unnamed === 0, `${result.unnamed} controls without a name`),
    line(result.hasMain || result.hasSkipLink, result.hasSkipLink ? "skip link" : result.hasMain ? "main landmark" : "no skip link or main landmark"),
    line(!result.outlineRemoved, result.outlineRemoved ? "focus outline removed by the site" : "focus outline kept"),
  );
  const fixedTotal = result.fixed.madeOperable + result.fixed.unskipped + result.fixed.named;
  box.append(heading, list);
  if (fixedTotal) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = `Fixed for you on this page: ${result.fixed.madeOperable} made keyboard-operable, ${result.fixed.unskipped} put back in the Tab order, ${result.fixed.named} named.`;
    box.append(note);
  }
};

chrome.storage.sync.get(DEFAULTS, (stored) => {
  for (const key of KEYS) {
    const box = document.getElementById(key);
    box.checked = Boolean(stored[key]);
    box.addEventListener("change", async () => {
      const settings = Object.fromEntries(KEYS.map((name) => [name, document.getElementById(name).checked]));
      await chrome.storage.sync.set(settings);
      show(await send({ type: "settings", settings }));
    });
  }
});

document.getElementById("check").addEventListener("click", async () => show(await send({ type: "check" })));
document.getElementById("landmarks").addEventListener("click", async () => {
  await send({ type: "command", command: "show-landmarks" });
  window.close();
});
document.getElementById("main").addEventListener("click", async () => {
  await send({ type: "command", command: "skip-to-main" });
  window.close();
});
