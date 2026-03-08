import { useState, useEffect } from "react";

const COLORS = {
  bg: "#0a0c10",
  panel: "#0f1318",
  border: "#1e2530",
  accent: "#f0b429",
  accentDim: "#7a5c14",
  white: "#e8dcc8",
  green: "#2ecc71",
  red: "#e74c3c",
  blue: "#3b82f6",
  purple: "#8b5cf6",
  cyan: "#06b6d4",
  gray: "#4a5568",
  grayLight: "#9ca3af",
};

const NODE_TYPES = {
  model:    { color: COLORS.accent,  bg: "#1a1400", border: "#f0b429" },
  engine:   { color: COLORS.cyan,    bg: "#001a1f", border: "#06b6d4" },
  trainer:  { color: COLORS.purple,  bg: "#10001a", border: "#8b5cf6" },
  server:   { color: COLORS.green,   bg: "#001a0a", border: "#2ecc71" },
  frontend: { color: COLORS.blue,    bg: "#001020", border: "#3b82f6" },
  economy:  { color: COLORS.red,     bg: "#1a0005", border: "#e74c3c" },
  storage:  { color: COLORS.grayLight, bg: "#111318", border: "#4a5568" },
};

const nodes = [
  // Row 1 — Models
  { id: "qwen",    label: "Qwen2.5-0.5B",    sub: "WHITE AGENT",         type: "model",   x: 120,  y: 60,  w: 160, h: 64 },
  { id: "llama",   label: "Llama-3.2-1B",    sub: "BLACK AGENT (fixed)", type: "model",   x: 560,  y: 60,  w: 170, h: 64 },

  // Row 2 — Core runtime
  { id: "engine",  label: "ChessEngine",      sub: "python-chess + FEN",  type: "engine",  x: 300,  y: 200, w: 160, h: 64 },
  { id: "grpo",    label: "GRPOTrainer",      sub: "PPO-clip + KL(β=0.04)", type: "trainer", x: 60,   y: 200, w: 180, h: 64 },
  { id: "lora",    label: "LoRA Adapters",    sub: "r=8  q_proj v_proj",  type: "trainer", x: 60,   y: 320, w: 180, h: 64 },

  // Row 3 — Server
  { id: "ws",      label: "WebSocket Server", sub: "FastAPI  /ws",        type: "server",  x: 295,  y: 340, w: 170, h: 64 },
  { id: "openenv", label: "OpenEnv 0.1",      sub: "POST /env/reset+step", type: "server",  x: 510,  y: 340, w: 160, h: 64 },

  // Row 4 — Economy
  { id: "eco",     label: "Economy Engine",   sub: "Entry fee · Prize pool · P&L", type: "economy", x: 295, y: 460, w: 190, h: 64 },

  // Row 5 — Frontend
  { id: "dash",    label: "React Dashboard",  sub: "Vite · Tailwind · nginx", type: "frontend", x: 295,  y: 580, w: 190, h: 64 },
  { id: "charts",  label: "Recharts / D3",    sub: "Wallet · GRPO · P&L",  type: "frontend", x: 530,  y: 580, w: 160, h: 64 },
  { id: "board",   label: "Live Board",       sub: "SVG chess renderer",   type: "frontend", x: 60,   y: 580, w: 160, h: 64 },

  // Storage
  { id: "ckpt",    label: "Checkpoints",      sub: "/checkpoints/step_N",  type: "storage", x: 60,   y: 440, w: 160, h: 64 },
  { id: "gpu",     label: "4× RTX 3070",      sub: "cuda:0  VRAM 8GB",     type: "storage", x: 540,  y: 200, w: 150, h: 64 },
];

const edges = [
  // Model → engine
  { from: "qwen",    to: "engine",  label: "get_move()",     color: COLORS.accent },
  { from: "llama",   to: "engine",  label: "get_move()",     color: COLORS.grayLight },

  // Engine → WS server
  { from: "engine",  to: "ws",      label: "FEN · SAN · result", color: COLORS.cyan },

  // WS → GRPO
  { from: "ws",      to: "grpo",    label: "log_prob · reward", color: COLORS.purple },

  // GRPO → LoRA
  { from: "grpo",    to: "lora",    label: "AdamW update",   color: COLORS.purple, dashed: true },

  // LoRA → Qwen (feedback)
  { from: "lora",    to: "qwen",    label: "weights patch",  color: COLORS.accent, dashed: true },

  // WS → Economy
  { from: "ws",      to: "eco",     label: "game_end event", color: COLORS.red },

  // Engine ↔ OpenEnv
  { from: "engine",  to: "openenv", label: "board state",    color: COLORS.green },

  // GRPO → checkpoint
  { from: "grpo",    to: "ckpt",    label: "save_pretrained()", color: COLORS.grayLight, dashed: true },

  // WS → Dashboard
  { from: "ws",      to: "dash",    label: "broadcast()",    color: COLORS.blue },

  // Dashboard → sub-components
  { from: "dash",    to: "charts",  label: "metrics props",  color: COLORS.blue },
  { from: "dash",    to: "board",   label: "FEN props",      color: COLORS.blue },

  // GPU
  { from: "qwen",    to: "gpu",     label: "cuda:0",         color: COLORS.grayLight, dashed: true },
  { from: "llama",   to: "gpu",     label: "cuda:0",         color: COLORS.grayLight, dashed: true },
];

