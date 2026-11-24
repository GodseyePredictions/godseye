"use client";

import { useCallback, useState } from "react";
import type { OwnerSummary } from "@/lib/owner";

const usd = (x: number, places = 2) => `$${x.toLocaleString("en-CA", { minimumFractionDigits: places, maximumFractionDigits: places })}`;
const signed = (x: number) => `${x >= 0 ? "+" : "−"}${usd(Math.abs(x))}`;

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="own-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </div>
  );
}

export function OwnerDashboard() {
  const [key, setKey] = useState("");
  const [data, setData] = useState<OwnerSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (k: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/owner/summary", { headers: { Authorization: `Bearer ${k}` }, cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "The summary could not be loaded.");
      setData(body);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "The summary could not be loaded.");
    } finally {
      setBusy(false);
    }
  }, []);

  // the key is held in memory only: reloading or closing the tab locks the page again
  const lock = () => {
    setData(null);
    setKey("");
  };

  if (!data) {
    return (
      <form
        className="own-gate"
        onSubmit={(e) => {
          e.preventDefault();
          if (key) void load(key);
        }}
      >
        <label htmlFor="own-key">Owner key</label>
        <input id="own-key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
        <button type="submit" disabled={busy || !key}>
          {busy ? "Checking…" : "Open"}
        </button>
        {error ? <p role="alert">{error}</p> : <p>This page is for the owner. It is not linked from the site.</p>}
      </form>
    );
  }

  const { users, advisor, nba } = data;
  return (
    <div className="own">
      <div className="own-bar">
        <span>As of {new Date(data.at).toLocaleString("en-CA", { dateStyle: "medium", timeStyle: "short" })}</span>
        <button type="button" onClick={() => void load(key)} disabled={busy}>
          Refresh
        </button>
        <button type="button" onClick={lock}>
          Lock
        </button>
      </div>

      <h2>Subscribers</h2>
      <div className="own-tiles">
        <Tile label="Pro" value={String(users.byPlan.pro)} />
        <Tile label="Elite" value={String(users.byPlan.elite)} />
        <Tile label="No plan" value={String(users.byPlan.none)} sub={`${users.canceled} cancelled`} />
        <Tile label="Payment overdue" value={String(users.pastDue)} />
        <Tile label="Set a bankroll" value={String(users.withBankroll)} sub={`of ${users.total} users`} />
      </div>

      <h2>Advisor</h2>
      <div className="own-tiles">
        <Tile label="Messages today" value={String(advisor.messagesToday)} />
        <Tile label="API cost, 7 days" value={usd(advisor.cost.last7Days)} sub={`${advisor.calls.last7Days} model calls`} />
        <Tile label="API cost, 30 days" value={usd(advisor.cost.last30Days)} sub={`${advisor.calls.last30Days} model calls`} />
        <Tile label="API cost, all time" value={usd(advisor.cost.allTime)} sub={`${advisor.calls.allTime} model calls`} />
      </div>
      {advisor.unpricedCalls ? <p className="own-note">{advisor.unpricedCalls} calls ran on a model with no price set, so the cost above is low by that much.</p> : null}
      {advisor.top.length ? (
        <div className="own-table">
          <table>
            <thead>
              <tr>
                <th scope="col">User</th>
                <th scope="col">Plan</th>
                <th scope="col">Today</th>
                <th scope="col">Calls, 30 days</th>
                <th scope="col">Cost, 30 days</th>
                <th scope="col">Cost, all time</th>
              </tr>
            </thead>
            <tbody>
              {advisor.top.map((r) => (
                <tr key={r.user}>
                  <th scope="row">{r.user}</th>
                  <td>{r.plan === "none" ? (r.status === "canceled" ? "cancelled" : "none") : r.plan}{r.status === "past_due" ? " (overdue)" : ""}</td>
                  <td>{r.messagesToday}</td>
                  <td>{r.calls30}</td>
                  <td>{usd(r.cost30, 4)}</td>
                  <td>{usd(r.costAll, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="own-note">No one has used the advisor yet.</p>
      )}

      <h2>NBA record (private)</h2>
      {nba ? (
        <>
          <div className="own-tiles">
            <Tile label="Slips issued" value={String(nba.issued)} sub={nba.from && nba.to ? `${nba.from} to ${nba.to}` : undefined} />
            <Tile label="Cashed" value={String(nba.cashed)} sub={nba.hitRate == null ? undefined : `${(nba.hitRate * 100).toFixed(1)}% of slips`} />
            <Tile label="Lost" value={String(nba.lost)} />
            <Tile label="Example stakes, net" value={signed(nba.exampleNet)} sub={`on ${usd(nba.exampleStaked)} staked`} />
          </div>
          <p className="own-note">Stakes are the example stakes from the Cashed slips tab applied to every slip issued, not bets placed. The public site shows winning slips only.</p>
        </>
      ) : (
        <p className="own-note">No graded record file was found.</p>
      )}
    </div>
  );
}
