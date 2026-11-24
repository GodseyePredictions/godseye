"use client";

/* The 1-to-1 advisor chat. Mobile-first: the conversation fills the screen, the composer stays at the
   bottom, and each tool result appears as a slip card under the reply. Conversations are stored per user
   on the server; this browser keeps only an anonymous id until sign-in exists. */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { Bet } from "@/lib/bets";
import type { Card, DisplayItem } from "@/lib/store/types";
import { readAccount, subscribeAccount } from "./BankrollStrategy";
import { ChatCard } from "./ChatCards";
import { NO_BETS, readBets, subscribeBets, writeBets } from "./betsStore";

const UID = "godseye.uid";
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** This browser's anonymous user id. Sign-in replaces it. */
export function userId(): string {
  try {
    let id = localStorage.getItem(UID);
    if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
      id = `anon_${crypto.randomUUID().replace(/-/g, "")}`;
      localStorage.setItem(UID, id);
    }
    return id;
  } catch {
    return "anon_private_window_0000";
  }
}

const TOOL_LABEL: Record<string, string> = {
  parse_slip: "Reading your slip",
  grade_slip: "Grading it against the algorithm",
  suggest_changes: "Looking for better legs",
  size_bet: "Sizing the stake",
  get_algo_picks: "Pulling the algorithm's picks",
  get_odds: "Checking prices",
  get_bankroll: "Checking your bankroll",
  log_bet: "Logging the bet",
  get_user_history: "Looking at your history",
  get_player_intel: "Pulling the algorithm's numbers on the player",
  get_game_intel: "Checking the game script",
};

type History = {
  summary: string;
  conversations: { id: string; startedAt: string; updatedAt: string; display: DisplayItem[] }[];
  plan: { tier: string; cap: number | null; usedToday: number; canChat: boolean; message: string | null };
  demo?: boolean;
};
type Pending = { text: string; image: boolean; reply: string; activity: string; cards: Card[] };

const toBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("The image could not be read."));
    r.readAsDataURL(file);
  });

function Items({ items }: { items: DisplayItem[] }) {
  return (
    <>
      {items.map((d, i) =>
        d.type === "card" ? (
          <div className="chat-card" key={i}>
            <ChatCard card={d.card} />
          </div>
        ) : (
          <div key={i} className={`chat-line ${d.who}`}>
            <div className="chat-text">
              {d.image && <span className="chat-attach">Slip screenshot</span>}
              {d.text}
            </div>
          </div>
        ),
      )}
    </>
  );
}

