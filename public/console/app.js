const MK = {atd:"Anytime TD",carries:"carries",rush_yds:"rush yds",rec:"receptions",rec_yds:"rec yds",pass_att:"pass att",pass_yds:"pass yds",pass_td:"pass TDs"};
const P = Object.fromEntries(D.players.map(p=>[p.id,p]));
const G = Object.fromEntries(D.games.map(g=>[g.id,g]));
const $ = s=>document.querySelector(s);
const esc = s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* ---------- odds helpers ---------- */
const am = p=>{p=Math.min(Math.max(p,1e-4),1-1e-4);const a=p>=.5?-100*p/(1-p):100*(1-p)/p;const r=Math.round(a);return (r>0?"+":"")+r};
const decOf = a=>{a=parseFloat(String(a).replace("+",""));if(!isFinite(a)||Math.abs(a)<100)return null;return a>0?1+a/100:1+100/-a};
const amFromDec = d=>d>=2?"+"+Math.round((d-1)*100):String(Math.round(-100/(d-1)));
const pct = (p,d=1)=>(p*100).toFixed(d)+"%";
const money = x=>(x<0?"-$":"$")+Math.abs(x).toFixed(2);

/* ---------- normal + copula ---------- */
function ninv(p){const a=[-39.69683028665376,220.9460984245205,-275.9285104469687,138.357751867269,-30.66479806614716,2.506628277459239],
b=[-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771542,-13.28068155288572],
c=[-.007784894002430293,-.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783],
d=[.007784695709041462,.3224671290700398,2.445134137142996,3.754408661907416];const pl=.02425;let q,r;
if(p<pl){q=Math.sqrt(-2*Math.log(p));return(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
if(p>1-pl){q=Math.sqrt(-2*Math.log(1-p));return-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)}
q=p-.5;r=q*q;return(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)}
function rng(seed){return function(){seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function chol(S){const n=S.length,L=S.map(()=>Array(n).fill(0));for(let i=0;i<n;i++)for(let j=0;j<=i;j++){let s=S[i][j];for(let k=0;k<j;k++)s-=L[i][k]*L[j][k];
if(i===j){if(s<=1e-9)return null;L[i][i]=Math.sqrt(s)}else L[i][j]=s/L[j][j]}return L}

function rho(a,b){
  const pa=P[a.id],pb=P[b.id]; if(pa.game!==pb.game) return 0;
  const rel = a.id===b.id?"SELF":(pa.team===pb.team?"TM":"OPP");
  if(a.mk==="atd"&&b.mk==="atd"){ if(rel==="OPP") return D.corr.atd.OPP??0.03;
    const k="TM:"+[pa.pos,pb.pos].sort().join("-"); return D.corr.atd[k]??D.corr.atd["TM:default"]??-0.04; }
  if(rel==="SELF"&&a.mk===b.mk) return 0.95;
  const x=[a.mk+"@"+pa.pos,b.mk+"@"+pb.pos].sort();
  const k=rel+"|"+x[0]+"|"+x[1];
  if(k in D.corr.legs) return D.corr.legs[k];
  return rel==="SELF"?(D.corr.legs._rel?.SELF??0.3):0;
}
function legP(l){ if(l.mk==="atd") return P[l.id].p; const m=D.props[l.id]?.[l.mk]; if(!m) return null; const i=m.k.indexOf(l.k); return i<0?null:m.p[i]; }
function jointP(legs){return jointPN(legs,60000)}
function jointPN(legs,NS){
  if(!legs.length) return null;
  const byG={}; legs.forEach(l=>{(byG[P[l.id].game]??=[]).push(l)});
  let out=1;
  for(const g in byG){ const L=byG[g], p=L.map(legP);
    if(L.length===1){out*=p[0];continue}
    let S=L.map((a,i)=>L.map((b,j)=>i===j?1:rho(a,b))), C=null, shrink=1;
    while(!(C=chol(S))&&shrink>0.2){shrink*=0.9;S=S.map((r,i)=>r.map((v,j)=>i===j?1:v*0.9))}
    const t=p.map(ninv), n=L.length, N=NS, R=rng(1234+n*7); let hit=0;
    for(let s=0;s<N;s++){ const z=[]; for(let i=0;i<n;i++){const u1=R()||1e-12,u2=R();z.push(Math.sqrt(-2*Math.log(u1))*Math.cos(6.283185307179586*u2))}
      let ok=true; for(let i=0;i<n&&ok;i++){let x=0;for(let k=0;k<=i;k++)x+=C[i][k]*z[k]; if(x>=t[i]) ok=false} if(ok)hit++ }
    out*=hit/N;
  }
  return out;
}

/* ---------- state ---------- */
const store={get(k,d){try{const v=localStorage.getItem("ge_"+k);return v?JSON.parse(v):d}catch(e){return d}},set(k,v){try{localStorage.setItem("ge_"+k,JSON.stringify(v))}catch(e){}}};
const state={tab:"picks", game:D.games[0]?.id, propsGame:D.games[0]?.id,
  slip:store.get("slip",{legs:[],stake:"10",bankroll:"500",book:"",margin:"10",legMargin:"6"}), saved:store.get("saved",[])};
function persist(){store.set("slip",state.slip);store.set("saved",state.saved)}
function toast(t){const e=document.createElement("div");e.className="toast";e.textContent=t;document.body.appendChild(e);setTimeout(()=>e.remove(),1600)}
const legKey=l=>l.id+"|"+l.mk+"|"+(l.k??"");
function addLeg(l,quiet){ if(state.slip.legs.some(x=>legKey(x)===legKey(l))){if(!quiet)toast("Already on the slip");return}
  state.slip.legs.push({...l,odds:"",status:"o"}); persist(); renderSlip(); if(!quiet)toast("Added to bet slip") }
function appendLegs(legs,label){ const before=state.slip.legs.length; legs.forEach(l=>addLeg(l,true)); persist(); renderSlip();
  const added=state.slip.legs.length-before; if(added) openSlip(true); toast(added?`${label}: ${added} leg${added>1?"s":""} added to slip`:"Already on the slip") }
function loadLegs(legs,label){ state.slip.legs=[]; state.slip.sgpOdds={}; legs.forEach(l=>addLeg(l,true)); state.slip.book=""; persist(); renderSlip(); openSlip(true); toast(label+" loaded into slip") }
const legLabel=l=>l.mk==="atd"?`${P[l.id].name} — Anytime TD`:`${P[l.id].name} ${l.k}+ ${MK[l.mk]}`;

/* ---------- views ---------- */
function gameLabel(g){return `${g.away} @ ${g.home}`}
function envPills(g){
  const out=[`<span class="pill">${esc(g.weekday)} ${esc(g.kick)}</span>`,`<span class="pill">${esc(g.venue)}</span>`];
  if(g.wx==="indoor") out.push(`<span class="pill">Indoors</span>`);
  else if(g.temp==null) out.push(`<span class="pill">No forecast (international)</span>`);
  else out.push(`<span class="pill ${g.wx==="rain"||g.wx==="snow"?"warn":""}">${esc(g.wx)} · ${g.temp}°F · wind ${g.wind} mph</span>`);
  out.push(`<span class="pill">${g.turf?"Turf":"Grass"}</span>`);
  const sp=g.spread_home; if(sp!=null) out.push(`<span class="pill">${sp>0?g.home+" −"+sp:sp<0?g.away+" −"+(-sp):"Pick'em"} · total ${g.total}</span>`);
  out.push(`<span class="pill gold">Implied ${g.away} ${g.implied[g.away]??"–"} / ${g.home} ${g.implied[g.home]??"–"}</span>`);
  const qn=qbNote(g); if(qn) out.push(`<span class="pill warn">${esc(qn)}</span>`);
  if(g.qb) out.push(`<span class="pill">QBs: ${esc(g.qb[g.away]||"—")} / ${esc(g.qb[g.home]||"—")}</span>`);
  return out.join("");
}

function qbNote(g){const bk=(D.personnel||[]).filter(x=>x.type==="backup_qb"&&(x.team===g.away||x.team===g.home));
  return bk.length?bk.map(x=>`${x.team}: ${x.name} starts (backup)`).join(" · "):""}
function renderPersonnel(){
  const P_=D.personnel||[], ov=P_.filter(x=>x.type==="override"), bk=P_.filter(x=>x.type==="backup_qb"), inj=P_.filter(x=>x.type==="injury");
  const sg=(D.singles||[]).slice().sort((a,b)=>b.p-a.p);
  return `<section class="panel"><div class="section-head"><div><h2>This week's personnel</h2>
    <p class="sub">Applied to every number on this platform. Injury report as of ${esc(D.meta.data_asof||"—")} · ${ov.length} user override${ov.length===1?"":"s"} logged · re-run at inactives (~90 min before kickoff).</p></div></div>
    <div class="pgrid">
      <div><h3>User reads &amp; late news</h3>${ov.length?ov.map(x=>`<div class="prow2"><b>${esc(x.name)}</b> <span class="pill bad">${esc(x.status)}</span> <span class="sub">${esc(x.team)} · ${esc(x.note)}</span></div>`).join(""):'<p class="sub">None.</p>'}</div>
      <div><h3>Projected backup starters</h3>${bk.length?bk.map(x=>`<div class="prow2"><b>${esc(x.name)}</b> <span class="pill warn">QB · ${esc(x.team)}</span> <span class="sub">${x.games} game${x.games===1?"":"s"} this season, ${pct(x.pct,0)} snaps when he played; singles only</span></div>`).join(""):'<p class="sub">Every projected starter is the regular starter.</p>'}</div>
      <div><h3>Singles only (off every parlay)</h3>${sg.length?sg.slice(0,14).map(x=>`<div class="prow2"><b>${esc(x.name)}</b> <span class="pill">${esc(x.pos)} · ${esc(x.team)} · ATD ${pct(x.p,0)}</span> <span class="sub">${esc(x.why)}</span></div>`).join("")+(sg.length>14?`<p class="sub">+${sg.length-14} more on the board.</p>`:""):'<p class="sub">None.</p>'}</div>
      <div><h3>Ruled Out / Doubtful (official report)</h3><p class="sub">${inj.length?inj.map(x=>`${esc(x.name)} (${esc(x.team)}${x.note?", "+esc(x.note):""})`).join(" · "):"None on this slate."}</p></div>
    </div></section>`;
}
function renderModel(){const R=D.rules||{};
  return `<section class="panel"><div class="section-head"><div><h2>Model &amp; rules</h2>
    <p class="sub">What every ATD and props number on this platform considers, the standing rules from your ledger, and how the model has tested. Data only: play-by-play, snap counts, rosters, injury reports, Vegas lines, NWS weather. No media or expert picks.</p></div></div></section>
  <section class="panel"><h3>Factors considered on every build</h3><p class="sub">All sixteen are always on (FACTORS.md). Each pick's intel shows the ones that apply to it.</p>
    <div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>Factor</th><th>How it enters</th></tr></thead><tbody>${(R.factors||[]).map((f,i)=>`<tr><td class="num">${i+1}</td><td><b>${esc(f[0])}</b></td><td>${esc(f[1])}</td></tr>`).join("")}</tbody></table></div></section>
  <section class="panel"><h3>Standing rules</h3><ol class="why" style="font-size:13px">${(R.standing||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ol></section>
  <section class="panel"><h3>Pending your call</h3>${(R.pending||[]).map(x=>`<div class="warns"><div>${esc(x)}</div></div>`).join("")}</section>
  <section class="panel"><h3>How it has tested</h3><div class="scroll"><table class="tbl"><tbody>${(R.stats||[]).map(x=>`<tr><td><b>${esc(x[0])}</b></td><td>${esc(x[1])}</td></tr>`).join("")}</tbody></table></div>
    <p class="sub">Grading is as shipped. After each week: <code>python run.py grade-card</code>, then the algorithm change is logged here and in the ledger.</p></section>
  <section class="panel"><h3>How the numbers are built</h3><ul class="why" style="font-size:13px">
    <li><b>ATD:</b> expected-TD play model → each player's share of his team's goal-line and end-zone opportunities, renormalized across who is actually active → team rushing/passing TD rates anchored on the Vegas total → gradient boosting over every factor group.</li>
    <li><b>Props:</b> one model per market trained on official box scores, giving P(X ≥ k) for every bet365 rung, with out-of-fold calibration per market.</li>
    <li><b>Correlation:</b> measured from out-of-sample results: teammates' TDs negative (RB–RB −0.07), opponents slightly positive (+0.03), QB pass TDs with his WR's TD +0.26, QB yards with his receivers' yards +0.23, same-player catches and yards +0.74. Legs in different games are independent.</li>
    <li><b>Ticket styles:</b> Chalk (highest probability, RB-heavy), Balanced (no position over half the legs, always a WR), Air (receivers only, capped at 8 legs).</li></ul></section>`;
}

function renderKPIs(){const rec=D.meta.record||{};
  const tiles=[
    ["Slate",`${D.meta.n_games}<small>games</small>`,`${D.meta.season} Week ${D.meta.week} · built ${D.meta.built}`],
    ["ATD tickets",`${(()=>{const n=D.algo.atd_styles?Object.values(D.algo.atd_styles).reduce((a,v)=>a+v.tickets.length,0):D.algo.atd.length;return n||(D.algo.atd_combos||[]).length})()}`,(D.algo.atd_styles&&Object.values(D.algo.atd_styles).some(v=>v.tickets.length))?"Chalk · Balanced · Air, one player per team":"In-game ATD doubles and trebles"],
    ["Game SGPs",`${(D.algo.sgp||[]).length}`,"best leg per slot, every game"],
    ["Singles only",`${(D.singles||[]).length}`,"Questionable / returning / backup QBs"],
    ["Model holdout",`0.387<small>log loss</small>`,"ATD, 2025–26 · AUC 0.76 · position baseline 0.444"],
    rec.tickets?["Last graded week",`${rec.cashed}<small>/ ${rec.tickets} cashed</small>`,`${rec.legs_hit}% of legs hit vs ${rec.legs_exp}% expected`]:["Props holdout",`87%<small>hit</small>`,"floor legs 2025–26, 82% expected"]];
  return `<section class="kpis">${tiles.map(t=>`<div class="kpi"><div class="k">${t[0]}</div><div class="v">${t[1]}</div><div class="d">${esc(t[2])}</div></div>`).join("")}</section>`}
function heatify(root){(root||document).querySelectorAll(".prob").forEach(el=>{const m=el.textContent.match(/(\d+(?:\.\d+)?)%/);if(!m)return;const p=parseFloat(m[1]);el.dataset.heat=p>=80?5:p>=65?4:p>=50?3:p>=35?2:1})}

const TEAMCOL={ARI:"#97233F",ATL:"#A71930",BAL:"#241773",BUF:"#00338D",CAR:"#0085CA",CHI:"#C83803",CIN:"#FB4F14",CLE:"#FF3C00",DAL:"#869397",DEN:"#FB4F14",DET:"#0076B6",GB:"#FFB612",HOU:"#A71930",IND:"#002C5F",JAX:"#9F792C",KC:"#E31837",LA:"#FFA300",LAC:"#FFC20E",LV:"#A5ACAF",MIA:"#008E97",MIN:"#4F2683",NE:"#C60C30",NO:"#D3BC8D",NYG:"#A5ACAF",NYJ:"#125740",PHI:"#004C54",PIT:"#FFB612",SEA:"#69BE28",SF:"#AA0000",TB:"#FF7900",TEN:"#4B92DB",WAS:"#5A1414"};
const tcol=t=>TEAMCOL[t]||"#888";
const l5strip=a=>a&&a.length?`<span class="l5" title="last ${a.length} games on this line">${a.map(h=>`<i class="${h?"on":""}"></i>`).join("")}</span>`:"";
function chartSVG(weekly){ if(!weekly||!weekly.length) return "";
  const W=560,H=170,p=28,n=weekly.length,max=16,bw=(W-2*p)/n;
  const y=v=>H-p-(v/max)*(H-2*p);
  const bars=weekly.map((w,i)=>`<rect x="${p+i*bw+bw*0.2}" y="${y(w.hits)}" width="${bw*0.6}" height="${H-p-y(w.hits)}" rx="3" fill="url(#gbar)"/>
    <text x="${p+i*bw+bw/2}" y="${H-p+14}" text-anchor="middle" font-size="10" fill="#a79da2">W${w.week}</text>
    <text x="${p+i*bw+bw/2}" y="${y(w.hits)-5}" text-anchor="middle" font-size="10" fill="#fff" font-family="var(--mono)">${w.hits}</text>`).join("");
  const line=weekly.map((w,i)=>`${i?"L":"M"}${p+i*bw+bw/2},${y(w.expected)}`).join("");
  const grid=[0,4,8,12,16].map(v=>`<line x1="${p}" x2="${W-p}" y1="${y(v)}" y2="${y(v)}" stroke="#2a2429"/><text x="${p-6}" y="${y(v)+3}" text-anchor="end" font-size="9" fill="#6f666b">${v}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Top-16 board hits per week vs model expectation">
    <defs><linearGradient id="gbar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d6192b"/><stop offset="1" stop-color="#7d0d1a"/></linearGradient></defs>
    ${grid}${bars}<path d="${line}" fill="none" stroke="#d9a53a" stroke-width="2" stroke-dasharray="4 3"/>
    ${weekly.map((w,i)=>`<circle cx="${p+i*bw+bw/2}" cy="${y(w.expected)}" r="3" fill="#d9a53a"/>`).join("")}</svg>`}
function renderHome(){
  const wk=D.meta.weekly||[]; const tot=wk.reduce((a,w)=>a+w.hits,0), exp=wk.reduce((a,w)=>a+w.expected,0);
  const top=D.players.filter(p=>!p.singles&&!G[p.game].started).slice(0,6);
  const sg=(D.algo.sgp||[]).filter(t=>!G[t.game].started).sort((a,b)=>b.p-a.p).slice(0,3);
  const chalk=(D.algo.atd_styles&&D.algo.atd_styles.chalk)?D.algo.atd_styles.chalk.tickets[0]:null;
  return `<section class="hero">
      <div class="hero-text"><div class="eyebrow">Elite NFL intelligence · model only, no media picks</div>
        <h2 class="hero-h">See the edge.<br><span>Win more.</span></h2>
        <p class="sub hero-sub">Anytime-TD and props probabilities from a model trained on every play since 2021, priced with measured leg correlations, graded as shipped every week. ${D.meta.season} Week ${D.meta.week} · ${D.meta.n_games} games.</p>
        <div class="row" style="margin-top:12px"><a class="btn primary" href="#picks">View this week's picks</a><a class="btn" href="#mysgp">Build a slip</a><a class="btn" href="#model">How it works</a></div></div>
      </section>
    ${renderKPIs()}
    <section class="panel"><div class="section-head"><div><h2>Track record</h2><p class="sub">Model's top-16 anytime-TD board each week, scored with no look-ahead. Bars = players who scored; gold line = what the model expected. ${wk.length?`Season: ${tot} of ${wk.length*16} (${exp.toFixed(0)} expected).`:""}</p></div></div>
      ${chartSVG(wk)}</section>
    <div class="grid2">
      <section class="panel"><div class="section-head"><div><h2>Featured anytime TDs</h2><p class="sub">Highest probabilities on the upcoming slate (singles-only players excluded).</p></div></div>
        ${top.length?top.map(p=>`<div class="feat"><span class="tc" style="background:${tcol(p.team)}"></span><div class="fn"><b>${esc(p.name)}</b><small>${p.pos} · ${p.team} ${p.home?"vs":"@"} ${p.opp} · ${esc(G[p.game].kick)}</small></div><span class="prob">${pct(p.p,0)}</span><span class="num fair">${am(p.p)}</span><button class="btn sm" data-add-atd="${p.id}">+</button></div>`).join(""):'<div class="empty">Every game on this slate has kicked off. The next build fills this.</div>'}
        ${chalk?`<p class="sub" style="margin-top:8px">Chalk 4-leg: ${chalk.legs.map(id=>esc(P[id].name)).join(" · ")} — ${pct(chalk.p)} · fair ${am(chalk.p)} <button class="btn sm" data-load-atd="chalk|4">Load</button></p>`:""}</section>
      <section class="panel"><div class="section-head"><div><h2>Featured SGPs</h2><p class="sub">Best leg per slot, every game, no TD legs.</p></div></div>
        ${sg.length?sg.map((t,i)=>`<div class="feat"><span class="tc" style="background:${tcol(G[t.game].home)}"></span><div class="fn"><b>${gameLabel(G[t.game])}</b><small>${t.legs.map(l=>esc(legLabel(l))).join(" · ")}</small></div><span class="prob">${pct(t.p,0)}</span><span class="num fair">${am(t.p)}</span><button class="btn sm" data-add-sgp="${D.algo.sgp.indexOf(t)}">+</button></div>`).join(""):'<div class="empty">No upcoming games on this slate.</div>'}</section>
    </div>`;
}
state.atdStyle=state.atdStyle||"chalk";
function renderPicks(){
  const styles=D.algo.atd_styles||{chalk:{label:"Chalk",desc:"",tickets:D.algo.atd}};
  const st=styles[state.atdStyle]?state.atdStyle:"chalk";
  const styleBar=`<div class="seg stylebar" role="group" aria-label="Ticket style">${Object.entries(styles).map(([k,v])=>`<button class="o" data-atd-style="${k}" aria-pressed="${k===st}">${esc(v.label)}</button>`).join("")}</div>
    <p class="sub">${esc(styles[st].desc)}</p>`;
  const anyTickets=Object.values(styles).some(v=>v.tickets.length);
  const combos0=(D.algo.atd_combos||[]);
  const comboCards=combos0.map((t,i)=>`<div class="ticket">
      <div class="top"><span class="legsn">${t.n}-LEG · ${gameLabel(G[t.game])}</span><span class="fair">fair ${am(t.p)}</span></div>
      <div class="pct">${pct(t.p)} to hit · independent ${pct(t.p_indep)} · bet if bet365 pays better than ${am(t.p)}</div>
      <ol>${t.legs.map(id=>`<li>${esc(P[id].name)} <span>${P[id].pos} ${P[id].team} · ${pct(P[id].p,0)}</span></li>`).join("")}</ol>
      <button class="btn primary" data-load-combo="${i}">Load into slip</button></div>`).join("");
  const atd=styles[st].tickets.map(t=>`<div class="ticket">
      <div class="top"><span class="legsn">${t.n}-LEG</span><span class="fair">fair ${am(t.p)}</span></div>
      <div class="pct">${pct(t.p)} to hit · bet if bet365 pays better than ${am(t.p)}</div>
      <ol>${t.legs.map(id=>`<li>${esc(P[id].name)} <span>${P[id].team} · ${pct(P[id].p,0)}</span></li>`).join("")}</ol>
      <button class="btn primary" data-load-atd="${st}|${t.n}">Load into slip</button></div>`).join("");
  const games=D.games.filter(g=>D.algo.props.some(t=>t.ticket.startsWith(g.id+"|")));
  const sel=state.propsGame&&games.some(g=>g.id===state.propsGame)?state.propsGame:games[0]?.id;
  const tk=D.algo.props.filter(t=>t.ticket.startsWith(sel+"|"));
  const blocks=["floor","aggressive"].map(b=>{
    const tiers=tk.filter(t=>t.ticket.includes("|"+b)).sort((a,c)=>a.legs.length-c.legs.length);
    if(!tiers.length) return `<div class="ticket"><h3>${b==="floor"?"Floor SGP":"Aggressive SGP"}</h3><div class="empty">No legs qualify</div></div>`;
    const top=tiers[tiers.length-1];
    return `<div class="ticket"><h3>${b==="floor"?"Floor SGP · 70–88% legs":"Aggressive SGP · 55–68% legs"}</h3>
      <ol>${top.legs.map(l=>`<li>${esc(legLabel(l))} <span>${pct(legP(l)??0,0)}</span></li>`).join("")}</ol>
      <div class="row">${tiers.map(t=>`<button class="btn sm" data-load-prop="${esc(t.ticket)}">${t.legs.length}-leg · ${pct(t.p)} · ${am(t.p)}</button>`).join("")}</div></div>`}).join("");
  const combos=D.algo.props.filter(t=>t.ticket.startsWith("combo")).sort((a,c)=>a.legs.length-c.legs.length);
  const scriptSummary=(D.script_sgp||[]).length?`<section class="panel"><div class="section-head"><div><h2>Script SGPs</h2>
      <p class="sub">Game read first, then the legs. 4/6/8/10-leg props ladders and the two anytime-TD hybrids per game.</p></div></div>
      <div class="row">${D.script_sgp.map((t,gi)=>{const top=t.ladder[0];return top?`<button class="btn" data-script-load="${gi}|ladder|${top.n}">${gameLabel(G[t.game])} · ${top.n}-leg · ${pct(top.p)}</button>`:""}).join("")}
      <a class="btn primary" href="#sgp">Open Game SGPs</a></div></section>`:"";
  const atdSection=anyTickets?`<section class="panel"><div class="section-head"><div><h2>Algorithm ATD parlays</h2>
      <p class="sub">One player per team (teammates split TDs). Each parlay builds on the one before it. Pick the variance you want:</p></div></div>
      ${styleBar}<div class="ladder" style="margin-top:10px">${atd}</div></section>`
    :`<section class="panel"><div class="section-head"><div><h2>Algorithm ATD picks</h2>
      <p class="sub">${D.games.length===1?"One game on the slate, so the one-player-per-team parlays cannot be built. These are the in-game anytime-TD doubles and trebles among parlay-eligible RB/QB legs, priced with the measured teammate/opponent correlations; WR/TE and flagged players are singles."
        :"Too few parlay-eligible players for 4-leg tickets. In-game doubles and trebles instead:"}</p></div></div>
      <div class="ladder" style="margin-top:10px">${comboCards||'<div class="empty">No parlay-eligible pair clears 25%. Play the board as singles.</div>'}</div></section>`;
  return renderKPIs()+atdSection+scriptSummary+`
    <section class="panel"><div class="section-head"><div><h2>Props SGPs by game</h2>
      <p class="sub">bet365 milestone legs. Props SGPs never carry TD legs. Questionable / returning players are singles only.</p></div></div>
      <div class="rail">${games.map(g=>`<button class="gchip" data-pgame="${g.id}" aria-pressed="${g.id===sel}"><b>${gameLabel(g)}</b><small>${esc(g.weekday.slice(0,3))} ${esc(g.kick)}${qbNote(g)?" · <span class=\"qbflag\">backup QB</span>":""}</small></button>`).join("")}</div>
      <div class="ladder" style="margin-top:12px">${blocks}</div></section>
    ${combos.length?`<section class="panel"><div class="section-head"><div><h2>Cross-game prop combos</h2>
      <p class="sub">Floor legs, at most 2 per game and 1 per team.</p></div></div>
      <div class="row">${combos.map(t=>`<button class="btn" data-load-prop="${esc(t.ticket)}">${t.legs.length}-leg · ${pct(t.p)} · fair ${am(t.p)}</button>`).join("")}</div></section>`:""}`+renderPersonnel();
}

function renderScriptSGP(){
  const S=D.script_sgp||[]; if(!S.length) return "";
  const fitpill=f=>f>=0.25?`<span class="pill good">script +${f.toFixed(2)}</span>`:f<=-0.25?`<span class="pill bad">script ${f.toFixed(2)}</span>`:"";
  const legrow=(l,i)=>{const p=P[l.id];return `<div class="sgprow"><span class="slot">${i+1}</span><div class="sgpleg"><div class="line1"><span class="nm">${esc(legLabel(l))}<small>${p.pos} · ${p.team}</small></span>${l.n?`<span class="pill">${l.hits}/${l.n} this season</span>`:""}${fitpill(l.fit)}<span class="prob">${pct(l.p,0)}</span><button class="btn sm" data-add-leg="${l.id}|${l.mk}|${l.k??""}" aria-label="Add leg">+</button></div>${l.why&&l.why.length?`<div class="sub">${l.why.map(esc).join(" · ")}</div>`:""}</div></div>`};
  return S.map((t,gi)=>{const g=G[t.game]; const top=t.ladder[t.ladder.length-1];
    return `<section class="panel"><div class="section-head"><div><h2>${gameLabel(g)}</h2><div class="envline">${envPills(g)}</div></div></div>
      <div class="scriptbox"><div class="lbl">Game script</div>${t.notes.map(n=>`<div class="sub">${esc(n)}</div>`).join("")}</div>
      <div class="row" style="margin:10px 0 6px">${t.ladder.map(x=>`<button class="btn ${x.n===4?"primary":""}" data-script-load="${gi}|ladder|${x.n}">${x.n}-leg · ${pct(x.p)} · fair ${am(x.p)}</button>`).join("")}</div>
      <p class="sub">Each longer ticket extends the shorter one. Legs ranked by probability with script fit as the tiebreaker; ≤2 legs per player.</p>
      ${top?top.legs.map(legrow).join(""):""}
      <div class="grid2" style="margin-top:12px">
        ${["hybrid1","hybrid2"].map(k=>{const h=t[k]; if(!h) return ""; const ttl=k==="hybrid1"?"1 anytime TD + 4 props":"2 anytime TDs + 4 props";
          return `<div class="ticket"><div class="top"><span class="legsn">${ttl}</span><span class="fair">fair ${am(h.p)}</span></div><div class="pct">${pct(h.p)} to hit</div>
            <ol>${h.legs.map(l=>`<li>${esc(legLabel(l))} <span>${pct(l.p,0)}</span></li>`).join("")}</ol>
            <button class="btn primary" data-script-load="${gi}|${k}|0">Load into slip</button></div>`}).join("")}
      </div></section>`}).join("");
}
function renderSGP(){
  const cards=(D.algo.sgp||[]).map((t,gi)=>{const g=G[t.game];
    const rows=t.legs.map((l,li)=>{const p=P[l.id];
      const alts=l.alts.length?`<div class="alts">Alternatives: ${l.alts.map(a=>`<button class="btn sm ghost" data-add-leg="${a.id}|${a.mk}|${a.k}">${esc(P[a.id]?.name||"")} ${a.k}+ ${MK[a.mk]} · ${pct(a.p,0)} +</button>`).join(" ")}</div>`:"";
      return `<div class="sgprow"><span class="slot">${esc(l.slot)}</span>
        <div class="sgpleg"><div class="line1"><span class="nm">${esc(p.name)} ${l.k}+ ${MK[l.mk]}<small>${p.pos} · ${p.team}</small></span>
          <span class="pill">${l.hits}/${l.n} this season</span><span class="prob">${pct(l.p,0)}</span>
          <button class="btn sm" data-add-leg="${l.id}|${l.mk}|${l.k}" aria-label="Add leg">+</button></div>
          <details><summary>Why this leg</summary><ul class="why">${l.why.map(w=>`<li>${w}</li>`).join("")}</ul></details>${alts}</div></div>`}).join("");
    return `<section class="panel sgpcard"><div class="section-head"><div><h2>${gameLabel(g)}</h2>
        <div class="envline">${envPills(g)}</div></div>
        <div class="sgpprice"><div class="big"><div><div class="lbl">${t.legs.length}-leg SGP</div><div class="sub">If independent ${pct(t.p_indep)}</div></div>
        <div class="val">${pct(t.p)}<small>fair ${am(t.p)}</small></div></div></div></div>
      ${rows}
      <div class="row" style="margin-top:10px"><button class="btn primary" data-add-sgp="${gi}">Add SGP to slip</button>
      <span class="sub">bet365 reprices same-game parlays: type the SGP price into the slip to check the edge.</span></div></section>`}).join("");
  const X=D.crossgame||{}; const lad=(key,title,note)=>{const T=X[key]||[]; if(!T.length) return "";
    return `<div class="ticket" style="grid-column:1/-1"><h3>${title}</h3><p class="sub">${note}</p>
      <div class="row">${T.map((t,i)=>`<button class="btn ${i===0?"primary":""}" data-load-xg="${key}|${i}">${t.n}-leg · ${t.games.length} games · ${pct(t.p)} · fair ${am(t.p)}</button>`).join("")}</div>
      <ol style="margin-top:8px">${T[T.length-1].legs.map(l=>`<li>${esc(legLabel(l))} <span>${P[l.id].team} · ${pct(l.p,0)}</span></li>`).join("")}</ol></div>`};
  const xgSection=(X.props&&X.props.length)?`<section class="panel"><div class="section-head"><div><h2>Cross-game SGP ladder</h2>
      <p class="sub">The best 2-leg stack from each game (legs that help each other, e.g. a QB with his receiver), multiplied across games. Only games that haven't kicked off. Each longer ticket adds the next game's stack.</p></div></div>
      <div class="ladder">${lad("props","Props ladder (no TD legs)","Two props per game.")}${lad("allpos","All-position ladder (stack + anytime TD)","Three legs per game: the prop stack plus the game's best eligible anytime TD.")}</div>
      <div class="scroll" style="margin-top:10px"><table class="tbl"><thead><tr><th>Game</th><th>Stack</th><th>Joint</th><th>Fair</th><th>Legs help each other?</th><th></th></tr></thead><tbody>
      ${(X.stacks||[]).map((s,i)=>`<tr><td>${gameLabel(G[s.game])}</td><td>${s.legs.map(l=>esc(legLabel(l))).join(" + ")}</td><td class="prob">${pct(s.p,0)}</td><td class="num">${am(s.p)}</td><td>${s.corr>=0.3?'<span class="pill good">strongly</span>':s.corr>=0.08?'<span class="pill">mildly</span>':'<span class="pill">independent</span>'}</td><td><button class="btn sm" data-add-stack="${i}">+ slip</button></td></tr>`).join("")}</tbody></table></div></section>`:"";
  const scr=renderScriptSGP();
  return xgSection+(scr?`<section class="panel"><div class="section-head"><div><h2>Script SGPs</h2><p class="sub">The game is read first (spread, totals, pass/run behaviour when leading or trailing, red-zone trend, pace, weather, run-lane and secondary edges); legs are then chosen for what that script favours, not one per position. Hybrids add the anytime-TD legs you asked for.</p></div></div></section>`+scr:"")+`<section class="panel"><div class="section-head"><div><h2>Slot SGPs (one leg per position)</h2>
    <p class="sub">One best leg per slot, every game: QB pass yards or passing TDs · RB rush yards · WR, TE and RB receptions or receiving yards.
    Legs are floor-band (70–88%) bet365 milestones with distinct players. If a slot has nothing that qualifies, it's skipped and the next-best leg fills in.
    Questionable and returning players are excluded. No TD legs.</p></div></div></section>${cards||'<section class="panel"><div class="empty">No SGPs built for this slate yet.</div></section>'}`;
}
function intelHTML(p){
  const i=p.intel, rb=p.pos==="RB"||p.pos==="QB";
  const cells=rb?[["Snap %",pct(i.snap??0,0)],["Carries/g",i.carries],["Inside-10/g",i.i10],["Inside-10 share",pct(i.i10_sh??0,0)],["RZ target share",pct(i.rz_tgt_sh??0,0)],["xTD/g",i.xtd],["TD/g recent",i.td],["Season",`${i.season_tds??0} TD / ${i.games??0} g`]]
    :[["Snap %",pct(i.snap??0,0)],["Targets/g",i.targets],["RZ targets/g",i.rz_tgt],["RZ target share",pct(i.rz_tgt_sh??0,0)],["End-zone share",pct(i.ez_sh??0,0)],["xTD/g",i.xtd],["TD/g recent",i.td],["Season",`${i.season_tds??0} TD / ${i.games??0} g`]];
  return `<dl class="intel">${cells.map(([a,b])=>`<div><dt>${a}</dt><dd>${b??"–"}</dd></div>`).join("")}</dl>
    <ul class="why">${p.why.map(w=>`<li>${w}</li>`).join("")}</ul><p class="risk"><b>Risk:</b> ${p.risk}</p>`;
}
function playerRow(p){
  const props=D.props[p.id]||{};
  const pg=Object.keys(props).map(mk=>{const m=props[mk];
    const opts=m.k.map((k,i)=>`<option value="${k}">${k}+ · ${pct(m.p[i],0)} · ${m.n?m.hits[i]+"/"+m.n:"–"}</option>`).join("");
    const di=m.p.reduce((bi,v,i)=>Math.abs(v-.78)<Math.abs(m.p[bi]-.78)?i:bi,0), def=m.k[di];
    return `<label>${MK[mk]} <select id="sel-${p.id}-${mk}" data-sel="${p.id}|${mk}">${opts.replace(`value="${def}"`,`value="${def}" selected`)}</select>${l5strip(m.l5&&m.l5[di])}
      <button class="btn sm" data-add-prop="${p.id}|${mk}" aria-label="Add ${esc(p.name)} ${MK[mk]}">+</button></label>`}).join("");
  const flags=[p.inj?`<span class="pill warn">${esc(p.inj)}</span>`:"",p.singles&&!p.inj?`<span class="pill warn">Singles only · missed ${p.missed4}/4</span>`:""].join("");
  return `<div class="prow" style="border-left:3px solid ${tcol(p.team)};padding-left:8px"><div class="line1"><span class="nm">${esc(p.name)}<small>${p.pos}</small></span>${flags}
      <span class="bar" aria-hidden="true"><i style="width:${Math.round(p.p*100)}%"></i></span><span class="prob">${pct(p.p,0)}</span>
      <button class="btn sm" data-add-atd="${p.id}">+ ATD</button></div>
    <details><summary>Intel & props</summary>${intelHTML(p)}${pg?`<div class="propgrid">${pg}</div>`:""}</details></div>`;
}
function renderBuild(){
  const g=G[state.game]||D.games[0];
  const col=t=>{const ps=D.players.filter(p=>p.game===g.id&&p.team===t).sort((a,b)=>b.p-a.p);
    return `<div class="teamcol"><h3>${t}<small>implied ${g.implied[t]??"–"} pts</small></h3>${ps.map(playerRow).join("")||'<div class="empty">No active players</div>'}</div>`};
  return `<section class="panel"><div class="section-head"><div><h2>Build a slip</h2>
      <p class="sub">Pick any game, add any player's ATD or prop rung. The slip prices it with live correlations.</p></div></div>
      <div class="rail">${D.games.map(x=>`<button class="gchip" data-game="${x.id}" aria-pressed="${x.id===g.id}"><b>${gameLabel(x)}</b><small>${esc(x.weekday.slice(0,3))} ${esc(x.kick)}${qbNote(x)?" · <span class=\"qbflag\">backup QB</span>":""}</small></button>`).join("")}</div>
      <div style="margin-top:14px"><h3 style="font-size:22px">${gameLabel(g)}</h3><div class="envline">${envPills(g)}</div></div>
      <div class="teams">${col(g.away)}${col(g.home)}</div></section>`;
}
function renderBoard(){
  const rows=D.players.slice(0,60).map((p,i)=>`<tr><td class="num">${i+1}</td><td><b>${esc(p.name)}</b></td><td>${p.pos}</td>
    <td>${p.team} ${p.home?"vs":"@"} ${p.opp}</td><td><span class="bar"><i style="width:${Math.round(p.p*100)}%"></i></span><span class="prob">${pct(p.p,0)}</span></td>
    <td class="num">${am(p.p)}</td><td class="num">${am(p.p-p.cushion)}</td>
    <td>${p.inj?`<span class="pill warn">${esc(p.inj)}</span>`:p.singles?`<span class="pill warn">Singles only</span>`:""}</td>
    <td><button class="btn sm" data-add-atd="${p.id}">+ ATD</button></td></tr>`).join("");
  return `<section class="panel"><div class="section-head"><div><h2>ATD board</h2>
    <p class="sub">Top 60 players this slate. "Play at" = the shortest price worth taking (fair + cushion: RB 3 pts, TE/QB 4, WR 6).</p></div></div>
    <div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>Player</th><th>Pos</th><th>Game</th><th>TD chance</th><th>Fair</th><th>Play at</th><th></th><th></th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function slipWarnings(legs){
  const w=[]; const ids={};
  legs.forEach(l=>{const p=P[l.id]; if(p.singles) w.push(`${p.name} is singles-only (${p.inj||"first game back"}). Keep him off parlays.`);});
  const atd=legs.filter(l=>l.mk==="atd");
  const byTeam={}; atd.forEach(l=>{(byTeam[P[l.id].team]??=[]).push(P[l.id].name)});
  Object.entries(byTeam).forEach(([t,n])=>{if(n.length>1)w.push(`${n.join(" + ")}: teammates split ${t}'s touchdowns (negative correlation).`)});
  legs.forEach(l=>{if(l.mk!=="atd"){const k=l.id+l.mk;ids[k]=(ids[k]||0)+1}});
  Object.entries(ids).forEach(([k,n])=>{if(n>1)w.push("Two rungs of the same market for one player: the lower rung is almost redundant.")});
  return [...new Set(w)];
}
function openSlip(v){const a=$("#slip");a.classList.toggle("open",v);$("#scrim").hidden=!v;$("#fab").setAttribute("aria-expanded",v);$("#fab").hidden=v}
function updateFab(pj){const n=state.slip.legs.length;$("#fabcnt").textContent=n;$("#fabp").textContent=n?`${pct(pj)} · ${am(pj)}`:"";
  const f=$("#fab");f.classList.remove("bump");void f.offsetWidth;f.classList.add("bump")}
const CLOSE=`<button class="closeslip" data-close-slip aria-label="Close bet slip">×</button>`;
function renderSlip(){
  const s=state.slip, legs=s.legs;
  updateFab(legs.length?jointP(legs):0);
  s.legMargin??="6";
  if(!legs.length){ $("#slip").innerHTML=`<div class="sliphead"><h2>Bet slip</h2>${CLOSE}</div>
    <div class="empty">Load an algorithm parlay or add players from <a href="#build" data-close-slip>Build a slip</a>.</div>${savedHTML()}`; return }
  // keep focus/caret while re-rendering on every keystroke
  const ae=document.activeElement, focusId=ae&&ae.id, caret=ae&&ae.selectionStart;
  const gIdx=Object.fromEntries(D.games.map((g,i)=>[g.id,i]));
  const pj=jointP(legs), pind=legs.reduce((a,l)=>a*(legP(l)??0),1);
  const stake=parseFloat(s.stake)||0, bank=parseFloat(s.bankroll)||0;
  const coM=(parseFloat(s.margin)||0)/100, legM=(parseFloat(s.legMargin)||0)/100;
  // price: your parlay price > product of your leg odds > estimate (fair x book margin per leg)
  const decs=legs.map(l=>decOf(l.odds));
  const estLeg=l=>{const p=legP(l)??.5;return 1/Math.min(.99,p*(1+legM))};
  s.sgpOdds??={};
  const groups={}; legs.forEach((l,i)=>{(groups[P[l.id].game]??=[]).push(i)});
  const gids=Object.keys(groups).sort((a,b)=>gIdx[a]-gIdx[b]);
  const gInfo=gids.map(g=>{const ix=groups[g], sg=ix.length>1?decOf(s.sgpOdds[g]):null, allL=ix.every(i=>decs[i]);
    const dec=sg||ix.reduce((a,i)=>a*(decs[i]||estLeg(legs[i])),1);
    return {g,ix,dec,src:sg?"sgp":allL?"legs":"est",p:ix.length>1?jointP(ix.map(i=>legs[i])):legP(legs[ix[0]])}});
  let bookDec, src;
  if(decOf(s.book)){bookDec=decOf(s.book);src="your bet365 slip price"}
  else{bookDec=gInfo.reduce((a,x)=>a*x.dec,1);const k=new Set(gInfo.map(x=>x.src));
    src=k.size===1&&k.has("est")?`estimated: fair odds less ${(legM*100).toFixed(0)}% book margin per leg`
      :k.has("est")?"your prices + estimates for the rest":gids.length>1?`${gids.length} games multiplied`:"your bet365 prices"}
  const estimated=!decOf(s.book)&&gInfo.some(x=>x.src==="est");
  const imp=1/bookDec, ev=pj*bookDec-1, kelly=Math.max(0,(pj*bookDec-1)/(bookDec-1));
  const ret=stake*bookDec, profit=ret-stake; state._px={dec:bookDec,est:estimated,stake};

  // cash-out ladder in kickoff order
  const byKick=(a,b)=>gIdx[P[a.l.id].game]-gIdx[P[b.l.id].game];
  const all=legs.map((l,i)=>({l,i}));
  const order=[...all.filter(x=>x.l.status==="w").sort(byKick),...all.filter(x=>x.l.status!=="w").sort(byKick)];
  const lost=legs.some(l=>l.status==="l");
  const wonSet=new Set(legs.map((l,i)=>l.status==="w"?i:-1));
  const rows=[]; let landed=[];
  for(let step=0;step<=order.length;step++){
    const remaining=order.slice(step).map(x=>x.l);
    const pr=remaining.length?jointP(remaining):1;
    const fair=ret*pr;
    const label=step===0?"Before kickoff":step===order.length?"All legs win (payout)":`After ${P[order[step-1].l.id].name} (leg ${step}) lands`;
    landed=order.slice(0,step).map(x=>x.i);
    const isNow=!lost&&landed.length===[...wonSet].filter(i=>i>=0).length&&landed.every(i=>wonSet.has(i));
    rows.push({label,pr,fair,offer:step===order.length?ret:fair*(1-coM),now:isNow,final:step===order.length});
  }
  const ladder=`<div class="scroll"><table class="tbl co"><thead><tr><th>When</th><th>Chance left</th><th>Fair value</th><th>Est. cash-out</th></tr></thead><tbody>
    ${rows.map(r=>`<tr class="${r.now?"now":""}"><td>${esc(r.label)}${r.now&&!r.final?' <span class="pill gold">now</span>':""}</td>
      <td class="num">${r.final?"—":pct(r.pr)}</td><td class="num">${money(r.fair)}</td><td class="num"><b>${money(r.offer)}</b></td></tr>`).join("")}
    </tbody></table></div>`;

  const verdict=ev>0
    ?`<div class="verdict good">+EV at ${amFromDec(bookDec)}: the model makes this ${pct(pj)}, the price implies ${pct(imp)}.${estimated?" (Estimated price: enter bet365's real odds to confirm.)":""}</div>`
    :`<div class="verdict ${estimated?"neutral":"bad"}">${estimated?"At a typical bet365 margin this slip is −EV.":"−EV at this price."} You need ${am(pj)} or longer to have an edge.</div>`;
  const warns=slipWarnings(legs);
  $("#slip").innerHTML=`<div class="sliphead"><h2>Bet slip · ${legs.length} leg${legs.length>1?"s":""}${gids.length>1?` · ${gids.length} games`:""}</h2><div class="row"><a class="btn sm" href="#audit" data-close-slip>Audit slip</a><button class="btn sm ghost" data-clear>Clear</button>${CLOSE}</div></div>
    <div>${gInfo.map(gi=>{const g=G[gi.g];return `<div class="sgpgroup">
      <div class="ghead"><div><b>${gameLabel(g)}</b> <span class="lsub">${gi.ix.length>1?gi.ix.length+"-leg SGP":"single leg"} · ${esc(g.kick)}</span></div>
        <div class="num">${gi.p==null?"–":pct(gi.p)} <span class="lsub">fair ${gi.p==null?"–":am(gi.p)}</span></div></div>
      ${gi.ix.length>1?`<div class="gprice"><label for="sgp-${gi.g}">bet365 SGP price</label><input id="sgp-${gi.g}" data-sgp="${gi.g}" value="${esc(s.sgpOdds[gi.g]??"")}" placeholder="est ${amFromDec(gi.ix.reduce((a,i)=>a*(decs[i]||estLeg(legs[i])),1))}"></div>`:""}
      ${gi.ix.map(i=>{const l=legs[i],p=P[l.id],lp=legP(l),d=decOf(l.odds);return `<div class="leg"><div><div class="lname">${esc(legLabel(l))}</div>
      <div class="lsub">${p.team} ${p.home?"vs":"@"} ${p.opp}</div></div><div class="lp">${lp==null?"–":pct(lp,0)}<div class="lsub">fair ${lp==null?"–":am(lp)}</div></div>
      <div class="ctl"><input id="odds-${i}" data-odds="${i}" value="${esc(l.odds)}" placeholder="est ${amFromDec(estLeg(l))}" aria-label="bet365 odds for ${esc(legLabel(l))}">
      ${d&&lp!=null?`<span class="pill ${lp>1/d?"good":"bad"}">${lp>1/d?"+":""}${((lp-1/d)*100).toFixed(0)} pts</span>`:""}
      <span class="seg" role="group" aria-label="Leg result">${[["o","Open"],["w","Won"],["l","Lost"]].map(([k,t])=>`<button class="${k}" data-status="${i}|${k}" aria-pressed="${l.status===k}">${t}</button>`).join("")}</span>
      <button class="x" data-rm="${i}" aria-label="Remove leg">×</button></div></div>`}).join("")}</div>`}).join("")}</div>
    ${warns.length?`<div class="warns">${warns.map(w=>`<div>${esc(w)}</div>`).join("")}</div>`:""}

    <div class="big"><div><div class="lbl">Model chance to hit</div><div class="sub">If independent ${pct(pind)} · correlation ×${(pj/pind).toFixed(3)}</div></div>
      <div class="val">${pct(pj)}<small>fair ${am(pj)}</small></div></div>

    <div class="pricebox">
      <div class="fields">
        <label for="f-stake">Stake ($)<input id="f-stake" data-field="stake" value="${esc(s.stake)}" inputmode="decimal"></label>
        <label for="f-book">bet365 total slip price<input id="f-book" data-field="book" value="${esc(s.book)}" placeholder="${amFromDec(bookDec)}"></label>
      </div>
      <div class="payout">
        <div><div class="lbl">Price</div><div class="pv">${amFromDec(bookDec)}</div><div class="sub">${esc(src)}</div></div>
        <div><div class="lbl">To win</div><div class="pv">${money(profit)}</div></div>
        <div><div class="lbl">Total return</div><div class="pv gold">${money(ret)}</div></div>
      </div>
    </div>
    ${verdict}
    <dl class="kv"><dt>Price implies</dt><dd>${pct(imp)}</dd>
      <dt>Edge (model − price)</dt><dd style="color:var(${pj>imp?"--good":"--bad"})">${(pj-imp>=0?"+":"")+((pj-imp)*100).toFixed(1)} pts</dd>
      <dt>Expected value of this bet</dt><dd style="color:var(${ev>0?"--good":"--bad"})">${(ev>=0?"+":"")+money(stake*ev)}</dd>
      <dt>Quarter-Kelly stake (bankroll ${money(bank)})</dt><dd>${money(bank*kelly/4)}</dd></dl>

    <div><h3>Cash-out ladder</h3>
      <p class="sub">${lost?"A leg has lost, so the slip is dead.":"What this slip should be worth as legs land, in kickoff order. bet365's offer is usually below fair value; take a cash-out only if it beats the fair value on the row you're at."}</p>
      ${ladder}</div>

    <details class="settings"><summary>Assumptions</summary><div class="fields" style="margin-top:8px">
      <label for="f-legm">Book margin per leg %<input id="f-legm" data-field="legMargin" value="${esc(s.legMargin)}" inputmode="decimal"></label>
      <label for="f-margin">Cash-out margin %<input id="f-margin" data-field="margin" value="${esc(s.margin)}" inputmode="decimal"></label>
      <label for="f-bank">Bankroll ($)<input id="f-bank" data-field="bankroll" value="${esc(s.bankroll)}" inputmode="decimal"></label></div>
      <p class="sub">Price order: your total slip price, else each game's SGP price (or leg odds) multiplied across games, else estimates. The estimated price applies the per-leg margin to the model's fair odds until you type bet365's real odds. Same-game parlays get repriced by bet365, so type the SGP price shown on your slip.</p></details>
    <div class="row"><button class="btn primary" data-track>Track this bet</button><button class="btn" data-save>Save slip</button><button class="btn" data-copy>Copy slip</button></div>${savedHTML()}`;
  heatify(document.getElementById("slip"));
  if(focusId){const el=document.getElementById(focusId);if(el){el.focus();try{el.setSelectionRange(caret,caret)}catch(e){}}}
}
function savedHTML(){ if(!state.saved.length) return "";
  return `<div><h3 style="margin-top:6px">Saved slips</h3>${state.saved.map((x,i)=>`<div class="leg"><div><div class="lname">${esc(x.name)}</div>
    <div class="lsub">${x.legs.length} legs · model ${pct(x.p)} · ${esc(x.when)}</div></div><div class="row"><button class="btn sm" data-open="${i}">Open</button><button class="x" data-del="${i}" aria-label="Delete saved slip">×</button></div></div>`).join("")}</div>` }

let lastTab=null;
function render(){
  const y=window.scrollY, sameTab=lastTab===state.tab; lastTab=state.tab;
  document.querySelectorAll("nav.tabs a").forEach(a=>a.setAttribute("aria-current",a.dataset.tab===state.tab?"page":"false"));
  $("#main").innerHTML=state.tab==="build"?renderBuild():state.tab==="board"?renderBoard():state.tab==="sgp"?renderSGP():state.tab==="mysgp"?renderMySGP():state.tab==="audit"?renderAudit():state.tab==="model"?renderModel():state.tab==="home"?renderHome():renderPicks();
  renderSlip(); heatify();
  if(sameTab) requestAnimationFrame(()=>window.scrollTo(0,y));   // never jump the page on an add/remove
}
function route(){const h=location.hash.slice(1);const extra=(window.GE_EXTRA_TABS||[]).includes(h);$("#main").hidden=extra;if(extra){state.tab=h;document.querySelectorAll("nav.tabs a").forEach(a=>a.setAttribute("aria-current",a.dataset.tab===h?"page":"false"));renderSlip();return}state.tab=["home","picks","sgp","mysgp","build","board","audit","model"].includes(h)?h:"home";render()}

document.addEventListener("click",e=>{
  const t=e.target.closest("button");if(!t)return;const d=t.dataset;
  if(d.loadCombo!=null){const t=D.algo.atd_combos[+d.loadCombo];loadLegs(t.legs.map(id=>({id,mk:"atd",k:null})),`${gameLabel(G[t.game])} ${t.n}-leg ATD`)}
  else if(d.loadAtd){const [st,n]=d.loadAtd.split("|");const sty=(D.algo.atd_styles||{})[st];const tk=(sty?sty.tickets:D.algo.atd).find(x=>x.n==n);loadLegs(tk.legs.map(id=>({id,mk:"atd",k:null})),`${sty?sty.label+" ":""}${tk.n}-leg ATD`)}
  else if(d.atdStyle){state.atdStyle=d.atdStyle;render()}
  else if(d.loadXg){const [k,i]=d.loadXg.split("|");const t=D.crossgame[k][+i];loadLegs(t.legs.map(l=>({id:l.id,mk:l.mk,k:l.k})),`Cross-game ${t.n}-leg`)}
  else if(d.addStack!=null){const s=D.crossgame.stacks[+d.addStack];appendLegs(s.legs.map(l=>({id:l.id,mk:l.mk,k:l.k})),`${gameLabel(G[s.game])} stack`)}
  else if(d.loadProp){const tk=D.algo.props.find(x=>x.ticket===d.loadProp);loadLegs(tk.legs.map(l=>({id:l.id,mk:l.mk,k:l.k})),`${tk.legs.length}-leg ticket`)}
  else if(d.pgame){state.propsGame=d.pgame;render()}
  else if(d.scriptLoad){const [gi,k,n]=d.scriptLoad.split("|");const t=D.script_sgp[+gi];const legs=k==="ladder"?t.ladder.find(x=>x.n==n).legs:t[k].legs;loadLegs(legs.map(l=>({id:l.id,mk:l.mk,k:l.k})),`${gameLabel(G[t.game])} ${k==="ladder"?n+"-leg":"hybrid"} SGP`)}
  else if(d.addSgp!=null){const t=D.algo.sgp[+d.addSgp];appendLegs(t.legs.map(l=>({id:l.id,mk:l.mk,k:l.k})),`${gameLabel(G[t.game])} SGP`)}
  else if(d.addLeg){const [id,mk,k]=d.addLeg.split("|");addLeg({id,mk,k:parseInt(k)})}
  else if(d.game){state.game=d.game;render()}
  else if(d.addAtd){addLeg({id:d.addAtd,mk:"atd",k:null})}
  else if(d.addProp){const [id,mk]=d.addProp.split("|");const k=parseInt(document.getElementById(`sel-${id}-${mk}`).value);addLeg({id,mk,k})}
  else if(d.rm!=null&&d.rm!==undefined&&t.classList.contains("x")&&!d.del){state.slip.legs.splice(+d.rm,1);persist();renderSlip()}
  else if(d.status){const [i,k]=d.status.split("|");state.slip.legs[+i].status=k;persist();renderSlip()}
  else if("clear" in d){state.slip.legs=[];state.slip.book="";persist();renderSlip()}
  else if("save" in d){const legs=state.slip.legs;state.saved.unshift({name:legs.slice(0,3).map(l=>P[l.id].name.split(" ").slice(-1)[0]).join(" · ")+(legs.length>3?` +${legs.length-3}`:""),
     legs:JSON.parse(JSON.stringify(legs)),p:jointP(legs),when:new Date().toLocaleString([], {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})});persist();renderSlip();toast("Slip saved")}
  else if(d.open!=null&&!d.del){const x=state.saved[+d.open];state.slip.legs=JSON.parse(JSON.stringify(x.legs));persist();renderSlip();toast("Slip opened")}
  else if(d.del!=null){state.saved.splice(+d.del,1);persist();renderSlip()}
  else if("copy" in d){const pj=jointP(state.slip.legs);const txt=state.slip.legs.map((l,i)=>`${i+1}. ${legLabel(l)} (${pct(legP(l)??0,0)})`).join("\n")+`\nModel: ${pct(pj)} · fair ${am(pj)}`;
     navigator.clipboard?.writeText(txt).then(()=>toast("Slip copied"),()=>toast("Copy blocked here: select the slip text instead"))}
});
let typing;
document.addEventListener("input",e=>{const t=e.target;
  if(t.dataset.odds!=null) state.slip.legs[+t.dataset.odds].odds=t.value.trim();
  else if(t.dataset.sgp){ state.slip.sgpOdds??={}; state.slip.sgpOdds[t.dataset.sgp]=t.value.trim(); }
  else if(t.dataset.field) state.slip[t.dataset.field]=t.value.trim();
  else return;
  persist(); clearTimeout(typing); typing=setTimeout(()=>{renderSlip(); if(state.tab==="audit"&&t.dataset.odds!=null) $("#main").innerHTML=renderAudit()},250)});

/* ================= Build your own SGP ================= */
state.my = {game: store.get("mygame", null)};
function persistMy(){store.set("mygame",state.my.game)}
function gameLegs(g){ return state.slip.legs.filter(l=>P[l.id].game===g) }
function jp(legs,N){ return legs.length?jointPN(legs,N):null }
const VOL = {carries:["carries/g",0],rush_yds:["rush yds/g",0],rec:["catches/g",0],rec_yds:["rec yds/g",0],pass_att:["attempts/g",0],pass_yds:["pass yds/g",0],pass_td:["TD passes/g",0]};
function legIntel(l){
  const p=P[l.id], pr=p.parts||{}, out=[];
  if(l.mk==="atd"){ ["outlook","role","form","matchup","scheme","game"].forEach(k=>pr[k]&&out.push(pr[k])); }
  else{
    pr.outlook&&out.push(pr.outlook);
    const v=p.vol?.[l.mk], m=D.props[l.id]?.[l.mk], i=m?m.k.indexOf(l.k):-1;
    if(v) out.push(`<b>Volume:</b> ${v[0]??"–"} ${VOL[l.mk][0]} recently, ${v[1]??"–"} season average${l.mk==="rec"&&p.vol?.tgt?` (on ${p.vol.tgt[0]} targets/g)`:""}.`);
    if(i>=0) out.push(`<b>This line:</b> ${l.k}+ ${MK[l.mk]} cleared in ${m.hits[i]} of ${m.n} games this season; model ${pct(m.p[i],0)}.`);
    ["matchup","scheme","game"].forEach(k=>pr[k]&&out.push(pr[k]));
  }
  out.push(`<b>Risk:</b> ${l.mk==="atd"?p.risk:(p.riskm?.[l.mk]??p.risk)}`);
  return out;
}
function bestRung(id,mk,lo=.70,hi=.88,t=.78){const m=D.props[id]?.[mk];if(!m)return null;let b=null;
  m.k.forEach((k,i)=>{const p=m.p[i];if(p>=lo&&p<=hi&&(!b||Math.abs(p-t)<Math.abs(b.p-t)))b={id,mk,k,p}});return b}
function candidates(g){
  const out=[];
  D.players.filter(p=>p.game===g&&!p.singles).forEach(p=>{
    Object.keys(D.props[p.id]||{}).forEach(mk=>{const b=bestRung(p.id,mk);if(b)out.push(b)});
    if(p.p>=.30) out.push({id:p.id,mk:"atd",k:null,p:p.p});
  });
  return out;
}
const sameLeg=(a,b)=>a.id===b.id&&a.mk===b.mk&&(a.k??null)===(b.k??null);
function suggestions(legs){
  const N=16000, base=jp(legs,N), g=P[legs[0].id].game, cands=candidates(g);
  const fmt=(x)=>`${pct(x)} (${x>=base?"+":""}${((x-base)*100).toFixed(1)} pts)`;
  // remove
  const rem=legs.map((l,i)=>{const rest=legs.filter((_,j)=>j!==i);const pr=jp(rest,N);
      const rsum=legs.reduce((a,o,j)=>a+(j===i?0:rho(l,o)),0);
      return {i,l,pr,why:rsum<-0.04?"fights other legs in your SGP (negative correlation)":`weakest link at ${pct(legP(l),0)}`}})
    .sort((a,b)=>b.pr-a.pr).slice(0,2).filter(x=>legs.length>1);
  // swaps
  const swaps=[];
  legs.forEach((l,i)=>{const opts=[];
    if(l.mk!=="atd"){const m=D.props[l.id]?.[l.mk];if(m){const j=m.k.indexOf(l.k);if(j>0)opts.push({id:l.id,mk:l.mk,k:m.k[j-1],p:m.p[j-1],tag:"safer line"})}}
    const pos=P[l.id].pos;
    cands.filter(c=>c.id!==l.id&&P[c.id].pos===pos&&(c.mk===l.mk||(l.mk!=="atd"&&c.mk!=="atd"&&["rec","rec_yds"].includes(c.mk)&&["rec","rec_yds"].includes(l.mk))))
      .filter(c=>!legs.some(o=>sameLeg(o,c))).forEach(c=>opts.push({...c,tag:"better "+pos}));
    opts.forEach(o=>{const nl=legs.map((x,j)=>j===i?o:x);const pr=jp(nl,N);if(pr>base+0.004)swaps.push({i,l,o,pr})});
  });
  swaps.sort((a,b)=>b.pr-a.pr);
  const seen=new Set(), swapTop=swaps.filter(s=>{if(seen.has(s.i))return false;seen.add(s.i);return true}).slice(0,4);
  // adds
  const adds=cands.filter(c=>!legs.some(o=>o.id===c.id&&o.mk===c.mk)).map(c=>{const pr=jp([...legs,c],N);
      const rs=legs.reduce((a,o)=>a+rho(c,o),0);return {c,pr,boost:rs}}).sort((a,b)=>b.pr-a.pr).slice(0,6);
  return {base,rem,swaps:swapTop,adds,fmt};
}
function grade(score){return score>=82?"A":score>=76?"B":score>=70?"C":score>=62?"D":"E"}
function renderMySGP(){
  const my=state.my; const g=G[my.game||state.game||D.games[0].id]; my.game=g.id;
  const legs=gameLegs(g.id);
  let card;
  if(!legs.length){
    card=`<section class="panel"><div class="section-head"><div><h2>Your SGP · ${gameLabel(g)}</h2>
      <p class="sub">Tap + on any line below: it goes straight into your bet slip and is scored here live, with swap, remove and add suggestions and intel for every player you add.</p></div></div>
      <div class="empty">No legs from this game in your slip yet. Tap + on any line below.</div></section>`;
  } else {
    const pj=jp(legs,60000), pind=legs.reduce((a,l)=>a*(legP(l)??0),1), score=100*Math.pow(pj,1/legs.length), S=suggestions(legs);
    const warns=slipWarnings(legs);
    card=`<section class="panel"><div class="section-head"><div><h2>Your SGP · ${gameLabel(g)}</h2>
        <p class="sub">${legs.length} leg${legs.length>1?"s":""} from this game in your bet slip · priced with measured correlations (props, ATDs, teammates, QB↔receivers)</p></div>
        <div class="row"><button class="btn primary" data-open-slip>Open bet slip</button><button class="btn ghost" data-my-clear>Remove this game's legs</button></div></div>
      <div class="scoregrid">
        <div class="big"><div><div class="lbl">Hit chance</div><div class="sub">If independent ${pct(pind)} · correlation ×${(pj/pind).toFixed(3)}</div></div><div class="val">${pct(pj)}<small>fair ${am(pj)}</small></div></div>
        <div class="big"><div><div class="lbl">SGP score</div><div class="sub">Average leg strength after correlation</div></div><div class="val">${score.toFixed(0)}<small class="grade g${grade(score)}">${grade(score)}</small></div></div>
      </div>
      ${warns.length?`<div class="warns" style="margin-top:10px">${warns.map(w=>`<div>${esc(w)}</div>`).join("")}</div>`:""}
      <div class="mylegs">${legs.map((l,i)=>{const p=P[l.id],lp=legP(l);return `<div class="myleg">
        <div class="line1"><span class="nm">${esc(legLabel(l))}<small>${p.pos} · ${p.team}</small></span><span class="prob">${lp==null?"–":pct(lp,0)}</span>
        <button class="x" data-my-rm="${i}" aria-label="Remove leg">×</button></div>
        <details open><summary>Intel</summary><ul class="why">${legIntel(l).map(w=>`<li>${w}</li>`).join("")}</ul></details></div>`}).join("")}</div>
      <div class="suggest">
        <div><h3>Swap suggestions</h3>${S.swaps.length?S.swaps.map(s=>`<div class="sug"><span>Swap <b>${esc(legLabel(s.l))}</b> → <b>${esc(legLabel(s.o))}</b> <span class="pill">${s.o.tag} · ${pct(s.o.p,0)}</span></span>
          <span class="sugr">${S.fmt(s.pr)} <button class="btn sm" data-my-swap="${s.i}|${s.o.id}|${s.o.mk}|${s.o.k??""}">Swap</button></span></div>`).join(""):'<p class="sub">No swap raises the hit chance meaningfully.</p>'}</div>
        <div><h3>Remove suggestions</h3>${S.rem.map(r=>`<div class="sug"><span>Remove <b>${esc(legLabel(r.l))}</b>: ${r.why}</span>
          <span class="sugr">${S.fmt(r.pr)} <button class="btn sm" data-my-rm="${r.i}">Remove</button></span></div>`).join("")||'<p class="sub">Add a second leg first.</p>'}</div>
        <div><h3>Add suggestions</h3>${S.adds.map(a=>`<div class="sug"><span>Add <b>${esc(legLabel(a.c))}</b> <span class="pill">${pct(a.c.p,0)}</span>${a.boost>0.08?' <span class="pill good">rises with your legs</span>':a.boost<-0.04?' <span class="pill bad">works against your legs</span>':""}</span>
          <span class="sugr">${S.fmt(a.pr)} <button class="btn sm" data-my-add="${a.c.id}|${a.c.mk}|${a.c.k??""}">Add</button></span></div>`).join("")}</div>
      </div></section>`;
  }
  const col=t=>{const ps=D.players.filter(p=>p.game===g.id&&p.team===t).sort((a,b)=>b.p-a.p);
    return `<div class="teamcol"><h3>${t}<small>implied ${g.implied[t]??"–"} pts</small></h3>${ps.map(p=>{
      const props=D.props[p.id]||{};
      const pg=Object.keys(props).map(mk=>{const m=props[mk];const b=bestRung(p.id,mk,0,1,.78); const bi=b?m.k.indexOf(b.k):-1;
        const opts=m.k.map((k,i)=>`<option value="${k}"${b&&b.k===k?" selected":""}>${k}+ · ${pct(m.p[i],0)} · ${m.n?m.hits[i]+"/"+m.n:"–"}</option>`).join("");
        return `<label>${MK[mk]} <select id="mysel-${p.id}-${mk}">${opts}</select>${l5strip(m.l5&&bi>=0&&m.l5[bi])}<button class="btn sm" data-my-prop="${p.id}|${mk}" aria-label="Add ${esc(p.name)} ${MK[mk]}">+</button></label>`}).join("");
      return `<div class="prow" style="border-left:3px solid ${tcol(p.team)};padding-left:8px"><div class="line1"><span class="nm">${esc(p.name)}<small>${p.pos}</small></span>
        ${p.inj?`<span class="pill warn">${esc(p.inj)}</span>`:p.singles?`<span class="pill warn">Singles only</span>`:""}
        <span class="prob">ATD ${pct(p.p,0)}</span><button class="btn sm" data-my-atd="${p.id}">+ ATD</button></div>
        ${pg?`<div class="propgrid">${pg}</div>`:""}</div>`}).join("")}</div>`};
  return `<section class="panel"><div class="section-head"><div><h2>Build your own SGP</h2>
      <p class="sub">Pick a game and tap + on props or anytime TDs: each one goes straight into your bet slip (bottom right) and is scored here. Add legs from several games and the slip combines them into one ticket.</p></div></div>
      <div class="rail">${D.games.map(x=>`<button class="gchip" data-my-game="${x.id}" aria-pressed="${x.id===g.id}"><b>${gameLabel(x)}</b><small>${esc(x.weekday.slice(0,3))} ${esc(x.kick)}${qbNote(x)?" · <span class=\"qbflag\">backup QB</span>":""}</small></button>`).join("")}</div>
      <div class="envline">${envPills(g)}</div></section>
    ${card}
    <section class="panel"><div class="section-head"><div><h2>Players · ${gameLabel(g)}</h2>
      <p class="sub">Each menu opens on the line closest to 78%. Lines show model chance and this season's hits.</p></div></div>
      <div class="teams">${col(g.away)}${col(g.home)}</div></section>`;
}
function myAdd(l){ state.my.game=P[l.id].game; persistMy(); addLeg({id:l.id,mk:l.mk,k:l.k??null}); render(); }
function slipIndex(l){ return state.slip.legs.findIndex(x=>sameLeg(x,l)) }
document.addEventListener("click",e=>{const t=e.target.closest("button");if(!t)return;const d=t.dataset;
  if(d.myGame){ state.my.game=d.myGame;persistMy();render() }
  else if(d.myAtd){ myAdd({id:d.myAtd,mk:"atd",k:null}) }
  else if(d.myProp){ const [id,mk]=d.myProp.split("|"); myAdd({id,mk,k:parseInt(document.getElementById(`mysel-${id}-${mk}`).value)}) }
  else if(d.myAdd){ const [id,mk,k]=d.myAdd.split("|"); myAdd({id,mk,k:k===""?null:parseInt(k)}) }
  else if(d.myRm!=null){ const legs=gameLegs(state.my.game); const i=slipIndex(legs[+d.myRm]); if(i>=0){state.slip.legs.splice(i,1); persist(); render(); toast("Removed from slip")} }
  else if(d.mySwap){ const [i,id,mk,k]=d.mySwap.split("|"); const legs=gameLegs(state.my.game); const si=slipIndex(legs[+i]); if(si>=0){const o=state.slip.legs[si]; state.slip.legs[si]={id,mk,k:k===""?null:parseInt(k),odds:"",status:o.status||"o"}; persist(); render(); toast("Swapped in your slip")} }
  else if("myClear" in d){ state.slip.legs=state.slip.legs.filter(l=>P[l.id].game!==state.my.game); persist(); render() }
  else if("openSlip" in d){ openSlip(true) }
});


/* ================= Slip audit: start / swap / remove ================= */
function strengthOf(l,lp){ if(lp==null) return ["Unknown","neutral"];
  if(l.mk==="atd") return lp>=.55?["Strong TD leg","good"]:lp>=.40?["Solid TD leg","good"]:lp>=.28?["Thin TD leg","warn"]:["Long-shot TD leg","bad"];
  return lp>=.78?["Strong","good"]:lp>=.65?["Solid","good"]:lp>=.55?["Thin","warn"]:["Risky","bad"] }
function auditSlip(legs){
  const N=20000, base=jointPN(legs,N);
  const res=legs.map((l,i)=>{
    const p=P[l.id], lp=legP(l), g=p.game;
    const rest=legs.filter((_,j)=>j!==i), pRest=rest.length?jointPN(rest,N):1;
    const rs=legs.map((o,j)=>({o,j})).filter(x=>x.j!==i&&P[x.o.id].game===g).map(x=>({o:x.o,r:rho(l,x.o)}));
    const neg=rs.filter(x=>x.r<=-0.04&&x.o.id!==l.id), pos=rs.filter(x=>x.r>=0.08);
    const dup=legs.some((o,j)=>j!==i&&o.id===l.id&&o.mk===l.mk&&(o.k??0)<(l.k??0))?false:legs.some((o,j)=>j!==i&&o.id===l.id&&o.mk===l.mk);
    // swap pool: same player (other lines / markets) + same-position players in this game
    const pool=[];
    if(l.mk==="atd"){
      candidates(g).filter(c=>c.mk==="atd"&&c.id!==l.id&&!legs.some(o=>o.id===c.id&&o.mk==="atd"))
        .forEach(c=>pool.push({...c,tag:`${P[c.id].team} ${P[c.id].pos} anytime TD`}));
    } else {
      if(!p.singles){
        const m=D.props[l.id]?.[l.mk];m&&m.k.forEach((k,j)=>{if(k!==l.k&&m.p[j]>=.55&&m.p[j]<=.93)pool.push({id:l.id,mk:l.mk,k,p:m.p[j],tag:k<l.k?"safer line":"bigger line"})});
        Object.keys(D.props[l.id]||{}).filter(mk=>mk!==l.mk&&!legs.some(o=>o.id===l.id&&o.mk===mk)).forEach(mk=>{const b=bestRung(l.id,mk);b&&pool.push({...b,tag:"same player, other market"})});
      }
      candidates(g).filter(c=>c.mk!=="atd"&&c.id!==l.id&&P[c.id].pos===p.pos&&!legs.some(o=>o.id===c.id&&o.mk===c.mk))
        .forEach(c=>pool.push({...c,tag:`other ${p.pos} in this game`}));
    }
    const scored=pool.map(o=>({o,pr:jointPN(legs.map((x,j)=>j===i?o:x),12000)})).sort((a,b)=>b.pr-a.pr);
    const options=[], seenP=new Set();
    for(const x of scored){const key=x.o.id+(x.o.id===l.id?x.o.mk+x.o.k:"");if(seenP.has(key))continue;seenP.add(key);options.push(x);if(options.length===3)break}
    // the verdict only recommends a swap that is clearly better (not just a safer line on an in-band leg)
    const best0=options.find(x=>(x.o.p>=(lp??0)+0.05&&x.o.id!==l.id)||(lp!=null&&lp<.70&&x.o.tag==="safer line"&&x.o.p>=.70))||null;
    const d=decOf(l.odds), edge=d&&lp!=null?lp-1/d:null;
    const m=D.props[l.id]?.[l.mk], mi=m?m.k.indexOf(l.k):-1;
    let verdict="start"; const why=[];
    let best=best0;
    const bestOther=options.find(x=>x.o.id!==l.id&&x.pr>base*1.02)||null;
    const swapGood=best&&best.pr>=base*1.08, swapAny=best&&best.pr>base*1.02;
    // of two conflicting legs, only the weaker one is flagged
    const negWeaker=neg.filter(x=>{const op=legP(x.o)??0;const oi=legs.indexOf(x.o);return op>(lp??0)||(op===(lp??0)&&oi<i)});
    const negStronger=neg.filter(x=>!negWeaker.includes(x));
    if(p.singles){best=bestOther;verdict=best?"swap":"remove";why.push(`${p.inj?p.inj:"First game back from a 2+ game absence"}: singles only under your rules.`)}
    else if(dup){verdict="remove";why.push("Same player and market twice: the lower line adds almost nothing.")}
    else if(negWeaker.length){best=bestOther&&!negWeaker.some(x=>P[x.o.id].team===P[bestOther.o.id].team&&bestOther.o.mk==="atd"&&x.o.mk==="atd")?bestOther:null;verdict=best?"swap":"remove";why.push(`Works against ${negWeaker.map(x=>`${legLabel(x.o)} (ρ ${x.r.toFixed(2)})`).join(", ")}: teammates splitting the same volume or TDs, and this is the weaker of the two.`)}
    else if(edge!=null&&edge<-0.03){verdict=swapAny?"swap":"remove";why.push(`bet365's price implies ${pct(1/d,0)} but the model has ${pct(lp,0)}: you're paying too much for this leg.`)}
    else if(swapGood){verdict="swap";why.push(`A better leg is available: the swap lifts the slip by ${((best.pr/base-1)*100).toFixed(0)}%.`)}
    else if(l.mk!=="atd"&&lp!=null&&lp<.55){verdict=swapAny?"swap":"start";why.push(`Below 55%: this leg is doing a lot of the slip's losing.`)}
    if(verdict==="start"){
      if(mi>=0&&m.n) why.push(`Cleared ${l.k}+ ${MK[l.mk]} in ${m.hits[mi]} of ${m.n} games this season.`);
      if(l.mk==="atd"){const it=p.intel; why.push(`${pct(it.i10_sh??0,0)} of his team's inside-10 carries, ${pct(it.rz_tgt_sh??0,0)} of red-zone targets; ${it.season_tds??0} TDs in ${it.games??0} games.`)}
      if(negStronger.length) why.push(`Conflicts with ${negStronger.map(x=>legLabel(x.o)).join(", ")}, but this is the stronger leg: keep it and drop the other.`);
      if(pos.length) why.push(`Moves with ${pos.map(x=>legLabel(x.o)).join(", ")} (positive correlation helps the slip).`);
      if(edge!=null&&edge>=0) why.push(`Priced fairly or better: +${(edge*100).toFixed(0)} pts edge at bet365's price.`);
      if(!why.length) why.push("No conflicts with your other legs and no clearly better option in this game.");
    }
    return {i,l,lp,verdict,why,best,options,pRest,edge,strength:strengthOf(l,lp)};
  });
  return {base,res};
}
function renderAudit(){
  const legs=state.slip.legs;
  if(!legs.length) return `<section class="panel"><h2>Audit slip</h2><div class="empty">Your bet slip is empty. Add legs from
    <a href="#picks">Algorithm picks</a>, <a href="#sgp">SGP</a> or <a href="#mysgp">Build your SGP</a>, then come back to audit it.</div></section>`;
  const A=auditSlip(legs);
  let after=legs.slice(); const changes=[];
  A.res.slice().sort((a,b)=>b.i-a.i).forEach(r=>{ if(r.verdict==="remove"){after.splice(r.i,1);changes.push(r)} else if(r.verdict==="swap"&&r.best){after[r.i]=r.best.o;changes.push(r)} });
  const pAfter=after.length?jointPN(after,30000):null;
  const n={start:0,swap:0,remove:0}; A.res.forEach(r=>n[r.verdict]++);
  const score=100*Math.pow(A.base,1/legs.length);
  const byG={}; A.res.forEach(r=>{(byG[P[r.l.id].game]??=[]).push(r)});
  const gids=Object.keys(byG).sort((a,b)=>D.games.findIndex(g=>g.id===a)-D.games.findIndex(g=>g.id===b));
  const card=r=>{const p=P[r.l.id];const V={start:["START","good"],swap:["SWAP","warn"],remove:["REMOVE","bad"]}[r.verdict];
    return `<div class="aleg v-${r.verdict}"><div class="line1"><span class="pill ${V[1]} vpill">${V[0]}</span>
      <span class="nm">${esc(legLabel(r.l))}<small>${p.pos} · ${p.team}</small></span>
      <span class="pill ${r.strength[1]}">${r.strength[0]}</span><span class="prob">${r.lp==null?"–":pct(r.lp,0)}</span></div>
      <ul class="why">${r.why.map(w=>`<li>${w}</li>`).join("")}</ul>
      ${r.options.length?`<div class="opts"><div class="lbl">${r.verdict==="swap"?"Swap options (best first)":"Swap options"}</div>${r.options.map((x,k)=>{const dlt=(x.pr-A.base)*100;
        return `<div class="sug${r.verdict==="swap"&&r.best&&x===r.best?" rec":""}"><span><b>${esc(legLabel(x.o))}</b> <span class="pill">${x.o.tag} · ${pct(x.o.p,0)}</span>${r.verdict==="swap"&&r.best&&x===r.best?' <span class="pill good">recommended</span>':""}</span>
        <span class="sugr">slip ${pct(x.pr)} <span style="color:var(${dlt>=0?"--good":"--bad"})">(${dlt>=0?"+":""}${dlt.toFixed(1)} pts)</span> <button class="btn sm" data-audit-swap="${r.i}|${x.o.id}|${x.o.mk}|${x.o.k??""}">Swap</button></span></div>`}).join("")}</div>`:""}
      ${r.verdict==="remove"?`<div class="sug"><span>Remove this leg</span><span class="sugr">slip ${pct(A.base)} → ${pct(r.pRest)} <button class="btn sm" data-audit-rm="${r.i}">Remove</button></span></div>`:""}
      <details><summary>Intel</summary><ul class="why">${legIntel(r.l).map(w=>`<li>${w}</li>`).join("")}</ul></details></div>`};
  return `<section class="panel"><div class="section-head"><div><h2>Slip audit</h2>
      <p class="sub">Every leg reviewed against the model: <b>Start</b> it, <b>Swap</b> it for a better leg in the same game, or <b>Remove</b> it. Checks: your rules (Questionable and returning players are singles only), legs that work against each other, bet365 price vs model, weak lines, and better options in the same game.</p></div></div>
    <div class="scoregrid">
      <div class="big"><div><div class="lbl">Slip now</div><div class="sub">${legs.length} legs · ${gids.length} game${gids.length>1?"s":""} · score ${score.toFixed(0)} ${grade(score)}</div></div><div class="val">${pct(A.base)}<small>fair ${am(A.base)}</small></div></div>
      <div class="big"><div><div class="lbl">With all suggestions</div><div class="sub">${n.start} start · ${n.swap} swap · ${n.remove} remove</div></div><div class="val">${pAfter==null?"–":pct(pAfter)}<small>${pAfter==null?"":"fair "+am(pAfter)}</small></div></div>
    </div>
    ${changes.length?`<div class="row" style="margin-top:10px"><button class="btn primary" data-audit-apply>Apply all ${changes.length} suggestion${changes.length>1?"s":""}</button>
      <span class="sub">Fewer legs or safer lines also mean a shorter price: check the new price in the bet slip.</span></div>`:`<div class="verdict good" style="margin-top:10px">Clean slip: every leg is a Start.</div>`}</section>
    ${gids.map(g=>`<section class="panel"><div class="section-head"><div><h3 style="font-size:20px">${gameLabel(G[g])}</h3><div class="envline">${envPills(G[g])}</div></div></div>
      ${byG[g].map(card).join("")}</section>`).join("")}`;
}
document.addEventListener("click",e=>{const t=e.target.closest("button");if(!t)return;const d=t.dataset;
  if(d.auditSwap){const [i,id,mk,k]=d.auditSwap.split("|");const o=state.slip.legs[+i];state.slip.legs[+i]={id,mk,k:k===""?null:parseInt(k),odds:"",status:o.status};persist();render();toast("Swapped")}
  else if(d.auditRm!=null){state.slip.legs.splice(+d.auditRm,1);persist();render();toast("Removed")}
  else if("auditApply" in d){const A=auditSlip(state.slip.legs);
    A.res.slice().sort((a,b)=>b.i-a.i).forEach(r=>{ if(r.verdict==="remove") state.slip.legs.splice(r.i,1);
      else if(r.verdict==="swap"&&r.best) state.slip.legs[r.i]={id:r.best.o.id,mk:r.best.o.mk,k:r.best.o.k??null,odds:"",status:"o"} });
    persist();render();toast("Suggestions applied")}
});

document.addEventListener("click",e=>{ if(state.tab==="audit"&&e.target.closest("#slip button")) setTimeout(()=>{$("#main").innerHTML=renderAudit()},0) });
document.addEventListener("click",e=>{ if(e.target.closest("#fab")) openSlip(true); else if(e.target.closest("[data-close-slip]")||e.target.id==="scrim") openSlip(false) });
document.addEventListener("keydown",e=>{ if(e.key==="Escape") openSlip(false) });
window.addEventListener("hashchange",route);
$("#meta").textContent=`${D.meta.season} Week ${D.meta.week} · ${D.meta.n_games} games · built ${D.meta.built} · injuries as of ${D.meta.data_asof||"—"} · ${D.meta.overrides} override${D.meta.overrides===1?"":"s"}`;
$("#recchip").textContent=D.meta.record&&D.meta.record.tickets?`Last week: ${D.meta.record.cashed}/${D.meta.record.tickets} tickets cashed`:`Graded as shipped, every week`;
route();

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

