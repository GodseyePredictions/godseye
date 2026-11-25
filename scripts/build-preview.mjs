// Builds the app as one self-contained HTML file, for sharing as a preview
// (for example as a Claude artifact). The real site is the Next.js app.
//
// Usage: node scripts/build-preview.mjs <output.html>
import { build } from "esbuild";
import { readFileSync, writeFileSync, mkdtempSync, existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const out = process.argv[2];
if (!out) throw new Error("Usage: node scripts/build-preview.mjs <output.html>");
const tmp = mkdtempSync(path.join(tmpdir(), "ge-preview-"));
// The NFL console's own script draws into the element with id "main". In this file every view shares one
// document, so no other view may use that id, or the console is drawn over it.
for (const f of ["src/app/(site)/page.tsx", "src/components/InfoPages.tsx", "src/components/NbaApp.tsx", "src/components/NhlApp.tsx"]) {
  if (/id="main"/.test(readFileSync(path.join(root, f), "utf8"))) throw new Error(`${f} uses id="main", which belongs to the NFL console`);
}

// React comes from the page's <script> tags (UMD globals), not from the bundle.
writeFileSync(path.join(tmp, "react.js"), "module.exports = window.React;");
writeFileSync(path.join(tmp, "react-dom.js"), "module.exports = window.ReactDOM;");
// next/link has no meaning in a single file: links become plain anchors and the shell below routes them.
writeFileSync(path.join(tmp, "link.js"),
  `const React = require("react"); module.exports = { __esModule: true, default: (p) => React.createElement("a", p) };`);
writeFileSync(
  path.join(tmp, "entry.jsx"),
  `import React from "react";
import ReactDOM from "react-dom";
import ConsoleApp from "${path.join(root, "src/components/ConsoleApp.tsx")}";
import NbaApp from "${path.join(root, "src/components/NbaApp.tsx")}";
import NhlApp from "${path.join(root, "src/components/NhlApp.tsx")}";
import Home from "${path.join(root, "src/app/(site)/page.tsx")}";
import { ContactPage, PrivacyPage, ResponsibleGamblingPage, TermsPage } from "${path.join(root, "src/components/InfoPages.tsx")}";
window.GE_INLINE = true;

// One page, four views. The view is read from the address: nothing (or a landing section) is the landing
// page, "nba-..." is the NBA side, "nhl-..." the NHL side, anything else is an NFL console tab.
const LANDING = ["", "how", "locks", "sports", "nfl", "nba"];
const INFO = { "terms": TermsPage, "privacy": PrivacyPage, "responsible-gambling": ResponsibleGamblingPage, "contact": ContactPage };
const viewOf = (h) => (h.startsWith("nba-") ? "nba" : h.startsWith("nhl-") ? "nhl" : INFO[h] ? "info" : LANDING.includes(h) ? "site" : "nfl");
const siteCss = (view) => view === "site" || view === "info";
const sub = (cb) => { window.addEventListener("hashchange", cb); return () => window.removeEventListener("hashchange", cb); };
function applyStyles(view) {
  document.getElementById("css-site").media = siteCss(view) ? "all" : "not all";
  document.getElementById("css-console").media = siteCss(view) ? "not all" : "all";
}
// Site-style links ("/", "/nfl#sgp", "/nba") are turned into views of this page.
document.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest("a[href]");
  if (!a) return;
  const href = a.getAttribute("href");
  // A section link on the landing or an information page scrolls there. It must not change the address,
  // because some section names ("picks") are also NFL console tabs.
  if (href.startsWith("#") && href.length > 1 && siteCss(viewOf(location.hash.slice(1)))) {
    const target = a.closest(".lp") && a.closest(".lp").querySelector("[id='" + href.slice(1).replace(/'/g, "") + "']");
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: "smooth" }); return; }
  }
  if (!href.startsWith("/")) return;
  e.preventDefault();
  const [path, tab] = href.split("#");
  const next = path === "/nba" ? "nba-" + (tab || "home") : path === "/nhl" ? "nhl-" + (tab || "home") : path === "/nfl" || path === "/app" ? tab || "home" : INFO[path.slice(1)] ? path.slice(1) : "";
  if (next) location.hash = next;
  else { history.replaceState(null, "", location.pathname + location.search); window.dispatchEvent(new HashChangeEvent("hashchange")); }
  window.scrollTo(0, 0);
});
function Shell() {
  const hash = React.useSyncExternalStore(sub, () => location.hash.slice(1), () => "");
  const view = viewOf(hash);
  React.useLayoutEffect(() => applyStyles(view), [view]);
  return (
    <>
      <div hidden={view !== "site"}><Home /></div>
      {view === "info" ? React.createElement(INFO[hash]) : null}
      <div hidden={view !== "nfl"}><ConsoleApp eyeSrc={window.GE_EYE} homeHref="/" /></div>
      <div hidden={view !== "nba"}><NbaApp prefix="nba-" /></div>
      <div hidden={view !== "nhl"}><NhlApp prefix="nhl-" /></div>
    </>
  );
}
applyStyles(viewOf(location.hash.slice(1)));
const rootEl = ReactDOM.createRoot(document.getElementById("root"));
ReactDOM.flushSync(() => rootEl.render(<Shell />));
`,
);

const js = await build({
  entryPoints: [path.join(tmp, "entry.jsx")],
  bundle: true,
  minify: true,
  write: false,
  format: "iife",
  jsx: "transform",
  tsconfigRaw: { compilerOptions: { jsx: "react" } },
  loader: { ".json": "json" },
  alias: {
    react: path.join(tmp, "react.js"),
    "react-dom": path.join(tmp, "react-dom.js"),
    "next/link": path.join(tmp, "link.js"),
    "@": path.join(root, "src"),
  },
});
const css = await build({
  entryPoints: [path.join(root, "src/app/(console)/console.css")],
  bundle: true,
  minify: true,
  write: false,
  external: ["/brand/*"],
});

// The landing page's stylesheet, without the Tailwind import (the page uses none of its classes).
writeFileSync(path.join(tmp, "site.css"),
  readFileSync(path.join(root, "src/app/(site)/globals.css"), "utf8")
    .replace(/@import\s+"tailwindcss";/, "")
    // the shared slip styles are inlined here: only one of the two stylesheets is switched on at a time
    .replace(/@import\s+"\.\.\/\.\.\/styles\/slip\.css";/, () => readFileSync(path.join(root, "src/styles/slip.css"), "utf8")));
if (!readFileSync(path.join(tmp, "site.css"), "utf8").includes(".gs-slip")) throw new Error("The slip styles were not inlined into the landing page's stylesheet");
const siteCss = await build({ entryPoints: [path.join(tmp, "site.css")], bundle: true, minify: true, write: false });
const b64 = (f) => "data:image/jpeg;base64," + readFileSync(path.join(root, f)).toString("base64");
const safe = (s) => s.replace(/<\/script/gi, "<\\/script");
const cssText = css.outputFiles[0].text.replace(/url\(["']?\/brand\/banner\.jpg["']?\)/, `url("${b64("public/brand/banner.jpg")}")`);
if (cssText.includes("/brand/")) throw new Error("An image path was not inlined");

const siteText = siteCss.outputFiles[0].text;
// Optional player photos (public/players/<name-slug>.jpg). None ship with the repo: add only images you have the right to use.
const photoDir = path.join(root, "public/players");
const photos = Object.fromEntries(
  (existsSync(photoDir) ? readdirSync(photoDir) : []).filter((f) => f.endsWith(".jpg")).map((f) => [f.slice(0, -4), b64("public/players/" + f)]),
);
const html = `<title>Godseye App Preview</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--font-display:"Saira Condensed";--font-body:"IBM Plex Sans";--font-mono:"IBM Plex Mono";color-scheme:dark}
body{background:#0a090b;color:#fff}[hidden]{display:none!important}
</style>
<style id="css-site">
${siteText}
</style>
<style id="css-console" media="not all">
${cssText}
</style>
<div id="root"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>
<script>window.GE_EYE=${JSON.stringify(b64("public/brand/eye.jpg"))};window.GE_BANNER=${JSON.stringify(b64("public/brand/banner.jpg"))};window.GE_PHOTOS=${JSON.stringify(photos)};window.GE_EXTRA_TABS=["markets","hybrids","paste","bets","report","scripts","games"];</script>
<script>
${safe(readFileSync(path.join(root, "public/console/data.js"), "utf8"))}
</script>
<script>
${safe(js.outputFiles[0].text)}
</script>
<script>
${safe(readFileSync(path.join(root, "public/console/app.js"), "utf8"))}
</script>
`;
// The published site always has the same parts (CLAUDE.md, "Publishing the site"). Refuse to write a file without them.
for (const [what, found] of [
  ["the landing page", js.outputFiles[0].text.includes("lp-hero")],
  ["the white slip styles on the landing page", siteText.includes(".gs-slip")],
  ["the white slip styles in the consoles", cssText.includes(".gs-slip")],
  ["set slips in the NFL console", readFileSync(path.join(root, "public/console/app.js"), "utf8").includes("function geSlip(")],
]) if (!found) throw new Error(`The build is missing ${what}`);
writeFileSync(out, html);
console.log(`${out}: ${(html.length / 1e6).toFixed(2)} MB`);
