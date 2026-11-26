/* Today's NFL slips (model/output/nfl_today.json, written by scripts/nfl-slate.sh): one pack per game, every leg a
   rung a sportsbook lists, every chance the NFL algorithm's. The algorithm's pick in each tier is outlined. */
import raw from "../../model/output/nfl_today.json";
import { Slip, american, pct } from "@/components/Slip";

type Leg = { text: string; p: number; record?: string; listed?: string; why?: string[] };
type S = { title: string; kind?: string; pick: boolean; p: number; fair: number; listedMultiplied?: number | null; legs: Leg[]; note?: string };
type CrossLeg = { text: string; p: number; side: string; who: string; game: string; listed?: string };
type Cross = { title: string; mix: string; pick: boolean; p: number; fair: number; listedMultiplied?: number | null; legs: CrossLeg[]; note?: string };
type Single = { name: string; team: string; pos: string; p: number; fair: number; flag: string; listed: string; why: string[] };
type Game = {
  game: string; game_id: string; kickoff: string; venue: string; listings: { source: string; pulled_at: string };
  sgps: S[]; hybrids: S[]; lotto: S | null;
  atd: { singles: Single[]; double: S | null; held: { name: string; why: string }[] };
};
type Today = {
  made_at: string; built_from: string; rules: string[]; listings: { source: string; pulled_at: string }; games: Game[];
  cross: { games: string[]; slips: Cross[]; held: { name: string; team: string; why: string }[] };
};
const T = raw as unknown as Today;
const et = (iso: string) => new Date(iso).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });

function Card({ s, game }: { s: S; game: string }) {
  return (
    <Slip
      badge={s.pick ? "Algo pick" : "Godseye slip"}
      pick={s.pick}
      title={s.title}
      meta={game}
      legs={s.legs.map((l) => ({ text: l.text, sub: [l.record, l.listed ? `listed ${l.listed}` : ""].filter(Boolean).join(" · ") || undefined, value: pct(l.p) }))}
      why={{ legs: s.legs.map((l) => ({ text: l.text, why: l.why ?? [] })) }}
      stats={[
        { label: "Chance to hit", value: pct(s.p, 1), tone: "red" },
        { label: "Chance to miss", value: pct(1 - s.p, 1) },
        { label: "Books' leg prices combined", value: s.listedMultiplied == null ? "–" : american(s.listedMultiplied) },
      ]}
      note={s.note}
    />
  );
}

function Tier({ title, sub, slips, game }: { title: string; sub?: string; slips: S[]; game: string }) {
  if (!slips.length) return null;
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {sub && <p className="sub">{sub}</p>}
        </div>
      </div>
      <div className="gs-slips ge-set">
        {slips.map((s, i) => (
          <Card s={s} game={game} key={i} />
        ))}
      </div>
    </section>
  );
}

const bySize = (list: S[]) => [...new Set(list.map((s) => s.title))].map((t) => list.filter((s) => s.title === t));

function GamePack({ g }: { g: Game }) {
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>{g.game}</h2>
            <p className="sub">
              {g.kickoff} · {g.venue}. Prices pulled {et(g.listings.pulled_at)} ET.
            </p>
          </div>
        </div>
      </section>
      {bySize(g.sgps).map((x) => (
        <Tier key={x[0].title} game={g.game} title={`${g.game}: ${x[0].title}`} sub="Props only, no touchdown legs." slips={x} />
      ))}
      {bySize(g.hybrids).map((x) => (
        <Tier key={x[0].title} game={g.game} title={`${g.game}: ${x[0].title}`} sub="Props legs plus one anytime touchdown." slips={x} />
      ))}
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>{g.game}: anytime TD</h2>
            <p className="sub">The algorithm&apos;s touchdown board for this game.</p>
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
            <Card s={g.atd.double} game={g.game} />
          </div>
        )}
      </section>
      {g.lotto && <Tier game={g.game} title={`${g.game}: lotto`} sub="A longshot: the algorithm makes it 1 in 16 or less likely, and the books' leg prices combine to +1500 or longer." slips={[g.lotto]} />}
    </>
  );
}

export function NflTonight() {
  const made = new Date(T.made_at).toLocaleString("en-CA", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Today: {T.games.map((g) => g.game).join(" · ")}</h2>
            <p className="sub">
              Made {made} ET from the algorithm&apos;s build of {T.built_from}. One pack per game. Each leg is set by its matchup and carries the price a sportsbook
              lists for that rung. The slip outlined in red in each tier is the algorithm&apos;s pick.
            </p>
          </div>
        </div>
        <ul className="why">
          {T.rules.map((r) => (
            <li key={r}>{r}</li>
          ))}
          <li>Prices from {T.listings.source}. &ldquo;Books&apos; leg prices combined&rdquo; multiplies each leg&apos;s listed price; a book prices the same legs as a same-game parlay shorter than that.</li>
        </ul>
      </section>
      {T.games.map((g) => (
        <GamePack g={g} key={g.game_id} />
      ))}
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Anytime TD across today&apos;s games</h2>
            <p className="sub">{T.cross.games.join(" · ")}. Ground and air together: the algorithm&apos;s most likely mix at each size.</p>
          </div>
        </div>
        <div className="gs-slips ge-set">
          {T.cross.slips.map((s) => (
            <Slip
              key={s.title}
              badge="Algo pick"
              pick
              title={s.title}
              meta={s.mix}
              legs={s.legs.map((l) => ({ text: l.text, sub: [l.side, l.who, l.game, l.listed ? `listed ${l.listed}` : ""].filter(Boolean).join(" · "), value: pct(l.p) }))}
              stats={[
                { label: "Chance to hit", value: pct(s.p, 1), tone: "red" },
                { label: "Chance to miss", value: pct(1 - s.p, 1) },
                { label: "Books' leg prices combined", value: s.listedMultiplied == null ? "–" : american(s.listedMultiplied) },
              ]}
              note={s.note}
            />
          ))}
        </div>
        <ul className="why">
          {T.cross.held.map((h) => (
            <li key={h.name}>
              {h.name} ({h.team}) is held out of touchdown parlays: {h.why}.
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
