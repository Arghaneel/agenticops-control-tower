/* AgenticOps Control Tower product page.
   Scripts copied from the DeepAgentLabs website (deepagentlabs.github.io, assets/js/*.js),
   each in its own block so their top-level names stay separate. Changes from the originals:
   - usecases-data.js: the Control Tower entry lists this repository's published use cases;
   - usecases.js / product.js: links to other packages are absolute (https://deepagentlabs.io/...);
   - product.js: screenshots open enlarged only when the figure contains an image. */

/* ---- site.js ---- */
{
const toggle = document.querySelector(".nav-toggle");
const nav = document.querySelector("#site-nav");

toggle?.addEventListener("click", () => {
  const open = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!open));
  nav?.classList.toggle("open", !open);
  toggle.textContent = open ? "Menu" : "Close";
});

nav?.querySelectorAll("a").forEach((link) =>
  link.addEventListener("click", () => {
    nav.classList.remove("open");
    toggle?.setAttribute("aria-expanded", "false");
    if (toggle) toggle.textContent = "Menu";
  }),
);

document.querySelector("#year").textContent = String(new Date().getFullYear());

const faqTriggers = [...document.querySelectorAll(".faq-trigger")];

faqTriggers.forEach((trigger) => {
  trigger.addEventListener("click", () => {
    const open = trigger.getAttribute("aria-expanded") !== "true";

    faqTriggers.forEach((item) => {
      const expanded = item === trigger && open;
      item.setAttribute("aria-expanded", String(expanded));
      item.closest(".faq-item")?.classList.toggle("is-open", expanded);
      const answer = document.getElementById(
        item.getAttribute("aria-controls"),
      );
      answer?.setAttribute("aria-hidden", String(!expanded));
    });
  });
});
}

/* ---- usecases-data.js ---- */
{
/* Use cases menu content: the ONLY place to edit it.
   Read by assets/js/usecases.js (builds the dropdown on every page) and by 404.html
   (shows the right name on "coming soon" pages).

   - packages: the six fixed categories, in the same order as the Products and Docs menus.
     Keep the ids; they match the product URLs. "summary" is the short grey line under the name.
   - useCases: placeholder examples for now. Replace the titles and slugs once the real
     use cases exist. They power the "Most asked" chips and the "coming soon" page names.

   Links (built automatically, or set your own):
     package item    -> /<id>/usecases/              (override with  href: "...")
     each use case   -> /<id>/usecases/<slug>/       (override with  href: "...", e.g. a GitHub link)

   "Most asked" chips in the dark card: add  mostAsked: "Short label"  to any use case.
   Chips appear in the order the use cases are listed here. Aim for about five. */
window.DAL_USECASES = {
  packages: [
    {
      id: "agenticlens",
      name: "AgenticLens",
      summary: "Trace runs, track cost, gate releases.",
      useCases: [
        { title: "Trace every agent run", slug: "trace-agent-runs" },
        { title: "Track cost and tokens", slug: "cost-tracking", mostAsked: "Cost tracking" },
        { title: "Gate releases on latency", slug: "release-gates" }
      ]
    },
    {
      id: "agentic-chaos",
      name: "Agentic Chaos",
      summary: "Break tools on purpose before production does.",
      useCases: [
        { title: "Simulate tool failures", slug: "tool-failures", mostAsked: "Tool failures" },
        { title: "Test timeouts and rate limits", slug: "timeouts-rate-limits" },
        { title: "Catch drift before production", slug: "drift-testing" }
      ]
    },
    {
      id: "agentic-sidecar",
      name: "Agentic Sidecar",
      summary: "Check every action before the agent takes it.",
      useCases: [
        { title: "Block unsafe actions", slug: "block-unsafe-actions", mostAsked: "Unsafe actions" },
        { title: "Check actions against intent", slug: "intent-checks" },
        { title: "Enforce team policies", slug: "policy-enforcement" }
      ]
    },
    {
      id: "agentic-evals",
      name: "Agentic Evals",
      summary: "Score answers and block bad releases in CI.",
      useCases: [
        { title: "Score agent answers", slug: "score-answers" },
        { title: "Check tool-call paths", slug: "trajectory-checks" },
        { title: "Block bad releases in CI", slug: "ci-gate", mostAsked: "CI gate" }
      ]
    },
    {
      id: "mcp",
      name: "MCP Server",
      summary: "Every tool from one MCP client.",
      useCases: [
        { title: "All tools from one client", slug: "one-client" },
        { title: "Validate runs against the spec", slug: "spec-validation" },
        { title: "Connect your AI assistant", slug: "connect-assistant" }
      ]
    },
    {
      id: "control-tower",
      name: "Control Tower",
      summary: "See and manage every agent in one place.",
      href: "usecases/",
      useCases: [
        { title: "Check fleet health from a snapshot", slug: "fleet-health-snapshot", href: "usecases/fleet-health-snapshot/", mostAsked: "Fleet health" },
        { title: "Turn a failed Lens run into an incident", slug: "lens-failure-to-incident", href: "usecases/lens-failure-to-incident/" },
        { title: "See evidence posture across the ecosystem", slug: "ecosystem-evidence-posture", href: "usecases/ecosystem-evidence-posture/" }
      ]
    }
  ]
};
}

