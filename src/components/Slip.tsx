/* The Godseye slip: a white paper ticket with a red title and black type (src/styles/slip.css).
   One component for every place a slip, pick, audit or stake is shown. */
import type { ReactNode } from "react";

export type SlipLeg = { text: string; sub?: string; value?: string; state?: "in" | "out" };
/** The reasoning behind a slip: the algorithm's read of the game, then its reasons leg by leg. */
export type SlipReasons = { intel?: string[]; legs?: { text: string; why: string[] }[] };
export type SlipStat = { label: string; value: string; tone?: "red" | "good" | "bad" };

export function Slip({
  title, meta, legs, stats, note, warn, big, children, plain, why,
}: {
  title: string;
  meta?: string;
  legs?: SlipLeg[];
  stats?: SlipStat[];
  note?: ReactNode;
  warn?: ReactNode;
  /** One large figure, such as a stake. */
  big?: string;
  children?: ReactNode;
  /** Without the ticket notches, for narrow or nested cards. */
  plain?: boolean;
  /** Shown folded under the legs: why the algorithm rates this slip as it does. */
  why?: SlipReasons;
}) {
  const reasons = why && ((why.intel?.length ?? 0) > 0 || (why.legs ?? []).some((l) => l.why.length > 0)) ? why : null;
  return (
    <article className={plain ? "gs-slip plain" : "gs-slip"}>
      <header className="gs-slip-head">
        <h3 className="gs-slip-title">{title}</h3>
        {meta && <span className="gs-slip-meta">{meta}</span>}
      </header>
      {big && <p className="gs-slip-big">{big}</p>}
      {legs && legs.length > 0 && (
        <ul className="gs-slip-legs">
          {legs.map((l, i) => (
            <li key={i} className={l.state}>
              <span>
                {l.text}
                {l.sub && <small>{l.sub}</small>}
              </span>
              {l.value && <span className="num">{l.value}</span>}
            </li>
          ))}
        </ul>
      )}
      {children}
      {reasons && (
        <details className="gs-slip-why">
          <summary>Why the algorithm rates it</summary>
          {reasons.intel && reasons.intel.length > 0 && (
            <>
              <h4>The game</h4>
              <ul>
                {reasons.intel.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </>
          )}
          {(reasons.legs ?? []).filter((l) => l.why.length > 0).map((l) => (
            <div key={l.text}>
              <h4>{l.text}</h4>
              <ul>
                {l.why.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
      {warn && <p className="gs-slip-note warn">{warn}</p>}
      {note && <p className="gs-slip-note">{note}</p>}
      {stats && stats.length > 0 && (
        <dl className="gs-slip-foot">
          {stats.map((s) => (
            <div key={s.label}>
              <dt>{s.label}</dt>
              <dd className={s.tone}>{s.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export const pct = (p: number | null | undefined, digits = 0) => (p == null || !Number.isFinite(p) ? "–" : `${(p * 100).toFixed(digits)}%`);
export const american = (a: number | null | undefined) => (a == null || !Number.isFinite(a) ? "–" : a > 0 ? `+${a}` : `−${Math.abs(a)}`);
