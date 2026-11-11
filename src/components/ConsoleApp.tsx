"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Logo } from "@/components/Logo";
import {
  averageClv,
  betDecimal,
  betProfit,
  betType,
  decimalToAmerican,
  formatAmerican,
  groupBy,
  parseSlip,
  summarize,
  type Bet,
  type Leg,
  type Status,
  type Summary,
} from "@/lib/bets";
import { checkSlip } from "@/lib/slip";
import predictions from "../../model/output/predictions.json";
import backtest from "../../model/output/backtest.json";

/* The eight console tabs are drawn by /console/app.js into #main.
   The four tracker tabs below are drawn by React into #extra. */
const EXTRA_TABS = ["paste", "bets", "report", "games"] as const;
type ExtraTab = (typeof EXTRA_TABS)[number];

declare global {
  interface Window {
    GE_EXTRA_TABS?: readonly string[];
    __geConsoleLoading?: boolean;
    /** Set by the single-file preview build, where the console scripts are already on the page. */
    GE_INLINE?: boolean;
  }
}

// ---------- bets store (this browser's storage, until accounts exist) ----------
const STORE = "godseye.bets.v1";
const EMPTY: Bet[] = [];
const listeners = new Set<() => void>();
let cache: Bet[] | null = null;

function readBets(): Bet[] {
  if (cache === null) {
    try {
      cache = JSON.parse(localStorage.getItem(STORE) ?? "[]") as Bet[];
    } catch {
      cache = [];
    }
  }
  return cache;
}
function writeBets(next: Bet[]) {
  cache = next;
  try {
    localStorage.setItem(STORE, JSON.stringify(next));
  } catch {
    /* storage unavailable: keep in memory for this visit */
  }
  listeners.forEach((l) => l());
}
function subscribeBets(cb: () => void) {
  // The console's "Track this bet" button writes to storage and fires this event.
  const reload = () => {
    cache = null;
    cb();
  };
  listeners.add(cb);
  window.addEventListener("ge-bets", reload);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("ge-bets", reload);
  };
}

function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}
const readHash = () => window.location.hash.slice(1);

