/**
 * ChessEcon — Real Backend WebSocket Hook
 * Connects to the Python FastAPI /ws endpoint and dispatches
 * all game, coaching, economy, and training events to the dashboard.
 *
 * FIX (reconnect-loop): Callbacks (onMessage, onOpen, onClose) are stored in
 * refs so they never appear in the useCallback/useEffect dependency arrays.
 * Previously, unstable function references caused the effect to re-run on
 * every render, immediately cancelling and recreating the WebSocket.
 * Also added CONNECTING guard and proper ping-interval cleanup on close.
 */
import { useEffect, useRef, useCallback } from "react";

export type WSEventType =
  | "game_start"
  | "move"
  | "coaching_request"
  | "coaching_result"
  | "game_end"
  | "training_step"
  | "economy_update"
  | "pong";

export interface WSMessage {
  type: WSEventType;
  data: Record<string, unknown>;
}

interface UseBackendWSOptions {
  url: string;
  onMessage: (msg: WSMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  enabled?: boolean;
}

export function useBackendWS({
  url,
  onMessage,
  onOpen,
  onClose,
  enabled = true,
}: UseBackendWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  // Store callbacks in refs so they never invalidate useCallback/useEffect
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const enabledRef = useRef(enabled);

  // Keep refs in sync with latest props on every render (no deps needed)
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;
  enabledRef.current = enabled;

  const clearPing = useCallback(() => {
    if (pingTimer.current) {
      clearInterval(pingTimer.current);
      pingTimer.current = null;
    }
  }, []);

  // connect is stable — only depends on url (not on any callback)
  const connect = useCallback(() => {
    if (!enabledRef.current || !mountedRef.current) return;
    // Do not create a new socket if one is already open or connecting
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (onOpenRef.current) onOpenRef.current();
        // Start ping interval to keep connection alive
        clearPing();
        pingTimer.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "ping" }));
          } else {
            clearPing();
          }
        }, 30_000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WSMessage;
          onMessageRef.current(msg);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        clearPing();
        if (onCloseRef.current) onCloseRef.current();
        // Auto-reconnect after 3 seconds if still enabled and mounted
        if (mountedRef.current && enabledRef.current) {
          reconnectTimer.current = setTimeout(connect, 3_000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket not available (e.g., SSR) — retry after delay
      if (mountedRef.current && enabledRef.current) {
        reconnectTimer.current = setTimeout(connect, 3_000);
      }
    }
  // Only depends on url — callbacks are read from refs
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, clearPing]);

  const send = useCallback((action: string, payload: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    clearPing();
    wsRef.current?.close();
    wsRef.current = null;
  }, [clearPing]);

  // Only re-run when enabled or url changes — not on every render
  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      connect();
    } else {
      disconnect();
    }
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url]);

  return { send, disconnect, connect };
}
