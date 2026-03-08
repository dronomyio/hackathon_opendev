/**
 * EventFeed — live scrolling event log
 * Design: Bloomberg terminal event stream with color-coded agent events
 */
import { useEffect, useRef } from "react";
import type { GameEvent } from "@/lib/simulation";

interface EventFeedProps {
  events: GameEvent[];
}

const EVENT_ICONS: Record<string, string> = {
  game_start: "▶",
  move: "→",
  coaching_request: "◈",
  coaching_response: "◉",
  game_end: "■",
  training_step: "⚡",
  wallet_update: "$",
};

function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}.${d.getMilliseconds().toString().padStart(3, "0").slice(0, 2)}`;
}

function getEventClass(event: GameEvent): string {
  if (event.type === "game_start") return "event-item event-game-start";
  if (event.type === "game_end") return "event-item event-game-end";
  if (event.type === "training_step") return "event-item event-training";
  if (event.type === "coaching_request" || event.type === "coaching_response") return "event-item event-coaching";
  if (event.type === "move") {
    return event.agent === "white" ? "event-item event-move-white" : "event-item event-move-black";
  }
  return "event-item";
}

function getAgentBadge(event: GameEvent) {
  if (event.type === "coaching_request" || event.type === "coaching_response") {
    return <span className="text-[9px] font-mono px-1 py-0.5 rounded-sm bg-agent-claude text-agent-claude border border-agent-claude">CLAUDE</span>;
  }
  if (event.agent === "white") {
    return <span className="text-[9px] font-mono px-1 py-0.5 rounded-sm bg-agent-white text-agent-white border border-agent-white">WHITE</span>;
  }
  if (event.agent === "black") {
    return <span className="text-[9px] font-mono px-1 py-0.5 rounded-sm bg-agent-black text-agent-black border border-agent-black">BLACK</span>;
  }
  if (event.type === "training_step") {
    return <span className="text-[9px] font-mono px-1 py-0.5 rounded-sm" style={{background: "oklch(0.60 0.15 290 / 0.15)", color: "oklch(0.60 0.15 290)", border: "1px solid oklch(0.60 0.15 290 / 0.4)"}}>GRPO</span>;
  }
  if (event.type === "game_start" || event.type === "game_end") {
    return <span className="text-[9px] font-mono px-1 py-0.5 rounded-sm" style={{background: "oklch(0.65 0.18 145 / 0.15)", color: "oklch(0.65 0.18 145)", border: "1px solid oklch(0.65 0.18 145 / 0.4)"}}>SYS</span>;
  }
  return null;
}

export default function EventFeed({ events }: EventFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [events.length]);

  return (
    <div ref={containerRef} className="overflow-y-auto h-full" style={{ scrollBehavior: "smooth" }}>
      {events.map((event) => (
        <div key={event.id} className={getEventClass(event)}>
          <span className="font-mono text-[9px] text-muted-foreground shrink-0 mt-0.5 w-16">
            {formatTime(event.timestamp)}
          </span>
          <span className="text-muted-foreground shrink-0 w-3 text-center text-[10px]">
            {EVENT_ICONS[event.type] ?? "·"}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              {getAgentBadge(event)}
              <span className="text-[11px] text-foreground/80 truncate">
                {event.message}
              </span>
            </div>
            {event.type === "training_step" && event.trainingLoss !== undefined && (
              <div className="flex gap-3 mt-0.5">
                <span className="text-[9px] font-mono text-muted-foreground">
                  loss: <span className="text-destructive">{event.trainingLoss.toFixed(4)}</span>
                </span>
                <span className="text-[9px] font-mono text-muted-foreground">
                  reward: <span style={{color: (event.combinedReward ?? 0) >= 0 ? "oklch(0.65 0.18 145)" : "oklch(0.60 0.20 25)"}}>
                    {(event.combinedReward ?? 0).toFixed(4)}
                  </span>
                </span>
              </div>
            )}
            {event.type === "coaching_request" && (
              <div className="flex gap-2 mt-0.5">
                <span className="text-[9px] font-mono text-muted-foreground">
                  complexity: <span className="text-agent-claude">{event.complexityLabel}</span>
                  <span className="ml-1 opacity-60">({event.complexity?.toFixed(2)})</span>
                </span>
              </div>
            )}
            {event.type === "game_end" && event.result && (
              <div className="flex gap-2 mt-0.5">
                <span className="text-[9px] font-mono">
                  result: <span className={event.result === "1-0" ? "text-agent-white" : event.result === "0-1" ? "text-agent-black" : "text-muted-foreground"}>{event.result}</span>
                </span>
                <span className="text-[9px] font-mono text-muted-foreground">
                  R: <span style={{color: (event.combinedReward ?? 0) >= 0 ? "oklch(0.65 0.18 145)" : "oklch(0.60 0.20 25)"}}>
                    {(event.combinedReward ?? 0).toFixed(3)}
                  </span>
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
      {events.length === 0 && (
        <div className="flex items-center justify-center h-full text-muted-foreground text-xs font-mono">
          Waiting for events...
        </div>
      )}
    </div>
  );
}
