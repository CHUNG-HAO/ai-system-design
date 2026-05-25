import Link from "next/link";
import { api, CaseSummary } from "@/lib/api";

export const dynamic = "force-dynamic";

function priorityClass(p: string) {
  return p === "P1" ? "tag tag-p1" : "tag tag-p2";
}

function esiClass(level: number) {
  if (level === 1) return "tag tag-esi-1";
  if (level === 2) return "tag tag-esi-2";
  return "tag tag-esi-3";
}

function relTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("zh-TW", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function getCases(): Promise<CaseSummary[]> {
  try {
    const res = await api.listCases();
    return res.items;
  } catch (e) {
    return [];
  }
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ priority?: string; condition?: string }>;
}) {
  const sp = await searchParams;
  const list = await getCases();

  const filtered = list.filter((c) => {
    if (sp.priority && c.priority !== sp.priority) return false;
    if (sp.condition && c.suspected_condition !== sp.condition) return false;
    return true;
  });

  const conditions = Array.from(new Set(list.map((c) => c.suspected_condition))).sort();

  const summary = {
    total: list.length,
    p1: list.filter((c) => c.priority === "P1").length,
    p2: list.filter((c) => c.priority === "P2").length,
  };

  return (
    <div className="space-y-5">
      <section className="card bg-gradient-to-r from-blue-50 to-violet-50 border-blue-200">
        <h2 className="text-lg font-semibold text-blue-900">📥 拍照 / 語音直接分級</h2>
        <p className="text-sm text-blue-700 mt-1">
          上傳一張現場照片或一段語音，AI 直接回傳病患狀態與分級建議，不需事先建檔。
        </p>
        <Link href="/intake" className="btn btn-primary mt-3 inline-block">
          進入現場輸入 →
        </Link>
      </section>

      <section className="card">
        <h1 className="text-lg font-semibold">急救通報案件清單</h1>
        <p className="text-sm text-slate-500 mt-1">
          資料來源：老師提供的合成資料集（{summary.total} 件，P1 {summary.p1} · P2 {summary.p2}）。點任一件進入 AI 分級與通報摘要。
        </p>

        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <FilterChip label="全部" href="/" active={!sp.priority && !sp.condition} />
          <FilterChip label="P1" href="/?priority=P1" active={sp.priority === "P1"} />
          <FilterChip label="P2" href="/?priority=P2" active={sp.priority === "P2"} />
          <span className="text-slate-300">|</span>
          {conditions.map((c) => (
            <FilterChip
              key={c}
              label={c}
              href={`/?condition=${encodeURIComponent(c)}`}
              active={sp.condition === c}
            />
          ))}
        </div>
      </section>

      <section className="card overflow-hidden p-0">
        {list.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            無法連到後端。請先在另一個 terminal 啟動：
            <pre className="mt-2 text-xs bg-slate-100 p-2 rounded inline-block text-left">
              cd poc/backend{"\n"}.venv/bin/uvicorn main:app --port 7302
            </pre>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-600 uppercase">
              <tr>
                <th className="text-left px-4 py-2">案件代碼</th>
                <th className="text-left px-4 py-2">疑似病症</th>
                <th className="text-left px-4 py-2">分級</th>
                <th className="text-left px-4 py-2">病患</th>
                <th className="text-left px-4 py-2">主訴</th>
                <th className="text-left px-4 py-2">收治醫院</th>
                <th className="text-left px-4 py-2">通報時間</th>
                <th className="text-left px-4 py-2">ACK</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 30).map((c) => (
                <tr
                  key={c.case_id}
                  className="border-t border-slate-100 hover:bg-blue-50/30"
                >
                  <td className="px-4 py-2">
                    <Link
                      href={`/cases/${c.case_id}`}
                      className="font-mono text-blue-600 hover:underline"
                    >
                      {c.case_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{c.suspected_condition}</td>
                  <td className="px-4 py-2">
                    <span className={priorityClass(c.priority)}>{c.priority}</span>
                    <span className={`ml-1 ${esiClass(c.esi_level)}`}>ESI {c.esi_level}</span>
                  </td>
                  <td className="px-4 py-2">
                    {c.age ? `${c.age}` : "—"} {c.sex || ""}
                  </td>
                  <td className="px-4 py-2 max-w-xs truncate text-slate-600">
                    {c.chief_complaint || "—"}
                  </td>
                  <td className="px-4 py-2">{c.hospital_name || "—"}</td>
                  <td className="px-4 py-2 text-slate-500 text-xs">
                    {relTime(c.alert_created_time)}
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {c.ack_minutes !== null ? `${c.ack_minutes} 分` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <DemoHint />
    </div>
  );
}

function FilterChip({
  label,
  href,
  active,
}: {
  label: string;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`px-2 py-1 rounded border ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-slate-600 border-slate-200 hover:border-blue-300"
      }`}
    >
      {label}
    </Link>
  );
}

function DemoHint() {
  return (
    <section className="card bg-blue-50/50 border-blue-200">
      <div className="text-sm">
        <div className="font-semibold text-blue-900">建議 demo 案例</div>
        <ul className="mt-1 text-blue-800 list-disc list-inside space-y-0.5">
          <li>
            <Link href="/cases/E0000001" className="underline">E0000001</Link> — 敗血症 P1（紅旗：高燒+心跳過快+qSOFA=2）
          </li>
          <li>
            <Link href="/cases/E0000005" className="underline">E0000005</Link> — 重大外傷 P1
          </li>
          <li>
            <Link href="/cases/E0000020" className="underline">E0000020</Link> — 看看其他病症
          </li>
        </ul>
      </div>
    </section>
  );
}
