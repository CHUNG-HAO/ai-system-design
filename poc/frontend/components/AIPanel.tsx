"use client";

import { useState } from "react";
import { api, CaseDetail, TriageResult, RecommendResult, SBARResult } from "@/lib/api";

export function AIClient({ caseDetail }: { caseDetail: CaseDetail }) {
  const caseId = caseDetail.case.case_id;
  const [triage, setTriage] = useState<TriageResult | null>(null);
  const [recommend, setRecommend] = useState<RecommendResult | null>(null);
  const [sbar, setSbar] = useState<SBARResult | null>(null);
  const [loading, setLoading] = useState<{ [k: string]: boolean }>({});
  const [err, setErr] = useState<{ [k: string]: string | null }>({});

  const run = async (key: string, fn: () => Promise<any>, setter: (v: any) => void) => {
    setLoading((s) => ({ ...s, [key]: true }));
    setErr((s) => ({ ...s, [key]: null }));
    try {
      const v = await fn();
      setter(v);
    } catch (e: any) {
      setErr((s) => ({ ...s, [key]: e?.message || "錯誤" }));
    } finally {
      setLoading((s) => ({ ...s, [key]: false }));
    }
  };

  return (
    <div className="space-y-5">
      {/* Triage */}
      <TriageCard
        loading={loading.triage}
        err={err.triage}
        result={triage}
        onRun={() => run("triage", () => api.triage(caseId), setTriage)}
      />

      {/* Recommend */}
      <RecommendCard
        loading={loading.recommend}
        err={err.recommend}
        result={recommend}
        onRun={() => run("recommend", () => api.recommend(caseId), setRecommend)}
      />

      {/* SBAR */}
      <SBARCard
        loading={loading.sbar}
        err={err.sbar}
        result={sbar}
        hasTriage={!!triage}
        onRun={() => run("sbar", () => api.sbar(caseId, triage?.triage), setSbar)}
      />
    </div>
  );
}

// ============================================================
function SourceBadge({ source }: { source: "qwen" | "fallback" }) {
  return source === "qwen" ? (
    <span className="tag tag-ai">🤖 Qwen 7B + RAG</span>
  ) : (
    <span className="tag bg-slate-100 text-slate-600 border border-slate-200">
      📐 規則引擎 fallback
    </span>
  );
}

