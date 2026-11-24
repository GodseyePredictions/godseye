/* Runs before `npm test` and `npm run build`. If a package the site needs is not installed
   (for example after pulling a change that added one), it runs `npm install` once.
   This is what lets a scheduled job pull main and test without knowing what changed. */
import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
const wanted = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies });
const missing = wanted.filter((name) => !existsSync(new URL(`../node_modules/${name}/package.json`, import.meta.url)));
if (missing.length) {
  console.log(`Installing missing packages: ${missing.join(", ")}`);
  execSync("npm install --no-audit --no-fund", { stdio: "inherit", cwd: new URL("..", import.meta.url) });
}
