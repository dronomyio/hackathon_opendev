import { useEffect, useRef, useCallback } from "react";

export type WSEventType = "game_start"|"move"|"coaching_request"|"coaching_result"|"game_end"|"training_step"|"economy_update"|"pong"|"status"|"snapshot";
export interface WSMessage { type: WSEventType; data: Record<string, unknown>; }
interface UseBackendWSOptions { url: string; onMessage: (msg: WSMessage) => void; onOpen?: () => void; onClose?: () => void; enabled?: boolean; }

export function useBackendWS({ url, onMessage, onOpen, onClose, enabled = true }: UseBackendWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const watchdogTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const enabledRef = useRef(enabled);
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  onMessageRef.current = onMessage;
  onOpenRef.current = onOpen;
  onCloseRef.current = onClose;
  enabledRef.current = enabled;

  const resetWatchdog = useCallback(() => {
    if (watchdogTimer.current) clearTimeout(watchdogTimer.current);
    watchdogTimer.current = setTimeout(() => {
      // No message in 10s — force reconnect
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    }, 10000);
  }, []);

  const connect = useCallback(() => {
    if (!enabledRef.current || !mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onopen = () => { if (onOpenRef.current) onOpenRef.current(); resetWatchdog(); };
      ws.onmessage = (e) => { resetWatchdog(); try { onMessageRef.current(JSON.parse(e.data) as WSMessage); } catch {} };
      ws.onclose = () => { if (watchdogTimer.current) clearTimeout(watchdogTimer.current); if (onCloseRef.current) onCloseRef.current(); if (mountedRef.current && enabledRef.current) reconnectTimer.current = setTimeout(connect, 3000); };
      ws.onerror = () => ws.close();
    } catch { if (mountedRef.current && enabledRef.current) reconnectTimer.current = setTimeout(connect, 3000); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  const send = useCallback((action: string, payload: Record<string, unknown> = {}) => { if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ action, ...payload })); }, []);
  const disconnect = useCallback(() => { if (reconnectTimer.current) clearTimeout(reconnectTimer.current); if (watchdogTimer.current) clearTimeout(watchdogTimer.current); wsRef.current?.close(); wsRef.current = null; }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) connect(); else disconnect();
    return () => { mountedRef.current = false; disconnect(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, url]);

  return { send, disconnect, connect };
}

