"""
ChessEcon Training — Model Loader
Downloads and loads Qwen/Llama models from HuggingFace for RL training.
Uses HF_TOKEN from .env for gated models (e.g., Llama-3.2-3B-Instruct).
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def download_model(model_name: str, cache_dir: str, hf_token: Optional[str] = None) -> str:
    """
    Download a model from HuggingFace Hub to local cache.
    Returns the local path to the downloaded model.
    """
    from huggingface_hub import snapshot_download, login

    if hf_token:
        login(token=hf_token, add_to_git_credential=False)
        logger.info("Logged in to HuggingFace Hub")

    local_path = Path(cache_dir) / model_name.replace("/", "--")
    if local_path.exists() and any(local_path.iterdir()):
        logger.info(f"Model already cached at {local_path}")
        return str(local_path)

    logger.info(f"Downloading {model_name} to {cache_dir} ...")
    path = snapshot_download(
        repo_id=model_name,
        cache_dir=cache_dir,
        token=hf_token,
        ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "tf_model*", "*.ot"],
    )
    logger.info(f"Model downloaded to {path}")
    return path


def load_model_and_tokenizer(
    model_name: str,
    cache_dir: str,
    device: str = "cpu",
    hf_token: Optional[str] = None,
    for_training: bool = True,
) -> Tuple:
    """
    Load a HuggingFace model and tokenizer for RL training.
    Returns (model, tokenizer).
    """
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        raise ImportError("transformers and torch are required for training. Run: pip install transformers torch")

    logger.info(f"Loading model: {model_name} on {device}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        token=hf_token,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = None
    if device == "cuda":
        try:
            import torch
            dtype = torch.bfloat16
        except Exception:
            pass

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        cache_dir=cache_dir,
        token=hf_token,
        torch_dtype=dtype,
        device_map=device if device != "cpu" else None,
        trust_remote_code=True,
    )

    if device == "cpu":
        model = model.to("cpu")

    if for_training:
        model.train()
    else:
        model.eval()

    total_params = sum(p.numel() for p in model.parameters()) / 1e6
    logger.info(f"Model loaded: {total_params:.1f}M parameters on {device}")
    return model, tokenizer


def generate_move(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 64,
    temperature: float = 0.9,
    device: str = "cpu",
) -> str:
    """Generate a chess move from the model given a prompt."""
    import torch

    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
        )
    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()
