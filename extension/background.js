// Forwards keyboard shortcuts to the page's AccessPath Assist content script.
chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || tab.id === undefined) return;
  try {
    await chrome.tabs.sendMessage(tab.id, { type: "command", command });
  } catch (error) {
    // Pages such as chrome:// cannot run content scripts; nothing to do there.
  }
});