/* ---- usecases.js ---- */
{
/* Builds the Use cases dropdown from assets/js/usecases-data.js, in the same layout as the
   Products and Docs menus: one item per package (icon, "<name> use cases", summary line).
   Fills  [data-uc-list]  (the grid) and  [data-uc-most-asked]  (chips in the dark card).
   Edit the data file, not this one. */
(() => {
  const data = window.DAL_USECASES;
  const list = document.querySelector("[data-uc-list]");
  const chips = document.querySelector("[data-uc-most-asked]");
  if (!data || !Array.isArray(data.packages) || !list) return;

  // same icons as the Products menu
  const ICONS = {
    "agenticlens": '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/><circle cx="11" cy="11" r="2"/>',
    "agentic-chaos": '<path d="M13 2 5 13h6l-1 9 8-11h-6l1-9z"/>',
    "agentic-sidecar": '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    "agentic-evals": '<path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/>',
    "mcp": '<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0V7zM12 16v5"/>',
    "control-tower": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>'
  };
  const FALLBACK_ICON = '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>';

  const packageHref = (pkg) => pkg.href || `https://deepagentlabs.io/${pkg.id}/usecases/`;
  const useCaseHref = (pkg, uc) => uc.href || `https://deepagentlabs.io/${pkg.id}/usecases/${uc.slug}/`;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };

  const items = document.createDocumentFragment();
  const featured = document.createDocumentFragment();

  data.packages.forEach((pkg) => {
    const li = el("li");
    const a = el("a", "mega-link");
    a.href = packageHref(pkg);

    const icon = el("span", "mega-icon");
    icon.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[pkg.id] || FALLBACK_ICON}</svg>`;

    const text = el("span", "mega-text");
    const title = el("strong", "", `${pkg.name} use cases `);
    const arrow = el("i", "", "→");
    arrow.setAttribute("aria-hidden", "true");
    title.append(arrow);
    text.append(title);
    if (pkg.summary) text.append(el("small", "", pkg.summary));

    a.append(icon, text);
    li.append(a);
    items.append(li);

    (pkg.useCases || []).forEach((uc) => {
      if (!uc.mostAsked) return;
      const chip = el("a", "", `${uc.mostAsked} `);
      chip.href = useCaseHref(pkg, uc);
      const go = el("span", "", "→");
      go.setAttribute("aria-hidden", "true");
      chip.append(go);
      featured.append(chip);
    });
  });

  list.replaceChildren(items);
  if (chips) chips.replaceChildren(featured);
})();
}

/* ---- nav.js ---- */
{
/* Mega-menu: hover to open on desktop, click/tap to toggle everywhere, Esc / outside click to close. */
(() => {
  const items = [...document.querySelectorAll(".nav-item.has-mega")];
  if (!items.length) return;

  const desktop = window.matchMedia("(min-width: 821px) and (hover: hover)");
  const scrim = document.createElement("div");
  scrim.className = "mega-scrim";
  scrim.setAttribute("aria-hidden", "true");
  document.body.appendChild(scrim);

  // sliding highlight behind the top-level menu items (desktop)
  const header = document.querySelector(".site-header");
  const navEl = document.querySelector("#site-nav");
  const glider = document.createElement("span");
  glider.className = "nav-glider";
  glider.setAttribute("aria-hidden", "true");
  header?.appendChild(glider);
  const tops = navEl
    ? [...navEl.querySelectorAll(":scope > a:not(.nav-cta), :scope > .nav-item > .nav-trigger")]
    : [];
  const moveTo = (el) => {
    if (!el || !header || !desktop.matches) return;
    const h = header.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const first = !glider.classList.contains("is-on");
    if (first) glider.style.transition = "none"; // appear in place, then slide afterwards
    glider.style.width = `${r.width + 26}px`;
    glider.style.transform = `translateX(${r.left - h.left - 13}px)`;
    glider.style.top = `${r.top - h.top + r.height / 2}px`;
    glider.classList.toggle("is-menu", !!el.closest(".nav-item.is-open"));
    if (first) {
      glider.offsetWidth; // flush
      glider.style.transition = "";
    }
    glider.classList.add("is-on");
  };
  const settle = () => {
    const t = openItem?.querySelector(".nav-trigger");
    if (t) moveTo(t);
    else glider.classList.remove("is-on", "is-menu");
  };
  tops.forEach((el) => {
    el.addEventListener("mouseenter", () => moveTo(el));
    el.addEventListener("focus", () => {
      if (el.matches(":focus-visible")) moveTo(el);
    });
  });
  navEl?.addEventListener("mouseleave", () => setTimeout(settle, 220));
  navEl?.addEventListener("focusout", (e) => {
    if (!navEl.contains(e.relatedTarget)) setTimeout(settle, 0);
  });
  window.addEventListener("resize", () => glider.classList.remove("is-on"));

  let openItem = null;
  let openTimer = 0;
  let closeTimer = 0;

  const setOpen = (item, open) => {
    item.classList.toggle("is-open", open);
    item.querySelector(".nav-trigger")?.setAttribute("aria-expanded", String(open));
  };

  const close = (item = openItem) => {
    if (!item) return;
    setOpen(item, false);
    if (openItem === item) openItem = null;
    if (!openItem) scrim.classList.remove("is-on");
    glider.classList.remove("is-menu");
    if (!navEl?.matches(":hover")) settle();
  };

  const open = (item) => {
    if (openItem && openItem !== item) close(openItem);
    setOpen(item, true);
    openItem = item;
    if (desktop.matches) scrim.classList.add("is-on");
    moveTo(item.querySelector(".nav-trigger"));
  };

  items.forEach((item) => {
    const trigger = item.querySelector(".nav-trigger");

    trigger?.addEventListener("click", () => {
      clearTimeout(openTimer);
      clearTimeout(closeTimer);
      item.classList.contains("is-open") ? close(item) : open(item);
    });

    item.addEventListener("mouseenter", () => {
      if (!desktop.matches) return;
      clearTimeout(closeTimer);
      // switch instantly between menus; small delay when opening from nothing
      openTimer = setTimeout(() => open(item), openItem ? 0 : 80);
    });

    item.addEventListener("mouseleave", () => {
      if (!desktop.matches) return;
      clearTimeout(openTimer);
      closeTimer = setTimeout(() => close(item), 200);
    });

    // close when keyboard focus leaves the menu
    item.addEventListener("focusout", (e) => {
      if (desktop.matches && !item.contains(e.relatedTarget)) close(item);
    });

    // following a link closes the menu (and the mobile nav via site.js)
    item.querySelectorAll(".mega a").forEach((a) => a.addEventListener("click", () => close(item)));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !openItem) return;
    const trigger = openItem.querySelector(".nav-trigger");
    close();
    trigger?.focus();
  });

  document.addEventListener("click", (e) => {
    if (openItem && !openItem.contains(e.target)) close();
  });

  // reset when switching between mobile and desktop layouts
  desktop.addEventListener?.("change", () => close());
})();
}

/* ---- background.js ---- */
{
/* Page background animation: a few slow, faint signals that travel the grid like
   signals on a circuit board.
   Sits behind all content (pointer-events: none), pauses when the tab is hidden,
   and is skipped entirely for people who prefer reduced motion. */
(() => {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const canvas = document.createElement("canvas");
  canvas.className = "bg-flow";
  canvas.setAttribute("aria-hidden", "true");
  document.body.prepend(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const GRID = 52;
  // signal colour comes from the theme (--flow-rgb), defaulting to deep green
  const DARK = getComputedStyle(document.documentElement).getPropertyValue("--flow-rgb").trim() || "61,122,18";
  let w = 0, h = 0, dpr = 1, packets = [], running = true, last = 0;

  const rand = (a, b) => a + Math.random() * (b - a);
  const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];

  const spawn = () => {
    const cols = Math.ceil(w / GRID), rows = Math.ceil(h / GRID);
    const d = dirs[(Math.random() * 4) | 0];
    return {
      x: ((Math.random() * cols) | 0) * GRID,
      y: ((Math.random() * rows) | 0) * GRID,
      dx: d[0], dy: d[1],
      speed: rand(14, 26),           // px per second (slow and calm)
      trail: [],
      life: rand(12, 22),             // seconds before it respawns
      age: 0,
    };
  };

  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round(Math.min(10, Math.max(5, (w * h) / 160000)));
    packets = Array.from({ length: count }, spawn);
  };

  const step = (p, dt) => {
    p.age += dt;
    const move = p.speed * dt;
    const px = p.x, py = p.y;
    p.x += p.dx * move; p.y += p.dy * move;
    // at a grid intersection, maybe turn
    const crossedX = p.dx && Math.floor(px / GRID) !== Math.floor(p.x / GRID);
    const crossedY = p.dy && Math.floor(py / GRID) !== Math.floor(p.y / GRID);
    if ((crossedX || crossedY) && Math.random() < 0.3) {
      p.x = Math.round(p.x / GRID) * GRID; p.y = Math.round(p.y / GRID) * GRID;
      const turn = p.dx ? [[0, 1], [0, -1]] : [[1, 0], [-1, 0]];
      const t = turn[(Math.random() * 2) | 0];
      p.dx = t[0]; p.dy = t[1];
    }
    p.trail.push([p.x, p.y]);
    if (p.trail.length > 90) p.trail.shift();
    if (p.age > p.life || p.x < -GRID || p.y < -GRID || p.x > w + GRID || p.y > h + GRID) Object.assign(p, spawn());
  };

  const draw = (now) => {
    if (!running) return;
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    ctx.clearRect(0, 0, w, h);

    packets.forEach((p) => {
      step(p, dt);
      const fade = Math.min(1, p.age / 0.6, (p.life - p.age) / 0.8);
      const n = p.trail.length;
      for (let i = 1; i < n; i++) {
        const a = (i / n) * 0.28 * fade;
        ctx.strokeStyle = `rgba(${DARK},${a})`;
        ctx.lineWidth = 1.3;
        ctx.beginPath();
        ctx.moveTo(p.trail[i - 1][0], p.trail[i - 1][1]);
        ctx.lineTo(p.trail[i][0], p.trail[i][1]);
        ctx.stroke();
      }
      // head
      ctx.fillStyle = `rgba(${DARK},${0.5 * fade})`;
      ctx.beginPath(); ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2); ctx.fill();
    });
    requestAnimationFrame(draw);
  };

  window.addEventListener("resize", resize);
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) { last = performance.now(); requestAnimationFrame(draw); }
  });

  resize();
  last = performance.now();
  requestAnimationFrame(draw);
})();
}

/* ---- copy.js ---- */
{
/* Adds a "copy" button to the right of every install command (pip install …). */
(() => {
  const targets = document.querySelectorAll("code.tl-pip, .mega-code, .dash-quickstart");
  if (!targets.length) return;

  const ICON_COPY = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="1.5"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/></svg>';
  const ICON_DONE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fallback for file:// pages or older browsers
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
      document.body.append(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      ta.remove();
      return ok;
    }
  };

  targets.forEach((el) => {
    if (el.querySelector(".copy-btn")) return;
    const text = el.textContent.trim();
    const label = document.createElement("span");
    label.className = "copy-text";
    label.textContent = text;
    el.textContent = "";
    el.classList.add("has-copy");

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.setAttribute("aria-label", `Copy “${text}”`);
    btn.innerHTML = ICON_COPY + '<span class="copy-tip">Copy</span>';
    let timer = 0;
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      const ok = await copyText(text);
      btn.classList.toggle("is-copied", ok);
      btn.innerHTML = (ok ? ICON_DONE : ICON_COPY) + `<span class="copy-tip">${ok ? "Copied" : "Press Ctrl+C"}</span>`;
      btn.setAttribute("aria-label", ok ? "Copied to clipboard" : `Copy “${text}”`);
      if (!ok) {
        const range = document.createRange();
        range.selectNodeContents(label);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      }
      clearTimeout(timer);
      timer = setTimeout(() => {
        btn.classList.remove("is-copied");
        btn.innerHTML = ICON_COPY + '<span class="copy-tip">Copy</span>';
        btn.setAttribute("aria-label", `Copy “${text}”`);
      }, 1800);
    });

    el.append(label, btn);
  });
})();
}

/* ---- product.js ---- */
{
/* Product pages: fill [data-pp-usecases="<package id>"] with that package's use cases
   from assets/js/usecases-data.js, so the page and the Use cases menu stay in sync. */
(() => {
  const list = document.querySelector("[data-pp-usecases]");
  const pkg = (window.DAL_USECASES?.packages || []).find((p) => p.id === list?.dataset.ppUsecases);
  if (!list || !pkg) return;
  (pkg.useCases || []).forEach((uc) => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = uc.href || `https://deepagentlabs.io/${pkg.id}/usecases/${uc.slug}/`;
    a.textContent = `${uc.title} `;
    const arrow = document.createElement("span");
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    a.append(arrow);
    li.append(a);
    list.append(li);
  });
})();