function loadScript(src: string) {
  return new Promise<void>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Could not load ${src}`));
    document.body.appendChild(s);
  });
}

const money = (n: number) => `${n < 0 ? "−" : ""}$${Math.abs(n).toFixed(2)}`;
const pct = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n * 100).toFixed(1)}%`;

const heat = (p: number) => (p >= 0.8 ? 5 : p >= 0.65 ? 4 : p >= 0.5 ? 3 : p >= 0.35 ? 2 : 1);

function Icon({ d, circle }: { d: string; circle?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      {circle ? <circle cx="12" cy="12" r={circle} /> : null}
      <path d={d} />
    </svg>
  );
}

export default function ConsoleApp({ eyeSrc, homeHref }: { eyeSrc?: string; homeHref?: string } = {}) {
  const hash = useSyncExternalStore(subscribeHash, readHash, () => "");
  const extra = (EXTRA_TABS as readonly string[]).includes(hash) ? (hash as ExtraTab) : null;
  const bets = useSyncExternalStore(subscribeBets, readBets, () => EMPTY);
  const setBets = (fn: (prev: Bet[]) => Bet[]) => writeBets(fn(readBets()));
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (window.__geConsoleLoading) return;
    window.__geConsoleLoading = true;
    window.GE_EXTRA_TABS = EXTRA_TABS;
    if (window.GE_INLINE) return;
    loadScript("/console/data.js")
      .then(() => loadScript("/console/app.js"))
      .catch(() =>
        setLoadError(
          "The picks data did not load. Check your connection and reload the page. Your saved bets are not affected.",
        ),
      );
  }, []);

  return (
    <div className="wrap">
      <header className="mast">
        <div className="brand">
          <Logo eyeSrc={eyeSrc} href={homeHref} />
          <p id="meta"></p>
        </div>
        <div className="topright">
          <span className="livechip">
            <i></i> Model-only, no media picks
          </span>
          <span className="livechip" id="recchip"></span>
        </div>
      </header>

      <button className="fab" id="fab" aria-controls="slip" aria-expanded="false">
        <span className="cnt" id="fabcnt">
          0
        </span>
        <span>Bet slip</span>
        <span className="fp" id="fabp"></span>
      </button>
      <div className="scrim" id="scrim" hidden></div>
      <aside className="slip panel" id="slip" aria-label="Bet slip" role="dialog" aria-modal="false"></aside>

      <div className="layout">
        <nav className="tabs" aria-label="Views">
          <a href="#home" data-tab="home">
            <Icon d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />
            Home
          </a>
          <span className="navgrp">Picks</span>
          <a href="#picks" data-tab="picks">
            <Icon d="M4 19h16M6 15l4-6 4 3 4-7" />
            Algorithm picks
          </a>
          <a href="#sgp" data-tab="sgp">
            <Icon d="M8 12h8M12 8v8" circle={9} />
            Game SGPs
          </a>
          <a href="#board" data-tab="board">
            <Icon d="M4 6h16M4 12h16M4 18h10" />
            ATD board
          </a>
          <span className="navgrp">Build</span>
          <a href="#mysgp" data-tab="mysgp">
            <Icon d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5" />
            Build your SGP
          </a>
          <a href="#build" data-tab="build">
            <Icon d="M12 5v14M5 12h14" />
            Quick add
          </a>
          <a href="#audit" data-tab="audit">
            <Icon d="M4 12l5 5L20 6" />
            Audit slip
          </a>
          <span className="navgrp">Track</span>
          <a href="#paste" data-tab="paste">
            <Icon d="M9 4h6v3H9zM7 5H5v15h14V5h-2M8 12h8M8 16h5" />
            Paste a slip
          </a>
          <a href="#bets" data-tab="bets">
            <Icon d="M4 7h16v10H4zM4 11h16M8 15h3" />
            My bets
          </a>
          <a href="#report" data-tab="report">
            <Icon d="M5 20V10M12 20V4M19 20v-7" />
            My report
          </a>
          <span className="navgrp">Model</span>
          <a href="#model" data-tab="model">
            <Icon
              d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"
              circle={3}
            />
            Model &amp; rules
          </a>
          <a href="#games" data-tab="games">
            <Icon d="M4 18h16M6 18V9l6-4 6 4v9M10 18v-5h4v5" />
            Game predictions
          </a>
        </nav>

        <div style={{ minWidth: 0 }}>
          {loadError && (
            <section className="panel">
              <div className="warns">
                <div>{loadError}</div>
              </div>
            </section>
          )}
          <main id="main"></main>
          <div id="extra" hidden={!extra}>
            {extra === "paste" && (
              <PasteTab
                onSave={(b) => {
                  setBets((prev) => [b, ...prev]);
                  window.location.hash = "bets";
                }}
              />
            )}
            {extra === "bets" && <BetsTab bets={bets} setBets={setBets} />}
            {extra === "report" && <ReportTab bets={bets} />}
            {extra === "games" && <GamesTab />}
            {extra && extra !== "games" && (
              <p className="t-note">
                Your bets are saved in this browser only. They are not sent anywhere, and clearing
                your browser data removes them.
              </p>
            )}
          </div>
        </div>
      </div>

      <p className="foot">
        Probabilities come from the ATTD model (data only: play-by-play, snaps, injuries, Vegas
        lines, NWS weather; no media picks). ATD = chance of at least one rushing or receiving TD
        if he plays. Joint chances use the model&apos;s measured correlations: teammates&apos; TDs
        are negatively correlated, opponents&apos; slightly positive, and a QB&apos;s pass yards
        move with his receivers&apos; yards. Cash-out values are estimates; bet365 sets its own
        offer. godseye is not a sportsbook and cannot promise winning bets. For adults of legal
        betting age in their province (18+ or 19+). If gambling is causing you harm, free and
        confidential help is available in every province.
      </p>
    </div>
  );
}

function Head({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        {sub && <p className="sub">{sub}</p>}
      </div>
    </div>
  );
}

