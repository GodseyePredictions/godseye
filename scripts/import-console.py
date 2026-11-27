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
# 2a. Every algorithm ticket is shown as a set slip (the white Godseye slip, src/styles/slip.css), never as a
#     button that only loads the bet slip. One helper draws them all.
js = patch(
    js,
    "function renderScriptSGP(){",
    """function geSlip(title,meta,legs,p,load){const lp=l=>l.p??legP(l);return `<article class="gs-slip"><header class="gs-slip-head"><h3 class="gs-slip-title">${esc(title)}</h3><span class="gs-slip-meta">${esc(meta)}</span></header><ul class="gs-slip-legs">${legs.map(l=>`<li><span>${esc(legLabel(l).replace(" — ",": "))}${l.n?`<small>cleared in ${l.hits} of ${l.n} games</small>`:""}</span><span class="num">${pct(lp(l)??0,0)}</span></li>`).join("")}</ul><dl class="gs-slip-foot"><div><dt>Chance to hit</dt><dd class="red">${pct(p)}</dd></div><div><dt>Chance to miss</dt><dd>${pct(1-p)}</dd></div><div><dt>Fair odds</dt><dd>${am(p)}</dd></div></dl><button class="btn ge-slip-add" ${load}>Add to bet slip</button></article>`}
function renderScriptSGP(){""",
)
#     the 4/6/8/10-leg ladder of each game
js = patch(
    js,
    """<div class="row" style="margin:10px 0 6px">${t.ladder.map(x=>`<button class="btn ${x.n===4?"primary":""}" data-script-load="${gi}|ladder|${x.n}">${x.n}-leg · ${pct(x.p)} · fair ${am(x.p)}</button>`).join("")}</div>""",
    """<div class="gs-slips ge-set">${t.ladder.map(x=>geSlip(`${x.n}-leg SGP`,gameLabel(g),x.legs,x.p,`data-script-load="${gi}|ladder|${x.n}"`)).join("")}</div>""",
)
js = patch(
    js,
    """      ${top?top.legs.map(legrow).join(""):""}""",
    """      ${top?`<h3 class="ge-set-title">Leg by leg: why each one is on the ${top.n}-leg</h3>`+top.legs.map(legrow).join(""):""}""",
)
#     the lotto, hybrid and aggressive tickets of each game
js = patch(js, """<div class="grid2" style="margin-top:12px">
        ${["lotto","hybrid1\"""", """<div class="gs-slips ge-set" style="margin-top:14px">
        ${["lotto","hybrid1\"""")
js = patch(
    js,
    """return `<div class="ticket"><div class="top"><span class="legsn">${ttl}</span><span class="fair">${am(h.p)}</span></div><div class="pct">${pct(h.p)} to hit</div>
            <ol>${h.legs.map(l=>`<li>${esc(legLabel(l))} <span>${pct(l.p,0)}</span></li>`).join("")}</ol>
            <button class="btn primary" data-script-load="${gi}|${k}|0">Load into slip</button></div>`}""",
    """return geSlip(ttl,gameLabel(g),h.legs,h.p,`data-script-load="${gi}|${k}|0"`)}""",
)
#     Props SGPs by game: one slip per leg count, not one list with buttons
js = patch(
    js,
    """return `<div class="ticket"><h3>${b==="floor"?"Floor SGP · 70–88% legs":"Aggressive SGP · 55–68% legs"}</h3>
      <ol>${top.legs.map(l=>`<li>${esc(legLabel(l))} <span>${pct(legP(l)??0,0)}</span></li>`).join("")}</ol>
      <div class="row">${tiers.map(t=>`<button class="btn sm" data-load-prop="${esc(t.ticket)}">${t.legs.length}-leg · ${pct(t.p)} · ${am(t.p)}</button>`).join("")}</div></div>`}""",
    """return `<div class="ge-block"><h3 class="ge-set-title">${b==="floor"?"Floor SGP · 70–88% legs":"Aggressive SGP · 55–68% legs"}</h3>
      <div class="gs-slips ge-set">${tiers.map(t=>geSlip(`${t.legs.length}-leg ${b==="floor"?"floor":"aggressive"} SGP`,gameLabel(G[sel]),t.legs,t.p,`data-load-prop="${esc(t.ticket)}"`)).join("")}</div></div>`}""",
)
js = patch(
    js,
    """<div class="row">${combos.map(t=>`<button class="btn" data-load-prop="${esc(t.ticket)}">${t.legs.length}-leg · ${pct(t.p)} · fair ${am(t.p)}</button>`).join("")}</div></section>""",
    """<div class="gs-slips ge-set">${combos.map(t=>geSlip(`${t.legs.length}-leg cross-game`,"Floor legs",t.legs,t.p,`data-load-prop="${esc(t.ticket)}"`)).join("")}</div></section>""",
)
#     Cashed slips (owner, 24 November): the same white slip, NFL slips only (NBA and NHL have their own tabs)
_a = js.index("const card=(title,pills,legs,meta,stake,ret)=>")
_b = js.index("const grid=cards=>", _a)
js = js[:_a] + """const card=(title,pills,legs,meta,stake,ret,stakeLabel="Example stake")=>`<article class="gs-slip gs-cashed"><header class="gs-slip-head"><h3 class="gs-slip-title">${esc(title)}</h3></header><div class="gs-cashed-pills">${pills}</div><ul class="gs-slip-legs gs-checks">${legs}</ul><p class="gs-cashed-meta">${meta}</p><dl class="gs-slip-foot gs-cashed-foot">${stake?`<div><dt>${stakeLabel}</dt><dd>${money(stake)}</dd></div>`:""}<div><dt>Cashed</dt><dd class="red">${stake?money(ret):"✓"}</dd></div></dl></article>`;
  """ + js[_b:]
