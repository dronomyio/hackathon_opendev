/**
 * EconomicPerformance — full-width Economic Performance Over Time chart
 * Shows: cumulative net P&L, per-game profit breakdown, coaching spend, prize income
 * Design: Quantitative Finance Dark — Bloomberg-style multi-series chart
 */
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid, Legend,
} from "recharts";
import { TooltipPanel } from "./Panel";

export interface EconomicDataPoint {
  game: number;
  prizeIncome: number;      // prize won this game (0 if lost)
  coachingSpend: number;    // coaching fees paid this game (negative)
  entryFee: number;         // entry fee paid (always -10)
  netPnl: number;           // net P&L this game
  cumulativePnl: number;    // running cumulative P&L
  whiteWallet: number;
  blackWallet: number;
}

interface EconomicPerformanceProps {
  data: EconomicDataPoint[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <TooltipPanel>
      <div style={{ color: "rgba(255,255,255,0.4)", marginBottom: "4px", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "3px" }}>
        Game #{label}
      </div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color, display: "flex", justifyContent: "space-between", gap: "1rem" }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 600 }}>
            {typeof p.value === "number"
              ? `${p.value >= 0 ? "+" : ""}${p.value.toFixed(2)}`
              : p.value}
          </span>
        </div>
      ))}
    </TooltipPanel>
  );
};

const LEGEND_STYLE = {
  fontSize: "9px",
  fontFamily: "IBM Plex Mono, monospace",
  paddingTop: "2px",
};

export default function EconomicPerformance({ data }: EconomicPerformanceProps) {
  if (data.length < 2) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        color: "rgba(255,255,255,0.25)",
        fontSize: "0.625rem",
        fontFamily: "IBM Plex Mono, monospace",
        flexDirection: "column",
        gap: "0.5rem",
      }}>
        <span style={{ fontSize: "1.5rem", opacity: 0.3 }}>📈</span>
        <span>Collecting economic data — start the simulation to see P&amp;L over time</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 6, right: 16, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="gradCumPnl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#27AE60" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#27AE60" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255,255,255,0.04)"
          vertical={false}
        />

        <XAxis
          dataKey="game"
          tick={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(255,255,255,0.3)" }}
          tickLine={false}
          axisLine={false}
          label={{ value: "Game #", position: "insideBottomRight", offset: -4, fontSize: 8, fill: "rgba(255,255,255,0.2)", fontFamily: "IBM Plex Mono" }}
        />

        {/* Left Y axis — per-game values */}
        <YAxis
          yAxisId="left"
          tick={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(255,255,255,0.3)" }}
          tickLine={false}
          axisLine={false}
          width={32}
        />

        {/* Right Y axis — cumulative P&L */}
        <YAxis
          yAxisId="right"
          orientation="right"
          tick={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(39,174,96,0.6)" }}
          tickLine={false}
          axisLine={false}
          width={36}
        />

        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine yAxisId="left" y={0} stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
        <ReferenceLine yAxisId="right" y={0} stroke="rgba(39,174,96,0.2)" strokeDasharray="2 2" />

        {/* Stacked bars: prize income (positive) and costs (negative) */}
        <Bar
          yAxisId="left"
          dataKey="prizeIncome"
          name="Prize Income"
          fill="#27AE60"
          fillOpacity={0.75}
          radius={[2, 2, 0, 0]}
          maxBarSize={18}
          isAnimationActive={false}
        />
        <Bar
          yAxisId="left"
          dataKey="entryFee"
          name="Entry Fee"
          fill="#E05C5C"
          fillOpacity={0.55}
          radius={[0, 0, 2, 2]}
          maxBarSize={18}
          isAnimationActive={false}
        />
        <Bar
          yAxisId="left"
          dataKey="coachingSpend"
          name="Coaching Cost"
          fill="#F5A623"
          fillOpacity={0.6}
          radius={[0, 0, 2, 2]}
          maxBarSize={18}
          isAnimationActive={false}
        />

        {/* Cumulative P&L line on right axis */}
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="cumulativePnl"
          name="Cumulative P&L"
          stroke="#27AE60"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />

        {/* Net P&L per game line */}
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="netPnl"
          name="Net P&L / Game"
          stroke="#2D9CDB"
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 2"
          isAnimationActive={false}
        />

        <Legend wrapperStyle={LEGEND_STYLE} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
