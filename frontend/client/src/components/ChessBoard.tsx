/**
 * ChessBoard component — live chess board with piece animations
 * Design: Quantitative Finance Dark — cream/brown squares, high-contrast pieces
 *
 * White pieces: bright white (#FFFFFF) with thick dark stroke — visible on ALL squares
 * Black pieces: vivid gold (#FFD700) with dark shadow — visible on ALL squares
 * Layout: fully self-contained, no overflow, stable position
 */
import { PIECES, type GameState } from "@/lib/simulation";

interface ChessBoardProps {
  state: GameState;
}

const LIGHT_SQ = "#F0D9B5";
const DARK_SQ  = "#B58863";
const FILES = ["a","b","c","d","e","f","g","h"];
const RANKS = ["8","7","6","5","4","3","2","1"];

export default function ChessBoard({ state }: ChessBoardProps) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Board + rank labels row */}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* Rank labels */}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-around", width: "14px", flexShrink: 0, paddingBottom: "14px" }}>
          {RANKS.map((r) => (
            <span key={r} style={{
              fontFamily: "IBM Plex Mono, monospace",
              fontSize: "9px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.55)",
              textAlign: "center",
              lineHeight: 1,
            }}>
              {r}
            </span>
          ))}
        </div>
        {/* Board + file labels column */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          {/* Board grid */}
          <div style={{
            flex: 1,
            display: "grid",
            gridTemplateColumns: "repeat(8, 1fr)",
            gridTemplateRows: "repeat(8, 1fr)",
            border: "1px solid rgba(255,255,255,0.15)",
            borderRadius: "2px",
            overflow: "hidden",
            minHeight: 0,
          }}>
            {state.board.map((row, rankIdx) =>
              row.map((piece, fileIdx) => {
                const isLight = (rankIdx + fileIdx) % 2 === 0;
                const isWhitePiece = piece !== null && piece === piece.toUpperCase();
                return (
                  <div
                    key={`${rankIdx}-${fileIdx}`}
                    style={{
                      background: isLight ? LIGHT_SQ : DARK_SQ,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      overflow: "hidden",
                    }}
                  >
                    {piece && (
                      <span
                        style={{
                          fontSize: "clamp(14px, 2.5vw, 28px)",
                          lineHeight: 1,
                          userSelect: "none",
                          // White pieces use hollow Unicode symbols (♔♕♖♗♘♙)
                          // Rendered in dark navy so the outline is visible on BOTH cream and brown squares
                          // Black pieces use filled Unicode symbols (♚♛♜♝♞♟) in vivid gold
                          color: isWhitePiece ? "#1a2744" : "#E8B400",
                          textShadow: isWhitePiece
                            ? "0 1px 2px rgba(255,255,255,0.5)"
                            : "0 1px 3px rgba(0,0,0,0.9), 0 0 8px rgba(232,180,0,0.5)",
                          filter: isWhitePiece
                            ? "drop-shadow(0 0 1px rgba(255,255,255,0.4))"
                            : "drop-shadow(0 0 3px rgba(232,180,0,0.6))",
                        }}
                      >
                        {PIECES[piece] ?? piece}
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>
          {/* File labels */}
          <div style={{ display: "flex", height: "14px", flexShrink: 0 }}>
            {FILES.map((f) => (
              <span key={f} style={{
                flex: 1,
                textAlign: "center",
                fontFamily: "IBM Plex Mono, monospace",
                fontSize: "9px",
                fontWeight: 600,
                color: "rgba(255,255,255,0.55)",
                lineHeight: "14px",
              }}>
                {f}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

