/**
 * ChessEcon Simulation Engine
 * ─────────────────────────────────────────────────────────────────────────
 * Generates realistic self-play game events in real time to drive the
 * live dashboard. In production this would be replaced by a WebSocket
 * connection to the actual ChessEcon backend.
 *
 * Design: Quantitative Finance Dark — Bloomberg-inspired terminal
 */

export type AgentColor = "white" | "black";
export type EventType =
  | "game_start"
  | "move"
  | "coaching_request"
  | "coaching_response"
  | "game_end"
  | "training_step"
  | "wallet_update";

export interface GameEvent {
  id: string;
  timestamp: number;
  type: EventType;
  agent?: AgentColor;
  move?: string;
  san?: string;
  fen?: string;
  complexity?: number;
  complexityLabel?: "SIMPLE" | "MODERATE" | "COMPLEX" | "CRITICAL";
  walletWhite?: number;
  walletBlack?: number;
  coachingFee?: number;
  result?: "1-0" | "0-1" | "1/2-1/2";
  reward?: number;
  economicReward?: number;
  combinedReward?: number;
  trainingLoss?: number;
  trainingStep?: number;
  message?: string;
  prizePool?: number;
}

export interface GameState {
  gameId: number;
  moveNumber: number;
  turn: AgentColor;
  fen: string;
  board: (string | null)[][];
  moves: string[];
  walletWhite: number;
  walletBlack: number;
  isOver: boolean;
  result?: "1-0" | "0-1" | "1/2-1/2";
  coachingCallsWhite: number;
  coachingCallsBlack: number;
}

export interface TrainingMetrics {
  step: number;
  loss: number[];
  reward: number[];
  winRate: number[];
  avgProfit: number[];
  coachingRate: number[];
  kl: number[];
  steps: number[];
}

// ── Chess piece unicode map ──────────────────────────────────────────────
export const PIECES: Record<string, string> = {
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
};

// ── Starting FEN ─────────────────────────────────────────────────────────
const STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR";

export function fenToBoard(fen: string): (string | null)[][] {
  const rows = fen.split(" ")[0].split("/");
  return rows.map((row) => {
    const cells: (string | null)[] = [];
    for (const ch of row) {
      if (/\d/.test(ch)) {
        for (let i = 0; i < parseInt(ch); i++) cells.push(null);
      } else {
        cells.push(ch);
      }
    }
    return cells;
  });
}

// ── Realistic opening/middlegame move sequences ──────────────────────────
const GAME_SCRIPTS = [
  // Ruy Lopez
  ["e2e4","e7e5","g1f3","b8c6","f1b5","a7a6","b5a4","g8f6","e1g1","f8e7","f1e1","b7b5","a4b3","d7d6","c2c3","e8g8","h2h3","c6a5","b3c2","c7c5","d2d4","d8c7"],
  // Sicilian
  ["e2e4","c7c5","g1f3","d7d6","d2d4","c5d4","f3d4","g8f6","b1c3","a7a6","c1g5","e7e6","d1d2","f8e7","e1c1","e8g8","f2f4","h7h6","g5h4","b8d7"],
  // Queen's Gambit
  ["d2d4","d7d5","c2c4","e7e6","b1c3","g8f6","c1g5","f8e7","e2e3","e8g8","g1f3","h7h6","g5h4","b7b6","c4d5","e6d5","f1d3","c8b7","e1g1","b8d7"],
  // King's Indian
  ["d2d4","g8f6","c2c4","g7g6","b1c3","f8g7","e2e4","d7d6","g1f3","e8g8","f1e2","e7e5","e1g1","b8c6","d4d5","c6e7","f3e1","f6d7","e1d3","f7f5"],
];

let scriptIndex = 0;
let moveIndex = 0;

function getNextMove(gameScript: string[]): string | null {
  if (moveIndex < gameScript.length) {
    return gameScript[moveIndex++];
  }
  return null;
}

