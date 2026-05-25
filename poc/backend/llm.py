"""Qwen 7B LLM 包裝。

預設用 mlx-lm 載入 4-bit 量化版本（Apple Silicon 原生加速）。
模型從 Hugging Face Hub 抓取，公開模型，不需登入 token。
模型未下載時第一次呼叫會自動下載，~5GB。

若 mlx-lm 載入失敗（例如非 Apple Silicon 機器），fallback 到 rule-based stub，
仍可 demo，不會擋住前端流程。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

MODEL_REPO = os.getenv("QWEN_MODEL", "mlx-community/Qwen2.5-7B-Instruct-4bit")

_qwen_state: dict[str, Any] = {"model": None, "tokenizer": None, "loaded": False, "error": None}


def _ensure_loaded():
    if _qwen_state["loaded"]:
        return
    try:
        from mlx_lm import load

        print(f"[LLM] loading {MODEL_REPO} (first call may download ~5GB) ...")
        model, tokenizer = load(MODEL_REPO)
        _qwen_state["model"] = model
        _qwen_state["tokenizer"] = tokenizer
        _qwen_state["loaded"] = True
        print("[LLM] Qwen ready.")
    except Exception as e:
        _qwen_state["loaded"] = False
        _qwen_state["error"] = str(e)
        print(f"[LLM] load failed, fallback enabled: {e}")


def is_available() -> bool:
    _ensure_loaded()
    return _qwen_state["model"] is not None


def generate(prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> str:
    """同步呼叫 Qwen 生成。失敗時回傳空字串，由上層 fallback。"""
    _ensure_loaded()
    if _qwen_state["model"] is None:
        return ""

    try:
        from mlx_lm import generate as mlx_generate

        tokenizer = _qwen_state["tokenizer"]
        messages = [{"role": "user", "content": prompt}]
        templated = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        text = mlx_generate(
            _qwen_state["model"],
            tokenizer,
            prompt=templated,
            max_tokens=max_tokens,
            verbose=False,
        )
        return text
    except Exception as e:
        print(f"[LLM] generate failed: {e}")
        return ""


def extract_json(text: str) -> dict[str, Any] | None:
    """從 LLM 輸出抽出第一個 JSON 物件。容錯處理 markdown code fence。"""
    if not text:
        return None
    # 移除 ```json ... ``` fence
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    # 直接抓第一個 { ... }
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        candidate = brace.group(0)
        # 收斂多餘 trailing content
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 試著找最後一個 } 收斂
            for end in range(len(candidate), 0, -1):
                try:
                    return json.loads(candidate[:end])
                except json.JSONDecodeError:
                    continue
    return None
