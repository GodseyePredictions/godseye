"use client";

import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";
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
import predictions from "../../../model/output/predictions.json";
import backtest from "../../../model/output/backtest.json";

const STORE = "godseye.bets.v1";

// Bets live in this browser's storage until accounts exist.
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

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

const tabs = ["Check a slip", "My bets", "Report", "NFL model"] as const;
type Tab = (typeof tabs)[number];

const money = (n: number) =>
  `${n < 0 ? "−" : ""}$${Math.abs(n).toFixed(2)}`;
const pct = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n * 100).toFixed(1)}%`;

export default function AppPage() {
  const [tab, setTab] = useState<Tab>("Check a slip");
  const bets = useSyncExternalStore(subscribe, readBets, () => EMPTY);
  const setBets = (fn: (prev: Bet[]) => Bet[]) => writeBets(fn(readBets()));

  return (
    <>
      <header className="wrap top">
        <Link href="/" className="brand">
          gods<span>eye</span>
        </Link>
        <nav aria-label="App sections" className="tabs">
          {tabs.map((t) => (
            <button
              key={t}
              className={t === tab ? "tab on" : "tab"}
              aria-current={t === tab ? "page" : undefined}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main className="wrap appmain">
        {tab === "Check a slip" && (
          <SlipTab
            onSave={(b) => {
              setBets((prev) => [b, ...prev]);
              setTab("My bets");
            }}
          />
        )}
        {tab === "My bets" && (
          <BetsTab bets={bets} setBets={setBets} goCheck={() => setTab("Check a slip")} />
        )}
        {tab === "Report" && <ReportTab bets={bets} />}
        {tab === "NFL model" && <ModelTab />}
        <p className="devnote">
          Your bets are saved in this browser only. They are not sent anywhere,
          and clearing your browser data removes them.
        </p>
      </main>
    </>
  );
}

function SlipTab({ onSave }: { onSave: (b: Bet) => void }) {
  const [text, setText] = useState("");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [stake, setStake] = useState("25");
  const [book, setBook] = useState("bet365");
  const [sport, setSport] = useState("NFL");
  const [parseMsg, setParseMsg] = useState("");

  const stakeNum = Number(stake) > 0 ? Number(stake) : 0;
  const valid = legs.filter((l) => Number.isFinite(l.odds) && Math.abs(l.odds) >= 100);
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
    <div className="cols">
      <section>
        <h1 className="display apph">Check a slip</h1>
        <label className="field">
          <span>Paste your slip, one leg per line with the odds last</span>
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Bills -3.5 -110\nJosh Allen over 249.5 pass yds -115"}
          />
        </label>
        {parseMsg && <p className="err">{parseMsg}</p>}
        <div className="row">
          <button className="btn btn-primary btn-sm" onClick={readText}>
            Add legs
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setLegs((p) => [...p, { description: "", odds: -110 }])}
          >
            Add a leg by hand
          </button>
        </div>

        {legs.map((l, i) => (
          <div className="legedit" key={i}>
            <label className="field grow">
              <span>Leg {i + 1}</span>
              <input
                value={l.description}
                onChange={(e) => update(i, { description: e.target.value })}
                placeholder="Bills -3.5"
              />
            </label>
            <label className="field narrow">
              <span>Odds</span>
              <input
                inputMode="numeric"
                value={Number.isFinite(l.odds) ? String(l.odds) : ""}
                onChange={(e) =>
                  update(i, { odds: e.target.value === "" ? NaN : Number(e.target.value) })
                }
              />
            </label>
            <label className="field mid">
              <span>Game (optional)</span>
              <input
                value={l.game ?? ""}
                onChange={(e) => update(i, { game: e.target.value })}
                placeholder="BUF @ MIA"
              />
            </label>
            <button
              className="x"
              aria-label={`Remove leg ${i + 1}`}
              onClick={() => setLegs((p) => p.filter((_, j) => j !== i))}
            >
              Remove
            </button>
          </div>
        ))}

        {legs.length > 0 && (
          <div className="legedit">
            <label className="field narrow">
              <span>Stake ($)</span>
              <input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} />
            </label>
            <label className="field mid">
              <span>Sportsbook</span>
              <input value={book} onChange={(e) => setBook(e.target.value)} />
            </label>
            <label className="field narrow">
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
          <p className="empty">
            Add at least one leg and the review appears here: payout, what the
            prices imply, and anything worth a second look.
          </p>
        ) : (
          <>
            <h2>
              {valid.length === 1 ? "Single" : `${valid.length}-leg parlay`} at{" "}
              <span className="num">{formatAmerican(decimalToAmerican(review.decimal))}</span>
            </h2>
            <p className="big num">
              {money(stakeNum)} to win {money(review.toWin)}
            </p>
            <ul className="findings">
              {review.findings.map((f, i) => (
                <li key={i} className={f.level}>
                  <strong>{f.title}</strong>
                  <span>{f.detail}</span>
                </li>
              ))}
            </ul>
            <button
              className="btn btn-primary"
              disabled={stakeNum <= 0}
              onClick={() =>
                onSave({
                  id: crypto.randomUUID(),
                  placedAt: new Date().toISOString(),
                  sport,
                  book: book.trim(),
                  legs: valid.map((l) => ({
                    ...l,
                    description: l.description.trim() || "Leg",
                  })),
                  stake: stakeNum,
                  status: "open",
                })
              }
            >
              Save to my bets
            </button>
            {stakeNum <= 0 && <p className="err">Enter a stake above zero to save this bet.</p>}
          </>
        )}
      </section>
    </div>
  );
}

function BetsTab({
  bets,
  setBets,
  goCheck,
}: {
  bets: Bet[];
  setBets: (fn: (prev: Bet[]) => Bet[]) => void;
  goCheck: () => void;
}) {
  const patch = (id: string, p: Partial<Bet>) =>
    setBets((prev) => prev.map((b) => (b.id === id ? { ...b, ...p } : b)));

  if (!bets.length)
    return (
      <section>
        <h1 className="display apph">My bets</h1>
        <p className="empty">No bets saved yet. Check a slip and save it to start your record.</p>
        <button className="btn btn-primary" onClick={goCheck}>
          Check a slip
        </button>
      </section>
    );

  return (
    <section>
      <h1 className="display apph">My bets</h1>
      {bets.map((b) => (
        <article className="bet" key={b.id}>
          <div className="bet-main">
            <div className="bet-meta">
              {new Date(b.placedAt).toLocaleDateString("en-CA")}, {b.sport}
              {b.book ? `, ${b.book}` : ""}
            </div>
            {b.legs.map((l, i) => (
              <div className="leg-row" key={i}>
                <span>{l.description}</span>
                <span className="num">{formatAmerican(l.odds)}</span>
              </div>
            ))}
            <div className="bet-meta num">
              {money(b.stake)} at {formatAmerican(decimalToAmerican(betDecimal(b)))}
              {b.status !== "open" && b.status !== "push" && (
                <b className={betProfit(b) >= 0 ? "up-t" : "down-t"}> {money(betProfit(b))}</b>
              )}
            </div>
          </div>
          <div className="bet-side">
            <label className="field">
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
              <label className="field">
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
              className="x"
              onClick={() => {
                if (confirm("Delete this bet from your record?"))
                  setBets((prev) => prev.filter((x) => x.id !== b.id));
              }}
            >
              Delete
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}

function Breakdown({ title, rows }: { title: string; rows: Summary[] }) {
  const max = Math.max(0.01, ...rows.map((r) => Math.abs(r.roi ?? 0)));
  return (
    <div className="bars">
      <h3>{title}</h3>
      <p>Return on settled stakes</p>
      {rows.map((r) => (
        <div className="bar-row" key={r.label}>
          <span>
            {r.label} <small>({r.won}–{r.lost}{r.push ? `–${r.push}` : ""})</small>
          </span>
          <span className="track">
            {r.roi !== null && (
              <span
                className={`fill ${r.roi >= 0 ? "up" : "down"}`}
                style={{ width: `${(Math.abs(r.roi) / max) * 50}%` }}
              />
            )}
          </span>
          <span className={`num ${r.roi === null ? "" : r.roi >= 0 ? "up-t" : "down-t"}`}>
            {r.roi === null ? "open" : pct(r.roi)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ReportTab({ bets }: { bets: Bet[] }) {
  const all = summarize("All bets", bets);
  const clv = averageClv(bets);
  if (!bets.length)
    return (
      <section>
        <h1 className="display apph">Report</h1>
        <p className="empty">
          Your report builds itself from your saved bets. Save a few and mark
          them won or lost to see where your money goes.
        </p>
      </section>
    );
  return (
    <section>
      <h1 className="display apph">Report</h1>
      <div className="stats">
        <div>
          <span>Record</span>
          <b className="num">
            {all.won}–{all.lost}
            {all.push ? `–${all.push}` : ""}
          </b>
        </div>
        <div>
          <span>Staked (settled)</span>
          <b className="num">{money(all.staked)}</b>
        </div>
        <div>
          <span>Profit</span>
          <b className={`num ${all.profit >= 0 ? "up-t" : "down-t"}`}>{money(all.profit)}</b>
        </div>
        <div>
          <span>Return</span>
          <b className="num">{all.roi === null ? "No settled bets" : pct(all.roi)}</b>
        </div>
        <div>
          <span>Closing line value</span>
          <b className="num">{clv === null ? "Add closing odds" : pct(clv)}</b>
        </div>
      </div>
      <div className="grid2">
        <Breakdown title="By bet type" rows={groupBy(bets, betType)} />
        <Breakdown title="By sport" rows={groupBy(bets, (b) => b.sport)} />
        <Breakdown title="By sportsbook" rows={groupBy(bets, (b) => b.book)} />
      </div>
      <p className="fine">
        Closing line value compares the price you took with the final price
        before kick-off, on singles where you entered closing odds. A positive
        number means you tend to get better prices than the market settles at.
      </p>
    </section>
  );
}

function ModelTab() {
  const e = backtest.margin_error_points;
  const ats = backtest.against_the_spread[0];
  return (
    <section>
      <h1 className="display apph">NFL model</h1>
      <div className="panel warnbox">
        <strong>This model does not beat the betting market.</strong>
        <span>
          Tested on {backtest.games_scored.toLocaleString("en-CA")} games (
          {backtest.test_seasons}), it missed the final margin by{" "}
          {e.model.toFixed(2)} points on average; the closing spread missed by{" "}
          {e.market_closing_spread.toFixed(2)}. Betting its side against the
          spread won {(ats.win_rate * 100).toFixed(1)}% of the time, and{" "}
          {(backtest.break_even_win_rate * 100).toFixed(1)}% is needed to break
          even. Treat these numbers as a second opinion, not as picks.
        </span>
      </div>
      <h2>
        {predictions.season} week {predictions.week}
      </h2>
      <div className="tablewrap">
        <table>
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
                  {g.away} at {g.home}
                </td>
                <td>{g.gameday}</td>
                <td className="num">{g.model_home_margin.toFixed(1)}</td>
                <td className="num">{(g.model_home_win_prob * 100).toFixed(0)}%</td>
                <td className="num">
                  {g.market_home_spread === null ? "No line" : g.market_home_spread.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="fine">
        A positive margin means the home team is expected to win by that many
        points. Predictions come from a file generated when the model was last
        run and do not update on their own.
      </p>
    </section>
  );
}
