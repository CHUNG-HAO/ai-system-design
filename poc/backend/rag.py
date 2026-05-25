"""RAG 檢索層。

corpus 來源:
1. intervention_protocols：5 個急重症的觸發條件 / 啟動流程 / 關鍵資源 / KPI
2. 歷史案例摘要：抽樣 ~200 件 ems_cases，把主訴+生命徵象+suspected_condition+outcome 串成檢索片段

embedding：sentence-transformers / BAAI/bge-small-zh-v1.5（公開、不需登入、約 100MB）
向量索引：in-memory FAISS IndexFlatIP（歸一化後 = cosine similarity）

第一次 import 會建立索引並 cache 到 cache/rag_index.npz，之後直接讀。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from data import ems_cases, intervention_protocols, outcomes, patients

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
EMB_CACHE = CACHE_DIR / "rag_embeddings.npy"
DOC_CACHE = CACHE_DIR / "rag_docs.json"

EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
N_HISTORICAL_CASES = int(os.getenv("RAG_HISTORICAL_CASES", "200"))


def _build_corpus() -> list[dict[str, Any]]:
    """產生要索引的文件清單。每筆有 id / kind / text / meta."""
    docs: list[dict[str, Any]] = []

    # 1) protocols
    for _, row in intervention_protocols.iterrows():
        text = (
            f"病症: {row['condition']}\n"
            f"觸發條件: {row['trigger_rule']}\n"
            f"啟動流程: {row['activation']}\n"
            f"關鍵資源: {row['key_resources']}\n"
            f"目標 KPI: {row['target_kpi']}\n"
            f"推薦規則: {row['demo_rule']}"
        )
        docs.append(
            {
                "id": f"protocol::{row['protocol_id']}",
                "kind": "protocol",
                "text": text,
                "meta": {
                    "protocol_id": row["protocol_id"],
                    "condition": row["condition"],
                    "activation": row["activation"],
                    "key_resources": row["key_resources"],
                    "target_kpi": row["target_kpi"],
                },
            }
        )

    # 2) 歷史案例摘要：每個 condition 抽 ~40 件，保證多樣性
    sample = (
        ems_cases.merge(patients, on="patient_id", how="left")
        .merge(outcomes[["case_id", "protocol_target_met",
                          "door_to_balloon_min", "door_to_ct_min",
                          "antibiotic_to_recognition_min",
                          "trauma_team_ready_min_from_arrival",
                          "disposition", "mortality_24h"]],
               on="case_id", how="left")
    )
    per_cond = max(1, N_HISTORICAL_CASES // max(1, sample["suspected_condition"].nunique()))
    sub = (
        sample.groupby("suspected_condition", group_keys=False)
        .apply(lambda g: g.head(per_cond))
    )

    for _, row in sub.iterrows():
        text = (
            f"案件: {row['case_id']} 疑似 {row['suspected_condition']} ({row['priority']}, ESI {row['esi_level']})\n"
            f"病患: {row.get('age','?')} 歲 {row.get('sex','?')}, "
            f"高血壓={int(row.get('has_hypertension',0))}, 糖尿病={int(row.get('has_diabetes',0))}, "
            f"心血管病史={int(row.get('has_cvd_history',0))}\n"
            f"主訴: {row.get('chief_complaint','')}\n"
            f"初始生命徵象: SBP {row.get('initial_sbp')}, HR {row.get('initial_hr')}, "
            f"RR {row.get('initial_rr')}, SpO2 {row.get('initial_spo2')}, "
            f"體溫 {row.get('initial_temp_c')}, GCS {row.get('initial_gcs')}\n"
            f"啟動: {row.get('activation_type','')}\n"
            f"流程是否達標: {row.get('protocol_target_met','')}, 24h 死亡: {row.get('mortality_24h','')}"
        )
        docs.append(
            {
                "id": f"case::{row['case_id']}",
                "kind": "historical_case",
                "text": text,
                "meta": {
                    "case_id": row["case_id"],
                    "condition": row["suspected_condition"],
                    "priority": row["priority"],
                    "esi_level": int(row["esi_level"]),
                    "protocol_target_met": _safe(row.get("protocol_target_met")),
                },
            }
        )

    return docs


def _embed(model, texts: list[str]) -> np.ndarray:
    vec = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )
    return np.asarray(vec, dtype="float32")


class RAGIndex:
    """簡單的 in-memory cosine-similarity 檢索器（用 numpy，免裝 faiss）."""

    def __init__(self):
        self.docs: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(EMBED_MODEL_NAME)
        return self._model

    def build_or_load(self):
        if EMB_CACHE.exists() and DOC_CACHE.exists():
            self.embeddings = np.load(EMB_CACHE)
            self.docs = json.loads(DOC_CACHE.read_text(encoding="utf-8"))
            print(f"[RAG] cache hit: {len(self.docs)} docs")
            return

        print("[RAG] building index from CSV ...")
        self.docs = _build_corpus()
        model = self._ensure_model()
        self.embeddings = _embed(model, [d["text"] for d in self.docs])
        np.save(EMB_CACHE, self.embeddings)
        DOC_CACHE.write_text(json.dumps(self.docs, ensure_ascii=False), encoding="utf-8")
        print(f"[RAG] built: {len(self.docs)} docs, dim={self.embeddings.shape[1]}")

    def retrieve(self, query: str, k: int = 4, kind: str | None = None) -> list[dict[str, Any]]:
        if self.embeddings is None:
            self.build_or_load()
        model = self._ensure_model()
        q = _embed(model, [query])[0]

        sims = self.embeddings @ q  # cosine, 已 normalize
        # 若指定 kind，先過濾
        if kind:
            mask = np.array([d["kind"] == kind for d in self.docs])
            sims = np.where(mask, sims, -1e9)

        idx = np.argsort(-sims)[:k]
        out = []
        for i in idx:
            out.append(
                {
                    "id": self.docs[i]["id"],
                    "kind": self.docs[i]["kind"],
                    "text": self.docs[i]["text"],
                    "meta": self.docs[i]["meta"],
                    "score": float(sims[i]),
                }
            )
        return out


_singleton: RAGIndex | None = None


def get_index() -> RAGIndex:
    global _singleton
    if _singleton is None:
        _singleton = RAGIndex()
        _singleton.build_or_load()
    return _singleton


def _safe(v):
    import math
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    return v
