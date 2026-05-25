"""語音轉文字 (ASR) 包裝 — Whisper-large-v3-turbo 經 mlx-whisper。

模型從 HuggingFace Hub 抓 `mlx-community/whisper-large-v3-turbo`，
公開模型不需登入。turbo 版本約 1.5GB，在 M4 上 RTF 約 0.05~0.1。

未安裝 mlx-whisper 時 fallback 回傳示意文字，前端流程仍可 demo。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MODEL_REPO = os.getenv("WHISPER_MODEL", "mlx-community/whisper-large-v3-turbo")
LANGUAGE = os.getenv("WHISPER_LANG", "zh")
# 救護員/醫師通報語境，引導 Whisper 用繁體中文與醫療詞彙
ASR_PROMPT = (
    "以下是台灣救護員或急診醫師的繁體中文通報內容，"
    "可能包含：胸痛、心肌梗塞、STEMI、中風、FAST、敗血症、qSOFA、外傷、車禍、"
    "OHCA、CPR、血壓、心跳、呼吸、意識、GCS、ECG 等醫療術語。"
)

_state: dict[str, Any] = {"tried": False, "loaded": False, "cc": None}


def _ensure_loaded():
    if _state["tried"]:
        return
    _state["tried"] = True
    try:
        import mlx_whisper  # noqa: F401
        _state["loaded"] = True
        print(f"[ASR] mlx-whisper available, model={MODEL_REPO}")
    except Exception as e:
        _state["loaded"] = False
        print(f"[ASR] mlx-whisper 不可用，fallback 模式: {e}")

    try:
        from opencc import OpenCC

        _state["cc"] = OpenCC("s2twp")  # 簡體 → 台灣繁體 (含醫療詞彙修正)
    except Exception as e:
        print(f"[ASR] opencc 不可用，輸出可能是簡體: {e}")


"""出現任一個簡體字就觸發轉換；常見救護/醫療相關簡體字集。"""
_SIMPLIFIED_TRIGGERS = set("败发烧压识岁体国个们应问题脑识识声讲讲听见过开关电报话护医护车护车")


def _to_traditional(text: str) -> str:
    """Whisper 的 initial_prompt 已偏向繁體，這裡只在偵測到簡體字才轉換，
    避免把繁體的『敗血症』被 opencc 過度轉成古體『敗血癥』。"""
    cc = _state.get("cc")
    if cc is None or not text:
        return text
    if not any(c in _SIMPLIFIED_TRIGGERS for c in text):
        return text
    try:
        return cc.convert(text)
    except Exception:
        return text


def is_available() -> bool:
    _ensure_loaded()
    return _state["loaded"]


def transcribe(audio_path: str) -> dict[str, Any]:
    """轉錄音檔。回傳 {text, language, segments?, source}."""
    _ensure_loaded()
    if not _state["loaded"]:
        return _fallback(audio_path)
    try:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=MODEL_REPO,
            language=LANGUAGE,
            initial_prompt=ASR_PROMPT,
        )
        text_raw = result.get("text", "").strip()
        text_zh_tw = _to_traditional(text_raw)
        return {
            "text": text_zh_tw,
            "text_raw": text_raw,
            "language": result.get("language", LANGUAGE),
            "segments": [
                {
                    "start": s.get("start"),
                    "end": s.get("end"),
                    "text": _to_traditional(s.get("text", "").strip()),
                }
                for s in result.get("segments", [])
            ],
            "_source": "mlx-whisper",
        }
    except Exception as e:
        print(f"[ASR] transcribe failed: {e}")
        return _fallback(audio_path, error=str(e))


def _fallback(audio_path: str, error: str | None = None) -> dict[str, Any]:
    name = Path(audio_path).name
    return {
        "text": (
            "（示意）50 多歲男性，發燒、意識變差、血壓偏低，呼吸急促。"
            "救護車已抵達現場，需要快速分級。"
        ),
        "language": LANGUAGE,
        "segments": [],
        "_source": "fallback_demo",
        "_note": (
            "ASR 未載入，這是示意轉錄。要做真實語音辨識請：\n"
            "  pip install mlx-whisper\n"
            f"  (檔案 {name} 無法處理" + (f"; 錯誤: {error}" if error else "") + ")"
        ),
    }
