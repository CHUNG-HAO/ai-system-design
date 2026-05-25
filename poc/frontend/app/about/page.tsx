export default function AboutPage() {
  return (
    <div className="card prose prose-sm max-w-none">
      <h2 className="text-lg font-semibold">急診分級 AI 輔助 POC</h2>
      <p className="text-slate-600">
        本系統針對「醫療人員負擔不來」與「爭取救護時間」兩大痛點，整合到院前資料、醫院能力與即時資源，
        由 Qwen 7B + RAG 給急救人員與醫院端三項輔助決策。
      </p>

      <h3 className="font-semibold mt-4">三大 AI 模組</h3>
      <ol className="list-decimal list-inside space-y-1 text-slate-700">
        <li>
          <b>AI 分級助手</b> — 讀生命徵象 + 主訴 + RAG 檢索 5 個 protocol 與相似歷史案例，自動建議 ESI / 紅旗 / 啟動流程。
        </li>
        <li>
          <b>AI 醫院推薦解釋</b> — 用自然語言解釋為什麼推薦某家醫院（PCI / 中風中心 / ICU 床數 / 壅塞度...）。
        </li>
        <li>
          <b>AI SBAR 通報訊息</b> — 自動產生發送給接收醫院的 SBAR 通報，省去救護員打字時間。
        </li>
      </ol>

      <h3 className="font-semibold mt-4">技術棧</h3>
      <ul className="list-disc list-inside space-y-1 text-slate-700">
        <li>前端：Next.js 15 + React 19 + Tailwind</li>
        <li>後端：FastAPI + pandas</li>
        <li>LLM：Qwen2.5-7B-Instruct-4bit（從 HuggingFace Hub 公開取得，不需登入）</li>
        <li>Embedding：BAAI/bge-small-zh-v1.5（HuggingFace 公開）</li>
        <li>RAG：in-memory cosine similarity (numpy)</li>
        <li>推論引擎：mlx-lm（Apple Silicon 原生加速）</li>
      </ul>

      <h3 className="font-semibold mt-4">資料來源</h3>
      <p className="text-slate-700">
        老師提供的 <code>期末專題參考資料集</code>，14 張資料表、1366 件 EMS 案件、含到院前生命徵象、
        通報、推薦排序、院內資源、處置事件與結果 KPI。
      </p>
    </div>
  );
}
