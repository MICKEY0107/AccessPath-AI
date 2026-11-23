// AccessPath Assist: helps people who use a keyboard or their voice on any website.
// The fixes and checks run locally in the page. Voice commands (off by default) use the
// browser's speech recognition, which Chrome may process on its servers.
(() => {
  if (window.__accesspathAssist) return;

  const DEFAULTS = {
    focusRing: true,
    keyboardFixes: true,
    nameControls: true,
    voice: false,
    voiceLang: "en-IN",
  };
  const CONTROL_SELECTOR =
    'a[href], button, input:not([type="hidden"]), select, textarea, summary, [tabindex], ' +
    '[role="button"], [role="link"], [role="checkbox"], [role="tab"], [role="menuitem"], ' +
    '[role="switch"], [contenteditable="true"]';
  const COMPOSITE =
    '[role="toolbar"], [role="menubar"], [role="menu"], [role="tablist"], [role="radiogroup"], ' +
    '[role="listbox"], [role="grid"], [role="tree"], [role="treegrid"]';
  const LANDMARKS =
    'main, [role="main"], nav, [role="navigation"], header, [role="banner"], footer, ' +
    '[role="contentinfo"], aside, [role="complementary"], form[aria-label], ' +
    '[role="search"], section[aria-label], section[aria-labelledby]';

  let settings = { ...DEFAULTS };
  const fixed = { madeOperable: 0, unskipped: 0, named: 0 };

  // Helpers ------------------------------------------------------------------

  const norm = (text) => (text || "").replace(/\s+/g, " ").trim();

  const spokenText = (text) => norm(String(text || "")
    .toLowerCase()
    .replace(/[.,!?;:]+/g, " "));

  const conversationalText = (text) => {
    let cleaned = spokenText(text);
    const starts = [
      /^(?:hey\s+)?access\s*path\s+assist\s+/,
      /^(?:please|kindly)\s+/,
      /^(?:can|could|would|will)\s+you\s+/,
      /^(?:i\s+want\s+to|i\s+would\s+like\s+to|help\s+me\s+to)\s+/,
    ];
    let changed = true;
    while (changed) {
      changed = false;
      for (const pattern of starts) {
        const next = cleaned.replace(pattern, "");
        if (next !== cleaned) { cleaned = next; changed = true; }
      }
    }
    cleaned = cleaned.replace(/\s+(?:please|for\s+me|thanks|thank\s+you)$/g, "");
    return norm(cleaned);
  };

  const isVisible = (element) => {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    if (style.visibility === "hidden" || style.display === "none") return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  const accessibleName = (element) => {
    const labelledBy = (element.getAttribute("aria-labelledby") || "")
      .split(/\s+/).filter(Boolean)
      .map((id) => norm(document.getElementById(id)?.textContent)).join(" ");
    const labels = Array.from(element.labels || []).map((label) => norm(label.textContent)).join(" ");
    const visibleText = Array.from(element.childNodes)
      .filter((node) => !(node instanceof Element && node.getAttribute("aria-hidden") === "true"))
      .map((node) => node.textContent).join(" ");
    const imageAlt = Array.from(element.querySelectorAll("img[alt]")).map((img) => img.alt).join(" ");
    return norm(
      element.getAttribute("aria-label") || labelledBy || labels || visibleText || imageAlt ||
        element.getAttribute("title") ||
        (element.tagName === "INPUT" && element.type === "submit" ? "Submit" : "") ||
        element.getAttribute("placeholder") ||
        (element.tagName === "INPUT" ? element.getAttribute("value") : "") || "",
    );
  };

  const focusables = () =>
    Array.from(document.querySelectorAll(CONTROL_SELECTOR)).filter(
      (element) => element.tabIndex >= 0 && !element.disabled && isVisible(element) &&
        !element.closest(".ap-assist-panel"),
    );

  const clickOnly = () =>
    Array.from(document.querySelectorAll("div, span, li, img, p, td, svg")).filter((element) => {
      if (element.closest(".ap-assist-panel") || !isVisible(element)) return false;
      if (element.tabIndex >= 0 || element.closest("a[href], button, label, summary")) return false;
      if (element.querySelector("a[href], button, input, select, textarea, [tabindex]")) return false;
      if (element.hasAttribute("onclick")) return true;
      if (element.getAttribute("role") === "button" && element.tabIndex < 0) return true;
      // Frameworks attach click handlers in script, so look for what a sighted user sees:
      // a small element that starts a pointer cursor (not one inherited from a parent).
      const parent = element.parentElement;
      const rect = element.getBoundingClientRect();
      return getComputedStyle(element).cursor === "pointer" &&
        (!parent || getComputedStyle(parent).cursor !== "pointer") &&
        rect.width <= 400 && rect.height <= 120 && norm(element.textContent).length <= 60 &&
        Boolean(norm(element.textContent) || element.getAttribute("aria-label") ||
          element.tagName === "IMG" || element.tagName.toLowerCase() === "svg");
    });

  // Controls taken out of the Tab order that look like they were left out by mistake. Sites
  // also do this on purpose, so these are skipped: duplicate links (a card's image and
  // title both link to one page), roving tabindex (a sibling of the same kind is in the
  // Tab order), anything behind an open modal, inert or hidden content, and unnamed ones.
  const skipped = () => {
    const modal = document.querySelector('dialog[open], [aria-modal="true"]:not(.ap-assist-panel)');
    const reachableLinks = new Set(
      focusables().filter((element) => element.matches("a[href]")).map((element) => element.href),
    );
    return Array.from(
      document.querySelectorAll('button, a[href], input, select, textarea, [role="button"]'),
    ).filter((element) => {
      if (element.getAttribute("tabindex") !== "-1" || element.disabled) return false;
      if (!isVisible(element) || element.closest(COMPOSITE)) return false;
      if (element.closest("[aria-hidden='true'], [inert], .ap-assist-panel")) return false;
      if (modal && !modal.contains(element)) return false;
      if (element.matches("a[href]") && reachableLinks.has(element.href)) return false;
      const siblings = element.parentElement ? Array.from(element.parentElement.children) : [];
      if (siblings.some((other) => other !== element && other.tagName === element.tagName &&
        other.getAttribute("tabindex") === "0")) return false;
      return Boolean(accessibleName(element));
    });
  };

  const unnamed = () =>
    focusables().filter((element) => {
      const tag = element.tagName.toLowerCase();
      const role = element.getAttribute("role");
      const interactive = ["a", "button", "select", "textarea", "input", "summary"].includes(tag) || role;
      return interactive && !accessibleName(element);
    });

  // A short name guessed from things a sighted user sees: tooltip, icon class, test id.
  const guessName = (element) => {
    const hints = [
      element.getAttribute("data-tooltip"), element.getAttribute("data-title"),
      element.querySelector("svg title")?.textContent, element.getAttribute("name"),
      element.getAttribute("data-testid"), element.getAttribute("id"),
      Array.from(element.classList).concat(
        Array.from(element.querySelector("[class]")?.classList || []),
      ).find((name) => /icon|btn|button/i.test(name)),
    ].filter(Boolean);
    const hint = hints[0];
    if (!hint) return "";
    const words = String(hint)
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/[-_]+/g, " ")
      .replace(/\b(icon|btn|button|fa|svg|ico|js)\b/gi, " ");
    const name = norm(words);
    return name ? name[0].toUpperCase() + name.slice(1) : "";
  };

  // Fixes --------------------------------------------------------------------

  const activate = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.currentTarget.click();
  };

  // Every change remembers the attributes it replaced, so turning a fix off undoes it.
  const changes = [];
  const change = (element, kind, attributes) => {
    const before = {};
    for (const [name, value] of Object.entries(attributes)) {
      before[name] = element.getAttribute(name);
      element.setAttribute(name, value);
    }
    element.setAttribute("data-ap-fixed", kind);
    changes.push({ element, kind, before });
  };

  const undo = (kinds) => {
    for (let index = changes.length - 1; index >= 0; index -= 1) {
      const { element, kind, before } = changes[index];
      if (!kinds.includes(kind)) continue;
      for (const [name, value] of Object.entries(before)) {
        if (value === null) element.removeAttribute(name); else element.setAttribute(name, value);
      }
      if (kind === "operable") element.removeEventListener("keydown", activate);
      element.removeAttribute("data-ap-fixed");
      changes.splice(index, 1);
      if (kind === "operable") fixed.madeOperable -= 1;
      else if (kind === "unskipped") fixed.unskipped -= 1;
      else fixed.named -= 1;
    }
  };

  const applyKeyboardFixes = () => {
    for (const element of clickOnly()) {
      if (element.hasAttribute("data-ap-fixed")) continue;
      const attributes = { tabindex: "0" };
      if (!element.getAttribute("role")) attributes.role = "button";
      change(element, "operable", attributes);
      element.addEventListener("keydown", activate);
      fixed.madeOperable += 1;
    }
    for (const element of skipped()) {
      if (element.hasAttribute("data-ap-fixed")) continue;
      change(element, "unskipped", { tabindex: "0" });
      fixed.unskipped += 1;
    }
  };

  const applyNames = () => {
    for (const element of unnamed()) {
      if (element.hasAttribute("data-ap-fixed")) continue;
      const name = guessName(element);
      if (!name) continue;
      change(element, "named", { "aria-label": name });
      fixed.named += 1;
    }
  };

  const applySettings = () => {
    document.documentElement.classList.toggle("ap-focus-ring", Boolean(settings.focusRing));
    if (settings.keyboardFixes) applyKeyboardFixes(); else undo(["operable", "unskipped"]);
    if (settings.nameControls) applyNames(); else undo(["named"]);
  };

  // Single-page apps add content later: re-apply the fixes, at most twice a second.
  let pending = null;
  const observer = new MutationObserver((records) => {
    if (pending || !(settings.keyboardFixes || settings.nameControls)) return;
    if (records.every((record) => panel && panel.contains(record.target))) return;
    pending = setTimeout(() => {
      pending = null;
      observer.disconnect();
      if (settings.keyboardFixes) applyKeyboardFixes();
      if (settings.nameControls) applyNames();
      observer.observe(document.documentElement, { childList: true, subtree: true });
    }, 500);
  });

  // Page check (the same problems AccessPath AI reports, in a quick local form) ---

  const checkPage = () => {
    const main = document.querySelector('main, [role="main"]');
    const firstLink = focusables()[0];
    const target = (href) => {
      try {
        return document.getElementById(decodeURIComponent(href.slice(1)));
      } catch (error) {
        return document.getElementById(href.slice(1)); // Not valid percent-encoding.
      }
    };
    const skipLink = firstLink && /^#./.test(firstLink.getAttribute("href") || "") &&
      target(firstLink.getAttribute("href"));
    const outlineRemoved = Array.from(document.styleSheets).some((sheet) => {
      try {
        return Array.from(sheet.cssRules || []).some((rule) =>
          /:focus/.test(rule.selectorText || "") && /outline:\s*(none|0)/.test(rule.cssText));
      } catch (error) {
        return false; // Cross-origin stylesheet.
      }
    });
    return {
      url: location.href,
      clickOnly: clickOnly().length,
      skipped: skipped().length,
      unnamed: unnamed().length,
      hasMain: Boolean(main),
      hasSkipLink: Boolean(skipLink),
      headings: document.querySelectorAll("h1, h2, h3, [role='heading']").length,
      outlineRemoved,
      focusable: focusables().length,
      fixed: { ...fixed },
    };
  };

  // Navigation ---------------------------------------------------------------

  const focusElement = (element) => {
    if (!element) return false;
    if (element.tabIndex < 0 && !/^(a|button|input|select|textarea)$/i.test(element.tagName)) {
      element.setAttribute("tabindex", "-1");
    }
    element.focus({ preventScroll: false });
    element.scrollIntoView({ block: "center" });
    return document.activeElement === element;
  };

  const skipToMain = () =>
    focusElement(document.querySelector('main, [role="main"]') || document.querySelector("h1"));

  const moveFocus = (step) => {
    const items = focusables();
    if (!items.length) return false;
    const index = items.indexOf(document.activeElement);
    const next = items[(index + step + items.length) % items.length];
    return focusElement(next);
  };

  let panel = null;
  let returnFocus = null;

  const closePanel = () => {
    if (!panel) return;
    panel.remove();
    panel = null;
    if (returnFocus && document.contains(returnFocus)) returnFocus.focus();
  };

  const openPanel = (title, items) => {
    closePanel();
    returnFocus = document.activeElement;
    panel = document.createElement("div");
    panel.className = "ap-assist-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.setAttribute("aria-label", title);
    const heading = document.createElement("h2");
    heading.textContent = title;
    panel.append(heading);
    const list = document.createElement("ul");
    for (const item of items) {
      const entry = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.label;
      button.addEventListener("click", () => { closePanel(); item.action(); });
      entry.append(button);
      list.append(entry);
    }
    if (!items.length) {
      const empty = document.createElement("li");
      empty.textContent = "Nothing found on this page.";
      list.append(empty);
    }
    panel.append(list);
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Close (Escape)";
    close.addEventListener("click", closePanel);
    panel.append(close);
    panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); closePanel(); return; }
      if (event.key !== "Tab") return;
      const buttons = Array.from(panel.querySelectorAll("button"));
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    document.body.append(panel);
    (panel.querySelector("li button") || close).focus();
  };

  const landmarkName = (element) => {
    const role = element.getAttribute("role") || {
      main: "Main", nav: "Navigation", header: "Banner", footer: "Footer", aside: "Complementary",
      form: "Form", section: "Region",
    }[element.tagName.toLowerCase()] || element.tagName.toLowerCase();
    const label = element.getAttribute("aria-label") ||
      norm(document.getElementById(element.getAttribute("aria-labelledby") || "")?.textContent);
    return label ? `${role[0].toUpperCase()}${role.slice(1)}: ${label}` : role[0].toUpperCase() + role.slice(1);
  };

  const showLandmarks = () => {
    const items = [];
    for (const element of document.querySelectorAll(LANDMARKS)) {
      if (!isVisible(element)) continue;
      items.push({ label: landmarkName(element), action: () => focusElement(element) });
    }
    for (const heading of document.querySelectorAll("h1, h2, h3")) {
      if (!isVisible(heading) || !norm(heading.textContent)) continue;
      items.push({
        label: `${heading.tagName}: ${norm(heading.textContent).slice(0, 80)}`,
        action: () => focusElement(heading),
      });
    }
    openPanel("Landmarks and headings", items.slice(0, 60));
  };

  // Voice --------------------------------------------------------------------

  let status = null;
  const say = (text) => {
    if (!status) {
      status = document.createElement("div");
      status.className = "ap-assist-status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      document.body.append(status);
    }
    status.hidden = false;
    status.textContent = text;
  };

  const findByName = (words) => {
    const wanted = conversationalText(words)
      .replace(/^(?:on|the)\s+/, "")
      .replace(/\s+(?:button|link|control|field)$/, "");
    if (!wanted) return null;
    const items = focusables().map((element) => ({
      element,
      name: spokenText(accessibleName(element)),
    })).filter((item) => item.name);
    const exact = items.find((item) => item.name === wanted);
    if (exact) return exact.element;
    const contained = items.find((item) => item.name.includes(wanted));
    if (contained) return contained.element;
    const wantedTokens = wanted.split(" ").filter((word) => word.length > 1);
    const tokenMatch = items
      .filter((item) => wantedTokens.every((word) => item.name.split(" ").includes(word)))
      .sort((left, right) => left.name.length - right.name.length)[0];
    return tokenMatch?.element || null;
  };

  const searchBox = () => document.querySelector(
    'input[type="search"], [role="search"] input, input[name*="search" i], ' +
    'input[aria-label*="search" i], input[placeholder*="search" i]',
  );

  const fillSearch = (query) => {
    const search = searchBox();
    if (!search || !focusElement(search)) return false;
    const prototype = search instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (setter) setter.call(search, query); else search.value = query;
    search.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: query }));
    search.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  };

  const voiceHelp = () => {
    openPanel("Voice command examples", [
      { label: "Try: move to the next item", action: () => moveFocus(1) },
      { label: "Try: go to main content", action: skipToMain },
      { label: "Try: go to the search box", action: () => focusElement(searchBox()) },
      { label: "Show landmarks", action: showLandmarks },
      { label: "Stop listening", action: () => stopVoice() },
    ]);
  };

  const result = (message, performed = true, recognized = true) => ({
    message, performed, recognized,
  });

  // Turns a spoken phrase into an action. The richer result lets speech recognition
  // try another transcript alternative when one guess names a control that is not present.
  const executeVoiceCommand = (phrase) => {
    let text = conversationalText(phrase);
    text = text
      .replace(/^(?:take|bring|move)\s+me\s+to\s+/, "go to ")
      .replace(/^navigate\s+to\s+/, "go to ")
      .replace(/^(click|press|open|select|activate)\s+on\s+/, "$1 ");
    let match;
    if (/^(?:next|tab|next item|move to the next item|go next)$/.test(text)) {
      return moveFocus(1) ? result("Next") : result("Nothing to focus", false);
    }
    if (/^(previous|back|shift tab|previous item)$/.test(text)) {
      return moveFocus(-1) ? result("Previous") : result("Nothing to focus", false);
    }
    if (/^(click|press|select|activate|open|enter)$/.test(text)) {
      const target = document.activeElement;
      if (!target || target === document.body) return result("Nothing is focused", false);
      target.click();
      return result(`Pressed ${accessibleName(target) || target.tagName.toLowerCase()}`);
    }
    if ((match = text.match(/^(?:search|look up|find)\s+(?:for\s+)?(.+)$/))) {
      const query = conversationalText(match[1]);
      if (/^(?:the\s+)?search(?:\s+box|\s+field)?$/.test(query)) {
        return focusElement(searchBox()) ? result("Search box") : result("No search box", false);
      }
      return fillSearch(query)
        ? result(`Search filled with ${query}`)
        : result("No search box", false);
    }
    if ((match = text.match(/^(?:click|press|open|select|go to|focus) (.+)$/))) {
      const name = conversationalText(match[1]).replace(/^(?:the)\s+/, "");
      if (/^(main|main content|content)$/.test(name)) {
        return skipToMain() ? result("Main content") : result("No main content", false);
      }
      if (/^search(?:\s+box|\s+field)?$/.test(name)) {
        return focusElement(searchBox()) ? result("Search box") : result("No search box", false);
      }
      const target = findByName(name);
      if (!target) return result(`No control named “${name}”`, false);
      focusElement(target);
      if (!/^(go to|focus)/.test(text)) target.click();
      return result(`${/^(go to|focus)/.test(text) ? "Focused" : "Pressed"} ${accessibleName(target)}`);
    }
    if (/^scroll down(?: a little| one page)?$/.test(text)) {
      window.scrollBy(0, innerHeight * 0.8);
      return result("Scrolled down");
    }
    if (/^scroll up(?: a little| one page)?$/.test(text)) {
      window.scrollBy(0, -innerHeight * 0.8);
      return result("Scrolled up");
    }
    if (/^(?:go to |scroll to )?(?:the )?top$/.test(text)) {
      window.scrollTo(0, 0);
      return result("Top of page");
    }
    if (/^(?:go to |scroll to )?(?:the )?bottom$/.test(text)) {
      window.scrollTo(0, document.documentElement.scrollHeight);
      return result("Bottom of page");
    }
    if (/^(?:show |open )?(?:the )?landmarks$/.test(text)) {
      showLandmarks();
      return result("Landmarks");
    }
    if (/^(?:help|voice help|what can i say|show commands)$/.test(text)) {
      voiceHelp();
      return result("Voice command examples");
    }
    if (/^(skip|skip to main|main content)$/.test(text)) {
      return skipToMain() ? result("Main content") : result("No main content", false);
    }
    if (/^(stop|stop listening|turn off voice)$/.test(text)) {
      stopVoice();
      return result("Voice off");
    }
    return result(`Not a command: “${phrase}”`, false, false);
  };

  const runVoiceCommand = (phrase) => executeVoiceCommand(phrase).message;

  // Voice listens only in the tab in front: it pauses when the tab is hidden, so a
  // command never acts on a page the person cannot see.
  let recognition = null;
  let voiceRequested = false;
  let restarts = [];
  const FATAL_VOICE_ERRORS = ["not-allowed", "service-not-allowed", "audio-capture"];
  const startVoice = () => {
    voiceRequested = true;
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      voiceRequested = false;
      say("Voice commands need speech recognition in Chrome.");
      return false;
    }
    if (recognition) return true;
    if (document.visibilityState !== "visible") return false;
    const current = new Recognition();
    recognition = current;
    current.continuous = true;
    current.interimResults = false;
    current.maxAlternatives = 3;
    current.lang = settings.voiceLang || navigator.language || document.documentElement.lang || "en-US";
    current.onresult = (event) => {
      if (document.visibilityState !== "visible") return;
      let fallback = null;
      let selected = null;
      const start = Number.isInteger(event.resultIndex) ? event.resultIndex : 0;
      for (let resultIndex = start; resultIndex < event.results.length && !selected; resultIndex += 1) {
        const speechResult = event.results[resultIndex];
        if (speechResult.isFinal === false) continue;
        for (let alternativeIndex = 0; alternativeIndex < speechResult.length; alternativeIndex += 1) {
          const phrase = speechResult[alternativeIndex].transcript;
          const outcome = executeVoiceCommand(phrase);
          if (!fallback || outcome.recognized) fallback = { phrase, outcome };
          if (outcome.performed) { selected = { phrase, outcome }; break; }
        }
      }
      const chosen = selected || fallback;
      if (!chosen) return;
      restarts = [];
      say(`Heard “${norm(chosen.phrase)}”. ${chosen.outcome.message}`);
    };
    current.onend = () => {
      if (recognition !== current) return;
      if (!voiceRequested) { recognition = null; return; }
      // Restart after silence, but give up if it keeps ending at once.
      const now = Date.now();
      restarts = restarts.filter((time) => now - time < 10000).concat(now);
      if (restarts.length > 5) {
        recognition = null;
        voiceRequested = false;
        say("Voice stopped because recognition kept ending. Check the microphone and start it again.");
        return;
      }
      setTimeout(() => {
        if (recognition !== current || !voiceRequested) return;
        try { current.start(); } catch (error) {
          recognition = null;
          voiceRequested = false;
          say("Voice could not restart. Start listening again.");
        }
      }, 300);
    };
    current.onerror = (event) => {
      if (FATAL_VOICE_ERRORS.includes(event.error)) {
        recognition = null;
        voiceRequested = false;
        say(event.error === "audio-capture" ? "Voice: no microphone found." : "Voice: microphone access was not allowed.");
        return;
      }
      if (event.error !== "no-speech" && event.error !== "aborted") say(`Voice: ${event.error}`);
    };
    try {
      current.start();
    } catch (error) {
      recognition = null;
      voiceRequested = false;
      say("Voice could not start. Check Chrome's microphone permission and try again.");
      return false;
    }
    say(`Listening in ${current.lang}: say “next”, “click Sign in”, “search for…”, or “voice help”.`);
    return true;
  };
  const stopVoice = (quiet = false) => {
    voiceRequested = false;
    const current = recognition;
    recognition = null;
    if (current) current.stop();
    if (!quiet) say("Voice commands off.");
  };
  document.addEventListener("visibilitychange", () => {
    if (!voiceRequested && !settings.voice) return;
    if (document.visibilityState === "visible") startVoice(); else stopVoice(true);
  });

  // Wiring -------------------------------------------------------------------

  const handle = (message) => {
    if (!message) return null;
    if (message.type === "settings") {
      const previousLanguage = settings.voiceLang;
      settings = { ...DEFAULTS, ...message.settings };
      applySettings();
      if (recognition && previousLanguage !== settings.voiceLang) stopVoice(true);
      if (settings.voice) startVoice(); else if (recognition) stopVoice();
      return checkPage();
    }
    if (message.type === "voice-status") {
      return {
        enabled: Boolean(settings.voice),
        listening: Boolean(recognition && voiceRequested),
        language: settings.voiceLang,
      };
    }
    if (message.type === "check") return checkPage();
    if (message.type === "fix") { applyKeyboardFixes(); applyNames(); return checkPage(); }
    if (message.type === "command") {
      if (message.command === "skip-to-main") return skipToMain();
      if (message.command === "show-landmarks") { showLandmarks(); return true; }
      if (message.command === "toggle-voice") return recognition ? (stopVoice(), false) : startVoice();
      if (message.command === "check-page") {
        const result = checkPage();
        say(`${result.skipped + result.clickOnly} unreachable, ${result.unnamed} unnamed controls`);
        return result;
      }
    }
    if (message.type === "voice-text") return runVoiceCommand(message.text);
    return null;
  };

  window.__accesspathAssist = {
    handle, checkPage, runVoiceCommand, applySettings, fixed,
    get settings() { return settings; },
  };
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      sendResponse(handle(message));
    });
    chrome.storage.sync.get(DEFAULTS, (stored) => handle({ type: "settings", settings: stored }));
  } else {
    applySettings();
  }
})();
