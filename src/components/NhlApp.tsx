"use client";

import { useSyncExternalStore } from "react";
import { Logo } from "@/components/Logo";
import { CashedSlip, Slip, american, pct } from "@/components/Slip";
import { NHL_CASHED_WAGER, cashedReturn, dollars } from "@/lib/cashed";
import raw from "../../model/nhl/output/nhl_site.json";

/* The NHL side of the console. It mirrors the NBA console's layout and reads the latest slate written by
   `python3 -m nhl.run_daily slate` (model/nhl/output/nhl_site.json). Every ticket is shown as a set slip. */

type Leg = {
  label: string; market: string; team: string | null; prob: number; price: number | null; book?: string | null; matchup?: string | null;
  rung_verified: boolean;
  why?: string[]; game?: string | null;
};
type Multi = {
  id: string; kind: string; title: string; chance: number; miss: number; book_price: number | null; games: string[]; how_chosen: string | null;
  rungs_verified: boolean; priced: boolean; start_utc: string; includes_early?: string[]; legs: Leg[];
};
type Cashed = {
  id: string; date: string; title: string; game: string; final: string; made_at: string; chance: number; fair_price: number;
  rungs_verified: boolean; legs: { label: string; prob: number; actual: number | string | null; price: number | null }[];
};
type Ticket = {
  id: string; kind: string; title: string; chance: number; miss: number; book_price: number | null; lift: number; priced: boolean;
  rungs_verified: boolean; edge: number | null; book: string | null; kelly_stake: number | null; legs: Leg[];
};
type Step = { what: string; value?: number; factor?: number };
type Projection = {
  player: string; team: string; pos: string; toi_min: number; line: string | null; pp: string | null;
  sog: number; pts: number; goals: number; ast: number; hits: number; blk: number; atg: number;
};
type Game = {
  id: string; label: string; home: string; away: string; start_utc: string; venue: string | null; paper: boolean; early: boolean;
  made_after_start: boolean; notes: string[];
  goalies: Record<string, { name: string | null; status: string; ok: boolean }>;
  lines_ok: Record<string, boolean>;
  referees: string[];
  sim: { home_goals: number; away_goals: number; total: number; home_win: number; overtime: number; blowout_prob: number; favourite: string;
         favourite_blowout_prob: number; blowout_flag: boolean; home_sog: number; away_sog: number };
  expected: Record<string, { goals: number; sog: number; pp_min: number; steps: Step[] }>;
  fair: { moneyline: Record<string, { prob: number; fair_price: number }>; totals: Record<string, { prob: number; fair_price: number }>;
          puck_line: Record<string, { prob: number; fair_price: number }> };
  game_lines: { book: string; market: string; side: string; line: number; price: number; model_prob: number; implied_prob: number; edge: number; tier: string | null }[];
  saves: Record<string, { name: string | null; expected: number | null; pull_prob: number | null }>;
  tickets: Ticket[];
  removed_count: number;
  projections: Projection[];
};
type Slate = {
  date: string; made_at: string; status: string; preview: boolean; early: boolean; mixed?: boolean; sims: number; floor: number; games: Game[]; multi: Multi[];
  cashed: Cashed[]; skipped: string[];
};

const slate = raw as unknown as Slate;
const TABS = ["home", "sgp", "multi", "cashed", "board", "model"] as const;
type Tab = (typeof TABS)[number];

