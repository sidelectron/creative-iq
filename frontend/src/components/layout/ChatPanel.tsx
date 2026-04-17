import { useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Send, Trash2, X } from "lucide-react";
import { useChatWebSocket, type ChatMessage } from "../../hooks/useChatWebSocket";
import { api } from "../../lib/api";

type Props = {
  brandId: string | null;
  onClose: () => void;
};

type ConvoRow = { id: string; title: string | null; message_count: number; last_message_at: string | null };
type MsgRow = { id: string; role: string; content: string; created_at: string };

const markdownComponents: Components = {
  a: ({ href, children }) =>
    href?.startsWith("/") ? (
      <Link to={href} className="font-medium text-accent underline underline-offset-2">
        {children}
      </Link>
    ) : (
      <a href={href} className="text-accent underline underline-offset-2" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
};

const STATIC_CHIPS = [
  "What changed recently in my creative performance?",
  "What should I test next based on my profile?",
  "Summarize my brand's top-performing ad patterns.",
  "Draft a short creative brief outline.",
  "How do my A/B test results compare to baseline?",
];

export function ChatPanel({ brandId, onClose }: Props): React.ReactElement {
  const [input, setInput] = useState("");
  const [jobSubId, setJobSubId] = useState("");
  const [convoOpen, setConvoOpen] = useState(false);
  const qc = useQueryClient();

  const {
    statusMessage,
    messages,
    followups,
    busy,
    send,
    sendSubscribeGeneration,
    connected,
    resetThread,
    selectConversation,
  } = useChatWebSocket(brandId, true);

  const convosQ = useQuery({
    queryKey: ["chat-convos", brandId],
    queryFn: async () => {
      const { data } = await api.get<{ items: ConvoRow[] }>(
        `/api/v1/brands/${brandId}/chat/conversations`,
        { params: { page: 1, page_size: 30 } },
      );
      return data.items;
    },
    enabled: !!brandId,
  });

  const deleteM = useMutation({
    mutationFn: async (conversationId: string) => {
      await api.delete(`/api/v1/brands/${brandId}/chat/conversations/${conversationId}`);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["chat-convos", brandId] }),
  });

  const loadConversation = async (c: ConvoRow) => {
    const { data } = await api.get<{ items: MsgRow[] }>(
      `/api/v1/brands/${brandId}/chat/conversations/${c.id}/messages`,
      { params: { page: 1, page_size: 100 } },
    );
    const mapped: ChatMessage[] = data.items.map((row) => ({
      id: row.id,
      role: row.role === "user" ? "user" : "assistant",
      content: row.content,
    }));
    selectConversation(c.id, mapped);
    setConvoOpen(false);
  };

  const chips = followups.length > 0 ? followups.slice(0, 5) : STATIC_CHIPS;

  return (
    <aside
      className="flex h-full w-full flex-col border-l border-slate-200 bg-white"
      aria-label="Chat with CreativeIQ"
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
        <h2 className="text-section text-slate-900">Chat with CreativeIQ</h2>
        <div className="flex flex-wrap gap-2">
          {brandId && (
            <button
              type="button"
              className="text-datalabel text-slate-600 hover:underline"
              onClick={() => setConvoOpen((o) => !o)}
            >
              Conversations
            </button>
          )}
          <button
            type="button"
            className="text-datalabel text-accent hover:underline"
            onClick={() => resetThread()}
          >
            New
          </button>
          <button type="button" className="rounded p-1 hover:bg-slate-100" onClick={onClose}>
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>
      </header>

      {convoOpen && brandId && (
        <div className="max-h-40 overflow-y-auto border-b border-slate-100 px-2 py-2 text-datalabel">
          {(convosQ.data ?? []).map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-1 border-b border-slate-50 py-1">
              <button
                type="button"
                className="min-w-0 flex-1 truncate text-left hover:text-accent"
                onClick={() => void loadConversation(c)}
              >
                {c.title ?? "Conversation"} ({c.message_count})
              </button>
              <button
                type="button"
                className="shrink-0 rounded p-1 text-danger hover:bg-red-50"
                title="Delete conversation"
                onClick={() => deleteM.mutate(c.id)}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {!brandId ? (
        <p className="p-4 text-datalabel text-muted">Select a brand to chat.</p>
      ) : (
        <>
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 && (
              <p className="text-datalabel text-muted">
                Ask about creative performance, tests, or briefs. Status lines show server text as-is.
              </p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[90%] rounded-lg px-3 py-2 text-body ${
                    m.role === "user"
                      ? "bg-accent text-white"
                      : m.role === "system"
                        ? "border border-dashed border-slate-300 bg-amber-50 text-slate-800"
                        : "border border-slate-200 bg-slate-50 text-slate-900"
                  } markdown-cite max-w-none`}
                >
                  {m.role === "assistant" ? (
                    <div>
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {m.content}
                      </ReactMarkdown>
                      {m.refs && m.refs.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2 border-t border-slate-200 pt-2">
                          {m.refs.map((r) => (
                            <Link
                              key={r.to + r.label}
                              to={r.to}
                              className="rounded-full bg-white px-2 py-0.5 text-datalabel text-accent shadow-sm ring-1 ring-slate-200 hover:bg-slate-50"
                            >
                              {r.label}
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2 text-datalabel text-muted">
                <span className="flex gap-1" aria-hidden>
                  <span className="chat-dot inline-block h-2 w-2 rounded-full bg-slate-400" />
                  <span className="chat-dot inline-block h-2 w-2 rounded-full bg-slate-400" />
                  <span className="chat-dot inline-block h-2 w-2 rounded-full bg-slate-400" />
                </span>
                {statusMessage ? <span>{statusMessage}</span> : <span>Thinking…</span>}
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-2">
            {chips.map((chip) => (
              <button
                key={chip}
                type="button"
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-datalabel hover:bg-slate-100"
                onClick={() => send(chip)}
                disabled={!connected || busy}
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="border-t border-slate-100 px-4 py-2">
            <p className="text-datalabel text-muted">Subscribe to generation job (WS)</p>
            <div className="mt-1 flex gap-2">
              <input
                className="min-w-0 flex-1 rounded border px-2 py-1 font-mono text-xs"
                placeholder="job UUID"
                value={jobSubId}
                onChange={(e) => setJobSubId(e.target.value)}
              />
              <button
                type="button"
                className="rounded border px-2 py-1 text-datalabel"
                disabled={!connected || !jobSubId.trim()}
                onClick={() => sendSubscribeGeneration(jobSubId.trim())}
              >
                Subscribe
              </button>
            </div>
          </div>

          <footer className="border-t border-slate-200 p-3">
            <div className="mb-2 flex items-center gap-2 text-datalabel text-muted">
              <button
                type="button"
                className="rounded p-1 opacity-40"
                title="Coming soon"
                disabled
                aria-disabled
              >
                <Paperclip className="h-4 w-4" aria-hidden />
              </button>
              {!connected && brandId ? <span>Connecting…</span> : null}
            </div>
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!input.trim() || busy) return;
                send(input.trim());
                setInput("");
              }}
            >
              <input
                className="flex-1 rounded border border-slate-300 px-3 py-2 text-body focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                placeholder="Message…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!connected || busy}
              />
              <button
                type="submit"
                className="rounded bg-accent p-2 text-white disabled:opacity-50"
                disabled={!connected || busy}
              >
                <Send className="h-5 w-5" aria-hidden />
              </button>
            </form>
          </footer>
        </>
      )}
    </aside>
  );
}
