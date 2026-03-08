"""
qwen_agent.py
─────────────
Loads Qwen2.5-0.5B-Instruct (or any HuggingFace causal LM) and uses it to
generate chess moves given a position prompt.

Key responsibilities:
  - Lazy model loading (first call triggers download + GPU placement)
  - Illegal-move retry loop (up to settings.max_move_retries attempts)
  - Log-probability extraction for GRPO training
  - Temperature annealing hook (called by the trainer after each update)
"""

import logging
import torch
from typing import Optional
from transformers import AutoTokenizer, AutoModelForCausalLM

from backend.settings import settings
from backend.chess_lib.chess_engine import ChessEngine

logger = logging.getLogger(__name__)

# ── Lazy singletons ───────────────────────────────────────────────────────────
_tokenizer = None
_model = None


def _load_model():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model

    logger.info("Loading model: %s …", settings.player_model)

    dtype_map = {
        "float16":  torch.float16,
        "bfloat16": torch.bfloat16,
        "float32":  torch.float32,
    }
    torch_dtype = dtype_map.get(settings.torch_dtype, torch.bfloat16)

    hf_kwargs = {}
    if settings.hf_token:
        hf_kwargs["token"] = settings.hf_token

    _tokenizer = AutoTokenizer.from_pretrained(
        settings.player_model,
        trust_remote_code=True,
        **hf_kwargs,
    )

    device_map = settings.device if settings.device != "auto" else "auto"

    _model = AutoModelForCausalLM.from_pretrained(
        settings.player_model,
        torch_dtype=torch_dtype,
        device_map=device_map,
        trust_remote_code=True,
        **hf_kwargs,
    )
    _model.eval()
    logger.info("Model loaded on device: %s", next(_model.parameters()).device)

    # Apply LoRA if requested
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
            _model = get_peft_model(_model, lora_config)
            _model.print_trainable_parameters()
            logger.info("LoRA adapter applied (rank=%d)", settings.lora_rank)
        except ImportError:
            logger.warning("peft not installed — running without LoRA. pip install peft")

    return _tokenizer, _model


class QwenAgent:
    """
    Wraps the Qwen model for chess move generation.

    Usage:
        agent = QwenAgent()
        san, log_prob = await agent.get_move(engine, "white", move_history)
    """

    def __init__(self):
        self._temperature = settings.temperature

    def set_temperature(self, temp: float):
        """Called by the GRPO trainer to anneal temperature over training."""
        self._temperature = max(0.1, temp)

    @property
    def temperature(self) -> float:
        return self._temperature

    def get_move(
        self,
        engine: ChessEngine,
        agent_color: str,
        move_history: list[str],
    ) -> tuple[str, float]:
        """
        Generate a legal chess move for the given position.

        Returns:
            (san_move, log_prob)
            - san_move: the chosen move in SAN notation
            - log_prob: sum of log-probs of the generated tokens (for GRPO)

        Falls back to a random legal move if all retries are exhausted.
        """
        tokenizer, model = _load_model()
        prompt = engine.build_prompt(agent_color, move_history)

        messages = [
            {"role": "system", "content": "You are a chess engine. Reply with only the move."},
            {"role": "user", "content": prompt},
        ]

        # Apply chat template
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        input_len = inputs["input_ids"].shape[1]

        best_san: Optional[str] = None
        best_log_prob: float = 0.0

        for attempt in range(settings.max_move_retries):
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=settings.max_new_tokens,
                    temperature=self._temperature,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id,
                    return_dict_in_generate=True,
                    output_scores=True,
                )

            generated_ids = outputs.sequences[0][input_len:]
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

            # Compute sum of log-probs for GRPO
            log_prob = _compute_log_prob(outputs.scores, generated_ids)

            san = engine.parse_model_output(generated_text)
            if san is not None:
                best_san = san
                best_log_prob = log_prob
                logger.debug(
                    "Move generated (attempt %d/%d): %s  log_prob=%.4f",
                    attempt + 1, settings.max_move_retries, san, log_prob,
                )
                break
            else:
                logger.debug(
                    "Illegal/unparseable output (attempt %d/%d): %r",
                    attempt + 1, settings.max_move_retries, generated_text,
                )

        if best_san is None:
            # All retries exhausted — fall back to random legal move
            best_san = engine.random_legal_move_san() or "e4"
            best_log_prob = 0.0
            logger.warning("All retries exhausted — using random fallback move: %s", best_san)

        return best_san, best_log_prob

    def get_move_log_prob_only(
        self,
        engine: ChessEngine,
        agent_color: str,
        move_history: list[str],
        san_move: str,
    ) -> float:
        """
        Compute the log-probability of a specific move under the current policy.
        Used by GRPO to evaluate the reference policy for KL computation.
        """
        tokenizer, model = _load_model()
        prompt = engine.build_prompt(agent_color, move_history)
        messages = [
            {"role": "system", "content": "You are a chess engine. Reply with only the move."},
            {"role": "user", "content": prompt},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        target_text = text + san_move
        inputs = tokenizer(target_text, return_tensors="pt").to(model.device)
        prompt_len = tokenizer(text, return_tensors="pt")["input_ids"].shape[1]

        with torch.no_grad():
            out = model(**inputs, labels=inputs["input_ids"])
        # Extract per-token log-probs for the generated portion only
        logits = out.logits[0, prompt_len - 1:-1]
        target_ids = inputs["input_ids"][0, prompt_len:]
        log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
        selected = log_probs.gather(1, target_ids.unsqueeze(1)).squeeze(1)
        return selected.sum().item()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_log_prob(scores, generated_ids) -> float:
    """
    Compute the sum of log-probabilities for the generated token sequence.
    `scores` is a tuple of (vocab_size,) tensors, one per generated step.
    """
    total = 0.0
    for step, score in enumerate(scores):
        if step >= len(generated_ids):
            break
        log_probs = torch.nn.functional.log_softmax(score[0], dim=-1)
        total += log_probs[generated_ids[step]].item()
    return total