js = patch(js, """const grid=cards=>`<div class="cgrid">${cards||""", """const grid=cards=>`<div class="gs-slips ge-set">${cards||""")
_a = js.index("const lgbar=`<div class=\"lgbar\">")
_b = js.index("\n", _a)
js = js[:_a] + 'const lgbar="";' + js[_b:]
js = patch(js, 'state.cashF={lg:"nfl",kind:"all",n:"all",week:"all"}); if(!f.lg) f.lg="nfl";', 'state.cashF={lg:"nfl",kind:"all",n:"all",week:"all"}); f.lg="nfl";')
js = patch(js, '''`<span class="cpill">Week ${s.week}</span><span class="cpill">${kindL[s.kind]||s.kind}</span><span class="cpill win">${s.n}-leg cashed</span>`,''',
               '''`<span>Week ${s.week}</span><span>${kindL[s.kind]||s.kind}</span><span class="win">${s.n}-leg cashed</span>`,''')
js = patch(js, '''s.legs.map(l=>`<li>${esc(l.t)} <span class="cact">(${esc(l.r)})</span></li>`).join(""),''',
               '''s.legs.map(l=>`<li><span>${esc(l.t)}</span></li>`).join(""),''')
#     Week 12 onward a cashed slip carries the books' listed price (owner, 25 November: a fair price is never shown as a price)
js = patch(js, """`<span>Model ${s.p?pct(s.p):"–"}</span><span>Fair price <b>${amS(s.fair)}</b></span>`""",
               """`<span>Model ${s.p?pct(s.p):"–"}</span>${s.price!=null?`<span>Price <b>${amS(s.price)}</b></span>`:`<span>Fair price <b>${amS(s.fair)}</b></span>`}`""")
