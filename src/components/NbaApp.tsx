"use client";

import { useState, useSyncExternalStore } from "react";
import { Logo } from "@/components/Logo";
import raw from "../../model/nba/output/nba_site.json";
import rawTrack from "../../model/nba/output/nba_track.json";

/* The NBA side of the console. It mirrors the NFL console's layout and reads the latest slate
   written by `python3 -m nba.run_slate` (model/nba/output/nba_site.json). */

type Leg = { label: string; p: number; price: number | null; reason: string | null; ev?: number | null; kelly_stake?: number | null };
type Ticket = {
  id: string;
  type: string;
  joint: number;
  naive: number;
  book_price: number | null;
  fair_price: number;
  ev: number | null;
  price_is_estimate: boolean;
  legs: Leg[];
};
type Player = {
  name: string;
  team: string;
  status: string;
  role: string;
  role_change: string;
  min_mean: number;
  min_p10: number;
  min_p90: number;
  pts: number;
  reb: number;
  ast: number;
  fg3m: number;
  stl: number;
  blk: number;
  gate_pts: number;
  gate_fg3m: number;
  blowout_exposure: number;
  inout_notes: string;
  adjustments: string[];
};
type Three = { ours: number; market: number | null; blend: number };
type Game = {
  id: string;
  home: string;
  away: string;
  tip_utc: string;
  preview: boolean;
  notes: string[];
  tickets: Ticket[];
  singles: Leg[];
  players: Player[];
  availability: { name: string; status: string; reason: string | null }[];
  card: {
    pace: { ours: number };
    margin_home: Three;
    total: Three;
    market_weight: number;
    win_prob_home: number;
    blowout_prob: number;
    close_prob: number;
    blowout_warning: boolean;
    scripts: { script: string; probability: number; who: string; players: string }[];
  };
};
type Multi = {
  id: string;
  type: string;
  n_legs: number;
  joint: number;
  fair_price: number;
  book_price: number | null;
  ev: number | null;
  parts: { matchup: string; joint: number; legs: Leg[] }[];
};
const slate = raw as unknown as { run_at: string; n_sims: number; games: Game[]; book: string | null; multi: Multi[] };
type TrackLeg = { label: string; p: number; price: number | null; result: string; actual: number | null };
type TrackTicket = { id: string; game: string; type: string; result: string; joint: number; price: number | null; hit: number; n: number; legs: TrackLeg[] };
const track = rawTrack as unknown as {
  made_at: string;
  slates: { date: string; issued_at: string; graded: number; won: number; tickets: TrackTicket[] }[];
  totals: Record<string, { tickets: number; won: number; expected: number; units: number }>;
};
const BOOK = slate.book === "draftkings" ? "DraftKings" : slate.book === "bet365" ? "bet365" : "the book";

const TABS = ["home", "sgp", "multi", "track", "board", "scripts", "avail", "model"] as const;
type Tab = (typeof TABS)[number];

const TICKET_NAMES: Record<string, string> = {
  props_4: "4-leg props SGP",
  props_6: "6-leg props SGP",
  props_8: "8-leg props SGP",
  multi_12: "12 props, 3 games",
  multi_15: "15 props, 3 games",
  game_script: "Game-script SGP",
  double_double: "Double-double ticket",
};

function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}
const readHash = () => window.location.hash.slice(1);
// Tab links are "#sgp" on the site and "#nba-sgp" in the single-file preview, where NFL and NBA share one page.

const pct = (p: number | null | undefined, d = 0) => (p == null ? "n/a" : `${(p * 100).toFixed(d)}%`);
const signed = (v: number | null | undefined) => (v == null ? "n/a" : `${v > 0 ? "+" : ""}${v.toFixed(1)}`);
const american = (a: number | null | undefined) => (a == null ? "no price" : a > 0 ? `+${a}` : `−${Math.abs(a)}`);
const heat = (p: number) => (p >= 0.85 ? 5 : p >= 0.75 ? 4 : p >= 0.65 ? 3 : p >= 0.5 ? 2 : 1);

