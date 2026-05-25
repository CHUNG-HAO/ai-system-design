"""FastAPI 入口。

啟動方式:
  cd poc/backend
  pip install -r requirements.txt
  uvicorn main:app --reload --port 7302

CORS 已開放 localhost:7301 (Next.js 前端)。
冷門 port 7301/7302 避免與 Docker / 其他常見服務衝突。
"""

from __future__ import annotations

from typing import Any

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import audio
import data
import llm
import prompts
import vision
from rag import get_index

UPLOAD_DIR = Path(__file__).resolve().parent / "cache" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="急診分級 POC API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7301", "http://127.0.0.1:7301"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "llm_available": llm.is_available(),
        "vision_available": vision.is_available(),
        "audio_available": audio.is_available(),
        "n_cases": len(data.ems_cases),
        "n_hospitals": len(data.hospitals),
    }


@app.get("/api/cases")
def list_cases(
    priority: str | None = None,
    condition: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    return {
        "items": data.list_cases(priority=priority, condition=condition, limit=limit),
        "filters": {
            "conditions": data.get_conditions(),
            "priorities": ["P1", "P2"],
        },
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    c = data.get_case(case_id)
    if c is None:
        raise HTTPException(404, f"case {case_id} not found")
    return c


@app.get("/api/protocols")
def list_protocols() -> dict[str, Any]:
    return {"items": data.list_all_protocols()}


# ----------------- AI 端點 -----------------

class TriageResponse(BaseModel):
    case_id: str
    triage: dict[str, Any]
    retrieved: list[dict[str, Any]]
    source: str  # "qwen" or "fallback"


@app.post("/api/triage/{case_id}", response_model=TriageResponse)
def ai_triage(case_id: str) -> TriageResponse:
    case = data.get_case(case_id)
    if case is None:
        raise HTTPException(404, f"case {case_id} not found")

    # RAG 查詢：以主訴 + 疑似病症 + 紅旗摘要為 query
    query = (
        f"{case['case'].get('suspected_condition','')}; "
        f"{case['case'].get('chief_complaint','')}; "
        f"SBP {case['case'].get('initial_sbp')}, HR {case['case'].get('initial_hr')}, "
        f"RR {case['case'].get('initial_rr')}, SpO2 {case['case'].get('initial_spo2')}, "
        f"GCS {case['case'].get('initial_gcs')}"
    )
    try:
        retrieved = get_index().retrieve(query, k=4)
    except Exception as e:
        print(f"[RAG] retrieve failed: {e}")
        retrieved = []

    prompt = prompts.build_triage_prompt(case, case["vitals"], retrieved)
    raw = llm.generate(prompt, max_tokens=600, temperature=0.2) if retrieved is not None else ""
    parsed = llm.extract_json(raw) if raw else None

    if parsed and "esi_level" in parsed:
        parsed.setdefault("_source", "qwen")
        source = "qwen"
        triage = parsed
    else:
        triage = prompts.fallback_triage(case, case["vitals"])
        source = "fallback"

    return TriageResponse(
        case_id=case_id,
        triage=triage,
        retrieved=retrieved,
        source=source,
    )


@app.post("/api/recommend/{case_id}")
def ai_recommend(case_id: str) -> dict[str, Any]:
    case = data.get_case(case_id)
    if case is None:
        raise HTTPException(404, f"case {case_id} not found")
    hospitals = data.get_hospitals_for_recommendation(case_id)
    if not hospitals:
        return {"case_id": case_id, "hospitals": [], "explanations": [], "source": "none"}

    prompt = prompts.build_recommend_prompt(case, hospitals)
    raw = llm.generate(prompt, max_tokens=500, temperature=0.3)
    parsed = llm.extract_json(raw) if raw else None
    if parsed and "explanations" in parsed:
        source = "qwen"
        out = parsed
    else:
        out = prompts.fallback_recommend(case, hospitals)
        source = "fallback"

    return {
        "case_id": case_id,
        "hospitals": hospitals,
        "explanations": out["explanations"],
        "source": source,
    }


class SBARRequest(BaseModel):
    case_id: str
    triage: dict[str, Any] | None = None


@app.post("/api/sbar")
def ai_sbar(req: SBARRequest) -> dict[str, Any]:
    case = data.get_case(req.case_id)
    if case is None:
        raise HTTPException(404, f"case {req.case_id} not found")

    triage = req.triage
    if not triage:
        triage = prompts.fallback_triage(case, case["vitals"])

    hospital_name = case["hospital"].get("hospital_name") if case.get("hospital") else None

    prompt = prompts.build_sbar_prompt(case, triage, hospital_name)
    raw = llm.generate(prompt, max_tokens=500, temperature=0.3)
    parsed = llm.extract_json(raw) if raw else None
    if parsed and "situation" in parsed:
        source = "qwen"
        sbar = parsed
    else:
        sbar = prompts.fallback_sbar(case, triage, hospital_name)
        source = "fallback"

    return {
        "case_id": req.case_id,
        "hospital_name": hospital_name,
        "sbar": sbar,
        "source": source,
    }


# ----------------- 📸 Vision: 拍照分析 -----------------


@app.post("/api/vision-triage")
async def vision_triage(image: UploadFile = File(...)) -> dict[str, Any]:
    """上傳照片 → Qwen2-VL 看圖分析 → 場景描述 + 紅旗 + 分級"""
    ext = Path(image.filename or "img.jpg").suffix or ".jpg"
    fid = uuid.uuid4().hex
    dst = UPLOAD_DIR / f"{fid}{ext}"
    content = await image.read()
    dst.write_bytes(content)

    result = vision.analyze(str(dst))
    return {
        "image_id": fid,
        "filename": image.filename,
        "size_bytes": len(content),
        "result": result,
        "source": result.get("_source", "unknown"),
    }


# ----------------- 🎤 Voice: 語音輸入 -----------------


@app.post("/api/voice-triage")
async def voice_triage(audio_file: UploadFile = File(..., alias="audio")) -> dict[str, Any]:
    """上傳音檔 → Whisper ASR → 把文字當主訴 → RAG + Qwen 7B 分級"""
    ext = Path(audio_file.filename or "voice.webm").suffix or ".webm"
    fid = uuid.uuid4().hex
    dst = UPLOAD_DIR / f"{fid}{ext}"
    content = await audio_file.read()
    dst.write_bytes(content)

    # 1) ASR
    asr = audio.transcribe(str(dst))
    transcript = asr.get("text", "").strip()

    # 2) RAG 檢索
    retrieved = []
    if transcript:
        try:
            retrieved = get_index().retrieve(transcript, k=4)
        except Exception as e:
            print(f"[RAG] retrieve failed: {e}")

    # 3) LLM 分級
    prompt = prompts.build_freetext_triage_prompt(transcript, retrieved)
    raw = llm.generate(prompt, max_tokens=600, temperature=0.2) if transcript else ""
    parsed = llm.extract_json(raw) if raw else None

    if parsed and "esi_level" in parsed:
        triage = parsed
        triage.setdefault("_source", "qwen")
        source = "qwen"
    else:
        triage = prompts.fallback_freetext_triage(transcript)
        source = "fallback"

    return {
        "audio_id": fid,
        "filename": audio_file.filename,
        "size_bytes": len(content),
        "asr": asr,
        "transcript": transcript,
        "retrieved": retrieved,
        "triage": triage,
        "source": source,
    }