function getCenter(node) {
  return { x: node.x + node.w / 2, y: node.y + node.h / 2 };
}

function EdgePath({ edge, nodes: allNodes }) {
  const from = allNodes.find(n => n.id === edge.from);
  const to   = allNodes.find(n => n.id === edge.to);
  if (!from || !to) return null;

  const f = getCenter(from);
  const t = getCenter(to);
  const dx = t.x - f.x, dy = t.y - f.y;
  const mx = f.x + dx * 0.5;
  const my = f.y + dy * 0.5;
  const d = `M${f.x},${f.y} Q${mx},${f.y + dy * 0.3} ${t.x},${t.y}`;

  const mid = { x: f.x + dx * 0.42, y: f.y + dy * 0.38 };

  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={edge.color}
        strokeWidth={1.5}
        strokeDasharray={edge.dashed ? "5,4" : undefined}
        opacity={0.55}
        markerEnd={`url(#arrow-${edge.color.replace('#','')})`}
      />
      {edge.label && (
        <text
          x={mid.x}
          y={mid.y - 5}
          fill={edge.color}
          fontSize={9}
          textAnchor="middle"
          opacity={0.8}
          fontFamily="'JetBrains Mono', monospace"
        >
          {edge.label}
        </text>
      )}
    </g>
  );
}

function NodeBox({ node, active, onClick }) {
  const t = NODE_TYPES[node.type];
  return (
    <g
      transform={`translate(${node.x},${node.y})`}
      style={{ cursor: "pointer" }}
      onClick={() => onClick(node)}
    >
      {/* Glow */}
      {active && (
        <rect
          x={-4} y={-4} width={node.w + 8} height={node.h + 8}
          rx={10} ry={10}
          fill="none"
          stroke={t.border}
          strokeWidth={2}
          opacity={0.5}
          filter="url(#glow)"
        />
      )}
      {/* Box */}
      <rect
        x={0} y={0} width={node.w} height={node.h}
        rx={6} ry={6}
        fill={t.bg}
        stroke={active ? t.border : COLORS.border}
        strokeWidth={active ? 1.5 : 1}
      />
      {/* Top accent stripe */}
      <rect x={0} y={0} width={node.w} height={3} rx={6} ry={0} fill={t.border} opacity={0.9} />

      {/* Label */}
      <text
        x={node.w / 2} y={26}
        fill={t.color}
        fontSize={12}
        fontWeight="700"
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
      >
        {node.label}
      </text>
      {/* Sub */}
      <text
        x={node.w / 2} y={44}
        fill={COLORS.grayLight}
        fontSize={9}
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
        opacity={0.75}
      >
        {node.sub}
      </text>
    </g>
  );
}

const LAYER_LABELS = [
  { y: 60,  label: "MODELS",   color: COLORS.accent },
  { y: 200, label: "RUNTIME",  color: COLORS.cyan },
  { y: 340, label: "SERVER",   color: COLORS.green },
  { y: 460, label: "ECONOMY",  color: COLORS.red },
  { y: 580, label: "FRONTEND", color: COLORS.blue },
];

