"""Add the Bankroll strategy tab to the live artifact source (the NBA React bundle cannot be rebuilt here).

usage: add_strategy.py LIVE.html nba_strategy.json OUT.html
Idempotent: a page that already has the tab only gets its data refreshed.
"""
import json
import re
import sys

live, data, out = sys.argv[1:4]
s = open(live).read()
strat = json.load(open(data))

COMPONENT = r"""
window.GEStrategy=function(){
  var S=window.GE_STRATEGY,e=React.createElement;
  var pct=function(p,d){return (p*100).toFixed(d||0)+"%"};
  var am=function(a){return a>0?"+"+a:"−"+Math.abs(a)};
  var head=function(t,sub){return e("div",{className:"section-head"},e("div",null,e("h2",null,t),sub?e("p",{className:"sub"},sub):null))};
  var kpi=function(k,v){return e("div",{className:"kpi",key:k},e("div",{className:"k"},k),e("div",{className:"v"},v))};
  if(new Date(Date.now()-11*3600e3).toISOString().slice(0,10)>S.date)
    return e("section",{className:"panel"},head("Bankroll strategy"),e("p",{className:"empty"},"No bankroll strategy is posted for today's slate yet."));
  var out=[e("section",{className:"panel",key:"intro"},head("Bankroll strategy",S.built),e("p",{className:"sub",style:{maxWidth:"75ch"}},S.intro))];
  S.bankrolls.forEach(function(b){
    out.push(e("section",{className:"panel",key:"b"+b.size},
      head("$"+b.size+" bankroll","Stake $"+b.staked+", hold $"+b.reserve+" in reserve"),
      e("div",{className:"kpis",style:{marginBottom:12}},kpi("Staked","$"+b.staked),kpi("Chance of a winning night",pct(b.win_chance)),kpi("Typical night","about +$"+b.typical),kpi("Lose all staked",pct(b.lose_all))),
      e("div",{className:"scroll"},e("table",{className:"tbl"},
        e("thead",null,e("tr",null,["Slip","Type","Stake","Model chance","Listed price","Profit if it cashes"].map(function(h){return e("th",{key:h},h)}))),
        e("tbody",null,b.rows.map(function(r){return e("tr",{key:r.slip},e("td",null,e("b",null,r.slip)),e("td",null,r.type),e("td",{className:"num"},"$"+r.stake),e("td",{className:"num"},pct(r.chance,r.chance<0.1?1:0)),e("td",{className:"num"},am(r.price)),e("td",{className:"num"},"about $"+r.profit))}),
          e("tr",{key:"hold"},e("td",null,"Held in reserve"),e("td",null),e("td",{className:"num"},"$"+b.reserve),e("td",null),e("td",null),e("td",null)))))));
  });
  var c=S.cross_game;
  out.push(e("section",{className:"panel",key:"cross"},head(c.name,"Model chance about "+pct(c.chance)+" · listed "+am(c.price)+" · take only at "+am(c.min_price)+" or better"),
    e("div",{className:"scroll"},e("table",{className:"tbl"},e("thead",null,e("tr",null,["Game","Leg","Model","DraftKings"].map(function(h){return e("th",{key:h},h)}))),
      e("tbody",null,c.legs.map(function(l){return e("tr",{key:l.label},e("td",null,l.game),e("td",null,e("b",null,l.label)),e("td",{className:"num"},pct(l.p)),e("td",{className:"num"},am(l.price)))}))))));
  out.push(e("section",{className:"panel",key:"notes"},head("How to use it"),e("ul",{className:"why"},S.notes.map(function(n,i){return e("li",{key:i},n)}))));
  return e(React.Fragment,null,out);
};
"""

block = "<script id=\"ge-strategy\">window.GE_STRATEGY=" + json.dumps(strat).replace("</", "<\\/") + ";" + COMPONENT + "</script>\n"

if 'id="ge-strategy"' in s:
    s = re.sub(r'<script id="ge-strategy">.*?</script>\n', lambda m: block, s, count=1, flags=re.S)
else:
    anchor = 'react-dom.production.min.js"></script>\n'
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor + block)
    a = '["home","sgp","multi","track","board","scripts","avail","model"]'
    assert s.count(a) == 1
    s = s.replace(a, '["home","sgp","multi","strategy","track","board","scripts","avail","model"]')
    a = '["multi","Multi-game slips","M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5"],'
    assert s.count(a) == 1
    s = s.replace(a, a + '["strategy","Bankroll strategy","M4 19h16M6 16V8M11 16V5M16 16v-6"],')
    m = re.findall(r'(\w+)==="multi"&&React\.createElement\((\w+),null\),', s)
    assert len(m) == 1
    v, comp = m[0]
    a = f'{v}==="multi"&&React.createElement({comp},null),'
    s = s.replace(a, a + f'{v}==="strategy"&&React.createElement(window.GEStrategy,null),')

open(out, "w").write(s)
print("ok", len(s), s.count("GEStrategy"))
