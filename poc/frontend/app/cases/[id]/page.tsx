import Link from "next/link";
import { api, CaseDetail } from "@/lib/api";
import VitalsChart from "@/components/VitalsChart";
import { AIClient } from "@/components/AIPanel";

export const dynamic = "force-dynamic";

function dt(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleString("zh-TW", { hour12: false });
}

function nv(v: any) {
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

async function loadCase(id: string): Promise<CaseDetail | null> {
  try {
    return await api.getCase(id);
  } catch {
    return null;
  }
}

export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const detail = await loadCase(id);

  if (!detail) {
    return (
      <div className="card text-center text-slate-600">
        <p>找不到案件 <code>{id}</code>，或後端未啟動。</p>
        <Link href="/" className="text-blue-600 hover:underline">← 回案件列表</Link>
      </div>
    );
  }

  const c = detail.case;
  const p = detail.patient;
  const h = detail.hospital;

  return (
    <div className="space-y-5">
      <header className="flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-blue-600 hover:underline">
            ← 回案件列表
          </Link>
          <h1 className="text-xl font-bold mt-1">
            <span className="font-mono">{c.case_id}</span>
            <span className="ml-3 text-base text-slate-600">
              {c.suspected_condition}
            </span>
          </h1>
        </div>
        <div className="flex gap-1.5">
          <span className={`tag ${c.priority === "P1" ? "tag-p1" : "tag-p2"}`}>
            {c.priority}
          </span>
          <span
            className={`tag ${
              c.esi_level === 1
                ? "tag-esi-1"
                : c.esi_level === 2
                ? "tag-esi-2"
                : "tag-esi-3"
            }`}
          >
            ESI {c.esi_level}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* 病患資料 */}
        <section className="card">
          <h3 className="font-semibold text-slate-900 mb-3">👤 病患資料</h3>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <Dt label="性別 / 年齡">
              {nv(p.sex)} / {nv(p.age)} 歲（{nv(p.age_group)}）
            </Dt>
            <Dt label="主訴">{nv(c.chief_complaint)}</Dt>
            <Dt label="高血壓">{p.has_hypertension ? "✓" : "—"}</Dt>
            <Dt label="糖尿病">{p.has_diabetes ? "✓" : "—"}</Dt>
            <Dt label="心血管病史">{p.has_cvd_history ? "✓" : "—"}</Dt>
            <Dt label="抗凝血劑">{p.has_anticoagulant ? "✓" : "—"}</Dt>
          </dl>

          <h3 className="font-semibold text-slate-900 mt-5 mb-3">⏱ 時間軸</h3>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <Dt label="派遣">{dt(c.dispatch_time)}</Dt>
            <Dt label="接觸病患">{dt(c.patient_contact_time)}</Dt>
            <Dt label="離開現場">{dt(c.depart_scene_time)}</Dt>
            <Dt label="通報建立">{dt(c.alert_created_time)}</Dt>
            <Dt label="預估到院">{dt(c.eta_time)}</Dt>
            <Dt label="實際到院">{dt(c.arrival_hospital_time)}</Dt>
          </dl>
        </section>

        {/* 生命徵象 */}
        <section className="card">
          <h3 className="font-semibold text-slate-900 mb-3">📈 救護車端生命徵象趨勢</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-xs mb-3">
            <Stat label="SBP" v={c.initial_sbp} u="mmHg" />
            <Stat label="HR" v={c.initial_hr} u="/min" />
            <Stat label="RR" v={c.initial_rr} u="/min" />
            <Stat label="SpO2" v={c.initial_spo2} u="%" />
            <Stat label="體溫" v={c.initial_temp_c} u="°C" />
            <Stat label="GCS" v={c.initial_gcs} u="" />
          </div>
          <VitalsChart vitals={detail.vitals} />
          <div className="mt-3 text-xs text-slate-500 grid grid-cols-2 md:grid-cols-4 gap-1">
            <span>qSOFA: {nv(c.qsofa)}</span>
            <span>Lactate: {nv(c.lactate_mmol_l)}</span>
            <span>NIHSS: {nv(c.nihss)}</span>
            <span>FAST+: {c.fast_positive === 1 ? "✓" : "—"}</span>
            <span>ECG STEMI: {c.ecg_stemi === 1 ? "✓" : "—"}</span>
            <span>ROSC: {c.prehospital_rosc === 1 ? "✓" : "—"}</span>
            <span>外傷機制: {nv(c.trauma_mechanism)}</span>
          </div>
        </section>
      </div>

      {/* AI 三部曲 */}
      <AIClient caseDetail={detail} />

      {/* 收治醫院實際資料 */}
      <section className="card">
        <h3 className="font-semibold text-slate-900 mb-3">
          🏨 實際收治醫院：{h?.hospital_name || "—"}
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-y-2 text-sm">
          <Dt label="層級">{nv(h?.hospital_level)}</Dt>
          <Dt label="地區">{nv(h?.region)}</Dt>
          <Dt label="PCI 能力">{h?.pci_capable === 1 ? "✓" : "—"}</Dt>
          <Dt label="中風中心">{nv(h?.stroke_center_level)}</Dt>
          <Dt label="外傷中心">L{nv(h?.trauma_center_level)}</Dt>
          <Dt label="CT">{h?.has_ct === 1 ? "✓" : "—"}</Dt>
          <Dt label="導管室">{h?.has_cath_lab === 1 ? "✓" : "—"}</Dt>
          <Dt label="神經介入">{h?.has_neuro_intervention === 1 ? "✓" : "—"}</Dt>
        </div>

        {detail.resource_orders.length > 0 && (
          <>
            <h4 className="font-semibold text-sm mt-4 mb-2">院內資源預約</h4>
            <table className="w-full text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-2 py-1">資源</th>
                  <th className="text-left px-2 py-1">狀態</th>
                  <th className="text-left px-2 py-1">請求</th>
                  <th className="text-left px-2 py-1">確認</th>
                  <th className="text-left px-2 py-1">耗時</th>
                </tr>
              </thead>
              <tbody>
                {detail.resource_orders.map((o, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-2 py-1 font-mono">{o.resource_type}</td>
                    <td className="px-2 py-1">
                      {o.request_status === "confirmed" ? (
                        <span className="text-green-700">✓ 已確認</span>
                      ) : (
                        <span className="text-amber-700">⚠ {o.request_status}</span>
                      )}
                    </td>
                    <td className="px-2 py-1">{dt(o.requested_time)}</td>
                    <td className="px-2 py-1">{dt(o.confirmed_time)}</td>
                    <td className="px-2 py-1">{nv(o.confirm_minutes)} 分</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  );
}

function Dt({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900">{children}</dd>
    </div>
  );
}

function Stat({ label, v, u }: { label: string; v: any; u: string }) {
  return (
    <div className="bg-slate-50 rounded p-2 text-center">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className="font-bold text-slate-900">
        {v ?? "—"}
        <span className="text-[10px] font-normal ml-0.5">{u}</span>
      </div>
    </div>
  );
}
