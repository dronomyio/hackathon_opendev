"""
agents/model_agent.py
─────────────────────
Unified chess agent that can load ANY HuggingFace CausalLM.

White → Qwen/Qwen2.5-0.5B-Instruct  (GRPO trainable)
Black → meta-llama/Llama-3.2-1B-Instruct (fixed opponent)

Key fix: tight UCI-format prompt + aggressive output parsing ensures
the model reliably produces legal moves rather than always falling back
to random. This is essential for GRPO to receive real gradient signal.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from backend.settings import settings
from backend.chess_engine import ChessEngine

logger = logging.getLogger(__name__)

# UCI move pattern: e2e4, g1f3, e1g1, a7a8q (promotion)
_UCI_RE = re.compile(r'\b([a-h][1-8][a-h][1-8][qrbn]?)\b')
# SAN fallback patterns: e4, Nf3, O-O, Bxf7+, exd5=Q
_SAN_RE = re.compile(r'\b(O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b')


class ModelAgent:
    """
    A chess-playing agent backed by any HuggingFace CausalLM.

    Usage:
        agent = ModelAgent("/models/Qwen_Qwen2.5-0.5B-Instruct")
        san, log_prob = agent.get_move(engine, "white", move_history)
    """

    def __init__(self, model_id: str, device: str = "auto"):
        self.model_id = model_id
        self.device = device
        self._temperature = settings.temperature
        self._tokenizer = None
        self._model = None
        self._loaded = False

    # ── Lazy model loading ─────────────────────────────────────────────────────

    def load(self) -> "ModelAgent":
        """Explicitly load model weights. Called once at startup."""
        if self._loaded:
            return self

        logger.info("Loading model: %s", self.model_id)

        dtype_map = {
            "float16":  torch.float16,
            "bfloat16": torch.bfloat16,
            "float32":  torch.float32,
        }
        torch_dtype = dtype_map.get(settings.torch_dtype, torch.bfloat16)

        hf_kwargs: dict = {}
        if settings.hf_token:
            hf_kwargs["token"] = settings.hf_token

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            **hf_kwargs,
        )
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=torch_dtype,
            device_map=self.device if self.device != "auto" else "auto",
            trust_remote_code=True,
            **hf_kwargs,
        )
        self._model.eval()

        if settings.lora_rank > 0:
            try:
                from peft import get_peft_model, LoraConfig, TaskType  # type: ignore
                lora_config = LoraConfig(
                    task_type=TaskType.CAUSAL_LM,
                    r=settings.lora_rank,
                    lora_alpha=settings.lora_rank * 2,
                    lora_dropout=0.05,
                    target_modules=["q_proj", "v_proj"],
                )
                self._model = get_peft_model(self._model, lora_config)
                logger.info("[%s] LoRA applied (rank=%d)", self.model_id, settings.lora_rank)
            except ImportError:
                logger.warning("[%s] peft not installed — running without LoRA", self.model_id)

        device_str = str(next(self._model.parameters()).device)
        logger.info("[%s] Loaded on %s", self.model_id, device_str)
        self._loaded = True
        return self

    @property
    def model(self):
        if not self._loaded:
            self.load()
        return self._model

    @property
    def tokenizer(self):
        if not self._loaded:
            self.load()
        return self._tokenizer

    def set_temperature(self, temp: float):
        self._temperature = max(0.1, temp)

    # ── Prompt building ────────────────────────────────────────────────────────

    def _build_prompt(self, engine: ChessEngine, color: str, history: list[str]) -> str:
        """
        Build a tight prompt that forces the model to output a single UCI move.

        We give it ALL legal moves so it only needs to pick one — no need to
        invent a move from scratch. This dramatically reduces illegal outputs.
        """
        legal_uci  = engine.legal_moves_uci          # full list e.g. ["e2e4","d2d4",...]
        legal_san  = engine.legal_moves_san           # same moves in SAN
        history_str = " ".join(history[-10:]) if history else "game start"

        # Show up to 30 legal moves so the model has enough context
        legal_display = " ".join(legal_uci[:30])

        system = (
            "You are a chess engine. "
            "You must respond with EXACTLY ONE move from the legal moves list. "
            "Use UCI format only (e.g. e2e4). No explanation, no punctuation."
        )
        user = (
            f"Color: {color}\n"
            f"FEN: {engine.fen}\n"
            f"Move history: {history_str}\n"
            f"Legal moves: {legal_display}\n"
            f"Your move (UCI):"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ]
        try:
            return self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            return f"<s>[INST] {system}\n{user} [/INST]"

    # ── Output parsing ─────────────────────────────────────────────────────────

    def _parse_move(self, text: str, engine: ChessEngine) -> Optional[str]:
        """
        Extract a legal move from model output.
        Priority: UCI match → SAN match → first token direct match.
        Returns SAN string if legal, else None.
        """
        text = text.strip()

        # 1. Try every UCI token in output order
        for m in _UCI_RE.finditer(text):
            san = engine.uci_to_san(m.group(1))
            if san:
                return san

        # 2. Try SAN tokens
        for m in _SAN_RE.finditer(text):
            san = engine.parse_model_output(m.group(1))
            if san:
                return san

        # 3. Try the raw first word (model sometimes outputs move + newline)
        first = text.split()[0] if text.split() else ""
        if first:
            san = engine.uci_to_san(first) or engine.parse_model_output(first)
            if san:
                return san

        return None

    # ── Move generation ────────────────────────────────────────────────────────

    def get_move(
        self,
        engine: ChessEngine,
        color: str,
        history: list[str],
    ) -> tuple[str, float]:
        """
        Generate a legal chess move. Returns (san_move, log_prob).
        Falls back to random legal move after max_move_retries.
        """
        if not self._loaded:
            self.load()

        prompt = self._build_prompt(engine, color, history)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        input_len = inputs["input_ids"].shape[1]

        best_san: Optional[str] = None
        best_lp = 0.0

        for attempt in range(settings.max_move_retries):
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=10,        # a UCI move is at most 5 chars
                    temperature=self._temperature,
                    do_sample=True,
                    pad_token_id=self._tokenizer.eos_token_id,
                    return_dict_in_generate=True,
                    output_scores=True,
                )
            gen_ids = outputs.sequences[0][input_len:]
            gen_text = self._tokenizer.decode(gen_ids, skip_special_tokens=True)
            lp = _compute_log_prob(outputs.scores, gen_ids)

            san = self._parse_move(gen_text, engine)
            if san:
                best_san, best_lp = san, lp
                logger.debug("[%s] ✓ move=%s attempt=%d lp=%.3f raw=%r",
                             self.model_id, san, attempt + 1, lp, gen_text)
                break
            logger.warning("[%s] ✗ attempt %d bad output: %r", self.model_id, attempt + 1, gen_text)

        if best_san is None:
            best_san = engine.random_legal_move_san() or "e4"
            best_lp = 0.0
            logger.warning("[%s] retries exhausted — random fallback: %s", self.model_id, best_san)

        return best_san, best_lp

    def get_move_log_prob_only(
        self,
        engine: ChessEngine,
        color: str,
        history: list[str],
        san_move: str,
    ) -> float:
        """Log-probability of a specific move under the current policy. Used for GRPO KL."""
        if not self._loaded:
            self.load()

        prompt = self._build_prompt(engine, color, history)
        # Convert SAN → UCI for consistency with prompt format
        uci = engine.san_to_uci(san_move) or san_move
        target_text = prompt + uci
        inputs = self._tokenizer(target_text, return_tensors="pt").to(self._model.device)
        prompt_len = self._tokenizer(prompt, return_tensors="pt")["input_ids"].shape[1]

        with torch.no_grad():
            out = self._model(**inputs, labels=inputs["input_ids"])

        logits = out.logits[0, prompt_len - 1:-1]
        target_ids = inputs["input_ids"][0, prompt_len:]
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        selected = log_probs.gather(1, target_ids.unsqueeze(1)).squeeze(1)
        return selected.sum().item()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_log_prob(scores, generated_ids) -> float:
    total = 0.0
    for step, score in enumerate(scores):
        if step >= len(generated_ids):
            break
        lp = torch.nn.functional.log_softmax(score[0], dim=-1)
        total += lp[generated_ids[step]].item()
    return total
