(() => {
  const slots = [...document.querySelectorAll("[data-slot-id]")];
  const continueButton = document.getElementById("continue");
  const status = document.getElementById("selection-status");

  for (const slot of slots) {
    slot.addEventListener("click", () => {
      for (const candidate of slots) candidate.setAttribute("aria-pressed", "false");
      slot.setAttribute("aria-pressed", "true");
      continueButton.disabled = false;
      status.textContent = `${slot.textContent.trim()} selected.`;
    });
  }

  continueButton?.addEventListener("click", () => {
    window.location.href = "details.html";
  });
})();
