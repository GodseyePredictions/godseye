/* The NFL "Anytime TD" tab: every touchdown-only slip for the day. Per-game boards and doubles come from
   model/output/nfl_today.json (scripts/nfl-today.ts); the slips across the day's games from
   model/output/nfl_atd_slips.json (scripts/nfl-atd-slips.ts). Every chance is the NFL algorithm's; every price is listed. */
import today from "../../model/output/nfl_today.json";
import raw from "../../model/output/nfl_atd_slips.json";
import { Slip, american, pct } from "@/components/Slip";

type Leg = { text: string; p: number; side: string; who: string; game: string; listed: string; matchup?: string };
type X = { title: string; size: number; game_id?: string; mix: string; pick: boolean; p: number; listedMultiplied: number | null; legs: Leg[]; note?: string };
type Atd = { made_at: string; games: string[]; listings: { source: string; pulled_at: string }; rules: string[]; left: { name: string; team: string; why: string }[]; slips: X[]; perGame?: X[] };
type GLeg = { text: string; p: number; listed?: string };
type GSlip = { title: string; pick: boolean; p: number; listedMultiplied?: number | null; legs: GLeg[]; note?: string };
type Single = { name: string; team: string; pos: string; p: number; flag: string; listed: string };
type Game = { game: string; game_id: string; kickoff: string; atd: { singles: Single[]; double: GSlip | null } };

const A = raw as unknown as Atd;
const T = today as unknown as { games: Game[] };
const chance = (p: number) => pct(p, p < 0.01 ? 2 : 1);
const et = (iso: string) => new Date(iso).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });

function CrossCard({ s }: { s: X }) {
  return (
    <Slip
      badge={s.pick ? "Algo pick" : "Godseye slip"}
      pick={s.pick}
      title={s.title}
      meta={s.mix}
      legs={s.legs.map((l) => ({ text: l.text, sub: [l.side, l.who, l.game, l.listed ? `listed ${l.listed}` : ""].filter(Boolean).join(" · "), value: pct(l.p) }))}
      why={{ legs: s.legs.map((l) => ({ text: l.text, why: l.matchup ? [l.matchup[0].toUpperCase() + l.matchup.slice(1) + "."] : [] })) }}
      stats={[
        { label: "Chance to hit", value: chance(s.p), tone: "red" },
        { label: "Chance to miss", value: chance(1 - s.p) },
        { label: "Books' leg prices combined", value: s.listedMultiplied == null ? "–" : american(s.listedMultiplied) },
      ]}
      note={s.note}
    />
  );
}

export function NflAtd() {
  const sizes = [...new Set(A.slips.map((s) => s.size))];
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Anytime TD: {A.games.length > 3 ? "the full slate" : "today's games"}</h2>
            <p className="sub">
              {A.games.join(" · ")}. Touchdown-only slips, ground and air. Prices from {A.listings.source}, pulled {et(A.listings.pulled_at)} ET. The slip outlined in red at each size is the
              algorithm&apos;s pick.
            </p>
          </div>
        </div>
        <ul className="why">
          {A.rules.map((r) => (
            <li key={r}>{r}</li>
          ))}
          <li>&ldquo;Books&apos; leg prices combined&rdquo; multiplies each leg&apos;s listed price. Confirm every player is active before kick-off.</li>
        </ul>
      </section>
      {sizes.map((n) => {
        const xs = A.slips.filter((s) => s.size === n);
        return (
          <section className="panel" key={n}>
            <div className="section-head">
              <div>
                <h2>{xs[0].title}</h2>
                {xs.length > 1 && <p className="sub">The algorithm&apos;s pick, and its best slip that mixes ground and air.</p>}
              </div>
            </div>
            <div className="gs-slips ge-set">
              {xs.map((s, i) => (
                <CrossCard s={s} key={i} />
              ))}
            </div>
          </section>
        );
      })}
      {[...new Set((A.perGame ?? []).map((s) => s.game_id as string))].map((gid) => {
        const xs = (A.perGame ?? []).filter((s) => s.game_id === gid);
        const g = { game: xs[0].title.split(":")[0], game_id: gid };
        return xs.length ? (
          <section className="panel" key={`pg-${gid}`}>
            <div className="section-head">
              <div>
                <h2>{g.game}: touchdown slips</h2>
                <p className="sub">Several scorers from this game. The algorithm&apos;s pick at each size, and its next best.</p>
              </div>
            </div>
            <div className="gs-slips ge-set">
              {xs.map((s, i) => (
                <CrossCard s={s} key={i} />
              ))}
            </div>
          </section>
        ) : null;
      })}
      {T.games.map((g) => (
        <section className="panel" key={g.game_id}>
          <div className="section-head">
            <div>
              <h2>{g.game}: touchdown board</h2>
              <p className="sub">{g.kickoff}. The algorithm&apos;s top scorers for this game.</p>
            </div>
          </div>
          <div className="scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Chance</th>
                  <th>Listed</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {g.atd.singles.map((p) => (
                  <tr key={p.name}>
                    <td>
                      <b>{p.name}</b> <small>{p.team} {p.pos}</small>
                    </td>
                    <td className="num">{pct(p.p, 1)}</td>
                    <td className="num">{p.listed || "–"}</td>
                    <td>{p.flag}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {g.atd.double && (
            <div className="gs-slips ge-set">
              <Slip
                badge="Algo pick"
                pick
                title={`${g.game}: TD double`}
                meta="One scorer from each team"
                legs={g.atd.double.legs.map((l) => ({ text: l.text, sub: l.listed ? `listed ${l.listed}` : undefined, value: pct(l.p) }))}
                stats={[
                  { label: "Chance to hit", value: chance(g.atd.double.p), tone: "red" },
                  { label: "Chance to miss", value: chance(1 - g.atd.double.p) },
                  { label: "Books' leg prices combined", value: g.atd.double.listedMultiplied == null ? "–" : american(g.atd.double.listedMultiplied) },
                ]}
              />
            </div>
          )}
        </section>
      ))}
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Left off touchdown slips</h2>
            <p className="sub">Players the algorithm rates 20% or better who do not go on a touchdown parlay today, and why.</p>
          </div>
        </div>
        <ul className="why">
          {A.left.map((h) => (
            <li key={h.name}>
              {h.name} ({h.team}): {h.why}.
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
