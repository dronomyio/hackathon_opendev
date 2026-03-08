/**
 * Panel — reusable trading terminal panel component
 * Replaces the .panel / .panel-header CSS classes to avoid Tailwind 4 @apply issues
 */
import { type ReactNode, type CSSProperties } from "react";

const PANEL_BG = "linear-gradient(135deg, oklch(0.12 0.016 240) 0%, oklch(0.10 0.014 240) 100%)";
const PANEL_BORDER = "1px solid rgba(255,255,255,0.08)";

interface PanelProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function Panel({ children, className = "", style }: PanelProps) {
  return (
    <div
      className={className}
      style={{
        background: PANEL_BG,
        border: PANEL_BORDER,
        borderRadius: "0.25rem",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

interface PanelHeaderProps {
  children: ReactNode;
  className?: string;
}

export function PanelHeader({ children, className = "" }: PanelHeaderProps) {
  return (
    <div
      className={`flex items-center gap-2 ${className}`}
      style={{
        padding: "0.375rem 0.75rem",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: "0.65rem",
        letterSpacing: "0.08em",
        textTransform: "uppercase" as const,
        color: "oklch(0.52 0.010 240)",
      }}
    >
      {children}
    </div>
  );
}

export function PanelDot({ color }: { color: string }) {
  return (
    <span
      style={{
        width: "0.375rem",
        height: "0.375rem",
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
        display: "inline-block",
      }}
    />
  );
}

/** Tooltip panel for Recharts */
export function TooltipPanel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        background: PANEL_BG,
        border: PANEL_BORDER,
        borderRadius: "0.25rem",
        padding: "0.375rem 0.5rem",
        fontSize: "0.625rem",
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      {children}
    </div>
  );
}
