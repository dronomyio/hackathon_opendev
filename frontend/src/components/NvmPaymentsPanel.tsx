/**
 * ChessEcon — Nevermined Payments Panel
 * Displays real-time NVM transaction history, integration status,
 * and cross-team agent payment activity.
 *
 * Design: Bloomberg terminal style — dark background, monospace font,
 * color-coded transaction types.
 */
import { useEffect, useState, useRef } from "react";

// ── Types ──────────────────────────────────────────────────────────────────────
interface NvmTransaction {
  tx_id: string;
  type: "verify" | "settle" | "order" | "token";
  agent_id: string;
  plan_id: string;
  credits: number;
  timestamp: string;
  success: boolean;
  error?: string;
  details?: Record<string, unknown>;
}

interface NvmStatus {
  available: boolean;
  environment: string;
  plan_id: string | null;
  agent_id: string | null;
  api_key_set: boolean;
  transaction_count: number;
}

interface NvmPanelData {
  transactions: NvmTransaction[];
  nvm_status: NvmStatus;
}

// ── Color scheme ───────────────────────────────────────────────────────────────
const TX_COLORS = {
  settle:  { accent: "#27AE60", label: "SETTLE" },
  verify:  { accent: "#2D9CDB", label: "VERIFY" },
  order:   { accent: "#F5A623", label: "ORDER"  },
  token:   { accent: "#9B59B6", label: "TOKEN"  },
};

const MONO = { fontFamily: "IBM Plex Mono, monospace" };

// ── Sub-components ─────────────────────────────────────────────────────────────
function StatusBadge({ available, environment }: { available: boolean; environment: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <span style={{
        display: "inline-block",
        width: "0.5rem",
        height: "0.5rem",
        borderRadius: "50%",
        background: available ? "#27AE60" : "#E05C5C",
        boxShadow: available ? "0 0 6px #27AE60" : "0 0 6px #E05C5C",
      }} />
      <span style={{ ...MONO, fontSize: "0.6875rem", color: available ? "#27AE60" : "#E05C5C" }}>
        {available ? `NVM ACTIVE · ${environment.toUpperCase()}` : "NVM INACTIVE"}
      </span>
    </div>
  );
}

function TxRow({ tx }: { tx: NvmTransaction }) {
  const color = TX_COLORS[tx.type] ?? { accent: "#888", label: tx.type.toUpperCase() };
  const time = new Date(tx.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "4.5rem 3.5rem 1fr 3rem 4rem",
      gap: "0.5rem",
      alignItems: "center",
      padding: "0.25rem 0.5rem",
      borderBottom: "1px solid rgba(255,255,255,0.04)",
      background: tx.success ? "transparent" : "rgba(224,92,92,0.05)",
    }}>
      {/* Time */}
      <span style={{ ...MONO, fontSize: "0.5625rem", color: "rgba(255,255,255,0.3)" }}>
        {time}
      </span>
      {/* Type badge */}
      <span style={{
        ...MONO,
        fontSize: "0.5625rem",
        fontWeight: 700,
        color: color.accent,
        background: `${color.accent}18`,
        border: `1px solid ${color.accent}40`,
        borderRadius: "0.125rem",
        padding: "0.0625rem 0.25rem",
        textAlign: "center",
      }}>
        {color.label}
      </span>
      {/* Agent / Plan */}
      <span style={{ ...MONO, fontSize: "0.5625rem", color: "rgba(255,255,255,0.55)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {tx.agent_id ? tx.agent_id.slice(0, 20) : "—"}
        {tx.plan_id ? <span style={{ color: "rgba(255,255,255,0.25)" }}> · {tx.plan_id.slice(0, 8)}</span> : null}
      </span>
      {/* Credits */}
      <span style={{ ...MONO, fontSize: "0.5625rem", color: tx.credits > 0 ? "#27AE60" : "rgba(255,255,255,0.3)", textAlign: "right" }}>
        {tx.credits > 0 ? `-${tx.credits}` : "—"}
      </span>
      {/* Status */}
      <span style={{
        ...MONO,
        fontSize: "0.5625rem",
        color: tx.success ? "#27AE60" : "#E05C5C",
        textAlign: "right",
      }}>
        {tx.success ? "OK" : "FAIL"}
      </span>
    </div>
  );
}

// ── Main panel ─────────────────────────────────────────────────────────────────
interface NvmPaymentsPanelProps {
  /** Backend base URL (e.g. http://localhost:8000) */
  backendUrl?: string;
  /** Live NVM transactions pushed via WebSocket */
  liveTransactions?: NvmTransaction[];
  /** NVM status from /api/config */
  nvmConfig?: {
    available: boolean;
    environment: string;
    plan_id: string | null;
    agent_id: string | null;
  };
}

