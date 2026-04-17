import { useCallback, useEffect, useRef, useState } from "react";
import { getStoredAccessToken } from "../lib/api";

export type ChatRefLink = { to: string; label: string };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  refs?: ChatRefLink[];
};

type WsFrame =
  | { type: "status"; message?: string; stage?: string }
  | { type: "response"; conversation_id?: string; content?: string }
  | {
      type: "metadata";
      suggested_followups?: string[];
      agent_type?: string;
      sources?: Record<string, unknown>;
      refs?: ChatRefLink[];
    }
  | { type: "error"; message?: string }
  | { type: "generation_complete"; message?: string; summary?: string; [k: string]: unknown };

function wsBaseUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

/** One WebSocket per brand; reuse for multiple turns (server read loop). */
export function useChatWebSocket(brandId: string | null, panelOpen: boolean) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef(0);
  const [connected, setConnected] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [followups, setFollowups] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const convoRef = useRef<string | null>(null);
  const pendingRefsRef = useRef<ChatRefLink[]>([]);

  const appendAssistant = useCallback((text: string, refs?: ChatRefLink[]) => {
    setMessages((m) => [
      ...m,
      { id: crypto.randomUUID(), role: "assistant", content: text, refs: refs?.length ? refs : undefined },
    ]);
  }, []);

  const appendSystem = useCallback((text: string) => {
    setMessages((m) => [
      ...m,
      { id: crypto.randomUUID(), role: "system", content: text },
    ]);
  }, []);

  useEffect(() => {
    if (!panelOpen || !brandId) {
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
      reconnectRef.current = 0;
      return;
    }
    const token = getStoredAccessToken();
    if (!token) return;

    const url = `${wsBaseUrl()}/ws/chat/${brandId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      reconnectRef.current = 0;
    };
    ws.onclose = () => {
      setConnected(false);
      setBusy(false);
    };
    ws.onmessage = (ev) => {
      try {
        const frame = JSON.parse(ev.data as string) as WsFrame;
        if (frame.type === "status") {
          setStatusMessage(frame.message ?? null);
        }
        if (frame.type === "response" && frame.content) {
          if (frame.conversation_id) convoRef.current = frame.conversation_id;
          const refs = pendingRefsRef.current;
          pendingRefsRef.current = [];
          appendAssistant(frame.content, refs);
          setBusy(false);
          setStatusMessage(null);
        }
        if (frame.type === "metadata") {
          if (frame.suggested_followups?.length) {
            setFollowups(frame.suggested_followups);
          }
          if (Array.isArray(frame.refs) && frame.refs.length) {
            pendingRefsRef.current = frame.refs.filter(
              (r): r is ChatRefLink =>
                typeof r === "object" &&
                r !== null &&
                typeof (r as ChatRefLink).to === "string" &&
                (r as ChatRefLink).to.startsWith("/") &&
                typeof (r as ChatRefLink).label === "string",
            );
          }
        }
        if (frame.type === "generation_complete") {
          const summary =
            typeof frame.summary === "string"
              ? frame.summary
              : typeof frame.message === "string"
                ? frame.message
                : JSON.stringify(frame);
          appendSystem(`Generation complete: ${summary}`);
          setBusy(false);
        }
        if (frame.type === "error") {
          appendAssistant(`Error: ${frame.message ?? "Unknown"}`);
          setBusy(false);
        }
      } catch {
        /* ignore */
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [panelOpen, brandId, appendAssistant, appendSystem]);

  const send = useCallback((content: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setBusy(true);
    setFollowups([]);
    pendingRefsRef.current = [];
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content }]);
    ws.send(
      JSON.stringify({
        type: "message",
        content,
        conversation_id: convoRef.current,
      }),
    );
  }, []);

  const sendSubscribeGeneration = useCallback((jobId: string) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "subscribe_generation", job_id: jobId }));
    appendSystem(`Subscribed to job ${jobId}…`);
  }, [appendSystem]);

  const resetThread = useCallback(() => {
    convoRef.current = null;
    pendingRefsRef.current = [];
    setMessages([]);
    setFollowups([]);
    setStatusMessage(null);
  }, []);

  const selectConversation = useCallback((conversationId: string, loaded: ChatMessage[]) => {
    convoRef.current = conversationId;
    pendingRefsRef.current = [];
    setMessages(loaded);
    setFollowups([]);
    setStatusMessage(null);
  }, []);

  return {
    connected,
    statusMessage,
    messages,
    followups,
    busy,
    send,
    sendSubscribeGeneration,
    resetThread,
    setMessages,
    selectConversation,
    conversationId: convoRef.current,
  };
}