/* Reveal on scroll: section headings and card groups fade up as they come into view. */
(() => {
  const root = document.documentElement;
  const items = [...document.querySelectorAll(".pp-rv, .pp-rv-kids")];
  if (!items.length) return;
  const show = (el) => el.classList.add("is-in");
  if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
    items.forEach(show);
    return;
  }
  // stagger the children of each group
  document.querySelectorAll(".pp-rv-kids").forEach((group) => {
    [...group.children].forEach((child, i) => child.style.setProperty("--d", `${Math.min(i, 6) * 0.08}s`));
  });
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { show(e.target); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -12% 0px" });
  items.forEach((el) => io.observe(el));
  // safety net: never leave content hidden
  setTimeout(() => items.forEach(show), 4000);
  root.classList.add("pp-js");
})();

/* Live fleet card (example data): heartbeats arrive, "last seen" ages tick,
   and now and then an agent changes state; counts and the bar follow. */
(() => {
  const card = document.querySelector("[data-fleet]");
  if (!card || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const rows = [...card.querySelectorAll("[data-fleet-rows] li")];
  const counts = { ok: 41, warn: 5, bad: 2 };
  const LABEL = { ok: "healthy", warn: "degraded", bad: "no heartbeat" };
  const age = rows.map((r) => {
    const t = r.querySelector("time").textContent;
    return t.endsWith("m") ? parseInt(t, 10) * 60 : parseInt(t, 10);
  });
  const fmt = (s) => (s >= 60 ? `${Math.floor(s / 60)}m` : `${s}s`);
  // "Recent activity" feed under the rows: newest on top, 3 lines
  const feedList = card.querySelector("[data-fleet-feed]");
  const feedAge = feedList ? [0, 12, 240] : [];
  const feedTime = (t) => (t < 3 ? "now" : fmt(t));
  const pushFeed = (cls, name, text) => {
    if (!feedList) return;
    const top = feedList.firstElementChild;
    if (top && top.querySelector("b")?.textContent === name && top.textContent.endsWith(text)) return; // no repeats
    const li = document.createElement("li");
    li.className = "is-new";
    li.innerHTML = `<time>now</time><b class="${cls}"></b> `;
    li.querySelector("b").textContent = name;
    li.append(text);
    feedList.prepend(li);
    feedAge.unshift(0);
    while (feedList.children.length > 3) { feedList.lastElementChild.remove(); feedAge.pop(); }
  };
  const NAME = (i) => rows[i].querySelector("span").textContent;
  const render = () => {
    Object.keys(counts).forEach((k) => {
      card.querySelector(`[data-count="${k}"]`).textContent = counts[k];
      card.querySelector(`[data-bar="${k}"]`).style.flexGrow = counts[k];
    });
  };
  const setState = (i, next) => {
    const r = rows[i];
    const prev = r.dataset.state;
    if (prev === next) return;
    counts[prev] -= 1;
    counts[next] += 1;
    r.dataset.state = next;
    r.querySelector("em").textContent = LABEL[next];
    r.classList.add("is-changed");
    pushFeed(next, NAME(i), next === "ok" ? "recovered → healthy" : next === "warn" ? (prev === "bad" ? "is back, still degraded" : "slowed down → degraded") : "stopped checking in");
    setTimeout(() => r.classList.remove("is-changed"), 1600);
    if (next !== "bad") age[i] = 0;
    render();
  };

  let visible = true;
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }).observe(card);
  let tick = 0;
  setInterval(() => {
    if (!visible || document.hidden) return;
    tick += 1;
    rows.forEach((r, i) => {
      const st = r.dataset.state;
      age[i] += 1;
      // healthy agents check in every few seconds, degraded ones slowly, unhealthy never
      const due = st === "ok" ? age[i] >= 3 + (i % 3) : st === "warn" ? age[i] >= 11 : false;
      if (due) {
        age[i] = 0;
        r.classList.remove("is-beat");
        void r.offsetWidth;
        r.classList.add("is-beat");
        if (Math.random() < 0.3 && feedList?.firstElementChild?.querySelector("b")?.textContent !== NAME(i)) pushFeed(st, NAME(i), st === "ok" ? "sent a heartbeat" : "checked in late");
      }
      r.querySelector("time").textContent = fmt(age[i]);
    });
    if (feedList) [...feedList.children].forEach((li, k) => {
      feedAge[k] += 1;
      li.querySelector("time").textContent = feedTime(feedAge[k]);
      if (feedAge[k] > 1) li.classList.remove("is-new");
    });
    // every ~6s something changes: degraded recovers, a healthy one slows down, or the silent one comes back
    if (tick % 6 === 0) {
      const warn = rows.findIndex((r) => r.dataset.state === "warn");
      const bad = rows.findIndex((r) => r.dataset.state === "bad");
      const roll = Math.random();
      if (bad > -1 && roll < 0.25) setState(bad, "warn");
      else if (warn > -1 && roll < 0.6) setState(warn, "ok");
      else {
        const healthy = rows.map((r, i) => (r.dataset.state === "ok" ? i : -1)).filter((i) => i > -1);
        if (healthy.length > 1) setState(healthy[Math.floor(Math.random() * healthy.length)], "warn");
      }
      // keep at least one unhealthy example on screen most of the time
      if (!rows.some((r) => r.dataset.state === "bad") && Math.random() < 0.5) {
        const w = rows.findIndex((r) => r.dataset.state === "warn");
        if (w > -1) { setState(w, "bad"); age[w] = 180; }
      }
    }
  }, 1000);
})();

