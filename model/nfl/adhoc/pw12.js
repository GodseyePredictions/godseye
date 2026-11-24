const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const errs=[];
  for (const [w,h] of [[1280,1600],[390,844]]) {
    const pg = await b.newPage({viewport:{width:w,height:h}}); pg.on('pageerror',e=>errs.push(e.message));
    await pg.goto('file:///home/user/attd/outputs/site/gods_eye.html'); await pg.waitForTimeout(500);
    for (const t of ['picks','sgp','atd']) { await pg.evaluate(s=>document.querySelector(s)&&document.querySelector(s).click(),`[data-tab="${t}"]`); await pg.waitForTimeout(400);
      if(t==='picks'&&w>1000){ for (const sel of ['[data-early-load^="hp|"]','[data-early-load^="hh|"]','[data-early-load^="mixed|"]','[data-early-load^="atd|"]','[data-early-load^="game|"]','[data-early-load^="master|"]','[data-early-load^="hyb|"]']) { const n=await pg.evaluate(s=>{const e=document.querySelector(s); if(!e) return -1; e.click(); return state.slip.legs.length}, sel); console.log(sel,n);} console.log(await pg.evaluate(()=>[...document.querySelectorAll('h2')].slice(0,4).map(x=>x.textContent))); } }
    console.log(w,'overflow', await pg.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth));
  }
  console.log('errors', errs); await b.close();
})();