js = patch(js, "sort((a,b)=>b.week-a.week||(b.fair||0)-(a.fair||0))", "sort((a,b)=>b.week-a.week||((b.price??b.fair)||0)-((a.price??a.fair)||0))")
#     Week 12 NFL cashed slips show a "Wager" (owner, 27 November) instead of "Example stake"
js = patch(js, "s.stake,s.ret)).join(\"\");\n  const aw=", "s.wager||s.stake,s.ret,s.wager?\"Wager\":\"Example stake\")).join(\"\");\n  const aw=")
#     cashed tabs show only the total wagered and the total cashed (owner, 27 November): no slip count, no "example stakes", no "fair prices"
js = patch(js, '<p class="sub" style="margin-top:10px">${S.length} slips shown · example stakes ${money(tot.st)} · cashed ${money(tot.rt)}</p></section>${grid(cards)}`;', '<p class="sub" style="margin-top:10px">Wagered ${money(tot.st)} · Total cashed ${money(tot.rt)}</p></section>${grid(cards)}`;')
js = patch(js, '<p class="sub" style="margin-top:10px">${S.length} slips shown · example stakes ${money(tot.st)} · cashed ${money(tot.rt)} at fair prices</p></section>', '<p class="sub" style="margin-top:10px">Wagered ${money(tot.st)} · Total cashed ${money(tot.rt)}</p></section>')
js = patch(js, 'const tot=S.reduce((a,s)=>({st:a.st+(s.stake||0),rt:a.rt+(s.ret||0)}),{st:0,rt:0});', 'const tot=S.reduce((a,s)=>({st:a.st+(s.wager||s.stake||0),rt:a.rt+(s.ret||0)}),{st:0,rt:0});')
#     no tally of tickets cashed or issued anywhere on the site (owner, 26 November): the record chip is not drawn
js = patch(js, '''rec.tickets?["Last graded week",`${rec.cashed}<small>/ ${rec.tickets} cashed</small>`,`${rec.legs_hit}% of legs hit vs ${rec.legs_exp}% expected`]:["Props holdout",`87%<small>hit</small>`,"floor legs 2025–26, 82% expected"]];''', '''["Props holdout",`87%<small>hit</small>`,"floor legs 2025–26, 82% expected"]];''')
js = patch(js, """$("#recchip").textContent=D.meta.record&&D.meta.record.tickets?`Last week: ${D.meta.record.cashed}/${D.meta.record.tickets} tickets cashed`:`Graded as shipped, every week`;""", "")
#     the home page's shortcuts open the Game SGPs tab, where the slips are
js = patch(
    js,
    """return top?`<button class="btn" data-script-load="${gi}|ladder|${top.n}">${gameLabel(G[t.game])} · ${top.n}-leg · ${pct(top.p)}</button>`:\"\"""",
    """return top?`<a class="btn" href="#sgp">${gameLabel(G[t.game])} · ${top.n}-leg · ${pct(top.p)}</a>`:\"\"""",
)

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
# 4. Stakes come from the site's staking engine (src/lib/staking.ts) only: the slip shows its answer and
#    drops its own bankroll field and quarter-Kelly sum.
js = patch(
    js,
    """      <dt>Quarter-Kelly stake (bankroll ${money(bank)})</dt><dd>${money(bank*kelly/4)}</dd></dl>""",
    """      <dt>Suggested stake (<a href="#bankroll" data-close-slip>Bankroll Strategy</a>)</dt><dd>${window.GE_STAKE?esc(window.GE_STAKE(pj,bookDec,estimated,legs.length)):"–"}</dd></dl>""",
)
js = patch(
    js,
    """
      <label for="f-bank">Bankroll ($)<input id="f-bank" data-field="bankroll" value="${esc(s.bankroll)}" inputmode="decimal"></label></div>""",
    """</div>""",
)
js = patch(
    js,
    """  if(!legs.length){ $("#slip").innerHTML=""",
    """  if(!legs.length){ if(window.GE_STAKE)window.GE_STAKE(0,0,true,0); $("#slip").innerHTML=""",
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

# The Cashed slips showcase (owner, 24 November): winning NFL slips only, with example stakes. The counts of slips
# issued and lost ("weeks", "excluded") are never put on the site. It is added to whatever data.js now holds, so
# it is there whether or not this run rewrote the week's data.
cashed_file = NFL / "outputs" / "cashed_slips.json"
data_js = out_public / "data.js"
if cashed_file.exists() and data_js.exists():
    text = data_js.read_text(encoding="utf8")
    cur = json.loads(text[text.index("{"):text.rindex("}") + 1])
    showcase = {k: v for k, v in json.loads(cashed_file.read_text(encoding="utf8")).items() if k not in ("weeks", "excluded")}
    for slip in showcase.get("slips", []):
        if any(str(l.get("r", "")).upper() in ("MISS", "LOST", "NO") for l in slip.get("legs", [])):
            raise SystemExit("import-console: the cashed showcase holds a slip with a losing leg")
    cur["cashed"] = showcase
    cur.pop("cashed_nba", None)
    data_js.write_text("const D = " + json.dumps(cur, separators=(",", ":")) + ";\n", encoding="utf8")
    print(f"cashed showcase: {len(showcase.get('slips', []))} winning slips")
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