/* "Inside the console": the list moves to the next screen on its own every few seconds
   (progress bar on the active item) and loops. Clicking an item jumps to it and the cycle
   carries on from there. It only runs while the section is on screen, and pauses while a
   screenshot is enlarged. Arrow keys move between screens. Off with "reduce motion". */
(() => {
  const box = document.querySelector("[data-pp-tabs]");
  if (!box) return;
  const tabs = [...box.querySelectorAll('[role="tab"]')];
  const STEP = 5000; // ms per screen
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let current = Math.max(0, tabs.findIndex((t) => t.getAttribute("aria-selected") === "true"));
  let elapsed = 0, last = 0, paused = false, visible = false;

  const select = (i, focus) => {
    current = (i + tabs.length) % tabs.length;
    elapsed = 0;
    tabs.forEach((t, k) => {
      const on = k === current;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      t.style.setProperty("--p", on && !calm ? 0 : 1);
      const panel = document.getElementById(t.getAttribute("aria-controls"));
      panel.hidden = !on;
      panel.classList.toggle("is-on", on);
    });
    if (focus) tabs[current].focus();
  };

  const loop = (now) => {
    requestAnimationFrame(loop);
    const dt = last ? now - last : 0;
    last = now;
    if (paused || !visible || document.hidden) return;
    elapsed += dt;
    tabs[current].style.setProperty("--p", Math.min(elapsed / STEP, 1));
    if (elapsed >= STEP) select(current + 1);
  };

  tabs.forEach((t, i) => {
    t.addEventListener("click", () => select(i));
    t.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      e.preventDefault(); select(i + d, true);
    });
  });
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0.2 }).observe(box);
  select(current);
  if (!calm) requestAnimationFrame(loop);

  // click to enlarge
  const zoom = document.createElement("div");
  zoom.className = "pp-zoom";
  zoom.hidden = true;
  zoom.setAttribute("role", "dialog");
  zoom.setAttribute("aria-modal", "true");
  zoom.setAttribute("aria-label", "Enlarged screenshot");
  zoom.innerHTML = '<img alt=""><button type="button" aria-label="Close">×</button>';
  document.body.append(zoom);
  const zimg = zoom.querySelector("img");
  let opener = null;
  const close = () => { zoom.hidden = true; paused = false; opener?.focus(); };
  box.querySelectorAll(".pp-show-stage figure").forEach((fig) => {
    fig.tabIndex = 0;
    if (!fig.querySelector("img")) return;
    const open = () => {
      const img = fig.querySelector("img");
      zimg.src = img.currentSrc || img.src;
      zimg.alt = img.alt;
      opener = fig; paused = true;
      zoom.hidden = false;
      zoom.querySelector("button").focus();
    };
    fig.addEventListener("click", open);
    fig.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  });
  zoom.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !zoom.hidden) close(); });
})();

