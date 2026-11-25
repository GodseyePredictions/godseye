// The check before publishing: opens the single-file preview and confirms the landing page, the NFL, NBA and
// NHL consoles and their slips render with no page errors. Prints what it found as JSON.
//
// Usage: node scripts/check-preview.cjs <built.html> <screenshot-dir> <react-umd-dir>
// <react-umd-dir> holds react.production.min.js and react-dom.production.min.js (from `npm pack react@18.3.1
// react-dom@18.3.1`, umd/ folder), served in place of the CDN copies so the check runs without internet access.
const { chromium } = require('playwright');
(async () => {
  const file = process.argv[2], out = process.argv[3];
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  const errs = []; p.on('pageerror', e => errs.push(String(e))); p.on('console', m => { if (m.type() === 'error' && !/fonts|net::|Failed to load resource/.test(m.text())) errs.push(m.text()); });
  const fs = require('fs');
  await p.route('**/cdnjs.cloudflare.com/**', route => { const f = route.request().url().split('/').pop(); route.fulfill({ contentType: 'application/javascript', body: fs.readFileSync(process.argv[4] + '/' + f) }); });
  await p.route('**/fonts.googleapis.com/**', route => route.fulfill({ contentType: 'text/css', body: '' }));
  await p.goto('file://' + file); await p.waitForTimeout(1500);
  const r = {};
  r.landing = await p.evaluate(() => ({ lp: !!document.querySelector('.lp'), sports: [...document.querySelectorAll('.lp-sport .lp-sport-name')].map(x => x.textContent), nhlLine: [...document.querySelectorAll('.lp-sport')].map(x => x.querySelector('.lp-sport-line')?.textContent)[2] }));
  await p.screenshot({ path: out + '/landing.png' });
  await p.evaluate(() => { location.hash = 'nhl-home'; }); await p.waitForTimeout(600);
  r.nhlHome = await p.evaluate(() => [...document.querySelectorAll('div:not([hidden]) > .wrap .nba-card h3')].map(x => x.textContent));
  await p.screenshot({ path: out + '/nhl-home.png' });
  await p.evaluate(() => { location.hash = 'nhl-sgp'; }); await p.waitForTimeout(600);
  r.nhlSlips = await p.evaluate(() => [...document.querySelectorAll('div:not([hidden]) > .wrap .gs-slip')].map(s => ({ title: s.querySelector('.gs-slip-title')?.textContent, legs: s.querySelectorAll('.gs-slip-legs li').length, foot: [...s.querySelectorAll('.gs-slip-foot div')].map(d => d.textContent) })));
  await p.screenshot({ path: out + '/nhl-sgp.png', fullPage: true });
  await p.evaluate(() => { location.hash = 'nhl-board'; }); await p.waitForTimeout(400);
  r.board = await p.evaluate(() => document.querySelectorAll('div:not([hidden]) > .wrap .tbl tbody tr').length);
  await p.evaluate(() => { location.hash = 'nhl-model'; }); await p.waitForTimeout(400);
  await p.evaluate(() => { location.hash = 'nba-home'; }); await p.waitForTimeout(600);
  r.nba = await p.evaluate(() => document.querySelectorAll('div:not([hidden]) > .wrap .nba-card').length);
  await p.evaluate(() => { location.hash = 'home'; }); await p.waitForTimeout(800);
  r.nfl = await p.evaluate(() => ({ main: !!document.getElementById('main'), text: (document.getElementById('main')?.innerText || '').length }));
  await p.evaluate(() => { location.hash = 'sgp'; }); await p.waitForTimeout(800);
  r.nflSlips = await p.evaluate(() => document.querySelectorAll('#main .gs-slip').length);
  r.errors = errs;
  console.log(JSON.stringify(r, null, 1)); await b.close();
})();