export function AdvisorChat({ sport }: { sport: "NFL" | "NBA" }) {
  const [history, setHistory] = useState<History | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [items, setItems] = useState<DisplayItem[]>([]);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const account = useSyncExternalStore(subscribeAccount, readAccount, () => null);
  const bets = useSyncExternalStore(subscribeBets, readBets, () => NO_BETS);
  const end = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async (open: "latest" | "keep") => {
    try {
      const res = await fetch("/api/advisor/history", { headers: { "x-godseye-user": userId() } });
      if (!res.ok) throw new Error();
      const h = (await res.json()) as History;
      setHistory(h);
      if (open === "latest" && h.conversations[0] && Date.now() - new Date(h.conversations[0].updatedAt).getTime() < 6 * 3600e3) {
        setConversationId(h.conversations[0].id);
        setItems(h.conversations[0].display);
      }
    } catch {
      setHistory({ summary: "", conversations: [], plan: { tier: "none", cap: 0, usedToday: 0, canChat: false, message: "The advisor is not available here. It needs the Godseye server." } });
    }
  }, []);
  useEffect(() => {
    // the user's stored conversations are only known once the browser asks for them
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadHistory("latest");
  }, [loadHistory]);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [items, pending]);

  const send = async () => {
    const text = draft.trim();
    if ((!text && !file) || busy) return;
    if (file && file.size > MAX_IMAGE_BYTES) {
      setError("That image is larger than 5 MB. Crop it to the slip and try again.");
      return;
    }
    setBusy(true);
    setError("");
    const attached = file;
    setPending({ text, image: !!attached, reply: "", activity: "", cards: [] });
    setDraft("");
    setFile(null);
    let finished = false;
    try {
      const image = attached ? { mediaType: attached.type, data: await toBase64(attached) } : null;
      const res = await fetch("/api/advisor", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-godseye-user": userId() },
        body: JSON.stringify({ conversationId, text, image, account, bets }),
      });
      if (!res.ok || !res.body) {
        const j = (await res.json().catch(() => null)) as { error?: string } | null;
        throw new Error(j?.error ?? "The advisor is not available here.");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let reply = "";
      const cards: Card[] = [];
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const e = JSON.parse(line) as
            | { type: "text"; delta: string } | { type: "tool"; name: string } | { type: "card"; card: Card } | { type: "retract" } | { type: "notice"; message: string }
            | { type: "bet"; bet: Bet } | { type: "blocked"; message: string } | { type: "done"; conversationId: string } | { type: "error"; message: string };
          if (e.type === "text") { reply += e.delta; setPending((p) => p && { ...p, reply, activity: "" }); }
          else if (e.type === "retract") { reply = ""; setPending((p) => p && { ...p, reply: "", activity: "Checking the numbers" }); }
          else if (e.type === "tool") setPending((p) => p && { ...p, activity: TOOL_LABEL[e.name] ?? "Working" });
          else if (e.type === "card") { cards.push(e.card); setPending((p) => p && { ...p, cards: [...cards] }); }
          else if (e.type === "notice") setError(e.message);
          else if (e.type === "bet") { if (!readBets().some((b) => b.id === e.bet.id)) writeBets([e.bet, ...readBets()]); }
          else if (e.type === "blocked") { finished = true; setError(e.message); setDraft(text); }
          else if (e.type === "error") throw new Error(e.message);
          else if (e.type === "done") {
            finished = true;
            const at = new Date().toISOString();
            setConversationId(e.conversationId);
            setItems((prev) => [
              ...prev, { type: "line", who: "you", text, image: !!attached, at },
              ...cards.map((card): DisplayItem => ({ type: "card", card })),
              ...(reply ? [{ type: "line" as const, who: "advisor" as const, text: reply, at }] : []),
            ]);
          }
        }
      }
      if (!finished) throw new Error("The connection dropped before the advisor finished. Try again.");
      void loadHistory("keep");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
      setDraft(text); // give the message back so it is not lost
    } finally {
      setPending(null);
      setBusy(false);
    }
  };

  const newChat = () => {
    setConversationId(null);
    setItems([]);
    setError("");
    setShowHistory(false);
  };
  const clearAll = async () => {
    await fetch("/api/advisor/history", { method: "DELETE", headers: { "x-godseye-user": userId() } }).catch(() => null);
    setConfirmClear(false);
    newChat();
    void loadHistory("keep");
  };

  const plan = history?.plan;
  const left = plan && plan.cap !== null ? Math.max(0, plan.cap - plan.usedToday) : null;
  const starters = [
    "Is this slip worth playing?",
    sport === "NFL" ? "What are the algorithm's picks this week?" : "What are the algorithm's picks tonight?",
    "How much room do I have left tonight?",
  ];

  return (
    <section className="chat" aria-label="Advisor chat">
      <header className="chat-top">
        <div>
          <h2>Your advisor</h2>
          <p>
            {plan ? (plan.tier === "none" ? "No active plan" : `${plan.tier === "pro" ? "Pro" : "Elite"} plan${left === null ? "" : ` · ${left} message${left === 1 ? "" : "s"} left today`}`) : "Loading…"}
            {history?.demo && <span className="chat-demo"> Demo mode: a scripted stand-in, not the real advisor</span>}
          </p>
        </div>
        <div className="chat-actions">
          <button className="btn sm" onClick={() => setShowHistory((v) => !v)} aria-expanded={showHistory}>
            History
          </button>
          <button className="btn sm" onClick={newChat} disabled={busy}>
            New chat
          </button>
        </div>
      </header>

      {showHistory && history && (
        <div className="chat-history">
          <h3>What your advisor remembers</h3>
          <p>{history.summary || "Nothing yet. After each chat, a short note on how you like to bet is kept here so the next one picks up where you left off."}</p>
          <h3>Past chats</h3>
          {history.conversations.length === 0 && <p>None yet.</p>}
          <ul>
            {history.conversations.map((c) => {
              const first = c.display.find((d) => d.type === "line" && d.who === "you");
              return (
                <li key={c.id}>
                  <button
                    onClick={() => {
                      setConversationId(c.id);
                      setItems(c.display);
                      setShowHistory(false);
                    }}
                  >
                    <b>{new Date(c.updatedAt).toLocaleDateString("en-CA", { month: "short", day: "numeric" })}</b>{" "}
                    {first && first.type === "line" ? first.text.slice(0, 70) || "Slip screenshot" : "Chat"}
                  </button>
                </li>
              );
            })}
          </ul>
          <button className={confirmClear ? "btn primary" : "btn"} onClick={() => (confirmClear ? clearAll() : setConfirmClear(true))} onBlur={() => setConfirmClear(false)}>
            {confirmClear ? "Confirm: delete all chats and notes" : "Clear my history"}
          </button>
          <p className="chat-small">Clearing removes every chat and the notes above. Your bets and bankroll are not touched.</p>
        </div>
      )}

      <div className="chat-log" aria-live="polite">
        {items.length === 0 && !pending && (
          <div className="chat-empty">
            <p>Ask about a player, a game or your own slip. Every number comes from the Godseye algorithms and your Bankroll Strategy settings.</p>
            <div className="chat-starters">
              {starters.map((s) => (
                <button key={s} onClick={() => setDraft(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <Items items={items} />
        {pending && (
          <>
            <Items items={[{ type: "line", who: "you", text: pending.text, image: pending.image, at: "" }, ...pending.cards.map((card): DisplayItem => ({ type: "card", card }))]} />
            <div className="chat-line advisor">
              <div className="chat-text">
                {pending.reply}
                {(pending.activity || !pending.reply) && <span className="chat-activity">{pending.activity || "Thinking"}…</span>}
              </div>
            </div>
          </>
        )}
        <div ref={end} />
      </div>

      {error && <p className="chat-error">{error}</p>}
      {plan && !plan.canChat && plan.message && !error && <p className="chat-error">{plan.message}</p>}

      <div className="chat-compose">
        {file && (
          <div className="chat-file">
            Attached: {file.name.slice(0, 32)}{" "}
            <button onClick={() => setFile(null)} aria-label="Remove the attachment">
              Remove
            </button>
          </div>
        )}
        <div className="chat-row">
          <label className="chat-attach-btn" title="Attach a slip screenshot">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 1 0 0-7a3.5 3.5 0 0 0 0 7z" />
            </svg>
            <span className="sr-only">Attach a slip screenshot</span>
            <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={busy} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <textarea
            rows={1}
            value={draft}
            disabled={busy}
            placeholder="Ask your advisor…"
            aria-label="Message to the advisor"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <button className="chat-send" disabled={busy || (!draft.trim() && !file)} onClick={() => void send()}>
            Send
          </button>
        </div>
        <p className="chat-small">
          The advisor explains what the algorithms say; it does not promise outcomes. A well-priced bet still loses, and a parlay loses more often than it wins.
        </p>
      </div>
    </section>
  );
}