/* "What it does" carousel: arrows, a progress line that follows the scroll, and drag-to-scroll with a mouse. */
(() => {
  const track = document.querySelector("[data-pp-carousel]");
  if (!track) return;
  const bar = document.querySelector("[data-pp-progress]");
  const prev = document.querySelector("[data-pp-prev]");
  const next = document.querySelector("[data-pp-next]");
  const step = () => (track.querySelector(".pp-fc")?.getBoundingClientRect().width || 400) + 24;
  const update = () => {
    const max = track.scrollWidth - track.clientWidth;
    const frac = track.clientWidth / track.scrollWidth;
    const pos = max > 0 ? track.scrollLeft / max : 0;
    if (bar) {
      bar.style.width = `${Math.max(frac, 0.12) * 100}%`;
      bar.style.transform = `translateX(${pos * (1 / Math.max(frac, 0.12) - 1) * 100}%)`;
    }
    if (prev) prev.disabled = track.scrollLeft <= 2;
    if (next) next.disabled = track.scrollLeft >= max - 2;
  };
  prev?.addEventListener("click", () => track.scrollBy({ left: -step() }));
  next?.addEventListener("click", () => track.scrollBy({ left: step() }));
  track.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { e.preventDefault(); track.scrollBy({ left: step() }); }
    if (e.key === "ArrowLeft") { e.preventDefault(); track.scrollBy({ left: -step() }); }
  });
  track.addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update);
  // drag with the mouse (touch already scrolls natively)
  let down = false, startX = 0, startLeft = 0, moved = false;
  track.addEventListener("pointerdown", (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    e.preventDefault();
    down = true; moved = false; startX = e.clientX; startLeft = track.scrollLeft;
  });
  addEventListener("pointermove", (e) => {
    if (!down) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 4) { moved = true; track.classList.add("is-drag"); }
    if (moved) track.scrollLeft = startLeft - dx;
  });
  addEventListener("pointerup", () => {
    if (!down) return;
    down = false;
    if (moved) {
      track.classList.remove("is-drag");
      const i = Math.round(track.scrollLeft / step());
      track.scrollTo({ left: i * step() });
      setTimeout(() => { moved = false; }, 0);
    }
  });
  track.addEventListener("click", (e) => { if (moved) { e.preventDefault(); e.stopPropagation(); } }, true);
  update();
})();