// ── Apply move to FEN (simplified) ───────────────────────────────────────
function applyMoveToBoard(
  board: (string | null)[][],
  move: string
): (string | null)[][] {
  const newBoard = board.map((row) => [...row]);
  const files = "abcdefgh";
  const fromFile = files.indexOf(move[0]);
  const fromRank = 8 - parseInt(move[1]);
  const toFile = files.indexOf(move[2]);
  const toRank = 8 - parseInt(move[3]);

  if (fromFile < 0 || fromRank < 0 || toFile < 0 || toRank < 0) return newBoard;

  const piece = newBoard[fromRank]?.[fromFile];
  if (!piece) return newBoard;

  newBoard[toRank][toFile] = piece;
  newBoard[fromRank][fromFile] = null;

  // Castling
  if (piece === "K" && move === "e1g1") {
    newBoard[7][5] = "R"; newBoard[7][7] = null;
  } else if (piece === "K" && move === "e1c1") {
    newBoard[7][3] = "R"; newBoard[7][0] = null;
  } else if (piece === "k" && move === "e8g8") {
    newBoard[0][5] = "r"; newBoard[0][7] = null;
  } else if (piece === "k" && move === "e8c8") {
    newBoard[0][3] = "r"; newBoard[0][0] = null;
  }

  return newBoard;
}

function boardToFen(board: (string | null)[][]): string {
  return board.map((row) => {
    let s = "";
    let empty = 0;
    for (const cell of row) {
      if (!cell) { empty++; }
      else { if (empty) { s += empty; empty = 0; } s += cell; }
    }
    if (empty) s += empty;
    return s;
  }).join("/");
}

function moveToSan(move: string, piece: string | null): string {
  if (!piece) return move;
  const files = "abcdefgh";
  const toFile = files[files.indexOf(move[2])];
  const toRank = move[3];
  const isCapture = false; // simplified
  if (move === "e1g1" || move === "e8g8") return "O-O";
  if (move === "e1c1" || move === "e8c8") return "O-O-O";
  const pieceLetter = piece.toUpperCase();
  if (pieceLetter === "P") return `${toFile}${toRank}`;
  return `${pieceLetter}${isCapture ? "x" : ""}${toFile}${toRank}`;
}

function complexityScore(moveNum: number): number {
  // Peaks in middlegame (moves 15-35)
  const base = 0.15 + 0.5 * Math.exp(-Math.pow(moveNum - 25, 2) / (2 * 12 * 12));
  return Math.min(1, Math.max(0, base + (Math.random() - 0.5) * 0.15));
}

function complexityLabel(score: number): "SIMPLE" | "MODERATE" | "COMPLEX" | "CRITICAL" {
  if (score < 0.20) return "SIMPLE";
  if (score < 0.45) return "MODERATE";
  if (score < 0.70) return "COMPLEX";
  return "CRITICAL";
}

let uid = 0;
function nextId() { return `evt-${++uid}`; }

