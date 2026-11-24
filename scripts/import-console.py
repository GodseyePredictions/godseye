"""Put the NFL console (God's Eye) into this app.

Usage:
  python3 -I scripts/import-console.py
      The normal weekly path. Reads the NFL algorithm's own files:
        model/nfl/attd/site_template.html     the console page (logic and styles)
        model/nfl/outputs/site/nfl_site.json  the week's data, written by `python run.py site` in model/nfl
      If the data file is absent, only the console logic and styles are refreshed and data.js is left alone.

  python3 -I scripts/import-console.py path/to/console.html
      The old path: import a single exported HTML page that already has its data inside.

Writes:
  public/console/data.js   the weekly model data (`const D = ...`)
  public/console/app.js    the console logic, patched for this site
  src/app/(console)/console-base.css   the console styles

The data is checked before it is written: it must be one JSON object with the sections the console reads.
The full rule checks run earlier, in model/nfl/attd/site_check.py, when the algorithm writes the file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NFL = ROOT / "model" / "nfl"
REQUIRED = ("meta", "games", "players", "props", "corr", "algo", "singles", "rules")
PLACEHOLDER = "/*__DATA__*/null"

if len(sys.argv) > 1:
    src = Path(sys.argv[1]).read_text(encoding="utf8")
    data_file = None
else:
    src = (NFL / "attd" / "site_template.html").read_text(encoding="utf8")
    data_file = NFL / "outputs" / "site" / "nfl_site.json"
lines = src.split("\n")

# ---------- locate the pieces ----------
script_start = next(i for i, l in enumerate(lines) if l.startswith("const D = "))
script_end = next(i for i, l in enumerate(lines) if l.strip() == "</script>" and i > script_start)
data_line = lines[script_start]
if data_file is not None:
    if PLACEHOLDER not in data_line:
        raise SystemExit("import-console: the template's data placeholder was not found")
    data_line = f"const D = {data_file.read_text(encoding='utf8').strip()};" if data_file.exists() else None
if data_line is not None:
    try:
        D = json.loads(data_line[data_line.index("{"):data_line.rindex("}") + 1])
    except ValueError as e:
        raise SystemExit(f"import-console: the week's data is not valid JSON ({e})")
    missing = [k for k in REQUIRED if k not in D]
    if missing:
        raise SystemExit(f"import-console: the week's data is missing: {', '.join(missing)}")
js_lines = [l for l in lines[script_start + 1 : script_end] if not l.startswith("const BANNER=")]
js = "\n".join(js_lines)

styles = re.findall(r"<style>(.*?)</style>", src, flags=re.S)
css = max(styles, key=len)

# The console keeps its own red, black and gold palette. Only the font references change.
js = js.replace('font-family="IBM Plex Mono"', 'font-family="var(--mono)"')

# ---------- JS patches ----------
def patch(text, old, new, count=1):
    if old not in text:
        raise SystemExit(f"import-console: expected snippet not found: {old[:70]!r}")
    return text.replace(old, new, count)

# 1. The hero no longer uses the embedded banner photo.
js = re.sub(r'<section class="hero" style="background-image:[^"]*">', '<section class="hero">', js, count=1)
if "BANNER" in js:
    raise SystemExit("import-console: BANNER is still referenced")

# 2. Tabs that this site adds (rendered by React) sit beside the console's own tabs.
js = patch(
    js,
    'function route(){const h=location.hash.slice(1);',
    'function route(){const h=location.hash.slice(1);'
    'const extra=(window.GE_EXTRA_TABS||[]).includes(h);$("#main").hidden=extra;'
    'if(extra){state.tab=h;document.querySelectorAll("nav.tabs a").forEach(a=>a.setAttribute("aria-current",a.dataset.tab===h?"page":"false"));renderSlip();return}',
)

# 3. Remember the slip's price so a bet can be sent to the tracker.
js = patch(
    js,
    "const ret=stake*bookDec, profit=ret-stake;",
    "const ret=stake*bookDec, profit=ret-stake; state._px={dec:bookDec,est:estimated,stake};",
)
js = patch(
    js,
    '<button class="btn" data-save>Save slip</button>',
    '<button class="btn primary" data-track>Track this bet</button><button class="btn" data-save>Save slip</button>',
)
js += r"""

/* ---------- godseye site: send the slip to "My bets" ---------- */
document.addEventListener("click",e=>{const t=e.target.closest("button[data-track]");if(!t)return;
  const px=state._px, legs=state.slip.legs;
  if(!legs.length||!px) return;
  if(px.est){toast("Type your book's real price first, so your record uses the odds you got");return}
  if(!(px.stake>0)){toast("Enter a stake above zero first");return}
  const price=px.dec>=2?Math.round((px.dec-1)*100):Math.round(-100/(px.dec-1));
  const bet={id:(crypto.randomUUID?crypto.randomUUID():String(Date.now())),placedAt:new Date().toISOString(),sport:"NFL",book:"bet365",
    legs:legs.map(l=>{const d=decOf(l.odds);return {description:legLabel(l).replace(" — ",": "),odds:d?parseInt(String(l.odds).replace("+","")):0,game:P[l.id].game}}),
    stake:px.stake,status:"open",price,modelChance:jointP(legs)};
  try{const k="godseye.bets.v1";const all=JSON.parse(localStorage.getItem(k)||"[]");all.unshift(bet);localStorage.setItem(k,JSON.stringify(all));
    window.dispatchEvent(new Event("ge-bets"));toast("Added to My bets")}
  catch(err){toast("Could not save: browser storage is unavailable")}
});
"""

# ---------- CSS: fonts come from this site's font loader ----------
for old, new in [
    ('--display:"Saira Condensed"', '--display:var(--font-display)'),
    ('--body:"IBM Plex Sans"', '--body:var(--font-body)'),
    ('--mono:"IBM Plex Mono"', '--mono:var(--font-mono)'),
]:
    if old not in css:
        raise SystemExit(f"import-console: expected font declaration not found: {old}")
    css = css.replace(old, new)

out_public = ROOT / "public" / "console"
out_public.mkdir(parents=True, exist_ok=True)
if data_line is not None:
    (out_public / "data.js").write_text(data_line + "\n", encoding="utf8")
(out_public / "app.js").write_text(js + "\n", encoding="utf8")
out_css = ROOT / "src" / "app" / "(console)"
out_css.mkdir(parents=True, exist_ok=True)
(out_css / "console-base.css").write_text(
    "/* Generated by scripts/import-console.py from the console export. Edit console.css, not this file. */\n" + css.strip() + "\n",
    encoding="utf8",
)
if data_line is None:
    print(f"no {data_file.relative_to(ROOT)} yet: data.js left as it is. Run `python run.py site` in model/nfl first.")
else:
    print(f"data.js: season {D['meta'].get('season')} week {D['meta'].get('week')}, built {D['meta'].get('built')}, {len(data_line):,} bytes")
print(f"app.js {len(js):,} bytes, console-base.css {len(css):,} bytes")
