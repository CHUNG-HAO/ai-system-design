"""LLM prompt 模板，與 fallback 規則引擎。

每個任務都有 build_prompt() 與 fallback()，前者餵給 Qwen，後者在 Qwen
不可用時模擬輸出，確保 demo 不會開天窗。
"""

from __future__ import annotations

from typing import Any

# =========================================================================
# 1) 分級助手：輸入病患資料 + RAG context → 輸出 ESI / 紅旗 / 應啟動 protocol
# =========================================================================

TRIAGE_SYSTEM = """你是急診分級的決策輔助 AI。請依據病患到院前資料、相似歷史案例與急救處置指引，
給出：
1. 建議 ESI 分級（1=最嚴重，5=最輕）
2. 建議優先級（P1=立即急救通報，P2=次優先）
3. 應啟動的院內 protocol（5 種之一，或 None）
4. 紅旗清單（重點異常徵象）
5. 簡短臨床推理（2-3 句）

務必只輸出 JSON，不要任何前後文字或 markdown fence，鍵名固定如下：
{
  "esi_level": 1-5 的整數,
  "priority": "P1" 或 "P2",
  "activation": "Code STEMI / 導管室預啟動" 等字串，或 "無",
  "red_flags": ["...", "..."],
  "reasoning": "..."
}
"""


def build_triage_prompt(case: dict, vitals: list[dict], rag_docs: list[dict]) -> str:
    p = case["patient"]
    c = case["case"]
    vital_summary = _format_vitals(vitals)

    # 把 RAG 結果壓縮成 context
    ctx_lines = []
    for d in rag_docs:
        ctx_lines.append(f"[{d['kind']}] {d['text']}")
    context = "\n\n".join(ctx_lines) if ctx_lines else "（無檢索結果）"

    return f"""{TRIAGE_SYSTEM}

# 檢索到的相關處置指引與相似歷史案例
{context}

# 本案病患資料
- 性別/年齡：{p.get('sex')} / {p.get('age')} 歲（{p.get('age_group')}）
- 病史：高血壓={p.get('has_hypertension')}、糖尿病={p.get('has_diabetes')}、心血管={p.get('has_cvd_history')}、抗凝血劑={p.get('has_anticoagulant')}
- 主訴：{c.get('chief_complaint')}
- 疑似病症（救護端初判）：{c.get('suspected_condition')}
- 初始生命徵象：SBP {c.get('initial_sbp')} / DBP {c.get('initial_dbp')} mmHg，HR {c.get('initial_hr')}，RR {c.get('initial_rr')}，SpO2 {c.get('initial_spo2')}%，體溫 {c.get('initial_temp_c')}°C，GCS {c.get('initial_gcs')}
- qSOFA={c.get('qsofa')}、Lactate={c.get('lactate_mmol_l')}、NIHSS={c.get('nihss')}、FAST 陽性={c.get('fast_positive')}、ECG STEMI={c.get('ecg_stemi')}
- 救護車到院前 ROSC={c.get('prehospital_rosc')}、外傷機制={c.get('trauma_mechanism')}

# 生命徵象趨勢（救護車端多次量測）
{vital_summary}

請輸出 JSON。"""


