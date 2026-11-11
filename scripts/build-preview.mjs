// Builds the app as one self-contained HTML file, for sharing as a preview
// (for example as a Claude artifact). The real site is the Next.js app.
//
// Usage: node scripts/build-preview.mjs <output.html>
import { build } from "esbuild";
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const out = process.argv[2];
if (!out) throw new Error("Usage: node scripts/build-preview.mjs <output.html>");
const tmp = mkdtempSync(path.join(tmpdir(), "ge-preview-"));

// React comes from the page's <script> tags (UMD globals), not from the bundle.
writeFileSync(path.join(tmp, "react.js"), "module.exports = window.React;");
writeFileSync(path.join(tmp, "react-dom.js"), "module.exports = window.ReactDOM;");
writeFileSync(
  path.join(tmp, "entry.jsx"),
  `import React from "react";
import ReactDOM from "react-dom";
import ConsoleApp from "${path.join(root, "src/components/ConsoleApp.tsx")}";
window.GE_INLINE = true;
const rootEl = ReactDOM.createRoot(document.getElementById("root"));
ReactDOM.flushSync(() => rootEl.render(<ConsoleApp eyeSrc={window.GE_EYE} homeHref="#home" />));
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

const b64 = (f) => "data:image/jpeg;base64," + readFileSync(path.join(root, f)).toString("base64");
const safe = (s) => s.replace(/<\/script/gi, "<\\/script");
const cssText = css.outputFiles[0].text.replace(/url\(["']?\/brand\/banner\.jpg["']?\)/, `url("${b64("public/brand/banner.jpg")}")`);
if (cssText.includes("/brand/")) throw new Error("An image path was not inlined");

const html = `<title>Godseye App Preview</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;700;800&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--font-display:"Saira Condensed";--font-body:"IBM Plex Sans";--font-mono:"IBM Plex Mono"}
${cssText}
</style>
<div id="root"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>
<script>window.GE_EYE=${JSON.stringify(b64("public/brand/eye.jpg"))};window.GE_EXTRA_TABS=["markets","hybrids","paste","bets","report","alerts","scripts","games"];</script>
<script>
${safe(readFileSync(path.join(root, "public/console/data.js"), "utf8"))}
</script>
<script>
${safe(readFileSync(path.join(root, "public/console/personnel-update.js"), "utf8"))}
</script>
<script>
${safe(readFileSync(path.join(root, "public/console/freshness-update.js"), "utf8"))}
</script>
<script>
${safe(readFileSync(path.join(root, "public/console/odds-update.js"), "utf8"))}
</script>
<script>
${safe(js.outputFiles[0].text)}
</script>
<script>
${safe(readFileSync(path.join(root, "public/console/app.js"), "utf8"))}
</script>
`;
writeFileSync(out, html);
console.log(`${out}: ${(html.length / 1e6).toFixed(2)} MB`);
