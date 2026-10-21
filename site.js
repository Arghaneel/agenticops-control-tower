// AgenticOps Control Tower product page: mobile menu and copy buttons.
const toggle = document.querySelector(".nav-toggle");
const links = document.querySelector("#nav-links");

toggle?.addEventListener("click", () => {
  const open = toggle.getAttribute("aria-expanded") !== "true";
  toggle.setAttribute("aria-expanded", String(open));
  links?.classList.toggle("open", open);
});

links?.addEventListener("click", (event) => {
  if (event.target instanceof HTMLAnchorElement && toggle?.getAttribute("aria-expanded") === "true") {
    toggle.setAttribute("aria-expanded", "false");
    links.classList.remove("open");
  }
});

async function copyText(text, label) {
  if (!label) return;
  const original = label.textContent;
  try {
    await navigator.clipboard.writeText(text);
    label.textContent = "Copied";
  } catch {
    label.textContent = "Select to copy";
  }
  setTimeout(() => { label.textContent = original; }, 1500);
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", () => copyText(button.dataset.copy, button.querySelector(".copy-state")));
});

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const target = document.getElementById(button.dataset.copyTarget);
    if (target) copyText(target.textContent.trim(), button);
  });
});
