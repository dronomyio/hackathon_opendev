/**
 * TrainingCharts — live GRPO training metrics using Recharts
 * Design: Quantitative Finance Dark — glowing line charts on dark canvas
 */
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Area, AreaChart,
} from "recharts";
import type { TrainingMetrics } from "@/lib/simulation";
import { Panel, PanelHeader, PanelDot, TooltipPanel } from "./Panel";

interface TrainingChartsProps {
  metrics: TrainingMetrics;
}

const HEX = {
  white: "#2D9CDB",
  black: "#E05C5C",
  claude: "#F5A623",
  profit: "#27AE60",
  loss: "#a78bfa",
  kl: "#f97316",
};

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <TooltipPanel>
      <div style={{ color: "rgba(255,255,255,0.4)", marginBottom: "2px" }}>step {label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(4) : p.value}
        </div>
      ))}
    </TooltipPanel>
  );
};

interface MiniChartProps {
  data: { step: number; value: number }[];
  color: string;
  label: string;
  refLine?: number;
  domain?: [number | "auto", number | "auto"];
}

function MiniChart({ data, color, label, refLine, domain }: MiniChartProps) {
  if (data.length < 2) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "rgba(255,255,255,0.3)", fontSize: "0.625rem", fontFamily: "IBM Plex Mono, monospace" }}>
        Collecting data...
      </div>
    );
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis dataKey="step" hide />
        <YAxis domain={domain ?? ["auto", "auto"]} hide />
        <Tooltip content={<CustomTooltip />} />
        {refLine !== undefined && (
          <ReferenceLine y={refLine} stroke="rgba(255,255,255,0.15)" strokeDasharray="3 3" />
        )}
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#grad-${label})`}
          dot={false}
          name={label}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

interface ChartCardProps {
  title: string;
  value: string;
  subValue?: string;
  color: string;
  children: React.ReactNode;
}

function ChartCard({ title, value, subValue, color, children }: ChartCardProps) {
  return (
    <Panel style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
      <PanelHeader>
        <PanelDot color={color} />
        <span>{title}</span>
        <span style={{ marginLeft: "auto", fontFamily: "IBM Plex Mono, monospace", fontSize: "0.6875rem", color }}>
          {value}
        </span>
        {subValue && (
          <span style={{ fontSize: "0.5625rem", color: "rgba(255,255,255,0.3)" }}>{subValue}</span>
        )}
      </PanelHeader>
      <div style={{ flex: 1, padding: "0.5rem", minHeight: 0 }}>
        {children}
      </div>
    </Panel>
  );
}

export default function TrainingCharts({ metrics }: TrainingChartsProps) {
  const toSeries = (arr: number[]) =>
    arr.map((v, i) => ({ step: metrics.steps[i] ?? i + 1, value: v }));

  const lastLoss = metrics.loss.at(-1);
  const lastReward = metrics.reward.at(-1);
  const lastWinRate = metrics.winRate.at(-1);
  const lastProfit = metrics.avgProfit.at(-1);
  const lastCoaching = metrics.coachingRate.at(-1);
  const lastKl = metrics.kl.at(-1);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "repeat(3, 1fr)", gap: "0.5rem", height: "100%" }}>
      <ChartCard title="GRPO LOSS" value={lastLoss !== undefined ? lastLoss.toFixed(4) : "—"} color={HEX.loss}>
        <MiniChart data={toSeries(metrics.loss)} color={HEX.loss} label="loss" domain={[0, 3]} />
      </ChartCard>

      <ChartCard
        title="POLICY REWARD"
        value={lastReward !== undefined ? lastReward.toFixed(4) : "—"}
        color={lastReward !== undefined && lastReward >= 0 ? HEX.profit : HEX.black}
      >
        <MiniChart
          data={toSeries(metrics.reward)}
          color={lastReward !== undefined && lastReward >= 0 ? HEX.profit : HEX.black}
          label="reward" refLine={0} domain={[-0.6, 0.6]}
        />
      </ChartCard>

      <ChartCard title="WIN RATE" value={lastWinRate !== undefined ? `${(lastWinRate * 100).toFixed(1)}%` : "—"} color={HEX.white}>
        <MiniChart data={toSeries(metrics.winRate)} color={HEX.white} label="win_rate" refLine={0.5} domain={[0.2, 0.8]} />
      </ChartCard>

      <ChartCard
        title="AVG PROFIT"
        value={lastProfit !== undefined ? `${lastProfit >= 0 ? "+" : ""}${lastProfit.toFixed(2)}` : "—"}
        subValue="units/game"
        color={lastProfit !== undefined && lastProfit >= 0 ? HEX.profit : HEX.black}
      >
        <MiniChart
          data={toSeries(metrics.avgProfit)}
          color={lastProfit !== undefined && lastProfit >= 0 ? HEX.profit : HEX.black}
          label="profit" refLine={0}
        />
      </ChartCard>

      <ChartCard title="COACHING RATE" value={lastCoaching !== undefined ? `${(lastCoaching * 100).toFixed(1)}%` : "—"} color={HEX.claude}>
        <MiniChart data={toSeries(metrics.coachingRate)} color={HEX.claude} label="coaching" domain={[0, 0.5]} />
      </ChartCard>

      <ChartCard title="KL DIVERGENCE" value={lastKl !== undefined ? lastKl.toFixed(4) : "—"} color={HEX.kl}>
        <MiniChart data={toSeries(metrics.kl)} color={HEX.kl} label="kl" refLine={0.1} domain={[0, 0.2]} />
      </ChartCard>
    </div>
  );
}