def fallback_triage(case: dict, vitals: list[dict]) -> dict[str, Any]:
    """規則引擎 fallback。涵蓋老師資料中的 5 大急重症。"""
    c = case["case"]
    cond = c.get("suspected_condition", "")
    red: list[str] = []

    sbp = _num(c.get("initial_sbp"))
    hr = _num(c.get("initial_hr"))
    rr = _num(c.get("initial_rr"))
    spo2 = _num(c.get("initial_spo2"))
    temp = _num(c.get("initial_temp_c"))
    gcs = _num(c.get("initial_gcs"))

    if sbp is not None and sbp != 0 and sbp < 90:
        red.append(f"低血壓 SBP={int(sbp)} mmHg")
    if hr == 0:
        red.append("心跳停止 HR=0")
    elif hr is not None and hr > 120:
        red.append(f"心跳過快 HR={int(hr)}")
    if rr is not None and rr >= 22:
        red.append(f"呼吸過快 RR={int(rr)}")
    if spo2 is not None and spo2 != 0 and spo2 < 90:
        red.append(f"低血氧 SpO2={int(spo2)}%")
    if temp is not None and temp >= 39:
        red.append(f"高燒 {temp}°C")
    if gcs is not None and gcs < 9:
        red.append(f"意識不清 GCS={int(gcs)}")
    if c.get("qsofa") and _num(c["qsofa"]) and _num(c["qsofa"]) >= 2:
        red.append(f"qSOFA={int(c['qsofa'])} 高敗血風險")
    if c.get("fast_positive") == 1:
        red.append("FAST 陽性")
    if c.get("ecg_stemi") == 1:
        red.append("ECG 顯示 ST elevation")
    if c.get("prehospital_rosc") == 1:
        red.append("到院前已 ROSC")

    activation_map = {
        "STEMI": "Code STEMI / 導管室預啟動",
        "疑似急性腦中風": "Code Stroke / 中風團隊預啟動",
        "敗血症/敗血性休克": "Sepsis Bundle / 敗血症一小時包",
        "重大外傷": "Trauma Team / 外傷團隊啟動",
        "到院前心跳停止": "OHCA Team / 急救復甦團隊",
    }
    activation = activation_map.get(cond, "無")

    priority = "P1" if cond in {"STEMI", "敗血症/敗血性休克", "到院前心跳停止", "重大外傷"} else "P2"
    esi = 1 if priority == "P1" else 2

    reasoning_parts = [f"救護端初判為 {cond}。"]
    if red:
        reasoning_parts.append("出現紅旗：" + "、".join(red[:3]) + "。")
    reasoning_parts.append(f"建議優先啟動 {activation}。")

    return {
        "esi_level": esi,
        "priority": priority,
        "activation": activation,
        "red_flags": red,
        "reasoning": " ".join(reasoning_parts),
        "_source": "fallback_rules",
    }


# =========================================================================
# 1b) 自由文字分級（給語音轉錄、現場手打用）
# =========================================================================

FREETEXT_TRIAGE_SYSTEM = """你是急診分級的決策輔助 AI。使用者剛剛用語音或文字描述了急救現場狀況。
請從這段自由描述中萃取病患資料、判讀紅旗、給出分級建議。

務必只輸出 JSON，鍵名固定如下：
{
  "extracted": {
    "age": 數字或 null,
    "sex": "M"/"F"/null,
    "chief_complaint": "...",
    "suspected_condition": "STEMI / 疑似急性腦中風 / 敗血症/敗血性休克 / 重大外傷 / 到院前心跳停止 / 其他"
  },
  "esi_level": 1-5,
  "priority": "P1" 或 "P2",
  "activation": "建議啟動 protocol 或 無",
  "red_flags": ["..."],
  "reasoning": "2-3 句說明"
}
"""


def build_freetext_triage_prompt(transcript: str, rag_docs: list[dict]) -> str:
    ctx_lines = []
    for d in rag_docs:
        ctx_lines.append(f"[{d['kind']}] {d['text']}")
    context = "\n\n".join(ctx_lines) if ctx_lines else "（無檢索結果）"

    return f"""{FREETEXT_TRIAGE_SYSTEM}

# 檢索到的相關處置指引與相似歷史案例
{context}

# 救護員 / 現場人員的自由描述
{transcript}

請輸出 JSON。"""


