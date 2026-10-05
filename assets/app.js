/* Renders data/menus.json. No build step, no dependencies. */
(() => {
  "use strict";

  const DAYS = ["Maanantai", "Tiistai", "Keskiviikko", "Torstai", "Perjantai"];
  const SHORT = ["Ma", "Ti", "Ke", "To", "Pe"];

  // Allergen codes as the restaurants write them, trailing the dish.
  const TAGS = /(?:^|[\s(])((?:VL|VE|MU|LL|[LGMVA])(?:\s*[,/]\s*(?:VL|VE|MU|LL|[LGMVA]))*)\s*$/;
  const PRICE = /(\d{1,2}[,.]\d{2})\s*€?\s*$/;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  /** Split "Lihapullia L, G 12,50€" into text + price + allergen chips. */
  function dish(line) {
    const li = el("li");
    let rest = line;
    let price = null, tags = null;

    const p = rest.match(PRICE);
    if (p) { price = p[1].replace(".", ",") + " €"; rest = rest.slice(0, p.index).trim(); }

    const t = rest.match(TAGS);
    if (t) { tags = t[1].split(/\s*[,/]\s*/); rest = rest.slice(0, t.index).trim(); }

    li.appendChild(document.createTextNode(rest.replace(/[\s,]+$/, "")));
    if (price) { li.appendChild(document.createTextNode(" ")); li.appendChild(el("span", "price", price)); }
    if (tags) {
      const box = el("span", "tags");
      tags.forEach(t => box.appendChild(el("span", "tag", t)));
      li.appendChild(box);
    }
    return li;
  }

  function card(r, weekday, weekStart) {
    const c = el("article", "card");

    const h = el("h2");
    const a = el("a", null, r.name);
    a.href = r.url; a.target = "_blank"; a.rel = "noopener noreferrer";
    h.appendChild(a);
    c.appendChild(h);

    const meta = el("p", "meta");
    [r.area, r.hours].filter(Boolean).forEach((bit, i) => {
      if (i) meta.appendChild(el("span", "dot", "·"));
      meta.appendChild(document.createTextNode(bit));
    });
    c.appendChild(meta);

    // A dated site that disagrees with the week we are showing is the most
    // specific thing we can say, so it wins over the generic stale badge.
    if (behind(r, weekStart)) c.appendChild(el("span", "badge week", "Edellisen viikon lista"));
    else if (r.status === "stale") c.appendChild(el("span", "badge stale", "Vanha tieto"));
    if (r.status === "error" || r.status === "empty") c.appendChild(el("span", "badge error", "Ei saatavilla"));

    const day = (r.days || []).find(d => d.weekday === weekday);
    if (day && day.items && day.items.length) {
      const ul = el("ul", "dishes");
      day.items.forEach(i => ul.appendChild(dish(i)));
      c.appendChild(ul);
    } else {
      c.appendChild(el("p", "note",
        r.status === "ok" ? "Ei listaa tälle päivälle." : "Listaa ei saatu haettua — katso ravintolan sivu."));
    }
    return c;
  }

  function render(data, weekday) {
    const grid = document.getElementById("grid");
    grid.textContent = "";
    data.restaurants.forEach(r => grid.appendChild(card(r, weekday, data.weekStart)));
    grid.hidden = false;
    document.getElementById("loading").hidden = true;
  }

  function buildTabs(data, active, onPick) {
    const nav = document.getElementById("days");
    nav.textContent = "";
    const start = new Date(data.weekStart + "T00:00:00");

    DAYS.forEach((name, i) => {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const b = el("button");
      b.type = "button";
      b.appendChild(el("span", "full", name));
      b.appendChild(el("span", "short", SHORT[i]));
      b.appendChild(el("span", "dt", `${d.getDate()}.${d.getMonth() + 1}.`));
      b.setAttribute("aria-current", String(i === active));
      b.addEventListener("click", () => onPick(i));
      nav.appendChild(b);
    });
  }

  const mondayOf = d => {
    const x = new Date(d);
    x.setHours(0, 0, 0, 0);
    x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
    return x;
  };

  function stamp(data) {
    const t = new Date(data.generatedAt);
    const when = t.toLocaleString("fi-FI", {
      weekday: "short", day: "numeric", month: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
    const p = document.getElementById("updated");
    p.textContent = `Listat muuttuivat viimeksi ${when}.`;
  }

  /** A restaurant whose own dates disagree with the week being displayed. */
  const behind = (r, weekStart) => Boolean(r.week) && r.week !== weekStart;

  const fiDate = iso => {
    const d = new Date(iso + "T00:00:00");
    return `${d.getDate()}.${d.getMonth() + 1}.`;
  };

  /** Two different failures, in order of how badly they mislead. */
  function banner(data) {
    const box = document.getElementById("banner");
    box.textContent = "";

    // 1. Nothing has run this week, so the whole page is a week behind.
    if (new Date(data.weekStart + "T00:00:00") < mondayOf(new Date())) {
      box.appendChild(el("strong", null, "Listat eivät ole tältä viikolta. "));
      box.appendChild(document.createTextNode(
        `Alla on viikon ${fiDate(data.weekStart)} lista — tämän viikon listoja ei ole haettu.`));
      box.hidden = false;
      return;
    }

    // 2. The page is current, but a restaurant is still serving an old week.
    const old = data.restaurants.filter(r => behind(r, data.weekStart));
    if (old.length) {
      box.appendChild(el("strong", null,
        old.length === 1 ? "Yksi lista on vanha. " : "Osa listoista on vanhoja. "));
      box.appendChild(document.createTextNode(
        `${old.map(r => r.name).join(", ")} näyttää yhä edellisen viikon listaa.`));
      box.hidden = false;
      return;
    }

    box.hidden = true;
  }

  async function init() {
    let data;
    try {
      const res = await fetch("data/menus.json", { cache: "no-cache" });
      if (!res.ok) throw new Error(res.status);
      data = await res.json();
    } catch (err) {
      document.getElementById("loading").textContent =
        "Listojen lataus epäonnistui. Yritä päivittää sivu.";
      return;
    }

    // Monday on weekends - nobody is reading this for Saturday.
    const wd = new Date().getDay();
    let active = wd === 0 || wd === 6 ? 0 : wd - 1;

    const show = i => { active = i; buildTabs(data, active, show); render(data, active); };
    show(active);
    stamp(data);
    banner(data);
  }

  init();
})();
