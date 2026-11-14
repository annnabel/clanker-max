#!/usr/bin/env python3
"""Pre-commit checks for the AI Field Guide (index.html).

Opens the page in headless Chromium and checks:
  1. console errors, uncaught page errors, and the page's own warnings
     ("missing source", "bad link")
  2. broken internal links: every [data-go] and href="#..." target exists,
     plus reading-path steps and card links[] ids
  3. missing source keys: every [[key]] in the file and in SECTIONS exists in SRC
  4. text rendered under 12px (desktop 1280px and phone 390px; SVG text is
     measured at its on-screen size after the SVG is scaled)
  5. WCAG AA text contrast in light and dark themes (4.5:1, or 3:1 for large
     text), plus SVG text using the browser's default black fill

All <details> panels are opened first so hidden text is checked too.

Usage:  python3 scripts/check.py [path/to/index.html] [--verbose] [--offline]
  --offline  block external requests (e.g. Google Fonts) so results don't
             depend on the network.
Exit code 0 if everything passes, 1 otherwise.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
VERBOSE = "--verbose" in sys.argv
OFFLINE = "--offline" in sys.argv
PAGE = Path(args[0]).resolve() if args else ROOT / "index.html"
MAX_SHOW = 1000 if VERBOSE else 15

# --------------------------------------------------------------------------
# In-page helpers (JavaScript)
# --------------------------------------------------------------------------

OPEN_ALL = "document.querySelectorAll('details').forEach(d => d.open = true)"

LINKS_JS = r"""
() => {
  const bad = [];
  const has = id => !!document.getElementById(id);
  document.querySelectorAll('[data-go]').forEach(el => {
    const id = el.getAttribute('data-go');
    if (!has(id)) bad.push({kind: 'data-go', target: id, text: (el.textContent || '').trim().slice(0, 60)});
  });
  document.querySelectorAll('a[href^="#"]').forEach(el => {
    const id = decodeURIComponent(el.getAttribute('href').slice(1));
    if (id && !has(id)) bad.push({kind: 'href', target: id, text: (el.textContent || '').trim().slice(0, 60)});
  });
  // Data-level links (reading paths and card links), even if not rendered
  if (typeof PATHS !== 'undefined') {
    for (const [k, p] of Object.entries(PATHS))
      p.steps.forEach(id => { if (!has(id)) bad.push({kind: 'path:' + k, target: id, text: ''}); });
  }
  if (typeof SECTIONS !== 'undefined') {
    SECTIONS.forEach(s => s.subs.forEach(sub => sub.cards.forEach(c => {
      if (!Array.isArray(c) && c.links) c.links.forEach(l => {
        if (!has(l[0])) bad.push({kind: 'card-link:' + c.id, target: l[0], text: l[1]});
      });
    })));
  }
  return {
    bad,
    total: document.querySelectorAll('[data-go], a[href^="#"]').length,
  };
}
"""

SRC_JS = r"""
() => {
  if (typeof SRC === 'undefined' || typeof SECTIONS === 'undefined') return null;
  const used = new Set();
  const walk = v => {
    if (typeof v === 'string') { for (const m of v.matchAll(/\[\[([^\]]+)\]\]/g)) used.add(m[1]); }
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(SECTIONS);
  const keys = Object.keys(SRC);
  const missing = [...used].filter(k => !SRC[k]);
  const unused = keys.filter(k => !used.has(k));
  const badTier = keys.filter(k => ![1, 2, 3].includes(SRC[k].t));
  return {used: used.size, defined: keys.length, missing, unused, badTier};
}
"""

# Shared JS: visibility test + colour normalisation via a 1px canvas.
COMMON_JS = r"""
const __cv = document.createElement('canvas'); __cv.width = __cv.height = 1;
const __cx = __cv.getContext('2d', {willReadFrequently: true});
const __cache = new Map();
function toRGBA(str) {               // any CSS colour -> [r,g,b,a(0..1)]
  if (!str || str === 'none' || str === 'transparent') return [0, 0, 0, 0];
  if (__cache.has(str)) return __cache.get(str);
  __cx.clearRect(0, 0, 1, 1);
  __cx.fillStyle = 'rgba(0,0,0,0)';
  __cx.fillStyle = str;
  __cx.fillRect(0, 0, 1, 1);
  const d = __cx.getImageData(0, 0, 1, 1).data;
  const out = [d[0], d[1], d[2], d[3] / 255];
  __cache.set(str, out); return out;
}
function over(top, bottom) {          // alpha-composite top over opaque bottom
  const a = top[3];
  return [0, 1, 2].map(i => top[i] * a + bottom[i] * (1 - a)).concat(1);
}
function lum(c) {
  const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
}
function ratio(a, b) { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
function visible(el) {
  for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
  }
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}
function ownText(el) {
  let t = '';
  el.childNodes.forEach(n => { if (n.nodeType === 3) t += n.textContent; });
  return t.replace(/\s+/g, ' ').trim();
}
function label(el) {
  let s = el.tagName.toLowerCase();
  if (el.id) s += '#' + el.id;
  const cls = el.getAttribute('class'); if (cls) s += '.' + cls.trim().split(/\s+/).join('.');
  const host = el.closest('[id]');
  if (host && host !== el) s += ' in #' + host.id;
  return s;
}
function textEls() {
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  for (let el = w.currentNode; el; el = w.nextNode()) {
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TITLE'].includes(el.tagName)) continue;
    const t = ownText(el);
    if (t && visible(el)) out.push([el, t]);
  }
  // form controls carry text in their value / options
  document.querySelectorAll('input[type=search], input[type=text], select').forEach(el => {
    if (visible(el)) out.push([el, el.value || el.placeholder || (el.options && el.options[el.selectedIndex]?.text) || '']);
  });
  return out;
}
"""

FONT_JS = COMMON_JS + r"""
() => {
  const bad = [];
  let n = 0;
  for (const [el, t] of textEls()) {
    n++;
    const css = parseFloat(getComputedStyle(el).fontSize);
    let px = css;
    const svg = el.ownerSVGElement;
    if (svg) {                       // on-screen size after the SVG is scaled
      const m = el.getScreenCTM();
      if (m) px = css * Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
    }
    if (px < 11.95) bad.push({el: label(el), text: t.slice(0, 50), px: +px.toFixed(1), css: +css.toFixed(1), svg: !!svg});
  }
  return {n, bad};
}
"""

CONTRAST_JS = COMMON_JS + r"""
() => {
  const bad = [], blackSvg = [], unknown = [];
  let n = 0;
  const bodyBg = toRGBA(getComputedStyle(document.body).backgroundColor);
  const pageBg = bodyBg[3] ? bodyBg : over(toRGBA(getComputedStyle(document.documentElement).backgroundColor), [255, 255, 255, 1]);

  // Background behind an HTML element: composite ancestor backgrounds.
  function htmlBg(el) {
    const layers = [];
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      const c = toRGBA(cs.backgroundColor);
      if (c[3] > 0) { layers.push(c); if (c[3] >= 0.999) break; }
    }
    let bg = pageBg;
    for (let i = layers.length - 1; i >= 0; i--) bg = over(layers[i], bg);
    return bg;
  }
  // Background behind SVG text: the last filled shape before it (in paint
  // order) whose box contains the text's centre, over the SVG's HTML background.
  function svgBg(el) {
    const svg = el.ownerSVGElement;
    let bg = htmlBg(svg);
    if (!bg) return null;
    const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const shapes = [...svg.querySelectorAll('rect, circle, ellipse, path, polygon')];
    for (const s of shapes) {
      if (s.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_PRECEDING) break; // s is after el
      const fill = getComputedStyle(s).fill;
      if (!fill || fill === 'none' || fill.startsWith('url')) continue;
      const b = s.getBoundingClientRect();
      if (cx < b.left || cx > b.right || cy < b.top || cy > b.bottom) continue;
      if (s.tagName === 'path' || s.tagName === 'polygon') {
        // only count paths that actually contain the point
        const svgPt = svg.createSVGPoint(); svgPt.x = cx; svgPt.y = cy;
        const m = s.getScreenCTM(); if (!m) continue;
        const local = svgPt.matrixTransform(m.inverse());
        if (!s.isPointInFill(local)) continue;
      }
      const c = toRGBA(fill);
      const op = parseFloat(getComputedStyle(s).fillOpacity) * parseFloat(getComputedStyle(s).opacity);
      bg = over([c[0], c[1], c[2], c[3] * op], bg);
    }
    return bg;
  }

  for (const [el, t] of textEls()) {
    n++;
    const cs = getComputedStyle(el);
    const svg = el.ownerSVGElement;
    let fgStr = svg ? cs.fill : cs.color;
    if (svg && cs.fill === 'rgb(0, 0, 0)') blackSvg.push({el: label(el), text: t.slice(0, 50)});
    let fg = toRGBA(fgStr);
    const bg = svg ? svgBg(el) : htmlBg(el);
    if (!bg) { unknown.push({el: label(el), text: t.slice(0, 50)}); continue; }
    let op = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    fg = over([fg[0], fg[1], fg[2], fg[3] * op], bg);
    const r = ratio(fg, bg);
    let px = parseFloat(cs.fontSize);
    if (svg) { const m = el.getScreenCTM(); if (m) px *= Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)); }
    const bold = parseInt(cs.fontWeight) >= 700;
    const large = px >= 24 || (bold && px >= 18.66);
    const need = large ? 3 : 4.5;
    if (r < need - 0.005) {
      const hex = c => '#' + c.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
      bad.push({el: label(el), text: t.slice(0, 50), ratio: +r.toFixed(2), need, fg: hex(fg), bg: hex(bg)});
    }
  }
  return {n, bad, blackSvg, unknown};
}
"""

# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

results = []   # (name, ok, summary, details[])


def record(name, ok, summary, details=()):
    results.append((name, ok, summary, list(details)))


def dedupe(items, key):
    seen, out = {}, []
    for it in items:
        k = key(it)
        if k in seen:
            seen[k]["count"] += 1
        else:
            it = dict(it, count=1)
            seen[k] = it
            out.append(it)
    return out


def static_source_check(html):
    """Regex check on the raw file, independent of the page running."""
    m = re.search(r"const SRC\s*=\s*\{(.*?)\n\};", html, re.S)
    keys = set(re.findall(r"^\s*([A-Za-z0-9_]+)\s*:\s*\{", m.group(1), re.M)) if m else set()
    code = re.sub(r"/\*.*?\*/", "", html, flags=re.S)   # ignore the markup legend in comments
    used = set(re.findall(r"\[\[([A-Za-z0-9]+)\]\]", code))  # same pattern fmt() uses
    return keys, used


def main():
    if not PAGE.exists():
        sys.exit(f"Not found: {PAGE}")
    html = PAGE.read_text(encoding="utf-8")
    url = PAGE.as_uri()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium",
                                        args=["--headless", "--no-sandbox"])

        def new_page(width, height, scheme="light", is_mobile=False):
            ctx = browser.new_context(viewport={"width": width, "height": height},
                                      color_scheme=scheme, is_mobile=is_mobile,
                                      has_touch=is_mobile, device_scale_factor=1)
            if OFFLINE:
                ctx.route(re.compile(r"^https?://"), lambda r: r.abort())
            return ctx, ctx.new_page()

        # ---- 1. console errors (desktop load, then mobile load) -----------
        console, net = [], []
        for (w, h, mob) in [(1280, 900, False), (390, 844, True)]:
            ctx, page = new_page(w, h, is_mobile=mob)
            vp = f"{w}px"
            page.on("console", lambda m, vp=vp: console.append(
                {"type": m.type, "text": m.text, "vp": vp})
                if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e, vp=vp: console.append(
                {"type": "pageerror", "text": str(e), "vp": vp}))
            page.on("requestfailed", lambda r, vp=vp: net.append(
                {"url": r.url, "err": r.failure, "vp": vp}))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(300)
            # exercise the theme toggle and a reading path, which run extra code
            page.evaluate("document.getElementById('themeBtn').click()")
            page.evaluate("document.getElementById('themeBtn').click()")
            page.wait_for_timeout(100)
            ctx.close()

        # Network failures for external resources (fonts) surface as console
        # "Failed to load resource" errors; report them separately.
        page_errs = [c for c in console if not c["text"].startswith("Failed to load resource")]
        res_errs = [c for c in console if c["text"].startswith("Failed to load resource")]
        page_errs = dedupe(page_errs, lambda c: (c["type"], c["text"]))
        record("Console errors / warnings", not page_errs,
               f"{len(page_errs)} distinct" + (f" (+{len(res_errs)} failed external loads, see below)" if res_errs else ""),
               [f"[{c['type']}] {c['text']}  ({c['vp']}, x{c['count']})" for c in page_errs])
        if net:
            nd = dedupe(net, lambda n: n["url"])
            record("External resources failed to load (info)", True,
                   f"{len(nd)} URL(s)" + (" — blocked by --offline" if OFFLINE else " — network, not a page bug"),
                   [f"{n['url']}  ({n['err']})" for n in nd])

        # ---- main desktop page for the DOM checks -------------------------
        ctx, page = new_page(1280, 900)
        page.goto(url, wait_until="load")
        page.wait_for_timeout(300)
        page.evaluate(OPEN_ALL)

        # ---- 2. internal links -------------------------------------------
        L = page.evaluate(LINKS_JS)
        bad = dedupe(L["bad"], lambda b: (b["kind"], b["target"]))
        record("Broken internal links", not bad,
               f"{len(bad)} broken of {L['total']} rendered links (+ reading paths and card links[])",
               [f"{b['kind']} -> #{b['target']}  {b['text']!r}" + (f" x{b['count']}" if b["count"] > 1 else "")
                for b in bad])

        # ---- 3. source keys ----------------------------------------------
        S = page.evaluate(SRC_JS)
        keys, used_raw = static_source_check(html)
        missing_raw = sorted(used_raw - keys) if keys else []
        if S is None:
            record("Missing source keys", False, "SRC or SECTIONS not found in page")
        else:
            missing = sorted(set(S["missing"]) | set(missing_raw))
            det = [f"missing: [[{k}]]" for k in missing]
            det += [f"bad tier: {k}" for k in S["badTier"]]
            record("Missing source keys", not missing and not S["badTier"],
                   f"{len(missing)} missing; {S['used']} keys cited, {S['defined']} defined in SRC", det)
            if S["unused"]:
                record("Unused SRC entries (info)", True, f"{len(S['unused'])} defined but never cited",
                       S["unused"])

        # ---- 4. text under 12px (desktop + phone) --------------------------
        font_bad, font_n = [], 0
        for label_, (w, h, mob) in {"desktop 1280px": (1280, 900, False),
                                     "phone 390px": (390, 844, True)}.items():
            c2, pg = new_page(w, h, is_mobile=mob)
            pg.goto(url, wait_until="load")
            pg.wait_for_timeout(300)
            pg.evaluate(OPEN_ALL)
            if mob:   # include the off-canvas nav
                pg.evaluate("document.getElementById('side').classList.add('open')")
                pg.wait_for_timeout(300)
            F = pg.evaluate(FONT_JS)
            font_n += F["n"]
            for b in F["bad"]:
                font_bad.append(dict(b, vp=label_))
            c2.close()
        fb = dedupe(font_bad, lambda b: (b["vp"], b["el"].split(" in ")[0], b["px"]))
        record("Text under 12px", not fb, f"{len(font_bad)} text elements under 12px ({len(fb)} distinct)",
               [f"{b['vp']}: {b['px']}px" + (f" (svg font-size {b['css']}, scaled)" if b["svg"] else "")
                + f"  {b['el']}  {b['text']!r}" + (f" x{b['count']}" if b["count"] > 1 else "")
                for b in fb])

        # ---- 5. contrast in both themes ----------------------------------
        for theme in ("light", "dark"):
            c3, pg = new_page(1280, 900, scheme=theme)
            pg.goto(url, wait_until="load")
            pg.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            pg.wait_for_timeout(300)
            pg.evaluate(OPEN_ALL)
            C = pg.evaluate(CONTRAST_JS)
            cb = dedupe(C["bad"], lambda b: (b["el"].split(" in ")[0], b["fg"], b["bg"]))
            record(f"Contrast ({theme} theme)", not cb,
                   f"{len(C['bad'])} of {C['n']} text elements below AA ({len(cb)} distinct)",
                   [f"{b['ratio']}:1 (needs {b['need']})  {b['fg']} on {b['bg']}  {b['el']}  {b['text']!r}"
                    + (f" x{b['count']}" if b["count"] > 1 else "") for b in cb])
            if C["blackSvg"]:
                bs = dedupe(C["blackSvg"], lambda b: b["el"].split(" in ")[0])
                record(f"SVG text with default black fill ({theme})", False, f"{len(C['blackSvg'])} elements",
                       [f"{b['el']}  {b['text']!r} x{b['count']}" for b in bs])
            if C["unknown"]:
                record(f"Contrast not measurable ({theme}, info)", True,
                       f"{len(C['unknown'])} elements over a background image/gradient",
                       [f"{b['el']}  {b['text']!r}" for b in C["unknown"]])
            c3.close()

        ctx.close()
        browser.close()

    # ---- report ----------------------------------------------------------
    print(f"\nAI Field Guide checks — {PAGE.name}{'  (offline)' if OFFLINE else ''}\n")
    failed = 0
    for name, ok, summary, details in results:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{mark}] {name}: {summary}")
        for d in details[:MAX_SHOW]:
            print(f"        - {d}")
        if len(details) > MAX_SHOW:
            print(f"        … {len(details) - MAX_SHOW} more (use --verbose)")
    print(f"\n{'All checks passed.' if not failed else f'{failed} check(s) failed.'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
