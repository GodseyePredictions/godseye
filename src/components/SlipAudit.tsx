"use client";

/* What the algorithm says about a pasted slip, leg by leg.
   It shows numbers from src/lib/advisor (the algorithms' own output) and src/lib/staking only. */
import { useEffect, useState, useSyncExternalStore } from "react";
import { auditSlip } from "@/lib/advisor/audit";
import { nbaCatalog, nflCatalog, parseConsoleData, type Catalog, type Sport } from "@/lib/advisor/legs";
import type { Bet, Leg } from "@/lib/bets";
import { tonightFrom } from "@/lib/staking";
import { readAccount, subscribeAccount } from "./BankrollStrategy";

const cache: Partial<Record<Sport, Promise<Catalog>>> = {};
function loadCatalog(sport: Sport): Promise<Catalog> {
  cache[sport] ??=
    sport === "NFL"
      ? fetch("/console/data.js")
          .then((r) => (r.ok ? r.text() : Promise.reject(new Error("no data"))))
          .then((t) => nflCatalog(parseConsoleData(t)))
      : import("../../model/nba/output/nba_site.json").then((m) => nbaCatalog(m.default));
  // a failed load is not remembered, so the next visit tries again
  cache[sport]!.catch(() => delete cache[sport]);
  return cache[sport]!;
}

const pct = (p: number) => `${(p * 100).toFixed(1)}%`;

export function SlipAudit({ legs, sport, bets }: { legs: Leg[]; sport: string; bets: Bet[] }) {
  const rated = sport === "NFL" || sport === "NBA" ? (sport as Sport) : null;
  const [loaded, setLoaded] = useState<{ sport: Sport; catalog: Catalog | null } | null>(null);
  const account = useSyncExternalStore(subscribeAccount, readAccount, () => null);
  const [now] = useState(() => new Date());

  useEffect(() => {
    if (!rated) return;
    let live = true;
    loadCatalog(rated).then(
      (catalog) => live && setLoaded({ sport: rated, catalog }),
      () => live && setLoaded({ sport: rated, catalog: null }),
    );
    return () => {
      live = false;
    };
  }, [rated]);

  if (!rated)
    return (
      <p className="sub">
        The algorithms cover NFL and NBA. A slip from another sport is unrated: the review above is from the prices alone.
      </p>
    );
  if (!loaded || loaded.sport !== rated) return <p className="sub">Checking the legs against the {rated} algorithm…</p>;
  if (!loaded.catalog) return <p className="sub">The {rated} algorithm&apos;s numbers did not load, so these legs cannot be rated right now.</p>;

  const audit = auditSlip(
    legs.map((l) => ({ text: l.description, odds: l.odds })),
    loaded.catalog,
    account ? { account, tonight: tonightFrom(bets, now), now } : {},
  );
  return (
    <div style={{ marginTop: 18 }}>
      <h3>What the {rated} algorithm says</h3>
      <p className="sub">
        {audit.rated} of {audit.legs.length} leg{audit.legs.length > 1 ? "s" : ""} rated · algorithm built {audit.built}
      </p>
      <ul className="t-findings">
        {audit.legs.map((l, i) => (
          <li key={i} className={l.status === "rated" ? "info" : "warn"}>
            <strong>
              Leg {i + 1}: {l.status === "rated" ? pct(l.prob as number) : "unrated"}
              {l.edge != null && ` · ${l.edge >= 0 ? "+" : "−"}${Math.abs(l.edge * 100).toFixed(1)} pts against its price`}
            </strong>
            <span>{l.note}</span>
          </li>
        ))}
        {audit.rules.map((r) => (
          <li key={r.rule} className={r.level}>
            <strong>{r.level === "warn" ? "Outside Godseye's ticket rules" : "Worth knowing"}</strong>
            <span>{r.detail}</span>
          </li>
        ))}
        <li className="info">
          <strong>Chance of the whole slip: {audit.slipProb == null ? "not stated" : pct(audit.slipProb)}</strong>
          <span>{audit.slipProbNote}</span>
        </li>
        {audit.stake && (
          <li className="info">
            <strong>Suggested stake: {audit.stake.status === "bet" ? audit.stake.label : audit.stake.status === "unrated" ? "unrated" : "no bet"}</strong>
            <span>{audit.stake.reason}</span>
          </li>
        )}
      </ul>
      {!account && (
        <p className="sub">
          Set a bankroll in <a href="#bankroll">Bankroll Strategy</a> to see a suggested stake for a rated single.
        </p>
      )}
    </div>
  );
}