// ── Main simulation class ─────────────────────────────────────────────────
export class ChessEconSimulation {
  private listeners: ((event: GameEvent) => void)[] = [];
  private stateListeners: ((state: GameState) => void)[] = [];
  private metricsListeners: ((metrics: TrainingMetrics) => void)[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  private running = false;

  public state: GameState = this.freshState();
  public metrics: TrainingMetrics = {
    step: 0,
    loss: [],
    reward: [],
    winRate: [],
    avgProfit: [],
    coachingRate: [],
    kl: [],
    steps: [],
  };
  public events: GameEvent[] = [];
  public gameCount = 0;
  public totalGames = 0;

  private freshState(): GameState {
    return {
      gameId: 0,
      moveNumber: 0,
      turn: "white",
      fen: STARTING_FEN,
      board: fenToBoard(STARTING_FEN),
      moves: [],
      walletWhite: 100,
      walletBlack: 100,
      isOver: false,
      coachingCallsWhite: 0,
      coachingCallsBlack: 0,
    };
  }

  on(listener: (event: GameEvent) => void) {
    this.listeners.push(listener);
    return () => { this.listeners = this.listeners.filter(l => l !== listener); };
  }

  onState(listener: (state: GameState) => void) {
    this.stateListeners.push(listener);
    return () => { this.stateListeners = this.stateListeners.filter(l => l !== listener); };
  }

  onMetrics(listener: (metrics: TrainingMetrics) => void) {
    this.metricsListeners.push(listener);
    return () => { this.metricsListeners = this.metricsListeners.filter(l => l !== listener); };
  }

  private emit(event: GameEvent) {
    this.events = [event, ...this.events].slice(0, 200);
    this.listeners.forEach(l => l(event));
  }

  private emitState() {
    this.stateListeners.forEach(l => l({ ...this.state }));
  }

  private emitMetrics() {
    this.metricsListeners.forEach(l => l({ ...this.metrics }));
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.startGame();
  }

  stop() {
    this.running = false;
    if (this.timer) clearTimeout(this.timer);
  }

  private schedule(fn: () => void, delay: number) {
    if (!this.running) return;
    this.timer = setTimeout(fn, delay);
  }

  private startGame() {
    this.gameCount++;
    this.totalGames++;
    const script = GAME_SCRIPTS[scriptIndex % GAME_SCRIPTS.length];
    scriptIndex++;
    moveIndex = 0;

    const entryFee = 10;
    this.state = {
      ...this.freshState(),
      gameId: this.gameCount,
      walletWhite: this.state.walletWhite - entryFee,
      walletBlack: this.state.walletBlack - entryFee,
    };

    this.emit({
      id: nextId(),
      timestamp: Date.now(),
      type: "game_start",
      walletWhite: this.state.walletWhite,
      walletBlack: this.state.walletBlack,
      prizePool: entryFee * 2 * 0.9,
      message: `Game #${this.gameCount} started — Prize pool: ${(entryFee * 2 * 0.9).toFixed(1)} units`,
    });
    this.emitState();

    this.schedule(() => this.playMove(script), 600);
  }

  private playMove(script: string[]) {
    if (!this.running) return;
    if (this.state.isOver) return;

    const move = getNextMove(script);
    const agent = this.state.turn;
    const progress = this.gameCount / Math.max(1, this.totalGames);

    // End game after script or random termination
    if (!move || this.state.moveNumber >= 22 + Math.floor(Math.random() * 8)) {
      this.endGame();
      return;
    }

    const complexity = complexityScore(this.state.moveNumber);
    const label = complexityLabel(complexity);
    const canAffordCoaching = (agent === "white" ? this.state.walletWhite : this.state.walletBlack) >= 15;
    const wantsCoaching = (label === "COMPLEX" || label === "CRITICAL") && canAffordCoaching && Math.random() < (0.35 - 0.25 * progress);

    // Apply move
    const newBoard = applyMoveToBoard(this.state.board, move);
    const piece = this.state.board[8 - parseInt(move[1])]?.["abcdefgh".indexOf(move[0])] ?? null;
    const san = moveToSan(move, piece);
    const newFen = boardToFen(newBoard);

    this.state = {
      ...this.state,
      board: newBoard,
      fen: newFen,
      moveNumber: this.state.moveNumber + 1,
      turn: agent === "white" ? "black" : "white",
      moves: [...this.state.moves, san],
    };

    if (wantsCoaching) {
      const fee = 5;
      if (agent === "white") {
        this.state.walletWhite -= fee;
        this.state.coachingCallsWhite++;
      } else {
        this.state.walletBlack -= fee;
        this.state.coachingCallsBlack++;
      }

      this.emit({
        id: nextId(),
        timestamp: Date.now(),
        type: "coaching_request",
        agent,
        complexity,
        complexityLabel: label,
        coachingFee: fee,
        walletWhite: this.state.walletWhite,
        walletBlack: this.state.walletBlack,
        message: `${agent === "white" ? "White" : "Black"} → Claude claude-opus-4-5 [${label}] fee: -${fee}`,
      });
      this.emitState();

      // Claude responds after a delay
      this.schedule(() => {
        this.emit({
          id: nextId(),
          timestamp: Date.now(),
          type: "coaching_response",
          agent,
          move,
          san,
          message: `Claude → ${agent === "white" ? "White" : "Black"}: best move ${san}`,
        });
        this.emitMoveEvent(agent, move, san, complexity, label);
        this.schedule(() => this.playMove(script), 900);
      }, 700);
    } else {
      this.emitMoveEvent(agent, move, san, complexity, label);
      this.schedule(() => this.playMove(script), 500 + Math.random() * 400);
    }
  }

  private emitMoveEvent(agent: AgentColor, move: string, san: string, complexity: number, label: string) {
    this.emit({
      id: nextId(),
      timestamp: Date.now(),
      type: "move",
      agent,
      move,
      san,
      fen: this.state.fen,
      complexity,
      complexityLabel: label as "SIMPLE" | "MODERATE" | "COMPLEX" | "CRITICAL",
      walletWhite: this.state.walletWhite,
      walletBlack: this.state.walletBlack,
      message: `${agent === "white" ? "White" : "Black"} plays ${san}`,
    });
    this.emitState();
  }

  private endGame() {
    const outcomes: ("1-0" | "0-1" | "1/2-1/2")[] = ["1-0", "0-1", "1/2-1/2"];
    const weights = [0.50, 0.35, 0.15];
    const r = Math.random();
    let result: "1-0" | "0-1" | "1/2-1/2" = "1-0";
    let cum = 0;
    for (let i = 0; i < outcomes.length; i++) {
      cum += weights[i];
      if (r < cum) { result = outcomes[i]; break; }
    }

    const prize = 18;
    const drawRefund = 5;
    if (result === "1-0") this.state.walletWhite += prize;
    else if (result === "0-1") this.state.walletBlack += prize;
    else { this.state.walletWhite += drawRefund; this.state.walletBlack += drawRefund; }

    this.state.isOver = true;
    this.state.result = result;

    const gameReward = result === "1-0" ? 1 : result === "0-1" ? -1 : 0;
    const economicReward = Math.random() * 0.6 - 0.2;
    const combinedReward = 0.4 * gameReward + 0.6 * economicReward;

    this.emit({
      id: nextId(),
      timestamp: Date.now(),
      type: "game_end",
      result,
      walletWhite: this.state.walletWhite,
      walletBlack: this.state.walletBlack,
      reward: gameReward,
      economicReward,
      combinedReward,
      message: `Game #${this.gameCount} ended — ${result} | Combined reward: ${combinedReward.toFixed(3)}`,
    });
    this.emitState();

    // Training step every 5 games
    if (this.gameCount % 5 === 0) {
      this.schedule(() => this.doTrainingStep(), 800);
    } else {
      this.schedule(() => this.startGame(), 1200);
    }
  }

  private doTrainingStep() {
    this.metrics.step++;
    const s = this.metrics.step;
    const loss = 2.5 * Math.exp(-s / 60) + 0.3 + (Math.random() - 0.5) * 0.16;
    const reward = -0.4 + 0.9 / (1 + Math.exp(-0.04 * (s - 80))) + (Math.random() - 0.5) * 0.12;
    const winRate = 0.35 + 0.22 / (1 + Math.exp(-0.1 * (s - 40))) + (Math.random() - 0.5) * 0.04;
    const avgProfit = -8 + 15 / (1 + Math.exp(-0.08 * (s - 45))) + (Math.random() - 0.5) * 2;
    const coachingRate = Math.max(0.05, 0.35 - 0.28 * (s / 100) + (Math.random() - 0.5) * 0.04);
    const kl = 0.05 + 0.03 * Math.exp(-s / 40) + Math.abs((Math.random() - 0.5) * 0.02);

    this.metrics.loss = [...this.metrics.loss, loss].slice(-80);
    this.metrics.reward = [...this.metrics.reward, reward].slice(-80);
    this.metrics.winRate = [...this.metrics.winRate, winRate].slice(-80);
    this.metrics.avgProfit = [...this.metrics.avgProfit, avgProfit].slice(-80);
    this.metrics.coachingRate = [...this.metrics.coachingRate, coachingRate].slice(-80);
    this.metrics.kl = [...this.metrics.kl, kl].slice(-80);
    this.metrics.steps = [...this.metrics.steps, s].slice(-80);

    this.emit({
      id: nextId(),
      timestamp: Date.now(),
      type: "training_step",
      trainingStep: s,
      trainingLoss: loss,
      reward,
      combinedReward: reward,
      message: `GRPO step #${s} — loss: ${loss.toFixed(4)} | reward: ${reward.toFixed(4)}`,
    });
    this.emitMetrics();

    this.schedule(() => this.startGame(), 1000);
  }
}

export const sim = new ChessEconSimulation();

// ── Economic performance data builder ────────────────────────────────────
export interface EconomicDataPoint {
  game: number;
  prizeIncome: number;
  coachingSpend: number;
  entryFee: number;
  netPnl: number;
  cumulativePnl: number;
  whiteWallet: number;
  blackWallet: number;
}