def fallback_freetext_triage(transcript: str) -> dict:
    """簡單的關鍵字 fallback：用中文急救用語匹配。"""
    t = transcript or ""
    cond = "其他"
    activation = "無"
    red: list[str] = []

    has = lambda *kws: any(k in t for k in kws)

    # 順序: 先判最致命的 OHCA → 中風 (避免被 STEMI 的 "ST" 誤觸) → STEMI → 外傷 → 敗血症
    if has("OHCA", "心跳停止", "無呼吸", "無脈搏", "CPR", "AED", "電擊"):
        cond = "到院前心跳停止"
        activation = "OHCA Team / 急救復甦團隊"
    elif has("中風", "FAST", "單側無力", "右側無力", "左側無力", "半側無力",
             "口齒不清", "顏面歪", "嘴角歪", "NIHSS", "言語不清"):
        cond = "疑似急性腦中風"
        activation = "Code Stroke / 中風團隊預啟動"
    elif has("胸痛", "胸悶", "ST elevation", "ST段", "ST抬高", "STEMI",
             "心肌梗塞", "冒冷汗", "PCI"):
        cond = "STEMI"
        activation = "Code STEMI / 導管室預啟動"
    elif has("外傷", "車禍", "機車", "自撞", "撞擊", "墜落", "墜樓",
             "穿刺", "刀傷", "槍傷", "骨折", "開放性", "重大出血", "大量出血",
             "腹部壓痛", "胸部撞擊"):
        cond = "重大外傷"
        activation = "Trauma Team / 外傷團隊啟動"
    elif has("發燒", "高燒", "敗血", "qSOFA", "感染", "lactate", "乳酸"):
        cond = "敗血症/敗血性休克"
        activation = "Sepsis Bundle / 敗血症一小時包"

    if has("意識不清", "意識變差", "意識改變", "昏迷", "無意識", "GCS"):
        red.append("意識變化")
    if has("血壓低", "低血壓", "休克", "收縮壓只剩", "收縮壓 8", "收縮壓 9"):
        red.append("低血壓 / 休克")
    if has("呼吸喘", "呼吸急", "呼吸困難", "呼吸急促"):
        red.append("呼吸窘迫")
    if has("發燒", "高燒"):
        red.append("發燒")
    if has("出血", "大量出血", "開放性"):
        red.append("出血")
    if has("骨折"):
        red.append("骨折")

    # 抽年齡（數字+歲）
    import re

    age = None
    m = re.search(r"(\d{2,3})\s*歲", t)
    if m:
        age = int(m.group(1))
    sex = None
    if "男" in t:
        sex = "M"
    elif "女" in t:
        sex = "F"

    # 5 大急重症一律 P1 / ESI 1（不論有沒有紅旗）；其他依紅旗
    P1_CONDS = {"STEMI", "疑似急性腦中風", "敗血症/敗血性休克", "重大外傷", "到院前心跳停止"}
    if cond in P1_CONDS:
        priority, esi = "P1", 1
    elif red:
        priority, esi = "P2", 2
    else:
        priority, esi = "P2", 3

    return {
        "extracted": {
            "age": age,
            "sex": sex,
            "chief_complaint": t[:80],
            "suspected_condition": cond,
        },
        "esi_level": esi,
        "priority": priority,
        "activation": activation,
        "red_flags": red,
        "reasoning": (
            f"從描述中辨識疑似 {cond}；偵測到的紅旗：" + ("、".join(red) if red else "無") + "。"
        ),
        "_source": "fallback_rules",
    }


# =========================================================================
# 2) 醫院推薦解釋
# =========================================================================

RECOMMEND_SYSTEM = """你是急救派送輔助 AI，請以 2-3 句自然語言解釋為什麼推薦這家醫院給此案病患。
重點覆蓋：醫院能力（PCI / 中風中心 / 外傷中心 / CT / 導管室）、即時資源（ED 床、ICU、CT、導管、外傷灣的可用數）、距離與壅塞度，
並對照病症需求。語氣專業簡潔，給急救員或調度員看。
"""


