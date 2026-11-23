// The AccessPath Assist popup: settings, a quick page check, and navigation helpers.
const DEFAULTS = {
  focusRing: true,
  keyboardFixes: true,
  nameControls: true,
  voice: false,
  voiceLang: "en-IN",
};
const TOGGLE_KEYS = ["focusRing", "keyboardFixes", "nameControls", "voice"];

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

const currentSettings = () => ({
  ...Object.fromEntries(
    TOGGLE_KEYS.map((name) => [name, document.getElementById(name).checked]),
  ),
  voiceLang: document.getElementById("voiceLang").value,
});

const showVoiceStatus = (status) => {
  const line = document.getElementById("voiceStatus");
  const button = document.getElementById("startVoice");
  if (!status) {
    line.textContent = "Voice is unavailable on this page.";
    button.disabled = true;
    return;
  }
  line.textContent = status.listening
    ? `Listening (${status.language}). Speak after the microphone prompt.`
    : "Not listening. Chrome may ask for microphone access when you start.";
  button.textContent = status.listening ? "Listening" : "Start listening";
  button.disabled = Boolean(status.listening);
};

const saveAndApply = async () => {
  const settings = currentSettings();
  await chrome.storage.sync.set(settings);
  show(await send({ type: "settings", settings }));
  showVoiceStatus(await send({ type: "voice-status" }));
};

chrome.storage.sync.get(DEFAULTS, (stored) => {
  for (const key of TOGGLE_KEYS) {
    const box = document.getElementById(key);
    box.checked = Boolean(stored[key]);
    box.addEventListener("change", saveAndApply);
  }
  document.getElementById("voiceLang").value = stored.voiceLang || DEFAULTS.voiceLang;
  document.getElementById("voiceLang").addEventListener("change", saveAndApply);
  send({ type: "voice-status" }).then(showVoiceStatus);
});

document.getElementById("startVoice").addEventListener("click", async () => {
  document.getElementById("voice").checked = true;
  await saveAndApply();
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
