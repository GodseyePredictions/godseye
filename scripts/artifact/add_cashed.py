"""Add the Cashed slips tab to the live artifact source (the NBA React bundle cannot be rebuilt here).

usage: add_cashed.py LIVE.html nba_cashed.json OUT.html
Idempotent: a page that already has the tab only gets its data refreshed.
"""
import json
import re
import sys

live, data, out = sys.argv[1:4]
s = open(live).read()
cashed = json.load(open(data))

COMPONENT = r"""
window.GECashed=function(){
  var C=window.GE_CASHED,e=React.createElement;
  var am=function(a){a=Math.round(a);return a>0?"+"+a:"−"+Math.abs(a)};
  var money=function(v){return "$"+v.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2})};
  var day=function(d){return new Date(d+"T12:00:00Z").toLocaleDateString("en-US",{weekday:"long",month:"long",day:"numeric",timeZone:"UTC"})};
  var head=function(t,sub){return e("div",{className:"section-head"},e("div",null,e("h2",null,t),sub?e("p",{className:"sub"},sub):null))};
  var kpi=function(k,v){return e("div",{className:"kpi",key:k},e("div",{className:"k"},k),e("div",{className:"v"},v))};
  if(!C.slips.length)return e("section",{className:"panel"},head("Cashed slips"),e("p",{className:"empty"},"No graded slips yet."));
  var staked=0,returned=0;C.slips.forEach(function(x){staked+=x.stake;returned+=x.returned});
  var R=C.stake_rule;
  var out=[e("section",{className:"panel",key:"intro"},head("Cashed slips","Algorithm slips that won, "+day(C.from)+" to "+day(C.to)),
    e("div",{className:"kpis",style:{marginBottom:12}},kpi("Slips cashed",C.cashed+" of "+C.issued),kpi("Example stakes on these slips",money(staked)),
      kpi("Would have returned",money(returned)),kpi("Same stakes on all "+C.issued+" slips",(C.all_net>=0?"+":"−")+money(Math.abs(C.all_net))+" net")),
    e("p",{className:"sub",style:{maxWidth:"80ch"}},"This page lists winners only: "+(C.issued-C.cashed)+" of the "+C.issued+" slips the algorithm issued in this period lost and are not shown. "
      +"Putting the same example stakes on every one of the "+C.issued+" slips would have meant "+money(C.all_staked)+" staked for the "+money(returned)+" returned. "
      +"Stakes are examples, not bets that were placed: $"+R.long+" on a slip listed at "+am(R.long_price)+" or longer, $"+R.short+" on a shorter one. "
      +"Returns use the listed price, which is DraftKings' leg prices multiplied together; a real same-game price pays less. "
      +"Every slip was issued before tip-off and graded from the official box score."))];
  C.nights.filter(function(n){return n.cashed>0}).sort(function(a,b){return a.date<b.date?1:-1}).forEach(function(n){
    out.push(e("section",{className:"panel",key:n.date},head(day(n.date),n.cashed+" of "+n.issued+" slips cashed"),
      e("div",{className:"scroll"},e("table",{className:"tbl"},
        e("thead",null,e("tr",null,["Slip","Listed price","Example stake","Would have returned","Profit"].map(function(h){return e("th",{key:h},h)}))),
        e("tbody",null,C.slips.filter(function(x){return x.date===n.date}).map(function(x){return e("tr",{key:x.id},
          e("td",null,e("b",null,x.game+" · "+x.type),e("div",{className:"sub",style:{maxWidth:"70ch"}},x.legs.map(function(l){return l.label+(l.actual==null?"":" ("+l.actual+")")}).join(" · "))),
          e("td",{className:"num"},am(x.price)),e("td",{className:"num"},money(x.stake)),e("td",{className:"num"},money(x.returned)),
          e("td",{className:"num"},e("span",{className:"pill good"},"+"+money(x.profit))))}))))));
  });
  return e(React.Fragment,null,out);
};
"""

block = "<script id=\"ge-cashed\">window.GE_CASHED=" + json.dumps(cashed).replace("</", "<\\/") + ";" + COMPONENT + "</script>\n"


def once(s, a, b):
    assert s.count(a) == 1, (a[:60], s.count(a))
    return s.replace(a, b)


if 'id="ge-cashed"' in s:
    s = re.sub(r'<script id="ge-cashed">.*?</script>\n', lambda m: block, s, count=1, flags=re.S)
else:
    anchor = 'react-dom.production.min.js"></script>\n'
    s = once(s, anchor, anchor + block)
    s = once(s, '["home","sgp","multi","strategy","track","board","scripts","avail","model"]',
             '["home","sgp","multi","strategy","cashed","track","board","scripts","avail","model"]')
    a = '["strategy","Bankroll strategy","M4 19h16M6 16V8M11 16V5M16 16v-6"],'
    s = once(s, a, a + '["cashed","Cashed slips","M5 12l4 4 10-10M4 20h16"],')
    m = re.findall(r'(\w+)==="strategy"&&React\.createElement\(window\.GEStrategy,null\),', s)
    assert len(m) == 1
    a = f'{m[0]}==="strategy"&&React.createElement(window.GEStrategy,null),'
    s = once(s, a, a + f'{m[0]}==="cashed"&&React.createElement(window.GECashed,null),')
    # the nav group headings sit in front of the item at a fixed index; one more item before them
    m = re.findall(r'(\w+)===4(&&React\.createElement\("span",\{className:"navgrp"\},"Tools"\),)(\w+)===7(&&React\.createElement\("span",\{className:"navgrp"\},"Model"\))', s)
    assert len(m) == 1
    v, t1, v2, t2 = m[0]
    s = once(s, f"{v}===4{t1}{v2}===7{t2}", f"{v}===5{t1}{v2}===8{t2}")

open(out, "w").write(s)
print("ok", len(s), s.count("GECashed"))
