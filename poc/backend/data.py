"""載入老師提供的 14 張 CSV 資料表，提供查詢介面。

所有 DataFrame 在 module import 時一次性載入，後續 query 走 in-memory filter，
這對 1366 筆案件而言完全足夠，不需要額外資料庫。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "期末專題參考資料集"


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    return pd.read_csv(path)


hospitals = _read_csv("hospitals")
ambulances = _read_csv("ambulances")
clinicians = _read_csv("clinicians")
patients = _read_csv("patients")
ems_cases = _read_csv("ems_cases")
prehospital_vitals = _read_csv("prehospital_vitals")
alerts = _read_csv("alerts")
routing_recommendations = _read_csv("routing_recommendations")
resource_orders = _read_csv("resource_orders")
treatment_events = _read_csv("treatment_events")
outcomes = _read_csv("outcomes")
intervention_protocols = _read_csv("intervention_protocols")
hospital_resource_snapshots = _read_csv("hospital_resource_snapshots")

# 時間欄位轉成 datetime 方便排序
for col in ("dispatch_time", "patient_contact_time", "depart_scene_time",
            "alert_created_time", "eta_time", "arrival_hospital_time"):
    if col in ems_cases.columns:
        ems_cases[col] = pd.to_datetime(ems_cases[col], errors="coerce")

prehospital_vitals["measured_at"] = pd.to_datetime(
    prehospital_vitals["measured_at"], errors="coerce"
)
alerts["alert_created_time"] = pd.to_datetime(alerts["alert_created_time"], errors="coerce")
alerts["first_ack_time"] = pd.to_datetime(alerts["first_ack_time"], errors="coerce")
hospital_resource_snapshots["snapshot_time"] = pd.to_datetime(
    hospital_resource_snapshots["snapshot_time"], errors="coerce"
)


def list_cases(
    priority: str | None = None,
    condition: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """回傳案件清單，預設依 alert_created_time 由新到舊排序。"""
    df = ems_cases.copy()
    if priority:
        df = df[df["priority"] == priority]
    if condition:
        df = df[df["suspected_condition"] == condition]

    df = df.sort_values("alert_created_time", ascending=False).head(limit)

    # join patient + hospital + alert
    df = df.merge(patients, on="patient_id", how="left")
    df = df.merge(
        hospitals[["hospital_id", "hospital_name"]],
        left_on="receiving_hospital_id",
        right_on="hospital_id",
        how="left",
    )
    df = df.merge(
        alerts[["case_id", "ack_minutes", "status"]],
        on="case_id",
        how="left",
    )

    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "case_id": row["case_id"],
                "suspected_condition": row["suspected_condition"],
                "priority": row["priority"],
                "esi_level": int(row["esi_level"]),
                "chief_complaint": row.get("chief_complaint"),
                "age": int(row["age"]) if pd.notna(row.get("age")) else None,
                "sex": row.get("sex"),
                "hospital_name": row.get("hospital_name"),
                "hospital_id": row.get("receiving_hospital_id"),
                "alert_created_time": _iso(row.get("alert_created_time")),
                "eta_time": _iso(row.get("eta_time")),
                "arrival_hospital_time": _iso(row.get("arrival_hospital_time")),
                "ack_minutes": _num(row.get("ack_minutes")),
            }
        )
    return out


def get_case(case_id: str) -> dict[str, Any] | None:
    """完整案件詳情：病患、案件、生命徵象、推薦、資源、結果。"""
    case_rows = ems_cases[ems_cases["case_id"] == case_id]
    if case_rows.empty:
        return None
    case = case_rows.iloc[0].to_dict()

    patient = patients[patients["patient_id"] == case["patient_id"]].iloc[0].to_dict()
    hospital = hospitals[hospitals["hospital_id"] == case["receiving_hospital_id"]]
    hospital_d = hospital.iloc[0].to_dict() if not hospital.empty else {}

    vitals = (
        prehospital_vitals[prehospital_vitals["case_id"] == case_id]
        .sort_values("sequence_no")
        .to_dict("records")
    )

    recs = routing_recommendations[
        routing_recommendations["case_id"] == case_id
    ]
    rec_d = recs.iloc[0].to_dict() if not recs.empty else {}

    orders = resource_orders[resource_orders["case_id"] == case_id].to_dict("records")
    alert_d = alerts[alerts["case_id"] == case_id]
    alert_d = alert_d.iloc[0].to_dict() if not alert_d.empty else {}
    out_d = outcomes[outcomes["case_id"] == case_id]
    out_d = out_d.iloc[0].to_dict() if not out_d.empty else {}

    # 取通報前最接近的院內資源快照
    snap = None
    if case.get("receiving_hospital_id"):
        snaps = hospital_resource_snapshots[
            hospital_resource_snapshots["hospital_id"] == case["receiving_hospital_id"]
        ]
        if not snaps.empty and pd.notna(case.get("alert_created_time")):
            snaps = snaps[snaps["snapshot_time"] <= case["alert_created_time"]]
            if not snaps.empty:
                snap = snaps.sort_values("snapshot_time", ascending=False).iloc[0].to_dict()

    return {
        "case": _clean(case),
        "patient": _clean(patient),
        "hospital": _clean(hospital_d),
        "vitals": [_clean(v) for v in vitals],
        "recommendation": _clean(rec_d),
        "resource_orders": [_clean(o) for o in orders],
        "alert": _clean(alert_d),
        "outcome": _clean(out_d),
        "hospital_snapshot": _clean(snap) if snap else None,
    }


def get_hospitals_for_recommendation(case_id: str) -> list[dict[str, Any]]:
    """回傳前 3 名推薦醫院的詳情，含 snapshot."""
    recs = routing_recommendations[routing_recommendations["case_id"] == case_id]
    if recs.empty:
        return []
    r = recs.iloc[0]
    out = []
    for i in (1, 2, 3):
        hid = r.get(f"recommended_hospital_{i}")
        if pd.isna(hid):
            continue
        h = hospitals[hospitals["hospital_id"] == hid]
        if h.empty:
            continue
        h_d = h.iloc[0].to_dict()
        # 找最近的 snapshot
        case_row = ems_cases[ems_cases["case_id"] == case_id].iloc[0]
        snaps = hospital_resource_snapshots[
            (hospital_resource_snapshots["hospital_id"] == hid)
            & (hospital_resource_snapshots["snapshot_time"] <= case_row["alert_created_time"])
        ]
        snap = None
        if not snaps.empty:
            snap = snaps.sort_values("snapshot_time", ascending=False).iloc[0].to_dict()

        out.append(
            {
                "rank": i,
                "hospital": _clean(h_d),
                "score": _num(r.get(f"score_{i}")),
                "travel_min": _num(r.get(f"travel_min_{i}")),
                "reason": r.get(f"reason_{i}"),
                "snapshot": _clean(snap) if snap else None,
                "is_selected": hid == r.get("selected_hospital_id"),
            }
        )
    return out


def get_protocol(condition: str) -> dict[str, Any] | None:
    rows = intervention_protocols[intervention_protocols["condition"] == condition]
    if rows.empty:
        return None
    return _clean(rows.iloc[0].to_dict())


def list_all_protocols() -> list[dict[str, Any]]:
    return [_clean(r) for r in intervention_protocols.to_dict("records")]


def get_conditions() -> list[str]:
    return sorted(ems_cases["suspected_condition"].dropna().unique().tolist())


# ---------- 工具 ----------
def _iso(v: Any) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        return None
    return float(v)


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """把 NaN 轉成 None，Timestamp 轉 iso，方便 JSON 序列化."""
    out = {}
    for k, v in d.items():
        if isinstance(v, pd.Timestamp):
            out[k] = v.isoformat() if pd.notna(v) else None
        elif isinstance(v, float):
            out[k] = None if pd.isna(v) else v
        elif v is None:
            out[k] = None
        else:
            out[k] = v
    return out