def build_recommend_prompt(case: dict, hospitals: list[dict]) -> str:
    cond = case["case"].get("suspected_condition")
    lines = []
    for h in hospitals:
        hd = h["hospital"]
        snap = h.get("snapshot") or {}
        cap = []
        if hd.get("pci_capable") == 1:
            cap.append("PCI capable")
        if hd.get("stroke_center_level"):
            cap.append(f"中風中心({hd['stroke_center_level']})")
        if hd.get("trauma_center_level"):
            cap.append(f"外傷中心 L{hd['trauma_center_level']}")
        if hd.get("has_cath_lab") == 1:
            cap.append("導管室")
        if hd.get("has_neuro_intervention") == 1:
            cap.append("神經介入")
        cap_str = ", ".join(cap) if cap else "—"

        snap_str = "—"
        if snap:
            snap_str = (
                f"ED床={snap.get('ed_beds_available')}, ICU={snap.get('icu_beds_available')}, "
                f"CT={snap.get('ct_available')}, 導管={snap.get('cath_lab_available')}, "
                f"外傷灣={snap.get('trauma_bays_available')}, 呼吸器={snap.get('ventilators_available')}, "
                f"壅塞度={snap.get('crowding_index')}"
            )

        lines.append(
            f"- 第{h['rank']}名 {hd['hospital_name']} (層級={hd['hospital_level']}, 區={hd['region']})\n"
            f"  能力: {cap_str}\n"
            f"  即時資源: {snap_str}\n"
            f"  系統分數: {h['score']:.1f}, 預估車程: {h['travel_min']} 分鐘\n"
            f"  系統內部理由: {h['reason']}"
        )

    return f"""{RECOMMEND_SYSTEM}

# 本案病症：{cond}

# 系統推薦的前 3 名醫院
{chr(10).join(lines)}

請對每一家輸出一段 2-3 句的解釋。輸出 JSON 格式：
{{
  "explanations": [
    {{"rank": 1, "hospital_name": "...", "explanation": "..."}},
    {{"rank": 2, "hospital_name": "...", "explanation": "..."}},
    {{"rank": 3, "hospital_name": "...", "explanation": "..."}}
  ]
}}
只輸出 JSON，不要任何前後文字。"""


def fallback_recommend(case: dict, hospitals: list[dict]) -> dict[str, Any]:
    cond = case["case"].get("suspected_condition")
    expl = []
    for h in hospitals:
        hd = h["hospital"]
        snap = h.get("snapshot") or {}
        parts = []
        if cond == "STEMI" and hd.get("pci_capable") == 1:
            parts.append(f"{hd['hospital_name']} 具備 PCI 能力與導管室")
            if snap.get("cath_lab_available"):
                parts.append("即時導管室可用")
        elif cond == "疑似急性腦中風":
            level = hd.get("stroke_center_level")
            if level:
                parts.append(f"{hd['hospital_name']} 是 {level} 中風中心")
            if snap.get("ct_available"):
                parts.append("CT 立即可用")
        elif cond == "敗血症/敗血性休克":
            parts.append(f"{hd['hospital_name']} ICU 可用 {snap.get('icu_beds_available','?')} 床")
            if snap.get("ventilators_available"):
                parts.append("呼吸器尚有量能")
        elif cond == "重大外傷":
            lvl = hd.get("trauma_center_level")
            if lvl:
                parts.append(f"{hd['hospital_name']} 為 L{lvl} 外傷中心")
            if snap.get("trauma_bays_available"):
                parts.append(f"外傷灣可用 {snap.get('trauma_bays_available')} 個")
        elif cond == "到院前心跳停止":
            parts.append(f"{hd['hospital_name']} ICU {snap.get('icu_beds_available','?')} 床、呼吸器 {snap.get('ventilators_available','?')} 台")

        if not parts:
            parts.append(f"{hd['hospital_name']} 系統綜合分數 {h['score']:.1f}")
        parts.append(f"預估車程 {h['travel_min']} 分鐘")
        if snap.get("crowding_index") is not None:
            parts.append(f"壅塞度 {snap['crowding_index']}")

        expl.append(
            {
                "rank": h["rank"],
                "hospital_name": hd["hospital_name"],
                "explanation": "，".join(parts) + "。",
            }
        )
    return {"explanations": expl, "_source": "fallback_rules"}


# =========================================================================
# 3) SBAR 通報摘要
# =========================================================================