// ============================================================
function TriageCard({
  loading,
  err,
  result,
  onRun,
}: {
  loading: boolean;
  err: string | null;
  result: TriageResult | null;
  onRun: () => void;
}) {
  return (
    <section className="card">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-900">🩺 AI 分級助手</h3>
          <p className="text-xs text-slate-500">
            Qwen 讀生命徵象 + RAG 檢索 5 個 protocol 與相似歷史案例 → 輸出 ESI / 紅旗 / 應啟動流程
          </p>
        </div>
        <button onClick={onRun} disabled={loading} className="btn btn-primary">
          {loading ? <span className="spinner mr-2 align-middle" /> : null}
          {loading ? "AI 分析中..." : result ? "重新分析" : "開始 AI 分級"}
        </button>
      </header>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      {result && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center">
            <span
              className={`tag ${
                result.triage.esi_level === 1
                  ? "tag-esi-1"
                  : result.triage.esi_level === 2
                  ? "tag-esi-2"
                  : "tag-esi-3"
              }`}
            >
              ESI {result.triage.esi_level}
            </span>
            <span className={`tag ${result.triage.priority === "P1" ? "tag-p1" : "tag-p2"}`}>
              {result.triage.priority}
            </span>
            <span className="tag bg-violet-100 text-violet-700 border border-violet-200">
              應啟動：{result.triage.activation}
            </span>
            <SourceBadge source={result.source} />
          </div>

          {result.triage.red_flags?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-slate-600">🚩 紅旗</div>
              <ul className="mt-1 flex flex-wrap gap-1.5 text-sm">
                {result.triage.red_flags.map((r, i) => (
                  <li
                    key={i}
                    className="px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 text-xs"
                  >
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold text-slate-600">📝 臨床推理</div>
            <p className="text-sm text-slate-700 mt-1 leading-relaxed">
              {result.triage.reasoning}
            </p>
          </div>

          <details className="text-xs text-slate-600">
            <summary className="cursor-pointer hover:text-slate-900">
              📚 RAG 檢索結果（{result.retrieved.length} 筆）
            </summary>
            <div className="mt-2 space-y-2">
              {result.retrieved.map((r, i) => (
                <div
                  key={i}
                  className="p-2 bg-slate-50 rounded border border-slate-200"
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-mono text-[10px] text-slate-500">
                      {r.id}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      相似度 {r.score.toFixed(3)}
                    </span>
                  </div>
                  <pre className="whitespace-pre-wrap text-[11px] text-slate-700 font-sans">
                    {r.text}
                  </pre>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {!result && !loading && (
        <p className="text-sm text-slate-400">
          按下「開始 AI 分級」，系統會用 Qwen 7B + RAG 即時運算（首次載入模型需要等待）。
        </p>
      )}
    </section>
  );
}

// ============================================================
function RecommendCard({
  loading,
  err,
  result,
  onRun,
}: {
  loading: boolean;
  err: string | null;
  result: RecommendResult | null;
  onRun: () => void;
}) {
  return (
    <section className="card">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-900">🏥 AI 醫院推薦解釋</h3>
          <p className="text-xs text-slate-500">
            依醫院能力、即時資源快照與病症需求，給推薦排序+自然語言解釋
          </p>
        </div>
        <button onClick={onRun} disabled={loading} className="btn btn-primary">
          {loading ? <span className="spinner mr-2 align-middle" /> : null}
          {loading ? "AI 解釋中..." : result ? "重新解釋" : "產生 AI 解釋"}
        </button>
      </header>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      {result && (
        <div className="space-y-3">
          <SourceBadge source={result.source} />
          {result.hospitals.map((h) => {
            const expl = result.explanations.find((e) => e.rank === h.rank);
            return (
              <div
                key={h.rank}
                className={`p-3 rounded border ${
                  h.is_selected
                    ? "border-green-300 bg-green-50"
                    : "border-slate-200 bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-slate-900">第 {h.rank} 名</span>
                  <span className="font-semibold">{h.hospital.hospital_name}</span>
                  {h.is_selected && (
                    <span className="tag bg-green-200 text-green-800 border border-green-300">
                      ✓ 實際送往
                    </span>
                  )}
                  <span className="text-xs text-slate-500 ml-auto">
                    分數 {h.score.toFixed(1)} · 車程 {h.travel_min.toFixed(1)} 分
                  </span>
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">
                  {expl?.explanation || "—"}
                </p>
                {h.snapshot && (
                  <div className="mt-2 text-[11px] text-slate-500 grid grid-cols-3 md:grid-cols-6 gap-x-3 gap-y-1">
                    <span>ED 床: {h.snapshot.ed_beds_available}</span>
                    <span>ICU: {h.snapshot.icu_beds_available}</span>
                    <span>CT: {h.snapshot.ct_available}</span>
                    <span>導管: {h.snapshot.cath_lab_available}</span>
                    <span>外傷灣: {h.snapshot.trauma_bays_available}</span>
                    <span>壅塞: {h.snapshot.crowding_index}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!result && !loading && (
        <p className="text-sm text-slate-400">按下「產生 AI 解釋」看推薦理由。</p>
      )}
    </section>
  );
}

// ============================================================
function SBARCard({
  loading,
  err,
  result,
  hasTriage,
  onRun,
}: {
  loading: boolean;
  err: string | null;
  result: SBARResult | null;
  hasTriage: boolean;
  onRun: () => void;
}) {
  return (
    <section className="card">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-slate-900">📡 AI SBAR 通報訊息</h3>
          <p className="text-xs text-slate-500">
            自動生成發送給接收醫院的 SBAR 格式通報 — 省去救護員打字時間
          </p>
        </div>
        <button onClick={onRun} disabled={loading} className="btn btn-primary">
          {loading ? <span className="spinner mr-2 align-middle" /> : null}
          {loading ? "AI 生成中..." : result ? "重新生成" : "生成 SBAR"}
        </button>
      </header>

      {!hasTriage && (
        <div className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
          提示：建議先跑「AI 分級」再生成 SBAR，可帶入紅旗與啟動流程。
        </div>
      )}

      {err && <div className="text-red-600 text-sm">{err}</div>}

      {result && (
        <div className="space-y-3">
          <SourceBadge source={result.source} />
          <div className="bg-slate-900 text-green-200 font-mono text-xs p-4 rounded space-y-2">
            <div className="text-yellow-300 font-bold">
              📟 通報至：{result.hospital_name || "—"}
            </div>
            <div className="text-emerald-300">{result.sbar.one_line_summary}</div>
            <div className="border-t border-slate-700 pt-2 space-y-1">
              <div>
                <span className="text-yellow-300 font-bold">S </span>
                {result.sbar.situation}
              </div>
              <div>
                <span className="text-yellow-300 font-bold">B </span>
                {result.sbar.background}
              </div>
              <div>
                <span className="text-yellow-300 font-bold">A </span>
                {result.sbar.assessment}
              </div>
              <div>
                <span className="text-yellow-300 font-bold">R </span>
                {result.sbar.recommendation}
              </div>
            </div>
          </div>
        </div>
      )}

      {!result && !loading && (
        <p className="text-sm text-slate-400">按下「生成 SBAR」產生通報訊息。</p>
      )}
    </section>
  );
}
