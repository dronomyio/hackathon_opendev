/**
 * ChessBoard component — live chess board with piece animations
 * Design: Quantitative Finance Dark — cream/brown squares, high-contrast pieces
 *
 * FIX: Black pieces now use #FFD700 (gold) instead of #1a1a2e (invisible on dark squares)
 * FIX: Square colors changed to classic chess cream (#F0D9B5) and brown (#B58863)
 * FIX: Larger font size and stronger shadows for visibility
 */
import { useEffect, useState } from "react";
import { PIECES, type GameState } from "@/lib/simulation";

interface ChessBoardProps {
  state: GameState;
}

export default function ChessBoard({ state }: ChessBoardProps) {
  const [lastMove, setLastMove] = useState<{ from: string; to: string } | null>(null);
  const [prevMoves, setPrevMoves] = useState<string[]>([]);

  useEffect(() => {
    if (state.moves.length > prevMoves.length) {
      setPrevMoves(state.moves);
    }
  }, [state.moves]);

  const files = "abcdefgh";
  const ranks = "87654321";

  const getSquareClass = (rank: number, file: number) => {
    const isLight = (rank + file) % 2 === 0;
    return isLight ? "chess-square-light" : "chess-square-dark";
  };

  return (
    <div className="flex flex-col gap-1">
      {/* Rank labels + board */}
      <div className="flex gap-1">
        {/* Rank labels */}
        <div className="flex flex-col justify-around w-4">
          {ranks.split("").map((r) => (
            <span key={r} className="text-center font-mono leading-none" style={{ fontSize: "10px", fontWeight: 600, color: "#c8c8c8" }}>
              {r}
            </span>
          ))}
        </div>
        {/* Board */}
        <div className="chess-board flex-1 aspect-square">
          {state.board.map((row, rankIdx) =>
            row.map((piece, fileIdx) => {
              const squareClass = getSquareClass(rankIdx, fileIdx);
              return (
                <div
                  key={`${rankIdx}-${fileIdx}`}
                  className={`${squareClass} flex items-center justify-center relative`}
                  style={{ aspectRatio: "1" }}
                >
                  {piece && (
                    <span
                      className="chess-piece select-none"
                      style={{
                        fontSize: "clamp(16px, 3vw, 32px)",
                        // White pieces: bright white; Black pieces: vivid gold — both visible on any square
                        color: piece === piece.toUpperCase() ? "#ffffff" : "#FFD700",
                        textShadow: piece === piece.toUpperCase()
                          ? "0 1px 3px rgba(0,0,0,0.9), 0 0 8px rgba(180,210,255,0.7)"
                          : "0 1px 3px rgba(0,0,0,0.9), 0 0 10px rgba(255,215,0,0.8)",
                        filter: piece === piece.toUpperCase()
                          ? "drop-shadow(0 0 4px rgba(180,210,255,0.6))"
                          : "drop-shadow(0 0 5px rgba(255,215,0,0.9))",
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
      </div>
      {/* File labels */}
      <div className="flex ml-5">
        {files.split("").map((f) => (
          <span key={f} className="flex-1 text-center font-mono" style={{ fontSize: "10px", fontWeight: 600, color: "#c8c8c8" }}>
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}

