/* Tonight's NFL slips (model/output/nfl_today.json, written by scripts/nfl-today.ts): every leg is a rung a
   sportsbook lists, and every chance is the NFL algorithm's. The algorithm's pick in each tier is outlined. */
import raw from "../../model/output/nfl_today.json";
import { Slip, american, pct } from "@/components/Slip";

type Leg = { text: string; p: number; record?: string; listed?: string; why?: string[] };
type S = { title: string; kind?: string; pick: boolean; p: number; fair: number; legs: Leg[]; note?: string };
type CrossLeg = { text: string; p: number; side: string; who: string; game: string };
type Cross = { title: string; mix: string; pick: boolean; p: number; fair: number; legs: CrossLeg[]; note?: string };
type Single = { name: string; team: string; pos: string; p: number; fair: number; flag: string; listed: string; why: string[] };
type Today = {
  game: string; kickoff: string; venue: string; built_from: string; made_at: string; listings: { source: string; pulled_at: string };
  script: string[]; rules: string[]; sgps: S[]; hybrids: S[]; lotto: S | null;
  atd: { singles: Single[]; double: S | null; held: { name: string; why: string }[] };
  cross: { games: string[]; slips: Cross[]; held: { name: string; team: string; why: string }[] };
};
const T = raw as unknown as Today;

function Card({ s }: { s: S }) {
  return (
    <Slip
      badge={s.pick ? "Algo pick" : "Godseye slip"}
      pick={s.pick}
      title={s.title}
      meta={T.game}
      legs={s.legs.map((l) => ({ text: l.text, sub: [l.record, l.listed ? `listed ${l.listed}` : ""].filter(Boolean).join(" · ") || undefined, value: pct(l.p) }))}
      why={{ legs: s.legs.map((l) => ({ text: l.text, why: l.why ?? [] })) }}
      stats={[
        { label: "Chance to hit", value: pct(s.p, 1), tone: "red" },
        { label: "Chance to miss", value: pct(1 - s.p, 1) },
        { label: "Fair price", value: american(s.fair) },
      ]}
      note={s.note}
    />
  );
}

function Tier({ title, sub, slips }: { title: string; sub?: string; slips: S[] }) {
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
          <Card s={s} key={i} />
        ))}
      </div>
    </section>
  );
}

const bySize = (list: S[]) => [...new Set(list.map((s) => s.title))].map((t) => list.filter((s) => s.title === t));

export function NflTonight() {
  const made = new Date(T.made_at).toLocaleString("en-CA", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Tonight: {T.game}</h2>
            <p className="sub">
              {T.kickoff} · {T.venue}. Made {made} ET from the algorithm&apos;s build of {T.built_from}. The slip outlined in red in each tier is the
              algorithm&apos;s pick; the other is the next-best Godseye slip.
            </p>
          </div>
        </div>
        <ul className="why">
          {T.rules.map((r) => (
            <li key={r}>{r}</li>
          ))}
          <li>Rungs checked against {T.listings.source} listings. bet365 is not in that feed: check each rung in the app before placing.</li>
        </ul>
      </section>
      {bySize(T.sgps).map((g) => (
        <Tier key={g[0].title} title={g[0].title} sub="Props only, no touchdown legs." slips={g} />
      ))}
      {bySize(T.hybrids).map((g) => (
        <Tier key={g[0].title} title={g[0].title} sub="Props legs plus one anytime touchdown." slips={g} />
      ))}
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Anytime TD tonight</h2>
            <p className="sub">The algorithm&apos;s touchdown board for this game.</p>
          </div>
        </div>
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Player</th>
                <th>Chance</th>
                <th>Fair</th>
                <th>Listed</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {T.atd.singles.map((p) => (
                <tr key={p.name}>
                  <td>
                    <b>{p.name}</b> <small>{p.team} {p.pos}</small>
                  </td>
                  <td className="num">{pct(p.p, 1)}</td>
                  <td className="num">{american(p.fair)}</td>
                  <td className="num">{p.listed || "–"}</td>
                  <td>{p.flag}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {T.atd.double && (
          <div className="gs-slips ge-set">
            <Card s={T.atd.double} />
          </div>
        )}
      </section>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Anytime TD: tonight + Thanksgiving</h2>
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
              legs={s.legs.map((l) => ({ text: l.text, sub: `${l.side} · ${l.who} · ${l.game}`, value: pct(l.p) }))}
              stats={[
                { label: "Chance to hit", value: pct(s.p, 1), tone: "red" },
                { label: "Chance to miss", value: pct(1 - s.p, 1) },
                { label: "Fair price", value: american(s.fair) },
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
      {T.lotto && <Tier title="Lotto" sub="A longshot: +1500 or longer on the algorithm's fair price." slips={[T.lotto]} />}
    </>
  );
}
