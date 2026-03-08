/**
 * WalletChart — live wallet balance history for both agents
 */
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend,
} from "recharts";
import { TooltipPanel } from "./Panel";

interface WalletPoint {
  game: number;
  white: number;
  black: number;
}

interface WalletChartProps {
  history: WalletPoint[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <TooltipPanel>
      <div style={{ color: "rgba(255,255,255,0.4)", marginBottom: "2px" }}>Game #{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toFixed(1) : p.value} units
        </div>
      ))}
    </TooltipPanel>
  );
};

export default function WalletChart({ history }: WalletChartProps) {
  if (history.length < 2) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "rgba(255,255,255,0.3)", fontSize: "0.625rem", fontFamily: "IBM Plex Mono, monospace" }}>
        Collecting wallet data...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="gradWhite" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2D9CDB" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#2D9CDB" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gradBlack" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#E05C5C" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#E05C5C" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="game"
          tick={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(255,255,255,0.3)" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(255,255,255,0.3)" }}
          tickLine={false}
          axisLine={false}
          width={32}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={100} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 4" />
        <ReferenceLine y={0} stroke="rgba(224,92,92,0.4)" strokeDasharray="2 2" />
        <Area type="monotone" dataKey="white" stroke="#2D9CDB" strokeWidth={1.8} fill="url(#gradWhite)" dot={false} name="White Agent" isAnimationActive={false} />
        <Area type="monotone" dataKey="black" stroke="#E05C5C" strokeWidth={1.8} fill="url(#gradBlack)" dot={false} name="Black Agent" isAnimationActive={false} />
        <Legend wrapperStyle={{ fontSize: "9px", fontFamily: "IBM Plex Mono", paddingTop: "4px" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