SBAR_SYSTEM = """你是負責產生急救通報訊息的 AI 助手。請輸出 SBAR 格式的通報內容給接收醫院。
S (Situation): 一句話描述病患、年齡、性別、疑似病症
B (Background): 病史與發病情境
A (Assessment): 生命徵象重點、嚴重度
R (Recommendation): ETA、請對方準備的資源與啟動的 protocol

請務必精簡，每段不超過 2 行，急救情境下要可以一眼看完。
"""


def build_sbar_prompt(case: dict, triage: dict, hospital_name: str | None) -> str:
    c = case["case"]
    p = case["patient"]
    eta = c.get("eta_time") or "未估"
    arrival = c.get("arrival_hospital_time") or "未估"
    return f"""{SBAR_SYSTEM}

# 案件資料
- 收治醫院: {hospital_name or '待定'}
- 病患: {p.get('sex')} {p.get('age')} 歲
- 病史: 高血壓={p.get('has_hypertension')}、糖尿病={p.get('has_diabetes')}、心血管={p.get('has_cvd_history')}
- 疑似病症: {c.get('suspected_condition')}
- 主訴: {c.get('chief_complaint')}
- 生命徵象: SBP {c.get('initial_sbp')}、HR {c.get('initial_hr')}、RR {c.get('initial_rr')}、SpO2 {c.get('initial_spo2')}%、體溫 {c.get('initial_temp_c')}°C、GCS {c.get('initial_gcs')}
- 紅旗: {", ".join(triage.get("red_flags", []) or [])}
- 應啟動: {triage.get("activation")}
- ETA: {eta}

請以 JSON 輸出：
{{
  "situation": "...",
  "background": "...",
  "assessment": "...",
  "recommendation": "...",
  "one_line_summary": "P1/P2 ..."
}}
只輸出 JSON。"""


def fallback_sbar(case: dict, triage: dict, hospital_name: str | None) -> dict[str, Any]:
    c = case["case"]
    p = case["patient"]
    history = []
    if p.get("has_hypertension"):
        history.append("高血壓")
    if p.get("has_diabetes"):
        history.append("糖尿病")
    if p.get("has_cvd_history"):
        history.append("心血管病史")
    history_str = "、".join(history) if history else "無特別病史"

    eta_min = ""
    if c.get("eta_time") and c.get("alert_created_time"):
        try:
            import pandas as pd

            t1 = pd.to_datetime(c["alert_created_time"])
            t2 = pd.to_datetime(c["eta_time"])
            eta_min = f"約 {int((t2 - t1).total_seconds() / 60)} 分鐘"
        except Exception:
            pass

    sbar = {
        "situation": f"{p.get('age','?')} 歲 {p.get('sex','?')}，疑似 {c.get('suspected_condition')}。",
        "background": f"主訴：{c.get('chief_complaint')}。病史：{history_str}。",
        "assessment": (
            f"SBP {c.get('initial_sbp')}/{c.get('initial_dbp')} mmHg、HR {c.get('initial_hr')}、"
            f"RR {c.get('initial_rr')}、SpO2 {c.get('initial_spo2')}%、體溫 {c.get('initial_temp_c')}°C、"
            f"GCS {c.get('initial_gcs')}。紅旗：{', '.join(triage.get('red_flags', []) or ['—'])}。"
        ),
        "recommendation": (
            f"ETA {eta_min}抵達{hospital_name or '收治醫院'}，請預啟動 {triage.get('activation')}。"
        ),
        "one_line_summary": (
            f"{triage.get('priority')} {c.get('suspected_condition')}，ETA {eta_min}，"
            f"請預備 {triage.get('activation')}"
        ),
        "_source": "fallback_rules",
    }
    return sbar


# ---------- 工具 ----------
def _format_vitals(vitals: list[dict]) -> str:
    if not vitals:
        return "（無）"
    lines = []
    for v in vitals[:6]:
        lines.append(
            f"- seq {v.get('sequence_no')} {v.get('phase')} @ {v.get('measured_at')}: "
            f"SBP {v.get('sbp')}, HR {v.get('hr')}, RR {v.get('rr')}, SpO2 {v.get('spo2')}, GCS {v.get('gcs')}"
        )
    return "\n".join(lines)


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