/* Numbers strip: count up from 0 when it comes into view. */
(() => {
  const nums = [...document.querySelectorAll("[data-count-to]")];
  if (!nums.length || matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
  nums.forEach((n) => { n.textContent = "0"; });
  const run = () => {
    const t0 = performance.now();
    const tick = (now) => {
      const k = Math.min((now - t0) / 1000, 1);
      const ease = 1 - Math.pow(1 - k, 3);
      nums.forEach((n) => { n.textContent = Math.round(+n.dataset.countTo * ease); });
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { run(); io.disconnect(); } }, { threshold: 0.2 });
  io.observe(nums[0].closest("ul"));
})();
}

/* ---- beam.js ---- */
{
/* Adds a travelling border beam (see beam.css) to a short list of key elements.
   Ambient beams only run while the element is on screen. */
(() => {
  const targets = [
    [".system-card", "glow"],                 // hero ecosystem card
    [".tl", "glow"],                          // framework showcase
    [".adp-card", "quick"],                   // downloads stat card
    [".rm-track .phase.active", "ink"],       // roadmap: milestone in review
    ["#v0-1 .rp-window", "glow"],              // roadmap page: milestone in review
    [".mega-side", "glow"],                   // spec card inside the menus
    [".nf-card", "glow"],                     // 404 card
    [".hero .button-primary, .cta .button, .nav-cta, .adp-foot .button", "hover"],
    [".newsletter-form", "focus"],
  ];
  const ambient = [];
  targets.forEach(([sel, kind]) => {
    document.querySelectorAll(sel).forEach((el) => {
      if (el.querySelector(":scope > .beam")) return;
      el.dataset.beam = kind;
      const s = document.createElement("span");
      s.className = "beam";
      s.setAttribute("aria-hidden", "true");
      el.append(s);
      if (kind !== "hover" && kind !== "focus") ambient.push(el);
    });
  });
  if (!("IntersectionObserver" in window)) {
    ambient.forEach((el) => el.classList.add("beam-on"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => e.target.classList.toggle("beam-on", e.isIntersecting));
  });
  ambient.forEach((el) => io.observe(el));
  // menus are display:none / hidden until opened, so run their beam whenever visible
  document.querySelectorAll(".mega-side[data-beam]").forEach((el) => el.classList.add("beam-on"));
})();
}
