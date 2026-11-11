import { useState } from "react";
import data from "../../model/output/game_markets.json";
import type { Leg } from "@/lib/bets";

type Factor = { factor: string; points: number };
type Check = { check: string; score: number | null; verdict: string; numbers?: string };
type AltLine = { line: number; p: number; fair_price: number; main: boolean };
type SafeSpread = { game_id: string; team: string; main_line: number; main_p: number; safe_line: number; p: number; fair_price: number; net_checks: number };
type MarketLeg = {
  game_id: string;
  market: string;
  label: string;
  p: number;
  price: number;
  market_p: number;
  edge: number;
  ev: number;
  dog: boolean;
  note?: string;
  personnel?: string;
  injury_report?: string[];
  for?: Factor[];
  against?: Factor[];
  checks?: Check[];
  net_checks?: number;
  safe?: boolean;
};
type Ticket = {
  legs: MarketLeg[];
  n: number;
  p: number;
  fair_price: number;
  market_price: number;
  ev: number;
  dogs: number;
};
type Row = { bets: number; win_rate: number; break_even: number; roi: number };

const tickets = data.tickets as unknown as Record<string, Ticket[]>;
const card = data.scorecard;
const MARKETS = [
  ["ml", "Moneylines"],
  ["spread", "Spreads"],
  ["total", "Game totals"],
] as const;
type MarketKey = (typeof MARKETS)[number][0];

const am = (n: number) => (n > 0 ? `+${n}` : `−${Math.abs(n)}`);
const pct = (p: number, d = 1) => `${(p * 100).toFixed(d)}%`;
const signedPct = (p: number) => `${p >= 0 ? "+" : "−"}${Math.abs(p * 100).toFixed(1)}%`;
const heat = (p: number) => (p >= 0.8 ? 5 : p >= 0.65 ? 4 : p >= 0.5 ? 3 : p >= 0.35 ? 2 : 1);
const line = (n: number) => (n > 0 ? `+${n}` : n === 0 ? "PK" : `−${Math.abs(n)}`);
const verdictPill = (v: string) => (v === "for" ? "good" : v === "against" ? "bad" : "neutral");
const gameName = (id: string) => {
  const [, , away, home] = id.split("_");
  return `${away} @ ${home}`;
};

