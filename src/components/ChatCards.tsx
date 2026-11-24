/* The cards the advisor chat shows under a reply: what each tool returned, as a Godseye slip.
   They display the tool's own numbers; nothing is recalculated here. */
import { MARKET_LABEL, type Market } from "@/lib/advisor/legs";
import type { Card } from "@/lib/store/types";
import { Slip, american, pct, type SlipLeg, type SlipStat } from "./Slip";

type Rated = { player: string; market: Market; threshold: number | null; prob?: number };
const legName = (l: Rated) => (l.market === "atd" ? `${l.player} anytime touchdown` : `${l.player} ${l.threshold}+ ${MARKET_LABEL[l.market] ?? l.market}`);
const money = (n: unknown) => (typeof n === "number" ? `$${Number.isInteger(n) ? n : n.toFixed(2)}` : "–");
const signedPct = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)}%`;

/* eslint-disable @typescript-eslint/no-explicit-any -- card data is the tool's JSON, read defensively */
export function ChatCard({ card }: { card: Card }) {
  const d = (card.data ?? {}) as any;
  switch (card.kind) {
    case "slip": {
      const legs: SlipLeg[] = (d.legs ?? []).map((l: any) => ({
        text: [l.player, l.market === "atd" ? "anytime touchdown" : l.market && l.market !== "other" ? `${l.threshold ?? "?"}${l.side === "under" ? " or fewer" : "+"} ${MARKET_LABEL[l.market as Market] ?? l.marketText}` : l.marketText].filter(Boolean).join(" ") || "Unread leg",
        sub: l.needs?.length ? `Could not read: ${l.needs.join(", ")}` : undefined,
        value: l.odds != null ? american(l.odds) : undefined,
      }));
      return (
        <Slip
          title="Your slip, as read"
          meta={d.book ?? undefined}
          legs={legs}
          warn={(d.problems ?? []).join(" ") || undefined}
          stats={[{ label: "Legs", value: String(legs.length) }, { label: "Slip price", value: american(d.totalOdds) }, { label: "Stake", value: d.stake != null ? money(d.stake) : "–" }]}
          note="Check every leg before it is graded."
        />
      );
    }
    case "audit": {
      const legs: SlipLeg[] = (d.legs ?? []).map((l: any) => ({
        text: l.match ? legName(l.match) : l.text,
        sub: l.status === "rated" ? [l.edge != null ? `${l.edge >= 0 ? "+" : "−"}${Math.abs(l.edge * 100).toFixed(1)} pts against its price` : null, l.injury ? `Listed ${l.injury}` : null, l.flags?.includes("fights-script") ? "Works against your other legs" : null, l.flags?.includes("singles-only") ? "Singles only this week" : null].filter(Boolean).join(" · ") || undefined : l.note,
        value: l.status === "rated" ? pct(l.prob, 1) : "unrated",
      }));
      const warns = (d.rules ?? []).filter((r: any) => r.level === "warn").map((r: any) => r.detail);
      const stats: SlipStat[] = [
        { label: "Chance to hit", value: d.joint == null ? "not stated" : pct(d.joint, 1), tone: "red" },
        { label: "Fair odds", value: american(d.fairOdds) },
        { label: "Book odds", value: american(d.bookOdds) },
        { label: "Value", value: d.value == null ? "not stated" : signedPct(d.value), tone: d.value == null ? undefined : d.value > 0 ? "good" : "bad" },
      ];
      return <Slip title="Slip audit" meta={`${d.rated ?? 0} of ${(d.legs ?? []).length} legs rated`} legs={legs} stats={stats} warn={warns.join(" ") || undefined} note={d.jointNote} />;
    }
    case "changes": {
      const out: SlipLeg[] = [
        ...(d.remove ?? []).map((r: any) => ({ text: legName(r.leg), sub: r.reason, value: "remove", state: "out" as const })),
        ...(d.swap ?? []).map((s: any) => ({ text: `${legName(s.to)}`, sub: `In place of ${legName(s.from)}. ${s.reason}`, value: pct(s.to.prob), state: "in" as const })),
        ...(d.add ?? []).map((a: any) => ({ text: legName(a.leg), sub: a.reason, value: pct(a.leg.prob), state: "in" as const })),
      ];
      const imp = d.improved;
      if (!imp) return <Slip title="Suggested changes" note={(d.notes ?? [])[0] ?? "Nothing to change."} />;
      return (
        <>
          <Slip title="Suggested changes" meta="Algorithm output only" legs={out} note={(d.notes ?? [])[0]} />
          <Slip
            title="Improved slip"
            meta={`${(imp.legs ?? []).length + (imp.unratedKept ?? []).length} legs`}
            legs={[...(imp.legs ?? []).map((l: any) => ({ text: legName(l), value: pct(l.prob) })), ...(imp.unratedKept ?? []).map((t: string) => ({ text: t, value: "unrated" }))]}
            stats={[{ label: "Chance to hit", value: imp.joint == null ? "not stated" : pct(imp.joint, 1), tone: "red" }, { label: "Fair odds", value: american(imp.fairOdds) }, { label: "Book odds", value: "your book" }]}
            note={imp.note}
          />
        </>
      );
    }
    case "stake": {
      const s = d.stake ?? {};
      return (
        <Slip
          title="Stake"
          meta="From the bankroll engine"
          big={s.status === "bet" ? s.label : s.status === "unrated" ? "No stake" : "No bet"}
          note={s.reason}
          warn={s.status === "blocked" ? "A limit you set is in force." : undefined}
          stats={[{ label: "Chance to hit", value: d.joint_probability == null ? "not stated" : pct(d.joint_probability, 1) }, { label: "Book odds", value: american(d.book_odds) }]}
        />
      );
    }
    case "picks": {
      const picks: any[] = d.picks ?? [];
      if (!picks.length) return <Slip title="Algorithm picks" note={d.note ?? "The algorithm has no picks for that."} />;
      const top = [...picks].sort((a, b) => (b.joint_probability ?? 0) - (a.joint_probability ?? 0)).slice(0, 3);
      return (
        <>
          {top.map((p, i) => (
            <Slip
              key={i}
              title={p.game}
              meta={p.kind}
              legs={(p.legs ?? []).map((l: any) => ({ text: l.leg, value: pct(l.probability) }))}
              stats={[{ label: "Chance to hit", value: pct(p.joint_probability, 1), tone: "red" }, ...(p.book_price != null ? [{ label: p.price_is_estimate ? "Legs multiplied" : "Book odds", value: american(p.book_price) }] : [])]}
              note={i === top.length - 1 && picks.length > top.length ? `${picks.length - top.length} more on the picks tabs.` : undefined}
            />
          ))}
        </>
      );
    }
    case "bankroll":
      if (!d.set) return <Slip title="Bankroll" note={d.note} />;
      return (
        <Slip
          title="Bankroll"
          meta={`${d.risk_profile} profile`}
          warn={d.limit_in_force ? d.limit_message : undefined}
          stats={[
            { label: "Bankroll", value: money(d.bankroll_dollars) }, { label: "One unit", value: money(d.unit_dollars) },
            { label: "Staked tonight", value: money(d.staked_tonight_dollars) }, { label: "Room left", value: money(d.room_left_tonight_dollars), tone: d.limit_in_force ? "bad" : undefined },
          ]}
        />
      );
    case "logged":
      if (!d.logged) return <Slip title="Not logged" note={d.reason} />;
      return (
        <Slip
          title="Bet logged"
          meta={d.bet?.book || undefined}
          legs={(d.bet?.legs ?? []).map((l: any) => ({ text: l.description }))}
          stats={[{ label: "Stake", value: money(d.bet?.stake) }, { label: "Price", value: american(d.bet?.price) }]}
          note="It counts toward tonight and is re-checked when the algorithm's numbers change."
        />
      );
    case "history": {
      const o = d.overall;
      if (!o) return <Slip title="Your history" note={d.note} />;
      const rows: SlipLeg[] = [...(d.by_leg_count ?? []), d.slips_with_a_touchdown_leg].filter((g: any) => g && g.bets > 0).map((g: any) => ({
        text: g.group, sub: `${g.won} won, ${g.lost} lost${g.open ? `, ${g.open} open` : ""}`, value: g.hit_rate == null ? "–" : pct(g.hit_rate),
      }));
      return (
        <Slip
          title="Your history"
          meta={`${o.bets} tracked bets`}
          legs={rows}
          stats={[{ label: "Won", value: String(o.won) }, { label: "Lost", value: String(o.lost) }, { label: "Result", value: `${o.profit_dollars < 0 ? "−" : "+"}$${Math.abs(o.profit_dollars)}`, tone: o.profit_dollars < 0 ? "bad" : "good" }]}
          note={d.note}
        />
      );
    }
    default:
      return null;
  }
}