function PasteTab({ onSave }: { onSave: (b: Bet) => void }) {
  const [text, setText] = useState("");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("25");
  const [book, setBook] = useState("bet365");
  const [sport, setSport] = useState("NFL");
  const [parseMsg, setParseMsg] = useState("");

  const stakeNum = Number(stake) > 0 ? Number(stake) : 0;
  const valid = useMemo(
    () => legs.filter((l) => Number.isFinite(l.odds) && Math.abs(l.odds) >= 100),
    [legs],
  );
  const review = useMemo(() => checkSlip(valid, stakeNum), [valid, stakeNum]);

  const readText = () => {
    const found = parseSlip(text);
    if (!found.length) {
      setParseMsg(
        "No legs found. Put each leg on its own line and end it with the odds, like: Bills -3.5 -110",
      );
      return;
    }
    setParseMsg("");
    setLegs((prev) => [...prev, ...found]);
    setText("");
  };
  const update = (i: number, patch: Partial<Leg>) =>
    setLegs((prev) => prev.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  return (
    <div className="t-cols">
      <section className="panel">
        <Head
          title="Paste a slip"
          sub="For any bet from any book or sport, including ones the model does not cover. One leg per line, odds last."
        />
        <label className="t-field">
          <span>Your slip</span>
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Bills -3.5 -110\nJosh Allen over 249.5 pass yds -115"}
          />
        </label>
        {parseMsg && <p className="t-err">{parseMsg}</p>}
        <div className="t-row">
          <button className="btn primary" onClick={readText}>
            Add legs
          </button>
          <button
            className="btn"
            onClick={() => setLegs((p) => [...p, { description: "", odds: -110 }])}
          >
            Add a leg by hand
          </button>
        </div>

        {legs.map((l, i) => (
          <div className="t-leg" key={i}>
            <label className="t-field t-grow">
              <span>Leg {i + 1}</span>
              <input
                value={l.description}
                onChange={(e) => update(i, { description: e.target.value })}
                placeholder="Bills -3.5"
              />
            </label>
            <label className="t-field t-narrow">
              <span>Odds</span>
              <input
                inputMode="numeric"
                value={Number.isFinite(l.odds) ? String(l.odds) : ""}
                onChange={(e) =>
                  update(i, { odds: e.target.value === "" ? NaN : Number(e.target.value) })
                }
              />
            </label>
            <label className="t-field t-mid">
              <span>Game (optional)</span>
              <input
                value={l.game ?? ""}
                onChange={(e) => update(i, { game: e.target.value })}
                placeholder="BUF @ MIA"
              />
            </label>
            <button
              className="t-x"
              aria-label={`Remove leg ${i + 1}`}
              onClick={() => setLegs((p) => p.filter((_, j) => j !== i))}
            >
              Remove
            </button>
          </div>
        ))}

        {legs.length > 0 && (
          <div className="t-leg">
            <label className="t-field t-narrow">
              <span>Stake ($)</span>
              <input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} />
            </label>
            <label className="t-field t-mid">
              <span>Sportsbook</span>
              <input value={book} onChange={(e) => setBook(e.target.value)} />
            </label>
            <label className="t-field t-narrow">
              <span>Sport</span>
              <select value={sport} onChange={(e) => setSport(e.target.value)}>
                <option>NFL</option>
                <option>NBA</option>
                <option>Other</option>
              </select>
            </label>
          </div>
        )}
      </section>

      <section className="panel">
        {valid.length === 0 ? (
          <>
            <Head title="Review" />
            <p className="empty">
              Add at least one leg and the review appears here: payout, what the prices imply, and
              anything worth a second look.
            </p>
          </>
        ) : (
          <>
            <Head
              title={`${valid.length === 1 ? "Single" : `${valid.length}-leg parlay`} at ${formatAmerican(decimalToAmerican(review.decimal))}`}
            />
            <p className="t-big num">
              {money(stakeNum)} to win {money(review.toWin)}
            </p>
            <ul className="t-findings">
              {review.findings.map((f, i) => (
                <li key={i} className={f.level}>
                  <strong>{f.title}</strong>
                  <span>{f.detail}</span>
                </li>
              ))}
            </ul>
            <button
              className="btn primary"
              disabled={stakeNum <= 0}
              onClick={() =>
                onSave({
                  id: crypto.randomUUID(),
                  placedAt: new Date().toISOString(),
                  sport,
                  book: book.trim(),
                  legs: valid.map((l) => ({ ...l, description: l.description.trim() || "Leg" })),
                  stake: stakeNum,
                  status: "open",
                })
              }
            >
              Save to my bets
            </button>
            {stakeNum <= 0 && <p className="t-err">Enter a stake above zero to save this bet.</p>}
          </>
        )}
      </section>
    </div>
  );
}