function Why({ leg }: { leg: MarketLeg }) {
  return (
    <details>
      <summary>Matchup checks and reasons</summary>
      {leg.checks && (
        <div className="scroll">
          <table className="tbl chk">
            <tbody>
              {leg.checks.map((c) => (
                <tr key={c.check}>
                  <td>
                    <b>{c.check}</b>
                  </td>
                  <td>
                    <span className={`pill ${verdictPill(c.verdict)}`}>{c.verdict}</span>
                  </td>
                  <td>{c.numbers}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ul className="why">
        {leg.note && <li>{leg.note}</li>}
        {(leg.for ?? []).map((f) => (
          <li key={f.factor}>
            <b>For:</b> {f.factor} ({f.points > 0 ? "+" : ""}
            {f.points.toFixed(1)} pts)
          </li>
        ))}
        {(leg.against ?? []).map((f) => (
          <li key={f.factor}>
            <b>Against:</b> {f.factor} ({f.points.toFixed(1)} pts)
          </li>
        ))}
        {leg.personnel && <li>{leg.personnel}</li>}
        {leg.injury_report && (
          <li>On the injury report (not in this model): {leg.injury_report.join(", ")}</li>
        )}
      </ul>
    </details>
  );
}

function TicketCard({ t, onTrack }: { t: Ticket; onTrack: (legs: Leg[]) => void }) {
  return (
    <div className="ticket">
      <div className="top">
        <span className="legsn">{t.n}-leg</span>
        <span className="fair num">{am(t.market_price)}</span>
      </div>
      <div className="pct">
        {pct(t.p)} to hit · fair {am(t.fair_price)} · {t.dogs} underdog{t.dogs === 1 ? "" : "s"}
      </div>
      <ol>
        {t.legs.map((l) => (
          <li key={l.game_id + l.label}>
            {l.label}{" "}
            <span>
              {pct(l.p, 0)} · {am(l.price)}
            </span>
          </li>
        ))}
      </ol>
      <span className={`pill ${t.ev > 0.02 ? "good" : t.ev < -0.02 ? "bad" : "neutral"}`}>
        {t.ev > 0.02
          ? `Model sees ${signedPct(t.ev)} value at these prices`
          : t.ev < -0.02
            ? `Overpriced by ${pct(-t.ev)}: bet only if your book pays better than ${am(t.fair_price)}`
            : `About fair: needs better than ${am(t.fair_price)}`}
      </span>
      <button
        className="btn primary"
        onClick={() =>
          onTrack(t.legs.map((l) => ({ description: l.label, odds: l.price, game: gameName(l.game_id) })))
        }
      >
        Review and track
      </button>
    </div>
  );
}

function History({ rows, unit }: { rows: Row[]; unit: string }) {
  const r = rows[0];
  if (!r) return null;
  return (
    <tr>
      <td>
        <b>{unit}</b>
      </td>
      <td className="num">{r.bets.toLocaleString("en-CA")}</td>
      <td className="num">{pct(r.win_rate)}</td>
      <td className="num">{pct(r.break_even)}</td>
      <td className={`num ${r.roi >= 0 ? "t-up" : "t-down"}`}>{signedPct(r.roi)}</td>
    </tr>
  );
}

export function MarketsTab({ onTrack }: { onTrack: (legs: Leg[]) => void }) {
  const [market, setMarket] = useState<MarketKey>("ml");
  const list = tickets[market] ?? [];
  const legs = data.games
    .map((g) => g[market] as unknown as MarketLeg | null)
    .filter((l): l is MarketLeg => !!l)
    .sort((a, b) => b.ev - a.ev);
  const safe = data.safe as unknown as {
    rule: string;
    moneylines: MarketLeg[];
    other_favourites: MarketLeg[];
    parlays: Ticket[];
    spreads: SafeSpread[];
  };
  const alts = Object.fromEntries(data.games.map((g) => [g.game_id, g.alt_spreads as AltLine[]]));
  const fav = card.strong_favourites as unknown as Record<string, Row & { average_forecast: number }>;
  const ints = data.interceptions;
  const intPicks = ints.filter((i) => i.recommended);
  const ic = data.interception_scorecard;
  const valueRows = card.moneyline_singles.filter((r) => r.min_ev === 0) as unknown as Row[];
  const history = (card.tickets as unknown as Record<string, { legs: number; weeks: number; hit: number; hits_expected: number; roi: number }[]>)[market] ?? [];

  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>
              Game parlays, {data.as_of.season} week {data.as_of.week}
            </h2>
            <p className="sub">
              Moneyline, spread and total tickets from the game model. It rates every team on
              efficiency, pace, possession, turnovers, penalties and its quarterback, then moves the
              market line a small step toward that view. Every moneyline and spread pick carries
              seven matchup checks, and a pick missing any of them is dropped ({data.gate.dropped_missing_a_check}{" "}
              of {data.gate.picks_considered} this week). Tickets rank legs by value at the listed
              price, so underdogs make every ticket; a favourite needs the checks to lean its way,
              and favourites shorter than −350 are left out.
            </p>
          </div>
        </div>
        <div className="warns">
          <div>
            Read this first: over {card.games.toLocaleString("en-CA")} games ({card.test_seasons})
            the model never saw, it did not beat the closing line. Its margin forecast missed by{" "}
            {card.margin_miss_points.blend.toFixed(2)} points against the line&apos;s{" "}
            {card.margin_miss_points.market_line.toFixed(2)}. Treat each ticket as the fair price
            for that combination, and bet only when your book pays more than fair.
          </div>
        </div>
        <div className="row stylebar" style={{ marginTop: 12 }}>
          {MARKETS.map(([k, label]) => (
            <button
              key={k}
              className={k === market ? "btn primary" : "btn"}
              aria-pressed={k === market}
              onClick={() => setMarket(k)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Safe picks</h2>
            <p className="sub">
              {safe.rule} Safe means likely to win, not good value: these prices are short, and the
              return over time has been close to zero.
            </p>
          </div>
        </div>
        {safe.moneylines.length === 0 ? (
          <p className="empty">No favourite passes every part of the safe rule this week.</p>
        ) : (
          <div className="mylegs">
            {safe.moneylines.map((l) => (
              <div className="myleg" key={l.game_id}>
                <div className="line1">
                  <span className="nm">
                    {l.label} <small>{gameName(l.game_id)}</small>
                  </span>
                  <span className="pill good">safe · checks {(l.net_checks ?? 0) > 0 ? "+" : ""}{l.net_checks}</span>
                  <span className="pill">{am(l.price)}</span>
                  <span className="prob" data-heat={heat(l.p)}>
                    {pct(l.p)}
                  </span>
                </div>
                <Why leg={l} />
              </div>
            ))}
          </div>
        )}
        {safe.parlays.map((t) => (
          <div className="warns" style={{ marginTop: 10 }} key={t.n}>
            <div>
              Safe {t.n}-leg parlay: {t.legs.map((l) => l.label).join(" + ")}. Model {pct(t.p)} to hit,
              fair {am(t.fair_price)}, listed {am(t.market_price)}.{" "}
              <button
                className="btn sm"
                onClick={() => onTrack(t.legs.map((l) => ({ description: l.label, odds: l.price, game: gameName(l.game_id) })))}
              >
                Review and track
              </button>
            </div>
          </div>
        ))}
        {safe.other_favourites.length > 0 && (
          <>
            <h3 style={{ marginTop: 14 }}>Strong favourites that did not pass</h3>
            <div className="mylegs">
              {safe.other_favourites.map((l) => (
                <div className="myleg" key={l.game_id}>
                  <div className="line1">
                    <span className="nm">
                      {l.label} <small>{gameName(l.game_id)}</small>
                    </span>
                    <span className="pill warn">checks {(l.net_checks ?? 0) > 0 ? "+" : ""}{l.net_checks}, needs +2</span>
                    <span className="pill">{am(l.price)}</span>
                    <span className="prob" data-heat={heat(l.p)}>
                      {pct(l.p)}
                    </span>
                  </div>
                  <Why leg={l} />
                </div>
              ))}
            </div>
          </>
        )}
        <h3 style={{ marginTop: 14 }}>Safer alternative spreads</h3>
        <p className="sub">
          The same side at the first alternative line the model gives 70% or better. No book prices
          are loaded for alternative lines, so compare the fair price with your book.
        </p>
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Team</th>
                <th>Main line</th>
                <th>Safer line</th>
                <th>Chance</th>
                <th>Fair price</th>
                <th>Checks</th>
              </tr>
            </thead>
            <tbody>
              {safe.spreads.map((r) => (
                <tr key={r.game_id}>
                  <td>
                    <b>{r.team}</b> <span className="sub">{gameName(r.game_id)}</span>
                  </td>
                  <td className="num">
                    {line(r.main_line)} ({pct(r.main_p, 0)})
                  </td>
                  <td className="num">
                    <b>{line(r.safe_line)}</b>
                  </td>
                  <td>
                    <span className="prob" data-heat={heat(r.p)}>
                      {pct(r.p)}
                    </span>
                  </td>
                  <td className="num">{am(r.fair_price)}</td>
                  <td>
                    <span className={`pill ${r.net_checks >= 2 ? "good" : r.net_checks < 0 ? "bad" : "neutral"}`}>
                      {r.net_checks > 0 ? "+" : ""}
                      {r.net_checks}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>{MARKETS.find(([k]) => k === market)![1]} tickets</h2>
            <p className="sub">
              Each ticket builds on the one before it. The price shown is the parlay at this
              week&apos;s listed odds.
            </p>
          </div>
        </div>
        {list.length ? (
          <div className="ladder">
            {list.map((t) => (
              <TicketCard key={t.n} t={t} onTrack={onTrack} />
            ))}
          </div>
        ) : (
          <p className="empty">Not enough priced games left this week to build a ticket.</p>
        )}
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Every game, best side first</h2>
            <p className="sub">
              The model&apos;s side in each game with its chance, the price, and what is pulling the
              forecast that way.
            </p>
          </div>
        </div>
        <div className="mylegs">
          {legs.map((l) => (
            <div className="myleg" key={l.game_id}>
              <div className="line1">
                <span className="nm">
                  {l.label} <small>{gameName(l.game_id)}</small>
                </span>
                {l.dog && <span className="pill gold">underdog</span>}
                <span className="pill">{am(l.price)}</span>
                <span className={`pill ${l.ev > 0 ? "good" : "neutral"}`}>value {signedPct(l.ev)}</span>
                <span className="prob" data-heat={heat(l.p)}>
                  {pct(l.p)}
                </span>
              </div>
              {market === "spread" && (
                <div className="alts">
                  Alternative lines:
                  {(alts[l.game_id] ?? []).map((a) => (
                    <span className={`pill ${a.main ? "gold" : ""}`} key={a.line}>
                      {line(a.line)} · {pct(a.p, 0)} · fair {am(a.fair_price)}
                    </span>
                  ))}
                </div>
              )}
              <Why leg={l} />
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Interceptions</h2>
            <p className="sub">
              Chance each starting quarterback throws at least one, from his own interception rate,
              the defence he faces, expected dropbacks and how far behind his team is expected to
              play. A leg is recommended only at {pct(data.interception_threshold, 0)} or higher.
            </p>
          </div>
        </div>
        {intPicks.length === 0 && (
          <div className="warns" style={{ marginBottom: 10 }}>
            <div>
              No interception leg clears the bar this week, so none is on a ticket. The highest is{" "}
              {ints[0]?.qb} at {ints[0] ? pct(ints[0].p) : "–"}.
            </div>
          </div>
        )}
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Quarterback</th>
                <th>Against</th>
                <th>Chance of 1+</th>
                <th>Fair price</th>
                <th>His rate per dropback</th>
                <th>Expected dropbacks</th>
              </tr>
            </thead>
            <tbody>
              {ints.slice(0, 12).map((i) => (
                <tr key={i.game_id + i.team}>
                  <td>
                    <b>{i.qb}</b> <span className="sub">{i.team}</span>{" "}
                    {i.recommended && <span className="pill good">recommended</span>}
                  </td>
                  <td>{i.opp}</td>
                  <td>
                    <span className="prob" data-heat={heat(i.p)}>
                      {pct(i.p)}
                    </span>
                  </td>
                  <td className="num">{am(i.fair_price)}</td>
                  <td className="num">{pct(i.inputs.qb_interception_rate)}</td>
                  <td className="num">{i.inputs.expected_dropbacks.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="sub">
          Tested on {ic.starts.toLocaleString("en-CA")} starts ({ic.test_seasons}): forecasts of
          57–62% came in at{" "}
          {pct(ic.calibration.find((c) => c.forecast_range === "57%-62%")?.actually_threw_one ?? 0, 0)}.
          Above 62% there are too few past cases to trust. No book price is loaded for this market,
          so compare the fair price with what your book offers.
        </p>
      </section>

      <section className="panel">
        <h3>How this has tested</h3>
        <p className="sub">
          Every season forecast by models fitted only on earlier seasons, settled at closing prices.
        </p>
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Single bets on the model&apos;s side</th>
                <th>Bets</th>
                <th>Won</th>
                <th>Needed</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              <History rows={valueRows} unit="Moneylines the model rated as value" />
              <History rows={card.moneyline_value_bets_split.underdogs as unknown as Row[]} unit="of which underdogs" />
              <History rows={card.moneyline_value_bets_split.favourites as unknown as Row[]} unit="of which favourites" />
              <History rows={card.spread_singles as unknown as Row[]} unit="Spreads" />
              <History rows={card.total_singles as unknown as Row[]} unit="Totals" />
              <History rows={[fav.all]} unit="Strong favourites, all" />
              <History rows={[fav.safe_checks_lean_their_way]} unit="Strong favourites that passed the safe rule" />
              <History rows={[fav.not_safe]} unit="Strong favourites that did not pass" />
              <History rows={[fav.checks_net_negative]} unit="Strong favourites with the checks against them" />
            </tbody>
          </table>
        </div>
        <p className="sub">
          The checks sort favourites in the right direction: those that passed won more often
          relative to their price than those that did not. The gap is small and the samples are
          a few hundred games, so read it as a lean, not a proven edge.
        </p>
        <div className="scroll" style={{ marginTop: 10 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Alternative lines, points moved</th>
                <th>Games</th>
                <th>Forecast</th>
                <th>Actually covered</th>
              </tr>
            </thead>
            <tbody>
              {card.alternative_lines.map((a) => (
                <tr key={a.points_moved}>
                  <td>
                    <b>{a.points_moved > 0 ? `${a.points_moved} easier` : `${-a.points_moved} harder`}</b>
                  </td>
                  <td className="num">{a.games.toLocaleString("en-CA")}</td>
                  <td className="num">{pct(a.average_forecast)}</td>
                  <td className="num">{pct(a.actually_covered)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="scroll" style={{ marginTop: 10 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>{MARKETS.find(([k]) => k === market)![1]} tickets, one a week</th>
                <th>Weeks</th>
                <th>Hit</th>
                <th>Expected hits</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.legs}>
                  <td>
                    <b>{h.legs}-leg</b>
                  </td>
                  <td className="num">{h.weeks}</td>
                  <td className="num">{h.hit}</td>
                  <td className="num">{h.hits_expected.toFixed(1)}</td>
                  <td className={`num ${h.roi >= 0 ? "t-up" : "t-down"}`}>{signedPct(h.roi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="sub">
          Long parlays hit rarely, so a few results swing the return either way. A positive figure
          on so few hits is luck until it holds over many more weeks. The model puts{" "}
          {pct(card.weight_on_fundamentals.margin, 0)} weight on its own margin and{" "}
          {pct(card.weight_on_fundamentals.total, 0)} on its own total; the rest is the market line.
        </p>
      </section>
    </>
  );
}

type HybridLeg = { kind: string; label: string; p: number; player_id?: string; price?: number; matchup?: string };
type Hybrid = {
  kind: string;
  game_id: string;
  legs: HybridLeg[];
  p: number;
  p_if_independent: number;
  correlation_lift: number;
  fair_price: number;
};

declare global {
  interface Window {
    appendLegs?: (legs: { id: string; mk: string; k: null }[], label: string) => void;
  }
}

export function HybridsTab() {
  const hybrids = data.hybrids as unknown as Hybrid[];
  const games = [...new Set(hybrids.map((h) => h.game_id))];
  const c = data.correlations;
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Hybrid SGPs</h2>
            <p className="sub">
              Same-game parlays that tie a game result to touchdown scorers. The game leg comes from
              the game model, the touchdown chances from the ATTD model, and the two are combined
              with correlations measured on {c.n_player_games.toLocaleString("en-CA")} past
              player-games. Players on the singles-only list are never used, a scorer whose position
              matchup is against him is passed over when another is available, and no hybrid is
              built for a game missing a matchup check.
            </p>
          </div>
        </div>
        <div className="envline">
          <span className="pill">RB scores and his team wins: {c.atd.RB.won.toFixed(2)}</span>
          <span className="pill">WR: {c.atd.WR.won.toFixed(2)}</span>
          <span className="pill">TE: {c.atd.TE.won.toFixed(2)}</span>
          <span className="pill">QB: {c.atd.QB.won.toFixed(2)}</span>
          <span className="pill">Any TD with the over: about {c.atd.WR.over.toFixed(2)}</span>
          <span className="pill">
            QB throws an interception and his team wins: {c.int.own_team_won.toFixed(2)}
          </span>
        </div>
        <p className="sub" style={{ marginTop: 8 }}>
          Because these legs move together, the true chance is higher than multiplying them. Books
          know this and cut the payout, so type your book&apos;s SGP price into the bet slip and
          compare it with the fair price here. No book SGP prices are loaded.
        </p>
      </section>

      {games.map((id) => (
        <section className="panel" key={id}>
          <div className="section-head">
            <h2>{gameName(id)}</h2>
          </div>
          <div className="ladder">
            {hybrids
              .filter((h) => h.game_id === id)
              .map((h) => {
                const tds = h.legs.filter((l) => l.kind === "atd" && l.player_id);
                return (
                  <div className="ticket" key={h.kind}>
                    <div className="top">
                      <span className="legsn" style={{ fontSize: 17 }}>
                        {h.kind}
                      </span>
                    </div>
                    <div className="pct">
                      {pct(h.p)} to hit · fair <b className="fair">{am(h.fair_price)}</b>
                    </div>
                    <ol>
                      {h.legs.map((l) => (
                        <li key={l.label}>
                          {l.label} <span>{pct(l.p, 0)}</span>{" "}
                          {l.matchup && <span className={`pill ${verdictPill(l.matchup)}`}>matchup {l.matchup}</span>}
                        </li>
                      ))}
                    </ol>
                    <span className="pill neutral">
                      {pct(h.p_if_independent)} if unrelated · ×{h.correlation_lift.toFixed(2)} from
                      correlation
                    </span>
                    <button
                      className="btn primary"
                      onClick={() =>
                        window.appendLegs?.(
                          tds.map((l) => ({ id: l.player_id!, mk: "atd", k: null })),
                          `${gameName(id)} hybrid`,
                        )
                      }
                    >
                      Add touchdown legs to slip
                    </button>
                  </div>
                );
              })}
          </div>
        </section>
      ))}
    </>
  );
}