function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}
const readHash = () => window.location.hash.slice(1);
const dropTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" }) + " ET";
const builtAt = (iso: string) =>
  new Date(iso).toLocaleString("en-CA", { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" }) + " ET";

function Icon({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function legSub(l: Leg) {
  const m = l.matchup ? ` · ${l.matchup} matchup` : "";
  return l.price == null ? `model ${pct(l.prob)}${m} · no listed price` : `model ${pct(l.prob)}${m} · ${l.book ?? "book"} ${american(l.price)}`;
}

function TicketSlip({ t, g }: { t: Ticket; g: Game }) {
  const why = {
    intel: [
      `${g.away} ${g.sim.away_goals.toFixed(2)}, ${g.home} ${g.sim.home_goals.toFixed(2)} on average over ${slate.sims.toLocaleString()} simulated games`,
      `${g.sim.favourite} is the favourite; blowout by the favourite after two periods in ${pct(g.sim.favourite_blowout_prob)} of them`,
      t.legs.length > 1
        ? `The legs hit together ${t.lift >= 1 ? "more" : "less"} often than their separate chances multiplied (${t.lift.toFixed(2)}x): the chance is counted from the same simulated games`
        : `Model chance ${pct(t.chance, 1)}, from the simulated games alone`,
    ],
    legs: t.legs.map((l) => ({ text: l.label, why: l.why ?? [] })),
  };
  return (
    <Slip
      title={t.title}
      meta={`${g.label} · ${dropTime(g.start_utc)}`}
      legs={t.legs.map((l) => ({
        text: l.label,
        sub: legSub(l),
        value: l.price == null ? pct(l.prob) : american(l.price),
      }))}
      stats={[
        { label: "Chance to hit", value: pct(t.chance, 1), tone: "good" },
        { label: "Chance to miss", value: pct(t.miss, 1), tone: "bad" },
        { label: "Price", value: t.book_price == null ? "not listed" : american(t.book_price), tone: "red" },
      ]}
      why={why}
      warn={
        g.early
          ? "Early slip: this game's goalies or lines were not all confirmed when it was made. It is re-run before puck drop. Rungs are not checked at a book; no stake is suggested."
          : slate.early
          ? "Early slip: issued before goalies and lines were confirmed. It is re-issued once they are. Rungs and prices are not checked at a book; no stake is suggested."
          : slate.preview
          ? "Preview: goalies and lines are not all confirmed. This slip is re-run before puck drop and is not final."
          : !t.rungs_verified
            ? "Test slip: no book ladder is connected for NHL props, so these rungs and prices are not checked at the book. No stake is suggested."
            : undefined
      }
      note={
        t.kind === "closer"
          ? `The algorithm's own pick: the listed line it rates most likely. ${t.book ?? "The book"} lists it at ${american(t.legs[0].price)}; the price is not an input to the pick.`
          : undefined
      }
    />
  );
}

function GameHead({ g }: { g: Game }) {
  return (
    <>
      <div className="section-head">
        <div>
          <h2>{g.label}</h2>
          <p className="sub">
            Puck drop {dropTime(g.start_utc)}
            {g.venue ? ` · ${g.venue}` : ""}
            {g.referees.length ? ` · referees ${g.referees.join(", ")}` : ""}
          </p>
        </div>
      </div>
      <div className="envline">
        <span className="pill gold">
          {g.sim.home_win >= 0.5 ? g.home : g.away} {pct(Math.max(g.sim.home_win, 1 - g.sim.home_win))}
        </span>
        <span className="pill">Total {g.sim.total.toFixed(1)}</span>
        <span className="pill">Overtime {pct(g.sim.overtime)}</span>
        <span className={`pill ${g.sim.blowout_flag ? "bad" : ""}`}>Blowout {pct(g.sim.blowout_prob)}</span>
        {[g.away, g.home].map((t) => (
          <span className={`pill ${g.goalies[t]?.ok ? "good" : "warn"}`} key={t}>
            {t} goalie: {g.goalies[t]?.name ?? "not listed"} ({g.goalies[t]?.status.toLowerCase()})
          </span>
        ))}
      </div>
    </>
  );
}

function GamePanel({ g }: { g: Game }) {
  return (
    <section className="panel">
      <GameHead g={g} />
      {g.notes.length > 0 && (
        <ul className="sub" style={{ margin: "10px 0 0", paddingLeft: 18 }}>
          {g.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {g.tickets.length > 0 ? (
        <div className="nba-tickets" style={{ marginTop: 12 }}>
          {g.tickets.map((t) => (
            <TicketSlip t={t} g={g} key={t.id} />
          ))}
        </div>
      ) : (
        <p className="sub" style={{ marginTop: 12 }}>
          No slip: not enough legs passed the gates.
        </p>
      )}
    </section>
  );
}

function MultiSlip({ t }: { t: Multi }) {
  return (
    <Slip
      title={t.title}
      meta={`${t.games.length} games · first puck drop ${dropTime(t.start_utc)}`}
      legs={t.legs.map((l) => ({
        text: l.label,
        sub: `${l.game ?? ""} · ${legSub(l)}`,
        value: l.price == null ? pct(l.prob) : american(l.price),
      }))}
      stats={[
        { label: "Chance to hit", value: pct(t.chance, t.chance < 0.1 ? 2 : 1), tone: "good" },
        { label: "Chance to miss", value: pct(t.miss, t.chance < 0.1 ? 2 : 1), tone: "bad" },
        { label: "Price", value: t.book_price == null ? "not listed" : american(t.book_price), tone: "red" },
      ]}
      why={{
        intel: [
          `How it was chosen: ${t.how_chosen ?? "by the algorithm"}`,
          "Legs in the same game are counted together from that game's simulated games; different games are independent, so their chances are multiplied",
          `Games: ${t.games.join(", ")}`,
        ],
        legs: t.legs.map((l) => ({ text: l.label, why: l.why ?? [] })),
      }}
      warn={
        slate.early
          ? "Early slip: issued before goalies and lines were confirmed. It is re-issued once they are. Rungs and prices are not checked at a book; no stake is suggested."
          : slate.preview
          ? "Preview: goalies and lines are not all confirmed. This slip is re-run before puck drop and is not final."
          : t.kind === "lotto" && (t.includes_early ?? []).length
            ? `A longshot by design, and it uses games whose goalies or lines were not all confirmed (${(t.includes_early ?? []).join(", ")}). It misses far more often than it hits. Fair price, not a book's. No stake is suggested.`
          : t.kind === "lotto"
            ? "A longshot by design: it misses far more often than it hits. Price: the book's leg prices multiplied; its same-game price will differ. No stake is suggested."
            : !t.rungs_verified
              ? "Test slip: rungs and prices are not checked at the book. No stake is suggested."
              : undefined
      }
    />
  );
}

function MultiTab() {
  const multis = slate.multi.filter((t) => t.kind !== "lotto");
  const lotto = slate.multi.filter((t) => t.kind === "lotto");
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Multi-game slips</h2>
            <p className="sub">The games the model reads best, three legs from each. Open &quot;Why the algorithm rates it&quot; for the breakdown of every pick.</p>
          </div>
        </div>
        {multis.length ? (
          <div className="nba-tickets">
            {multis.map((t) => (
              <MultiSlip t={t} key={t.id} />
            ))}
          </div>
        ) : (
          <p className="sub">No multi-game slip: not enough games passed every gate.</p>
        )}
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Lotto ticket</h2>
            <p className="sub">One longshot at +5000 or longer on the book&apos;s leg prices multiplied, built from each player&apos;s most likely listed longshot rung.</p>
          </div>
        </div>
        {lotto.length ? (
          <div className="nba-tickets">
            {lotto.map((t) => (
              <MultiSlip t={t} key={t.id} />
            ))}
          </div>
        ) : (
          <p className="sub">No lotto ticket: the board does not hold enough qualifying longshot legs across three games.</p>
        )}
      </section>
    </>
  );
}

function CashedTab() {
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Cashed slips</h2>
          <p className="sub">
            Winning NHL algorithm slips only. Losing slips are not shown here. Each slip is shown at a {dollars(NHL_CASHED_WAGER)} wager,
            cashed at the algorithm&apos;s fair price for the slip; a sportsbook&apos;s price would differ. These were test slips: the rungs were
            not checked at a book and no bet was placed.
          </p>
        </div>
      </div>
      {slate.cashed.length ? (
        <div className="gs-slips ge-set">
          {slate.cashed.map((c) => (
            <CashedSlip
              key={c.id}
              title={`${c.game} · ${c.title}`}
              pills={[new Date(`${c.date}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }), `Final ${c.final}`]}
              legs={c.legs.map((l) => l.label)}
              model={pct(c.chance, 1)}
              price={american(c.fair_price)}
              priceLabel="Fair price"
              stake={dollars(NHL_CASHED_WAGER)}
              stakeLabel="Wager"
              cashed={(() => {
                const r = cashedReturn(NHL_CASHED_WAGER, c.fair_price);
                return r == null ? null : dollars(r);
              })()}
            />
          ))}
        </div>
      ) : (
        <p className="sub">No cashed slips yet.</p>
      )}
    </section>
  );
}

function HomeTab({ prefix }: { prefix: string }) {
  const tickets = slate.games.reduce((n, g) => n + g.tickets.length, 0);
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>NHL slate, {slate.date}</h2>
          <p className="sub">
            {slate.games.length} games · {tickets} slips · built {builtAt(slate.made_at)} · {slate.sims.toLocaleString()} simulated games each
          </p>
        </div>
      </div>
      <p className="sub">
        {slate.mixed
          ? "Gated slips where both goalies and both teams' lines are confirmed. Games still waiting on a confirmation carry early slips on today's personnel and are re-run before puck drop. Test slips: no stake on props."
          : slate.early
          ? "Early card. Issued before goalies and lines were confirmed; each game is re-issued once they are. Slips are logged and graded."
          : slate.preview
          ? "Preview. Goalies and lines are not all confirmed yet, so these slips will be re-run before puck drop and are not final."
          : "Test slate. The NHL model is new and has not yet been checked against closing lines. Slips are for testing and grading, not staking."}
      </p>
      <div className="nba-grid">
        {slate.games.map((g) => (
          <a className="nba-card" href={`#${prefix}sgp`} key={g.id}>
            <h3>{g.label}</h3>
            <span className="sub">Puck drop {dropTime(g.start_utc)}</span>
            <span>
              <span className="pill gold">
                {g.sim.home_win >= 0.5 ? g.home : g.away} {pct(Math.max(g.sim.home_win, 1 - g.sim.home_win))}
              </span>{" "}
              <span className="pill">Total {g.sim.total.toFixed(1)}</span>{" "}
              <span className={`pill ${g.sim.blowout_flag ? "bad" : ""}`}>Blowout {pct(g.sim.blowout_prob)}</span>
            </span>
            <span className="sub">
              {g.early ? "Early · " : "Confirmed · "}
              {g.tickets.length ? `${g.tickets.length} slips` : "No slip"} · goalies {Object.values(g.goalies).every((x) => x.ok) ? "confirmed" : "not both confirmed"}
            </span>
          </a>
        ))}
      </div>
      {slate.games.length === 0 && <p className="sub">No games on the board. {slate.skipped.join(" · ")}</p>}
    </section>
  );
}

function BoardTab() {
  return (
    <>
      {slate.games.map((g) => (
        <section className="panel" key={g.id}>
          <GameHead g={g} />
          <p className="sub" style={{ marginTop: 10 }}>
            Expected saves: {[g.away, g.home].map((t) => `${g.saves[t]?.name ?? t + " goalie"} ${g.saves[t]?.expected ?? "n/a"}`).join(" · ")}
          </p>
          <div style={{ overflowX: "auto" }}>
            <table className="tbl" style={{ marginTop: 8 }}>
              <thead>
                <tr>
                  <th>Player</th><th>Team</th><th>Line</th><th>PP</th><th>TOI</th><th>Shots</th><th>Points</th><th>Goals</th><th>Assists</th><th>Hits</th><th>Blocks</th><th>Scores</th>
                </tr>
              </thead>
              <tbody>
                {g.projections.map((p) => (
                  <tr key={p.player + p.team}>
                    <td>{p.player}</td><td>{p.team}</td><td>{p.line ?? ""}</td><td>{p.pp ?? ""}</td>
                    <td className="num">{p.toi_min.toFixed(1)}</td><td className="num">{p.sog.toFixed(2)}</td><td className="num">{p.pts.toFixed(2)}</td>
                    <td className="num">{p.goals.toFixed(2)}</td><td className="num">{p.ast.toFixed(2)}</td><td className="num">{p.hits.toFixed(2)}</td>
                    <td className="num">{p.blk.toFixed(2)}</td><td className="num">{pct(p.atg)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  );
}

function ModelTab() {
  return (
    <>
      {slate.games.map((g) => (
        <section className="panel" key={g.id}>
          <GameHead g={g} />
          {[g.away, g.home].map((t) => (
            <div key={t} style={{ marginTop: 12 }}>
              <p className="sub" style={{ margin: 0 }}>
                <b>{t}</b>: {g.expected[t].goals.toFixed(2)} expected goals before empty net and overtime · {g.expected[t].sog.toFixed(1)} shots ·{" "}
                {g.expected[t].pp_min.toFixed(1)} power-play minutes
              </p>
              <ul className="sub" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {g.expected[t].steps.map((s) => (
                  <li key={s.what}>
                    {s.what}: {s.value != null ? s.value.toFixed(2) : `x${(s.factor ?? 1).toFixed(3)}`}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="sub" style={{ marginTop: 12 }}>
            Model chances: {Object.entries(g.fair.moneyline).map(([k, v]) => `${k} wins ${pct(v.prob)}`).join(" · ")} ·{" "}
            {Object.entries(g.fair.totals).map(([k, v]) => `${k} ${pct(v.prob)}`).join(" · ")}
          </p>
        </section>
      ))}
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Rules</h2>
          </div>
        </div>
        <ul className="sub" style={{ paddingLeft: 18 }}>
          <li>Every game is simulated {slate.sims.toLocaleString()} times before any prop is set. Props are drawn inside those same games.</li>
          <li>A slip&apos;s chance is the share of simulated games in which every leg hits, never the legs multiplied.</li>
          <li>Slip legs are floor rungs at {pct(slate.floor)} or better (saves 85%), from shots, points, assists, goals, hits, blocks, saves, moneyline, puck line and total.</li>
          <li>Matchups first: each leg is marked strong, neutral or weak from tonight&apos;s opponent, rink and game script. Weak matchups stay off; a strong one may take a higher listed rung.</li>
          <li>Every leg carries the price a book lists for that exact rung (FanDuel, then BetMGM). A rung no book lists is not used. Odds never choose a leg.</li>
          <li>The lotto ticket is the exception to the floor: listed longshot rungs on purpose, at +5000 or longer on the book&apos;s leg prices.</li>
          <li>No confirmed starting goalie, no leg on that game&apos;s total, saves or scoring props. No game-day lines, no legs on that team&apos;s skaters.</li>
          <li>Picks come only from the Godseye NHL algorithm. No expert, media or consensus picks.</li>
        </ul>
      </section>
    </>
  );
}

export default function NhlApp({ prefix = "" }: { prefix?: string } = {}) {
  const rawHash = useSyncExternalStore(subscribeHash, readHash, () => "");
  const hash = rawHash.startsWith(prefix) ? rawHash.slice(prefix.length) : "";
  const tab: Tab = (TABS as readonly string[]).includes(hash) ? (hash as Tab) : "home";
  const nav: [Tab, string, string][] = [
    ["home", "Home", "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"],
    ["sgp", "Game slips", "M8 12h8M12 8v8M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0"],
    ["multi", "Multi-game & lotto", "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5"],
    ["cashed", "Cashed slips", "M5 12l4 4 10-10M4 20h16"],
    ["board", "Projection board", "M4 6h16M4 12h16M4 18h10"],
    ["model", "Model & rules", "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"],
  ];
  return (
    <div className="wrap">
      <header className="mast">
        <div className="brand">
          <Logo />
          <p id="meta">
            NHL · {slate.games.length} games · built {builtAt(slate.made_at)}
          </p>
        </div>
        <div className="topright">
          <nav className="sports" aria-label="Sport">
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/">Home</a>
            <a href="/nfl">NFL</a>
            <a href="/nba">NBA</a>
            <a href="/nhl" aria-current="page">
              NHL
            </a>
          </nav>
          <span className="livechip">
            <i></i> Model-only, no media picks
          </span>
        </div>
      </header>
      <div className="layout">
        <nav className="tabs" aria-label="Views">
          {nav.map(([id, label, d]) => (
            <a href={`#${prefix}${id}`} aria-current={tab === id ? "page" : "false"} key={id}>
              <Icon d={d} />
              {label}
            </a>
          ))}
        </nav>
        <div style={{ minWidth: 0 }}>
          {tab === "home" && <HomeTab prefix={prefix} />}
          {tab === "sgp" && slate.games.map((g) => <GamePanel g={g} key={g.id} />)}
          {tab === "multi" && <MultiTab />}
          {tab === "cashed" && <CashedTab />}
          {tab === "board" && <BoardTab />}
          {tab === "model" && <ModelTab />}
        </div>
      </div>
      <footer className="foot">
        For adults of legal betting age in their province. Model output is information, not a promise: most bettors lose over time. If
        gambling is causing you harm, free and confidential help is available in every province:{" "}
        <a href="/responsible-gambling">where to get help</a>. <a href="/terms">Terms</a> · <a href="/privacy">Privacy</a>
      </footer>
    </div>
  );
}