function tipTime(iso: string) {
  return new Date(iso).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" }) + " ET";
}
function builtAt(iso: string) {
  return (
    new Date(iso).toLocaleString("en-CA", {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZone: "America/Toronto",
    }) + " ET"
  );
}

function Icon({ d }: { d: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

function Prob({ p }: { p: number }) {
  return (
    <span className="prob" data-heat={heat(p)}>
      {pct(p)}
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  const cls = status === "confirmed_in" ? "good" : status === "out" || status === "doubtful" ? "bad" : status === "questionable" ? "warn" : "neutral";
  return <span className={`pill ${cls}`}>{status.replace("_", " ")}</span>;
}

function TicketCard({ t, game }: { t: Ticket; game: Game }) {
  const kind = t.type.replace("preview_", "");
  return (
    <div className="ticket">
      <div className="top">
        <span className="legsn" style={{ fontSize: 20 }}>
          {TICKET_NAMES[kind] ?? kind}
        </span>
        <span className="fair num">{t.book_price == null ? `fair ${american(t.fair_price)}` : american(t.book_price)}</span>
      </div>
      <div className="pct">
        Model chance all legs hit: <b>{pct(t.joint, 1)}</b> · multiplying the legs would say {pct(t.naive, 1)}
        {t.ev != null && <> · expected value {signed(t.ev * 100)}%</>}
      </div>
      <ol>
        {t.legs.map((l) => (
          <li key={l.label}>
            {l.label} <Prob p={l.p} /> {l.price != null && <span className="num">{american(l.price)}</span>}
            <small>{l.reason}</small>
          </li>
        ))}
      </ol>
      {game.preview ? (
        <span className="pill warn">Model-only: rung and price not checked at bet365</span>
      ) : (
        <>
          {t.price_is_estimate && (
            <span className="pill neutral">
              Price is {BOOK}&apos;s leg prices multiplied together. Its same-game price will be lower.
            </span>
          )}
          {t.ev != null && t.ev < 0 && (
            <span className="pill neutral">
              The model rates this below {BOOK}&apos;s price. On the first graded slate the book&apos;s prices were the more accurate.
            </span>
          )}
        </>
      )}
    </div>
  );
}

function GameHeader({ g }: { g: Game }) {
  const c = g.card;
  return (
    <>
      <div className="section-head">
        <div>
          <h2>
            {g.away} @ {g.home}
          </h2>
          <p className="sub">Tip {tipTime(g.tip_utc)}</p>
        </div>
      </div>
      <div className="envline">
        <span className="pill gold">
          {c.margin_home.blend >= 0 ? g.home : g.away} by {Math.abs(c.margin_home.blend).toFixed(1)}
        </span>
        <span className="pill">Total {c.total.blend.toFixed(1)}</span>
        <span className="pill">
          {g.home} win {pct(c.win_prob_home)}
        </span>
        <span className={`pill ${c.blowout_warning ? "bad" : ""}`}>Blowout {pct(c.blowout_prob)}</span>
        <span className="pill">Close game {pct(c.close_prob)}</span>
      </div>
    </>
  );
}

function ScriptCard({ g }: { g: Game }) {
  const c = g.card;
  return (
    <section className="panel" id={`g-${g.id}`}>
      <GameHeader g={g} />
      <div className="scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th></th>
              <th>Our number</th>
              <th>Market</th>
              <th>Blend</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{g.home} margin</td>
              <td className="num">{signed(c.margin_home.ours)}</td>
              <td className="num">{signed(c.margin_home.market)}</td>
              <td className="num">{signed(c.margin_home.blend)}</td>
            </tr>
            <tr>
              <td>Total points</td>
              <td className="num">{c.total.ours.toFixed(1)}</td>
              <td className="num">{c.total.market == null ? "n/a" : c.total.market.toFixed(1)}</td>
              <td className="num">{c.total.blend.toFixed(1)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="sub">
        Pace {c.pace.ours} possessions.{" "}
        {c.margin_home.market == null
          ? "No market line was available, so the blend is our number alone."
          : `The blend leans ${pct(c.market_weight)} on the market.`}
      </p>
      <h3 style={{ marginTop: 14 }}>Most likely scripts</h3>
      <ul className="nba-scripts">
        {c.scripts.map((s) => (
          <li key={s.script}>
            <Prob p={s.probability} />
            <span>
              {s.script}
              <small>{s.who}</small>
              {s.players && <small>{s.players}</small>}
            </span>
          </li>
        ))}
      </ul>
      {c.blowout_warning && (
        <div className="warns" style={{ marginTop: 12 }}>
          <div>
            Blowout warning: starters&apos; higher rungs are left off tickets and every leg must still clear 70% inside the simulated blowouts.
          </div>
        </div>
      )}
    </section>
  );
}

function HomeTab({ prefix }: { prefix: string }) {
  const tickets = slate.games.flatMap((g) => g.tickets.map((t) => ({ g, t })));
  const best = [...tickets].filter((x) => x.t.type.endsWith("props_4")).sort((a, b) => b.t.joint - a.t.joint).slice(0, 3);
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Tonight&apos;s NBA slate</h2>
            <p className="sub">
              {slate.games.length} games · built {builtAt(slate.run_at)} · {slate.n_sims.toLocaleString()} simulated games each
            </p>
          </div>
        </div>
        <div className="nba-grid">
          {slate.games.map((g) => (
            <a className="nba-card" href={`#${prefix}scripts`} key={g.id}>
              <h3>
                {g.away} @ {g.home}
              </h3>
              <span className="sub">Tip {tipTime(g.tip_utc)}</span>
              <span>
                <span className="pill gold">
                  {g.card.margin_home.blend >= 0 ? g.home : g.away} by {Math.abs(g.card.margin_home.blend).toFixed(1)}
                </span>{" "}
                <span className="pill">Total {g.card.total.blend.toFixed(1)}</span>{" "}
                <span className={`pill ${g.card.blowout_warning ? "bad" : ""}`}>Blowout {pct(g.card.blowout_prob)}</span>
              </span>
              <span className="sub">
                {g.tickets.length ? `${g.tickets.length} tickets` : "No bet"} · {g.availability.filter((a) => a.status === "questionable").length} questionable
              </span>
            </a>
          ))}
        </div>
      </section>
      {best.length > 0 && (
        <section className="panel">
          <div className="section-head">
            <div>
              <h2>Highest-probability 4-leg tickets</h2>
              <p className="sub">Ranked by the model&apos;s chance that every leg hits. All game tickets are under Game SGPs.</p>
            </div>
          </div>
          <div className="nba-tickets">
            {best.map(({ g, t }) => (
              <div key={t.id}>
                <p className="sub" style={{ margin: "0 0 6px" }}>
                  {g.away} @ {g.home}
                </p>
                <TicketCard t={t} game={g} />
              </div>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function SgpTab() {
  const anyPreview = slate.games.some((g) => g.preview);
  return (
    <>
      {anyPreview && (
        <section className="panel">
          <div className="warns">
            <div>
              These are model-only tickets. No bet365 prices are loaded yet, so the thresholds are standard milestones (10+, 15+, 20+ and so
              on), not rungs read from the book. Check that each rung exists and what it pays before you place anything. Only players
              cleared on the official injury report are used.
            </div>
          </div>
        </section>
      )}
      {slate.games.map((g) => (
        <section className="panel" key={g.id}>
          <GameHeader g={g} />
          {g.tickets.length > 0 ? (
            <div className="nba-tickets" style={{ marginTop: 12 }}>
              {g.tickets.map((t) => (
                <TicketCard t={t} game={g} key={t.id} />
              ))}
            </div>
          ) : (
            <p className="empty">No bet for this game.</p>
          )}
          {g.notes
            .filter((n) => !n.startsWith("MODEL-ONLY"))
            .map((n) => (
              <p className="sub" key={n}>
                {n.replace("game_script:", "Game-script ticket:").replace("double_double:", "Double-double ticket:").replace("props_4:", "4-leg ticket:").replace("props_6:", "6-leg ticket:")}
              </p>
            ))}
          {g.singles.length > 0 && (
            <>
              <h3 style={{ marginTop: 14 }}>Singles (edge rungs, straight bets only)</h3>
              <div className="scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Leg</th>
                      <th>Model</th>
                      <th>Book</th>
                      <th>Expected value</th>
                      <th>Stake (quarter Kelly)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.singles.map((s) => (
                      <tr key={s.label}>
                        <td>{s.label}</td>
                        <td>
                          <Prob p={s.p} />
                        </td>
                        <td className="num">{american(s.price)}</td>
                        <td className="num">{signed((s.ev ?? 0) * 100)}%</td>
                        <td className="num">{pct(s.kelly_stake, 2)} of bankroll</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      ))}
    </>
  );
}

function MultiTab() {
  if (!slate.multi?.length)
    return (
      <section className="panel">
        <p className="empty">No multi-game slip today: it needs prices and qualifying tickets in at least three games.</p>
      </section>
    );
  return (
    <>
      <section className="panel">
        <p className="sub" style={{ margin: 0 }}>
          The strongest ticket from each of the three best games, joined into one slip. Games do not affect each other, so the
          slip&apos;s chance is each game&apos;s counted chance multiplied together. Prices are {BOOK}&apos;s leg prices.
        </p>
      </section>
      {slate.multi.map((m) => (
        <section className="panel" key={m.id}>
          <div className="section-head">
            <div>
              <h2>
                {m.n_legs} props across {m.parts.length} games
              </h2>
              <p className="sub">
                Model chance every leg hits: <b>{pct(m.joint, 1)}</b> · fair {american(m.fair_price)} · leg prices multiplied{" "}
                {american(m.book_price)}
              </p>
            </div>
            {m.ev != null && <span className="pill neutral">Model vs price {signed(m.ev * 100)}%</span>}
          </div>
          <div className="nba-tickets">
            {m.parts.map((p) => (
              <div className="ticket" key={p.matchup}>
                <div className="top">
                  <span className="legsn" style={{ fontSize: 20 }}>
                    {p.matchup}
                  </span>
                  <span className="fair num">{pct(p.joint)}</span>
                </div>
                <ol>
                  {p.legs.map((l) => (
                    <li key={l.label}>
                      {l.label} <Prob p={l.p} /> <span className="num">{american(l.price)}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

function ResultPill({ r }: { r: string }) {
  const cls = r === "won" ? "good" : r === "lost" ? "bad" : r === "pending" ? "gold" : "neutral";
  return <span className={`pill ${cls}`}>{r === "won" ? "Cashed" : r === "lost" ? "Lost" : r === "pending" ? "Pending" : "Void"}</span>;
}

function TrackTab() {
  const [open, setOpen] = useState<string | null>(null);
  const order = ["props_4", "props_6", "props_8", "multi_12", "multi_15"];
  const rows = order.filter((k) => track.totals[k]).map((k) => ({ k, ...track.totals[k] }));
  const all = rows.reduce((a, r) => ({ tickets: a.tickets + r.tickets, won: a.won + r.won, expected: a.expected + r.expected, units: a.units + r.units }), { tickets: 0, won: 0, expected: 0, units: 0 });
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Track record</h2>
            <p className="sub">Every slip issued here, graded from the official box score. Updated {builtAt(track.made_at)}.</p>
          </div>
        </div>
        {rows.length === 0 ? (
          <p className="empty">Nothing graded yet.</p>
        ) : (
          <div className="scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Slip</th>
                  <th>Graded</th>
                  <th>Cashed</th>
                  <th>Model expected</th>
                  <th>Units at 1 per slip</th>
                </tr>
              </thead>
              <tbody>
                {[...rows, { k: "all", ...all }].map((r) => (
                  <tr key={r.k}>
                    <td>{r.k === "all" ? <b>All slips</b> : (TICKET_NAMES[r.k] ?? r.k)}</td>
                    <td className="num">{r.tickets}</td>
                    <td className="num">{r.won}</td>
                    <td className="num">{r.expected.toFixed(1)}</td>
                    <td className="num">{signed(r.units)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="sub">
          Units use {BOOK}&apos;s leg prices multiplied together; a real same-game price pays less. A short record like this one is mostly
          luck in either direction.
        </p>
      </section>
      {track.slates.map((sl) => (
        <section className="panel" key={sl.date}>
          <div className="section-head">
            <div>
              <h2>{new Date(sl.date + "T12:00:00Z").toLocaleDateString("en-CA", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" })}</h2>
              <p className="sub">
                Issued {builtAt(sl.issued_at)} · {sl.graded ? `${sl.won} of ${sl.graded} cashed` : `${sl.tickets.length} slips pending`}
              </p>
            </div>
          </div>
          <div className="scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Game</th>
                  <th>Slip</th>
                  <th>Result</th>
                  <th>Legs hit</th>
                  <th>Model chance</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {sl.tickets.map((t) => (
                  <TrackRow key={t.id} t={t} open={open === t.id} toggle={() => setOpen(open === t.id ? null : t.id)} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  );
}

function TrackRow({ t, open, toggle }: { t: TrackTicket; open: boolean; toggle: () => void }) {
  return (
    <>
      <tr onClick={toggle} style={{ cursor: "pointer" }}>
        <td>{t.game}</td>
        <td>{TICKET_NAMES[t.type] ?? t.type}</td>
        <td>
          <ResultPill r={t.result} />
        </td>
        <td className="num">{t.result === "pending" ? `${t.n} legs` : `${t.hit} of ${t.n}`}</td>
        <td className="num">{pct(t.joint, 1)}</td>
        <td className="num">{american(t.price)}</td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6}>
            <ul className="why">
              {t.legs.map((l) => (
                <li key={l.label}>
                  {l.label} · model {pct(l.p)} · {american(l.price)} · <ResultPill r={l.result} />
                  {l.actual != null && l.result !== "void" ? ` (finished with ${l.actual})` : ""}
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  );
}

function BoardTab() {
  const [gid, setGid] = useState(slate.games[0]?.id ?? "");
  const [open, setOpen] = useState<string | null>(null);
  const g = slate.games.find((x) => x.id === gid) ?? slate.games[0];
  if (!g) return <section className="panel"><p className="empty">No games on the slate.</p></section>;
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Projection board</h2>
          <p className="sub">Averages across the simulated games, if the player takes the floor. Click a row for the adjustments behind it.</p>
        </div>
        <select className="nba-select" value={g.id} onChange={(e) => setGid(e.target.value)} aria-label="Game">
          {slate.games.map((x) => (
            <option key={x.id} value={x.id}>
              {x.away} @ {x.home}
            </option>
          ))}
        </select>
      </div>
      <div className="scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Player</th>
              <th>Status</th>
              <th>Role</th>
              <th>Minutes (10th to 90th)</th>
              <th>PTS</th>
              <th>REB</th>
              <th>AST</th>
              <th>3PM</th>
              <th>STL</th>
              <th>BLK</th>
              <th>Shooting gate</th>
            </tr>
          </thead>
          <tbody>
            {g.players.map((p) => (
              <FragmentRow key={p.name} p={p} open={open === p.name} toggle={() => setOpen(open === p.name ? null : p.name)} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FragmentRow({ p, open, toggle }: { p: Player; open: boolean; toggle: () => void }) {
  return (
    <>
      <tr onClick={toggle} style={{ cursor: "pointer" }}>
        <td>
          <b>{p.name}</b> <span className="sub">{p.team}</span>
        </td>
        <td>
          <StatusPill status={p.status} />
        </td>
        <td>{p.role}</td>
        <td className="num">
          {p.min_mean.toFixed(1)} ({p.min_p10.toFixed(0)} to {p.min_p90.toFixed(0)})
        </td>
        <td className="num">{p.pts.toFixed(1)}</td>
        <td className="num">{p.reb.toFixed(1)}</td>
        <td className="num">{p.ast.toFixed(1)}</td>
        <td className="num">{p.fg3m.toFixed(1)}</td>
        <td className="num">{p.stl.toFixed(1)}</td>
        <td className="num">{p.blk.toFixed(1)}</td>
        <td>
          <span className={`pill ${p.gate_pts ? "good" : "neutral"}`}>points {p.gate_pts ? "pass" : "fail"}</span>{" "}
          <span className={`pill ${p.gate_fg3m ? "good" : "neutral"}`}>threes {p.gate_fg3m ? "pass" : "fail"}</span>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={11}>
            <div className="why">
              {p.role_change && (
                <p>
                  <b>Role change:</b> {p.role_change}
                </p>
              )}
              <p>
                <b>What moved the projection from baseline:</b>
              </p>
              <ul>
                {p.adjustments.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              {p.inout_notes && (
                <p>
                  <b>Teammates in and out:</b> {p.inout_notes}
                </p>
              )}
              <p>
                <b>Blowout exposure:</b> {pct(p.blowout_exposure)} of his points, rebounds and assists are lost in simulated blowouts.
              </p>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function AvailTab() {
  return (
    <>
      <section className="panel">
        <p className="sub" style={{ margin: 0 }}>
          From the official NBA injury report as of {builtAt(slate.run_at)}. Only players marked available, or not listed on a report their
          team has filed, can go on a ticket. Everyone else is held off until a later report clears them.
        </p>
      </section>
      {slate.games.map((g) => (
        <section className="panel" key={g.id}>
          <div className="section-head">
            <div>
              <h2>
                {g.away} @ {g.home}
              </h2>
            </div>
          </div>
          {g.availability.length === 0 ? (
            <p className="empty">Everyone on both rosters is cleared.</p>
          ) : (
            <div className="scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Status</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {g.availability.map((a) => (
                    <tr key={a.name}>
                      <td>{a.name}</td>
                      <td>
                        <StatusPill status={a.status} />
                      </td>
                      <td>{a.reason ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </>
  );
}

function ModelTab() {
  const rules = [
    ["Algorithm only", "Every pick comes from the model's own output. No expert, media or consensus picks."],
    ["No verified availability, no leg", "A player without a cleared status on the official injury report cannot be on a ticket."],
    ["70% floor", "Every same-game parlay leg must have a model chance of 70% or better. Lower-chance value rungs are straight singles only."],
    ["Three props tickets per game", "A 4-leg, a 6-leg and an 8-leg from points, rebounds, assists and threes, best legs from either team."],
    ["Only rungs the book lists", "Legs are milestone rungs read from the book's ladder, each checked against the player's over/under line."],
    ["Game script first", "The game is simulated before any player number. Blowout risk is checked before a leg is considered."],
    ["Counted, never multiplied", "A ticket's chance is the share of simulated games in which every leg hits."],
    ["Every number explained", "Each projection lists what moved it from the player's baseline."],
  ];
  const tested = [
    ["Legs the model called 70 to 80%", "hit 77.1%", "79,294 legs"],
    ["Legs the model called 80 to 90%", "hit 86.3%", "71,821 legs"],
    ["Final margin inside the simulated 10 to 90% band", "79.4% of games", "target 80%"],
    ["Blowouts", "predicted 45.7%, actual 47.0%", "2,462 games"],
    ["4-leg tickets", "modelled 63.0%, hit 64.8%", "2,462 tickets"],
    ["6-leg tickets", "modelled 46.4%, hit 51.0%", "2,462 tickets"],
  ];
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>How the NBA model works</h2>
            <p className="sub">Each game is played 10,000 times. Players are simulated inside those same games.</p>
          </div>
        </div>
        <ol>
          <li>Availability: who is cleared, questionable or out, from the official injury report.</li>
          <li>Game script: pace, margin and total, blended with the market line, then 10,000 simulated games.</li>
          <li>Minutes: each player&apos;s minutes in each simulated game, including who sits in a blowout.</li>
          <li>Rates: per-minute shots, rebounds, assists, steals and blocks, moved by recent form, the opponent and who is out.</li>
          <li>Player simulation: each simulated game&apos;s team totals are shared out among the players on the floor.</li>
          <li>Tickets: legs that clear the rules, combined by their joint chance.</li>
        </ol>
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Rules</h2>
          </div>
        </div>
        <div className="scroll">
          <table className="tbl">
            <tbody>
              {rules.map(([a, b]) => (
                <tr key={a}>
                  <td>
                    <b>{a}</b>
                  </td>
                  <td>{b}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>How it tested</h2>
            <p className="sub">Walk-forward over 2024-25 and 2025-26, using only what was known before each tip-off.</p>
          </div>
        </div>
        <div className="scroll">
          <table className="tbl">
            <tbody>
              {tested.map(([a, b, c]) => (
                <tr key={a}>
                  <td>{a}</td>
                  <td className="num">{b}</td>
                  <td className="sub">{c}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="warns" style={{ marginTop: 12 }}>
          <div>
            The test measured how often legs hit, not profit. There were no historical bet365 prices to test against, so nothing here shows
            the model beats the book. Known weak spots: double-doubles and triple-doubles are under-forecast, and the model has no data on
            defensive schemes or individual matchups.
          </div>
        </div>
      </section>
    </>
  );
}

export default function NbaApp({ prefix = "" }: { prefix?: string } = {}) {
  const raw_hash = useSyncExternalStore(subscribeHash, readHash, () => "");
  const hash = raw_hash.startsWith(prefix) ? raw_hash.slice(prefix.length) : "";
  const tab: Tab = (TABS as readonly string[]).includes(hash) ? (hash as Tab) : "home";
  const nav: [Tab, string, string][] = [
    ["home", "Home", "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"],
    ["sgp", "Game SGPs", "M8 12h8M12 8v8M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0"],
    ["multi", "Multi-game slips", "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5"],
    ["track", "Track record", "M5 20V10M12 20V4M19 20v-7"],
    ["board", "Projection board", "M4 6h16M4 12h16M4 18h10"],
    ["scripts", "Game scripts", "M4 5h16M4 12h10M4 19h16M17 9l3 3-3 3"],
    ["avail", "Availability", "M4 12l5 5L20 6"],
    ["model", "Model & rules", "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"],
  ];
  return (
    <div className="wrap">
      <header className="mast">
        <div className="brand">
          <Logo />
          <p id="meta">
            NBA · {slate.games.length} games · built {builtAt(slate.run_at)}
          </p>
        </div>
        <div className="topright">
          {/* Plain links on purpose: each sport page loads its own data and scripts, so switching is a full page load. */}
          <nav className="sports" aria-label="Sport">
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/">Home</a>
            <a href="/nfl">NFL</a>
            <a href="/nba" aria-current="page">
              NBA
            </a>
          </nav>
          <span className="livechip">
            <i></i> Model-only, no media picks
          </span>
        </div>
      </header>
      <div className="layout">
        <nav className="tabs" aria-label="Views">
          {nav.map(([id, label, d], i) => (
            <span key={id} style={{ display: "contents" }}>
              {i === 1 && <span className="navgrp">Picks</span>}
              {i === 4 && <span className="navgrp">Tools</span>}
              {i === 7 && <span className="navgrp">Model</span>}
              <a href={`#${prefix}${id}`} aria-current={tab === id ? "page" : "false"}>
                <Icon d={d} />
                {label}
              </a>
            </span>
          ))}
        </nav>
        <div style={{ minWidth: 0 }}>
          {tab === "home" && <HomeTab prefix={prefix} />}
          {tab === "sgp" && <SgpTab />}
          {tab === "multi" && <MultiTab />}
          {tab === "track" && <TrackTab />}
          {tab === "board" && <BoardTab />}
          {tab === "scripts" && slate.games.map((g) => <ScriptCard g={g} key={g.id} />)}
          {tab === "avail" && <AvailTab />}
          {tab === "model" && <ModelTab />}
        </div>
      </div>
      <footer className="foot">
        For adults of legal betting age in their province. Model output is information, not a promise: most bettors lose over time. If
        gambling is causing you harm, free and confidential help is available in every province.
      </footer>
    </div>
  );
}
