"use client";

/* The 1-to-1 advisor chat. The conversation is kept in this browser until accounts exist and is sent
   with each message; the server runs the advisor and streams its answer back. */
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ChatMessage } from "@/lib/advisor/agent";
import { readAccount, subscribeAccount } from "./BankrollStrategy";
import { NO_BETS, readBets, subscribeBets } from "./betsStore";

const STORE = "godseye.chat.v1";
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const TOOL_LABEL: Record<string, string> = {
  parse_slip: "Reading your slip",
  grade_slip: "Grading it against the algorithm",
  suggest_changes: "Looking for better legs",
  get_player_intel: "Pulling the algorithm's numbers on the player",
  get_game_intel: "Checking the game script",
};

/** What the chat window shows: the words exchanged, not the tool traffic in between. */
type Line = { who: "you" | "advisor"; text: string; image?: boolean };
function linesOf(messages: ChatMessage[]): Line[] {
  const out: Line[] = [];
  for (const m of messages) {
    if (typeof m.content === "string") {
      out.push({ who: m.role === "user" ? "you" : "advisor", text: m.content });
      continue;
    }
    if (m.content.some((b) => b.type === "tool_result")) continue;
    const text = m.content
      .filter((b): b is Extract<typeof b, { type: "text" }> => b.type === "text")
      .map((b) => b.text.replace(/\n*\[The user attached a bet slip screenshot[^\]]*\]/, "").replace("[bet slip screenshot, already read]", ""))
      .join("")
      .trim();
    const image = m.role === "user" && m.content.some((b) => b.type === "image" || (b.type === "text" && b.text.includes("bet slip screenshot")));
    if (text || image) out.push({ who: m.role === "user" ? "you" : "advisor", text, image });
  }
  return out;
}

function load(): ChatMessage[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE) ?? "[]");
    return Array.isArray(raw) ? (raw as ChatMessage[]) : [];
  } catch {
    return [];
  }
}
function save(messages: ChatMessage[]) {
  try {
    localStorage.setItem(STORE, JSON.stringify(messages));
  } catch {
    /* storage unavailable or full: the chat still works for this visit */
  }
}

const toBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("The image could not be read."));
    r.readAsDataURL(file);
  });

export function AdvisorChat({ sport }: { sport: "NFL" | "NBA" }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [ready, setReady] = useState(false);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ you: Line; reply: string; activity: string } | null>(null);
  const [error, setError] = useState("");
  const account = useSyncExternalStore(subscribeAccount, readAccount, () => null);
  const bets = useSyncExternalStore(subscribeBets, readBets, () => NO_BETS);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // the saved conversation is only known in the browser, so it is loaded after the first paint
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMessages(load());
    setReady(true);
  }, []);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages, pending]);

  const send = async () => {
    const text = draft.trim();
    if ((!text && !file) || busy) return;
    if (file && file.size > MAX_IMAGE_BYTES) {
      setError("That image is larger than 5 MB. Crop it to the slip and try again.");
      return;
    }
    setBusy(true);
    setError("");
    setPending({ you: { who: "you", text, image: !!file }, reply: "", activity: "" });
    setDraft("");
    const attached = file;
    setFile(null);
    try {
      const image = attached ? { mediaType: attached.type, data: await toBase64(attached) } : null;
      const res = await fetch("/api/advisor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, text, image, account, bets }),
      });
      if (!res.ok || !res.body) {
        const j = (await res.json().catch(() => null)) as { error?: string } | null;
        throw new Error(j?.error ?? "The advisor is not available here.");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let done = false;
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const e = JSON.parse(line) as
            | { type: "text"; delta: string } | { type: "tool"; name: string } | { type: "notice"; message: string }
            | { type: "done"; messages: ChatMessage[] } | { type: "error"; message: string };
          if (e.type === "text") setPending((p) => p && { ...p, reply: p.reply + e.delta, activity: "" });
          else if (e.type === "tool") setPending((p) => p && { ...p, activity: TOOL_LABEL[e.name] ?? "Working" });
          else if (e.type === "notice") setError(e.message);
          else if (e.type === "error") throw new Error(e.message);
          else if (e.type === "done") {
            done = true;
            setMessages(e.messages);
            save(e.messages);
          }
        }
      }
      if (!done) throw new Error("The connection dropped before the advisor finished. Try again.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
      setDraft(text); // give the message back so it is not lost
    } finally {
      setPending(null);
      setBusy(false);
    }
  };

  const lines = linesOf(messages);
  const empty = ready && lines.length === 0 && !pending;
  const bubble = (l: Line, key: string | number) => (
    <div key={key} className={`chat-line ${l.who}`}>
      <div className="chat-who">{l.who === "you" ? "You" : "Advisor"}</div>
      <div className="chat-text">
        {l.image && <span className="pill neutral">Slip screenshot</span>}
        {l.image && l.text ? " " : ""}
        {l.text}
      </div>
    </div>
  );

  return (
    <section className="panel chat">
      <div className="section-head">
        <div>
          <h2>Advisor</h2>
          <p className="sub">
            Ask about a player, a game or your own slip. Every number it quotes comes from the {sport} and other Godseye algorithms and your Bankroll Strategy
            settings.
          </p>
        </div>
        {lines.length > 0 && (
          <button
            className="btn sm"
            disabled={busy}
            onClick={() => {
              setMessages([]);
              save([]);
              setError("");
            }}
          >
            New chat
          </button>
        )}
      </div>

      <div className="chat-log" aria-live="polite">
        {empty && (
          <div className="empty">
            <p>Try one of these:</p>
            <div className="t-row" style={{ justifyContent: "center" }}>
              {[
                "Attach a screenshot of your slip and ask: is this worth playing?",
                sport === "NFL" ? "What does the algorithm think of tonight's game script?" : "Who is out tonight, and who gains minutes?",
                "What is a safer rung for a player on my slip?",
              ].map((s) => (
                <button key={s} className="btn" onClick={() => setDraft(s.startsWith("Attach") ? "Is this slip worth playing?" : s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {lines.map((l, i) => bubble(l, i))}
        {pending && bubble(pending.you, "pending-you")}
        {pending && (
          <div className="chat-line advisor">
            <div className="chat-who">Advisor</div>
            <div className="chat-text">
              {pending.reply}
              {(pending.activity || !pending.reply) && <span className="chat-activity">{pending.activity || "Thinking"}…</span>}
            </div>
          </div>
        )}
        <div ref={end} />
      </div>

      {error && <p className="t-err">{error}</p>}
      {!account && <p className="sub">No bankroll is set, so the advisor cannot suggest stakes. Set one in Bankroll Strategy.</p>}

      <div className="chat-input">
        <textarea
          rows={2}
          value={draft}
          disabled={busy}
          placeholder="Ask the advisor…"
          aria-label="Message to the advisor"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <div className="t-row" style={{ margin: 0, alignItems: "center" }}>
          <label className="btn">
            {file ? `Attached: ${file.name.slice(0, 24)}` : "Attach a slip"}
            <input type="file" accept="image/png,image/jpeg,image/webp" hidden disabled={busy} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          {file && (
            <button className="t-x" onClick={() => setFile(null)}>
              Remove
            </button>
          )}
          <button className="btn primary" disabled={busy || (!draft.trim() && !file)} onClick={send}>
            Send
          </button>
        </div>
      </div>
      <p className="t-note">
        The advisor explains what the algorithms say; it does not promise outcomes. A well-priced bet still loses, and a parlay loses more often than it wins. This
        conversation is saved in this browser only. Screenshots are sent to be read and are not kept.
      </p>
    </section>
  );
}