function BetsTab({
  bets,
  setBets,
}: {
  bets: Bet[];
  setBets: (fn: (prev: Bet[]) => Bet[]) => void;
}) {
  const patch = (id: string, p: Partial<Bet>) =>
    setBets((prev) => prev.map((b) => (b.id === id ? { ...b, ...p } : b)));
  const [confirmId, setConfirmId] = useState<string | null>(null);

  return (
    <>
      <section className="panel">
        <Head
          title="My bets"
          sub="Bets you tracked from the bet slip or saved from Paste a slip. Mark each one when it settles."
        />
        {!bets.length && (
          <>
            <p className="empty">
              No bets tracked yet. Build a slip from the picks and press Track this bet, or paste a
              slip from your sportsbook.
            </p>
            <div className="t-row" style={{ justifyContent: "center" }}>
              <a className="btn primary" href="#picks">
                See algorithm picks
              </a>
              <a className="btn" href="#paste">
                Paste a slip
              </a>
            </div>
          </>
        )}
      </section>
      {bets.map((b) => (
        <article className="t-bet" key={b.id}>
          <div className="t-bet-main">
            <div className="sub">
              {new Date(b.placedAt).toLocaleDateString("en-CA")}, {b.sport}
              {b.book ? `, ${b.book}` : ""}
              {b.modelChance != null && ` · model ${(b.modelChance * 100).toFixed(1)}% when tracked`}
            </div>
            {b.legs.map((l, i) => (
              <div className="t-bet-leg" key={i}>
                <span>{l.description}</span>
                {l.odds ? <span className="num">{formatAmerican(l.odds)}</span> : null}
              </div>
            ))}
            <div className="sub num">
              {money(b.stake)} at {formatAmerican(decimalToAmerican(betDecimal(b)))}
              {(b.status === "won" || b.status === "lost") && (
                <b className={betProfit(b) >= 0 ? "t-up" : "t-down"}> {money(betProfit(b))}</b>
              )}
            </div>
          </div>
          <div className="t-bet-side">
            <label className="t-field">
              <span>Result</span>
              <select
                value={b.status}
                onChange={(e) => patch(b.id, { status: e.target.value as Status })}
              >
                <option value="open">Open</option>
                <option value="won">Won</option>
                <option value="lost">Lost</option>
                <option value="push">Push</option>
              </select>
            </label>
            {b.legs.length === 1 && (
              <label className="t-field">
                <span>Closing odds</span>
                <input
                  inputMode="numeric"
                  defaultValue={b.closingOdds ?? ""}
                  placeholder="−120"
                  onBlur={(e) => {
                    const n = Number(e.target.value.replace("−", "-"));
                    patch(b.id, {
                      closingOdds: Number.isFinite(n) && Math.abs(n) >= 100 ? n : undefined,
                    });
                  }}
                />
              </label>
            )}
            <button
              className="t-x"
              onClick={() => {
                if (confirmId === b.id) {
                  setBets((prev) => prev.filter((x) => x.id !== b.id));
                  setConfirmId(null);
                } else setConfirmId(b.id);
              }}
              onBlur={() => setConfirmId(null)}
            >
              {confirmId === b.id ? "Confirm delete" : "Delete"}
            </button>
          </div>
        </article>
      ))}
    </>
  );
}

function Breakdown({ title, rows }: { title: string; rows: Summary[] }) {
  const max = Math.max(0.01, ...rows.map((r) => Math.abs(r.roi ?? 0)));
  return (
    <section className="panel t-bars">
      <h3>{title}</h3>
      <p className="sub">Return on settled stakes</p>
      {rows.map((r) => (
        <div className="t-bar-row" key={r.label}>
          <span>
            {r.label}{" "}
            <small>
              ({r.won}–{r.lost}
              {r.push ? `–${r.push}` : ""})
            </small>
          </span>
          <span className="t-track">
            {r.roi !== null && (
              <span
                className={`t-fill ${r.roi >= 0 ? "up" : "down"}`}
                style={{ width: `${(Math.abs(r.roi) / max) * 50}%` }}
              />
            )}
          </span>
          <span className={`num ${r.roi === null ? "" : r.roi >= 0 ? "t-up" : "t-down"}`}>
            {r.roi === null ? "open" : pct(r.roi)}
          </span>
        </div>
      ))}
    </section>
  );
}