export default function NvmPaymentsPanel({
  backendUrl = "",
  liveTransactions = [],
  nvmConfig,
}: NvmPaymentsPanelProps) {
  const [data, setData] = useState<NvmPanelData | null>(null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll NVM transactions from backend every 5 seconds
  const fetchTransactions = async () => {
    if (!backendUrl) return;
    try {
      const res = await fetch(`${backendUrl}/api/chess/nvm-transactions?limit=20`);
      if (res.ok) {
        const json = await res.json() as NvmPanelData;
        setData(json);
      }
    } catch {
      // Backend not available — use live WS data
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchTransactions();
    intervalRef.current = setInterval(fetchTransactions, 5_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [backendUrl]);

  // Merge polled + live WS transactions (deduplicated by tx_id)
  const allTxs: NvmTransaction[] = (() => {
    const polled = data?.transactions ?? [];
    const merged = [...liveTransactions, ...polled];
    const seen = new Set<string>();
    return merged.filter(t => {
      if (seen.has(t.tx_id)) return false;
      seen.add(t.tx_id);
      return true;
    }).slice(0, 30);
  })();

  const status: NvmStatus = data?.nvm_status ?? {
    available: nvmConfig?.available ?? false,
    environment: nvmConfig?.environment ?? "sandbox",
    plan_id: nvmConfig?.plan_id ?? null,
    agent_id: nvmConfig?.agent_id ?? null,
    api_key_set: false,
    transaction_count: 0,
  };

  const settleCount = allTxs.filter(t => t.type === "settle" && t.success).length;
  const totalCredits = allTxs.filter(t => t.type === "settle" && t.success).reduce((s, t) => s + t.credits, 0);
  const externalCalls = allTxs.filter(t => t.type === "verify" || t.type === "settle").length;

  return (
    <div style={{
      background: "rgba(10,12,18,0.95)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: "0.25rem",
      display: "flex",
      flexDirection: "column",
      height: "100%",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        padding: "0.5rem 0.75rem",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "0.5rem",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <div style={{ width: "0.375rem", height: "0.375rem", borderRadius: "50%", background: "#9B59B6" }} />
          <span style={{ ...MONO, fontSize: "0.625rem", fontWeight: 700, letterSpacing: "0.1em", color: "rgba(255,255,255,0.7)", textTransform: "uppercase" }}>
            Nevermined Payments
          </span>
        </div>
        <StatusBadge available={status.available} environment={status.environment} />
      </div>

      {/* KPI row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr 1fr",
        gap: "0.5rem",
        padding: "0.5rem 0.75rem",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        {[
          { label: "Settled Txs", value: String(settleCount), color: "#27AE60" },
          { label: "Credits Burned", value: String(totalCredits), color: "#F5A623" },
          { label: "API Calls", value: String(externalCalls), color: "#2D9CDB" },
        ].map(k => (
          <div key={k.label} style={{ display: "flex", flexDirection: "column", gap: "0.125rem" }}>
            <span style={{ ...MONO, fontSize: "0.5rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.3)" }}>
              {k.label}
            </span>
            <span style={{ ...MONO, fontSize: "1rem", fontWeight: 700, color: k.color, fontVariantNumeric: "tabular-nums" }}>
              {k.value}
            </span>
          </div>
        ))}
      </div>

      {/* Plan / Agent info */}
      {status.plan_id && (
        <div style={{
          padding: "0.375rem 0.75rem",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex",
          gap: "1rem",
        }}>
          <span style={{ ...MONO, fontSize: "0.5625rem", color: "rgba(255,255,255,0.3)" }}>
            PLAN <span style={{ color: "#9B59B6" }}>{status.plan_id.slice(0, 16)}…</span>
          </span>
          {status.agent_id && (
            <span style={{ ...MONO, fontSize: "0.5625rem", color: "rgba(255,255,255,0.3)" }}>
              AGENT <span style={{ color: "#9B59B6" }}>{status.agent_id.slice(0, 16)}…</span>
            </span>
          )}
        </div>
      )}

      {/* Column headers */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "4.5rem 3.5rem 1fr 3rem 4rem",
        gap: "0.5rem",
        padding: "0.25rem 0.5rem",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
      }}>
        {["TIME", "TYPE", "AGENT · PLAN", "CRED", "STATUS"].map(h => (
          <span key={h} style={{ ...MONO, fontSize: "0.5rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "rgba(255,255,255,0.25)" }}>
            {h}
          </span>
        ))}
      </div>

      {/* Transaction list */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {allTxs.length === 0 ? (
          <div style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            gap: "0.5rem",
            padding: "1rem",
          }}>
            <span style={{ ...MONO, fontSize: "0.625rem", color: "rgba(255,255,255,0.2)", textAlign: "center" }}>
              {status.available
                ? "No NVM transactions yet.\nStart a game to see cross-team payments."
                : "Set NVM_API_KEY in .env to enable\ncross-team agent-to-agent payments."}
            </span>
            {!status.available && (
              <a
                href="https://nevermined.app"
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...MONO, fontSize: "0.5625rem", color: "#9B59B6", textDecoration: "underline" }}
              >
                Get API key at nevermined.app →
              </a>
            )}
          </div>
        ) : (
          allTxs.map(tx => <TxRow key={tx.tx_id} tx={tx} />)
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: "0.375rem 0.75rem",
        borderTop: "1px solid rgba(255,255,255,0.06)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span style={{ ...MONO, fontSize: "0.5rem", color: "rgba(255,255,255,0.2)" }}>
          x402 PROTOCOL · NEVERMINED SANDBOX
        </span>
        <a
          href="https://nevermined.app"
          target="_blank"
          rel="noopener noreferrer"
          style={{ ...MONO, fontSize: "0.5rem", color: "rgba(155,89,182,0.6)", textDecoration: "none" }}
        >
          nevermined.app ↗
        </a>
      </div>
    </div>
  );
}

export type { NvmTransaction, NvmStatus };
