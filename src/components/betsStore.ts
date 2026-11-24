/* Tracked bets, shared by every page that shows or saves them.
   They live in this browser's storage until accounts exist. */
import type { Bet } from "@/lib/bets";

const STORE = "godseye.bets.v1";
export const NO_BETS: Bet[] = [];
const listeners = new Set<() => void>();
let cache: Bet[] | null = null;

export function readBets(): Bet[] {
  if (cache === null) {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE) ?? "[]");
      cache = Array.isArray(raw) ? (raw as Bet[]) : [];
    } catch {
      cache = [];
    }
  }
  return cache;
}
export function writeBets(next: Bet[]) {
  cache = next;
  try {
    localStorage.setItem(STORE, JSON.stringify(next));
  } catch {
    /* storage unavailable: keep in memory for this visit */
  }
  listeners.forEach((l) => l());
}
export function subscribeBets(cb: () => void) {
  // The console's "Track this bet" button writes to storage and fires "ge-bets";
  // "storage" fires when another tab of the site saves a bet.
  const reload = () => {
    cache = null;
    cb();
  };
  listeners.add(cb);
  window.addEventListener("ge-bets", reload);
  window.addEventListener("storage", reload);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("ge-bets", reload);
    window.removeEventListener("storage", reload);
  };
}