function ReportTab({ bets }: { bets: Bet[] }) {
  const all = summarize("All bets", bets);
  const clv = averageClv(bets);
  if (!bets.length)
    return (
      <section className="panel">
        <Head title="My report" />
        <p className="empty">
          Your report builds itself from your tracked bets. Track a few and mark them won or lost
          to see where your money goes.
        </p>
      </section>
    );
  const tiles: [string, string, string, string?][] = [
    ["Record", `${all.won}–${all.lost}${all.push ? `–${all.push}` : ""}`, `${all.bets} bets tracked`],
    ["Staked", money(all.staked), "settled bets only"],
    ["Profit", money(all.profit), "won minus lost", all.profit >= 0 ? "t-up" : "t-down"],
    ["Return", all.roi === null ? "–" : pct(all.roi), "profit over settled stakes"],
    ["Closing line value", clv === null ? "–" : pct(clv), "singles with closing odds"],
  ];
  return (
    <>
      <section className="kpis">
        {tiles.map(([k, v, d, cls]) => (
          <div className="kpi" key={k}>
            <div className="k">{k}</div>
            <div className={`v ${cls ?? ""}`}>{v}</div>
            <div className="d">{d}</div>
          </div>
        ))}
      </section>
      <div className="grid2">
        <Breakdown title="By bet type" rows={groupBy(bets, betType)} />
        <Breakdown title="By sport" rows={groupBy(bets, (b) => b.sport)} />
        <Breakdown title="By sportsbook" rows={groupBy(bets, (b) => b.book)} />
      </div>
      <p className="t-note">
        Closing line value compares the price you took with the final price before kick-off, on
        singles where you entered closing odds. A positive number means you tend to get better
        prices than the market settles at.
      </p>
    </>
  );
}

function GamesTab() {
  const e = backtest.margin_error_points;
  const ats = backtest.against_the_spread[0];
  return (
    <section className="panel">
      <Head
        title={`Game predictions, ${predictions.season} week ${predictions.week}`}
        sub="A separate team-rating model for spreads and winners. It is not the ATTD model behind the picks."
      />
      <div className="warns" style={{ marginBottom: 12 }}>
        <div>
          This game model does not beat the betting market. Tested on{" "}
          {backtest.games_scored.toLocaleString("en-CA")} games ({backtest.test_seasons}), it missed
          the final margin by {e.model.toFixed(2)} points on average; the closing spread missed by{" "}
          {e.market_closing_spread.toFixed(2)}. Betting its side against the spread won{" "}
          {(ats.win_rate * 100).toFixed(1)}% of the time, and{" "}
          {(backtest.break_even_win_rate * 100).toFixed(1)}% is needed to break even. Treat it as a
          second opinion, not as picks.
        </div>
      </div>
      <div className="scroll">
        <table className="tbl">
          <thead>
            <tr>
              <th>Game</th>
              <th>Date</th>
              <th>Model home margin</th>
              <th>Model home win chance</th>
              <th>Market home margin</th>
            </tr>
          </thead>
          <tbody>
            {predictions.games.map((g) => (
              <tr key={g.game_id}>
                <td>
                  <b>
                    {g.away} @ {g.home}
                  </b>
                </td>
                <td>{g.gameday}</td>
                <td className="num">{g.model_home_margin.toFixed(1)}</td>
                <td>
                  <span className="prob" data-heat={heat(g.model_home_win_prob)}>
                    {(g.model_home_win_prob * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="num">
                  {g.market_home_spread === null ? "No line" : g.market_home_spread.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub">
        A positive margin means the home team is expected to win by that many points. These numbers
        come from a file generated when the model was last run and do not update on their own.
      </p>
    </section>
  );
}
