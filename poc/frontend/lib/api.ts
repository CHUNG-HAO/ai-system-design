// Server-side (Next.js Node runtime) 直接打 backend；
// Client-side (瀏覽器) 走 Next rewrite 避開 CORS。
const BASE =
  typeof window === "undefined"
    ? process.env.BACKEND_URL || "http://127.0.0.1:7302"
    : "";

export interface CaseSummary {
  case_id: string;
  suspected_condition: string;
  priority: string;
  esi_level: number;
  chief_complaint: string | null;
  age: number | null;
  sex: string | null;
  hospital_name: string | null;
  hospital_id: string | null;
  alert_created_time: string | null;
  eta_time: string | null;
  arrival_hospital_time: string | null;
  ack_minutes: number | null;
}

export interface CaseListResponse {
  items: CaseSummary[];
  filters: {
    conditions: string[];
    priorities: string[];
  };
}

export interface Vital {
  vital_id: string;
  case_id: string;
  sequence_no: number;
  measured_at: string | null;
  phase: string;
  sbp: number | null;
  dbp: number | null;
  hr: number | null;
  rr: number | null;
  spo2: number | null;
  gcs: number | null;
  source: string;
}

export interface CaseDetail {
  case: Record<string, any>;
  patient: Record<string, any>;
  hospital: Record<string, any>;
  vitals: Vital[];
  recommendation: Record<string, any>;
  resource_orders: Record<string, any>[];
  alert: Record<string, any>;
  outcome: Record<string, any>;
  hospital_snapshot: Record<string, any> | null;
}

export interface TriageResult {
  case_id: string;
  triage: {
    esi_level: number;
    priority: string;
    activation: string;
    red_flags: string[];
    reasoning: string;
    _source?: string;
  };
  retrieved: { id: string; kind: string; text: string; meta: any; score: number }[];
  source: "qwen" | "fallback";
}

export interface RecommendResult {
  case_id: string;
  hospitals: {
    rank: number;
    hospital: Record<string, any>;
    score: number;
    travel_min: number;
    reason: string;
    snapshot: Record<string, any> | null;
    is_selected: boolean;
  }[];
  explanations: { rank: number; hospital_name: string; explanation: string }[];
  source: "qwen" | "fallback";
}

export interface SBARResult {
  case_id: string;
  hospital_name: string | null;
  sbar: {
    situation: string;
    background: string;
    assessment: string;
    recommendation: string;
    one_line_summary: string;
    _source?: string;
  };
  source: "qwen" | "fallback";
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} — ${await res.text()}`);
  }
  return res.json();
}

export const api = {
  listCases: (params?: { priority?: string; condition?: string }) => {
    const q = new URLSearchParams();
    if (params?.priority) q.set("priority", params.priority);
    if (params?.condition) q.set("condition", params.condition);
    return jsonFetch<CaseListResponse>(
      `/api/cases${q.toString() ? "?" + q.toString() : ""}`
    );
  },
  getCase: (caseId: string) => jsonFetch<CaseDetail>(`/api/cases/${caseId}`),
  triage: (caseId: string) =>
    jsonFetch<TriageResult>(`/api/triage/${caseId}`, { method: "POST" }),
  recommend: (caseId: string) =>
    jsonFetch<RecommendResult>(`/api/recommend/${caseId}`, { method: "POST" }),
  sbar: (caseId: string, triage?: any) =>
    jsonFetch<SBARResult>(`/api/sbar`, {
      method: "POST",
      body: JSON.stringify({ case_id: caseId, triage }),
    }),
  health: () => jsonFetch<{ ok: boolean; llm_available: boolean; n_cases: number }>(`/api/health`),
};