export default function ArchitectureDiagram() {
  const [active, setActive] = useState(null);
  const [pulse, setPulse] = useState(null);
  const svgW = 760, svgH = 700;

  // Auto-pulse edges periodically for "live" feel
  useEffect(() => {
    const ids = ["qwen→engine", "engine→ws", "ws→grpo", "ws→eco", "ws→dash"];
    let i = 0;
    const t = setInterval(() => {
      setPulse(ids[i % ids.length]);
      i++;
    }, 1200);
    return () => clearInterval(t);
  }, []);

  const arrowColors = [...new Set(edges.map(e => e.color))];

  return (
    <div style={{
      background: COLORS.bg,
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "32px 16px",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{
          fontSize: 11, letterSpacing: "0.35em", color: COLORS.accent,
          textTransform: "uppercase", marginBottom: 8, opacity: 0.8,
        }}>
          AdaBoost AI · Hackathon 2026
        </div>
        <div style={{
          fontSize: 28, fontWeight: 800, color: COLORS.white,
          letterSpacing: "-0.02em", lineHeight: 1.1,
        }}>
          ChessEcon Architecture
        </div>
        <div style={{ fontSize: 12, color: COLORS.grayLight, marginTop: 6, opacity: 0.7 }}>
          Multi-Agent Chess Economy · GRPO Training · OpenEnv 0.1 · TextArena
        </div>
      </div>

      {/* SVG diagram */}
      <div style={{
        background: COLORS.panel,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 12,
        padding: "12px 8px",
        width: "100%",
        maxWidth: 880,
        overflowX: "auto",
      }}>
        <svg
          viewBox={`-60 30 ${svgW + 80} ${svgH - 10}`}
          width="100%"
          style={{ display: "block" }}
        >
          <defs>
            {arrowColors.map(c => (
              <marker
                key={c}
                id={`arrow-${c.replace('#','')}`}
                markerWidth="8" markerHeight="8"
                refX="6" refY="3"
                orient="auto"
              >
                <path d="M0,0 L0,6 L8,3 z" fill={c} opacity={0.7} />
              </marker>
            ))}
            <filter id="glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Layer labels */}
          {LAYER_LABELS.map(l => (
            <text
              key={l.label}
              x={-12} y={l.y + 36}
              fill={l.color}
              fontSize={8}
              fontWeight="700"
              textAnchor="end"
              letterSpacing="0.15em"
              opacity={0.6}
              fontFamily="'JetBrains Mono', monospace"
              transform={`rotate(-90, -12, ${l.y + 36})`}
            >
              {l.label}
            </text>
          ))}

          {/* Layer dividers */}
          {[160, 295, 420, 540].map(y => (
            <line key={y} x1={0} y1={y} x2={svgW} y2={y}
              stroke={COLORS.border} strokeWidth={1} strokeDasharray="3,6" opacity={0.4} />
          ))}

          {/* Edges */}
          {edges.map((e, i) => (
            <EdgePath key={i} edge={e} nodes={nodes} />
          ))}

          {/* Nodes */}
          {nodes.map(n => (
            <NodeBox
              key={n.id}
              node={n}
              active={active?.id === n.id}
              onClick={setActive}
            />
          ))}
        </svg>
      </div>

      {/* Detail panel */}
      <div style={{
        marginTop: 20,
        width: "100%",
        maxWidth: 880,
        minHeight: 80,
        background: COLORS.panel,
        border: `1px solid ${active ? NODE_TYPES[active.type].border : COLORS.border}`,
        borderRadius: 8,
        padding: "14px 20px",
        transition: "border-color 0.2s",
      }}>
        {active ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span style={{
                fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase",
                color: NODE_TYPES[active.type].color, opacity: 0.8,
              }}>
                {active.type}
              </span>
              <span style={{ fontSize: 15, fontWeight: 700, color: COLORS.white }}>
                {active.label}
              </span>
              <span style={{ fontSize: 11, color: COLORS.grayLight, opacity: 0.7 }}>
                {active.sub}
              </span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {edges
                .filter(e => e.from === active.id || e.to === active.id)
                .map((e, i) => (
                  <div key={i} style={{
                    fontSize: 10,
                    padding: "3px 10px",
                    borderRadius: 4,
                    background: `${e.color}18`,
                    border: `1px solid ${e.color}40`,
                    color: e.color,
                  }}>
                    {e.from === active.id ? "→" : "←"} {e.from === active.id ? e.to : e.from}: {e.label}
                  </div>
                ))}
            </div>
          </div>
        ) : (
          <div style={{ color: COLORS.grayLight, fontSize: 11, opacity: 0.5 }}>
            Click any node to inspect connections ·{" "}
            <span style={{ color: COLORS.accent }}>Qwen (White)</span> trains live with GRPO ·{" "}
            <span style={{ color: COLORS.grayLight }}>Llama (Black)</span> is a fixed opponent
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{
        display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16,
        justifyContent: "center",
      }}>
        {Object.entries(NODE_TYPES).map(([key, t]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{
              width: 10, height: 10, borderRadius: 2,
              background: t.bg, border: `1.5px solid ${t.border}`,
            }} />
            <span style={{ fontSize: 10, color: t.color, textTransform: "uppercase", letterSpacing: "0.1em" }}>
              {key}
            </span>
          </div>
        ))}
      </div>

      {/* Data flow summary */}
      <div style={{
        marginTop: 20,
        width: "100%",
        maxWidth: 880,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 12,
      }}>
        {[
          { label: "Training Loop", value: "GRPO per game", color: COLORS.purple },
          { label: "Reward Signal", value: "+1 win / -1 loss", color: COLORS.accent },
          { label: "KL Coefficient", value: "β = 0.04", color: COLORS.cyan },
          { label: "LoRA Rank", value: "r = 8  (q,v proj)", color: COLORS.purple },
          { label: "Entry Fee", value: "10 units / game", color: COLORS.red },
          { label: "Prize Pool", value: "18 units (90%)", color: COLORS.green },
          { label: "Max Moves", value: "15 → material adj.", color: COLORS.accent },
          { label: "Transport", value: "FastAPI WebSocket", color: COLORS.blue },
        ].map(item => (
          <div key={item.label} style={{
            background: COLORS.panel,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 6,
            padding: "10px 14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}>
            <span style={{ fontSize: 10, color: COLORS.grayLight, opacity: 0.7 }}>{item.label}</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: item.color }}>{item.value}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 24, fontSize: 9, color: COLORS.grayLight, opacity: 0.35, letterSpacing: "0.15em" }}>
        CHESSECON · TEXTARENA + META OPENENV + GRPO · HACKATHON 2026 · ADABOOST AI
      </div>
    </div>
  );
}

