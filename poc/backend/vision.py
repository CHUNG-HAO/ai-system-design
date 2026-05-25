"""Qwen2-VL-7B 視覺語言模型包裝。

預設用 mlx-vlm（Apple Silicon 原生加速）載入 4-bit 量化版本。
從 HuggingFace Hub 抓 `mlx-community/Qwen2-VL-7B-Instruct-4bit`，公開模型不需登入。

未安裝 mlx-vlm 時 fallback 回傳「demo mode」結果，前端流程仍可走。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

MODEL_REPO = os.getenv("QWEN_VL_MODEL", "mlx-community/Qwen2-VL-7B-Instruct-4bit")

_state: dict[str, Any] = {"model": None, "processor": None, "loaded": False, "tried": False}


def _ensure_loaded():
    if _state["tried"]:
        return
    _state["tried"] = True
    try:
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        print(f"[VLM] loading {MODEL_REPO} (first call may download ~5GB) ...")
        model, processor = load(MODEL_REPO)
        _state["model"] = model
        _state["processor"] = processor
        _state["loaded"] = True
        print("[VLM] Qwen2-VL ready.")
    except Exception as e:
        _state["loaded"] = False
        print(f"[VLM] load failed, fallback enabled: {e}")


def is_available() -> bool:
    _ensure_loaded()
    return _state["loaded"]


TRIAGE_VISION_PROMPT = """你是急診分級的決策輔助 AI，請看這張急救現場的照片，分析病患可能的狀況並給出分級。

請依以下面向觀察並輸出 JSON（只有 JSON，不要其他文字、不要 markdown fence）：

可觀察的線索包含但不限於：
- 病患外觀（意識、姿勢、面色、出血、傷口、燒燙傷、嘔吐物、瞳孔）
- 環境（車禍、墜落、火場、室內室外、現場規模）
- 設備（氧氣面罩、IV 線、固定器、AED、夾板、心電圖紙）
- ECG 影像若可見，注意 ST 段抬高或壓低
- 藥袋/藥盒若可見，留意抗凝血劑、降血壓、降血糖等

輸出 JSON 格式：
{
  "scene_description": "你看到了什麼，2-3 句",
  "visible_red_flags": ["紅旗1", "紅旗2"],
  "esi_level": 1-5 的整數,
  "priority": "P1" 或 "P2",
  "suspected_condition": "STEMI / 疑似急性腦中風 / 敗血症 / 重大外傷 / 到院前心跳停止 / 其他",
  "activation": "建議啟動的院內 protocol，或 無",
  "next_steps": ["建議下一步處置1", "建議下一步處置2"],
  "confidence": "high" / "medium" / "low",
  "reasoning": "你判斷的理由，2-3 句"
}
"""


def analyze(image_path: str) -> dict[str, Any]:
    """看圖回傳分級結果。若 VLM 不可用，回傳 fallback 樣本。"""
    _ensure_loaded()
    if not _state["loaded"]:
        return _fallback(image_path)

    try:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        model = _state["model"]
        processor = _state["processor"]
        config = model.config

        formatted = apply_chat_template(
            processor, config, TRIAGE_VISION_PROMPT, num_images=1
        )

        output = generate(
            model,
            processor,
            formatted,
            image=[image_path],
            max_tokens=600,
            verbose=False,
        )
        # mlx-vlm 的 generate 可能回 str 或 dict; 取出文字
        text = output if isinstance(output, str) else getattr(output, "text", str(output))

        parsed = _extract_json(text)
        if parsed:
            parsed.setdefault("_raw", text)
            parsed.setdefault("_source", "qwen2-vl")
            return parsed
        return {
            "_source": "qwen2-vl",
            "_raw": text,
            "scene_description": text[:200],
            "visible_red_flags": [],
            "esi_level": 3,
            "priority": "P2",
            "suspected_condition": "需進一步評估",
            "activation": "無",
            "next_steps": ["建立 IV 線", "持續監測生命徵象"],
            "confidence": "low",
            "reasoning": "VLM 輸出無法解析為 JSON，已回傳原始文字供參考。",
        }
    except Exception as e:
        print(f"[VLM] generate failed: {e}")
        return _fallback(image_path, error=str(e))


def _fallback(image_path: str, error: str | None = None) -> dict[str, Any]:
    """沒裝 mlx-vlm 或推論失敗時的 demo 樣本。"""
    name = Path(image_path).name.lower()
    # 根據檔名 hint 給示意（純 demo 用途）
    if "ecg" in name or "stemi" in name or "心電" in name:
        return {
            "_source": "fallback_demo",
            "_note": "VLM 未載入，這是示意輸出。要看真實分析請 pip install mlx-vlm。",
            "scene_description": "（示意）疑似 12 導程心電圖，下壁導程 II/III/aVF 可能有 ST 段抬高。",
            "visible_red_flags": ["ECG 疑似 ST elevation"],
            "esi_level": 1,
            "priority": "P1",
            "suspected_condition": "STEMI",
            "activation": "Code STEMI / 導管室預啟動",
            "next_steps": ["12 導程 ECG 再次確認", "抽 troponin", "預啟動導管室"],
            "confidence": "medium",
            "reasoning": "（示意）這是 fallback 輸出，僅供 UI 流程展示。",
        }
    if "trauma" in name or "wound" in name or "外傷" in name or "blood" in name:
        return {
            "_source": "fallback_demo",
            "_note": "VLM 未載入，這是示意輸出。要看真實分析請 pip install mlx-vlm。",
            "scene_description": "（示意）疑似嚴重外傷，可見明顯出血或開放性傷口。",
            "visible_red_flags": ["大量出血", "可見開放性傷口"],
            "esi_level": 1,
            "priority": "P1",
            "suspected_condition": "重大外傷",
            "activation": "Trauma Team / 外傷團隊啟動",
            "next_steps": ["大量輸液預備", "啟動大量輸血流程", "外傷 CT 預備"],
            "confidence": "medium",
            "reasoning": "（示意）這是 fallback 輸出，僅供 UI 流程展示。",
        }
    return {
        "_source": "fallback_demo",
        "_note": "VLM 未載入。pip install mlx-vlm 後再試一次可看到真實 Qwen2-VL 分析。",
        "scene_description": "（示意）尚無 VLM 可分析，這是 fallback 訊息。",
        "visible_red_flags": [],
        "esi_level": 3,
        "priority": "P2",
        "suspected_condition": "需進一步評估",
        "activation": "無",
        "next_steps": ["建立 IV 線", "持續監測生命徵象", "等待 VLM 載入後重新分析"],
        "confidence": "low",
        "reasoning": "fallback 模式，無法做真實圖像分析。" + (f" 錯誤: {error}" if error else ""),
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        candidate = brace.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            for end in range(len(candidate), 0, -1):
                try:
                    return json.loads(candidate[:end])
                except json.JSONDecodeError:
                    continue
    return None
