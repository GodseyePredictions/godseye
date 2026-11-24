/**
 * The algorithms' current output, loaded on the server for the advisor's tools.
 * Files are re-read when they change on disk, so a new build is picked up without a restart.
 * The two paths are written out in full so the build knows exactly which files the server needs.
 */
import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import type { AdvisorContext } from "./agent.ts";
import { nbaIntel, nflIntel } from "./intel.ts";
import { nbaCatalog, nflCatalog, parseConsoleData } from "./legs.ts";
import { nbaPicks, nflPicks } from "./picks.ts";

type Cached = { mtime: number; data: unknown } | null;
let nflCache: Cached = null;
let nbaCache: Cached = null;
let nbaAuditCache: Cached = null;

function loadNfl(): unknown | null {
  try {
    const file = path.join(process.cwd(), "public/console/data.js");
    const mtime = statSync(file).mtimeMs;
    if (nflCache?.mtime !== mtime) nflCache = { mtime, data: parseConsoleData(readFileSync(file, "utf8")) };
    return nflCache.data;
  } catch {
    return null; // the NFL output is not on this server: its tools will say so
  }
}

function loadNba(): unknown | null {
  try {
    const file = path.join(process.cwd(), "model/nba/output/nba_site.json");
    const mtime = statSync(file).mtimeMs;
    if (nbaCache?.mtime !== mtime) nbaCache = { mtime, data: JSON.parse(readFileSync(file, "utf8")) };
    return nbaCache.data;
  } catch {
    return null;
  }
}

/** The NBA run's audit data (every rated rung, and correlations). Missing or unreadable: the catalog falls back to posted picks. */
function loadNbaAudit(): unknown | null {
  try {
    const file = path.join(process.cwd(), "model/nba/output/nba_audit.json");
    const mtime = statSync(file).mtimeMs;
    if (nbaAuditCache?.mtime !== mtime) nbaAuditCache = { mtime, data: JSON.parse(readFileSync(file, "utf8")) };
    return nbaAuditCache.data;
  } catch {
    return null;
  }
}

export function loadAlgorithmData(): Pick<AdvisorContext, "catalogs" | "intel" | "picks"> {
  const nfl = loadNfl();
  const nba = loadNba();
  return {
    catalogs: { ...(nfl ? { NFL: nflCatalog(nfl) } : {}), ...(nba ? { NBA: nbaCatalog(nba, loadNbaAudit() ?? undefined) } : {}) },
    intel: { ...(nfl ? { NFL: nflIntel(nfl) } : {}), ...(nba ? { NBA: nbaIntel(nba) } : {}) },
    picks: { ...(nfl ? { NFL: nflPicks(nfl) } : {}), ...(nba ? { NBA: nbaPicks(nba) } : {}) },
  };
}
