"use client";

import { useRef, useState } from "react";

type Mode = "photo" | "voice";

interface VisionResult {
  scene_description: string;
  visible_red_flags: string[];
  esi_level: number;
  priority: string;
  suspected_condition: string;
  activation: string;
  next_steps: string[];
  confidence: string;
  reasoning: string;
  _source?: string;
  _note?: string;
}

interface VisionResponse {
  image_id: string;
  filename: string;
  size_bytes: number;
  result: VisionResult;
  source: string;
}

interface VoiceResponse {
  audio_id: string;
  filename: string;
  size_bytes: number;
  transcript: string;
  asr: { _source?: string; _note?: string; language?: string };
  triage: {
    extracted: { age: number | null; sex: string | null; chief_complaint: string; suspected_condition: string };
    esi_level: number;
    priority: string;
    activation: string;
    red_flags: string[];
    reasoning: string;
    _source?: string;
  };
  retrieved: { id: string; kind: string; text: string; score: number }[];
  source: string;
}

export default function IntakePage() {
  const [mode, setMode] = useState<Mode>("photo");
  return (
    <div className="space-y-5">
      <header className="card">
        <h1 className="text-lg font-semibold">📥 現場輸入 — 一鍵上傳，AI 自動分級</h1>
        <p className="text-sm text-slate-500 mt-1">
          上傳一張照片或一段語音，系統會直接回傳病患狀態與分級建議。不需要事先建檔。
        </p>
        <div className="mt-4 flex gap-2">
          <TabButton active={mode === "photo"} onClick={() => setMode("photo")}>
            📸 照片
          </TabButton>
          <TabButton active={mode === "voice"} onClick={() => setMode("voice")}>
            🎤 語音
          </TabButton>
        </div>
      </header>

      {mode === "photo" ? <PhotoTab /> : <VoiceTab />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium border ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-slate-600 border-slate-200 hover:border-blue-300"
      }`}
    >
      {children}
    </button>
  );
}

// ============================================================ 照片
function PhotoTab() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<VisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handlePick = (f: File | null) => {
    setFile(f);
    setResult(null);
    setErr(null);
    if (f) {
      const url = URL.createObjectURL(f);
      setPreview(url);
    } else {
      setPreview(null);
    }
  };

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setErr(null);
    const fd = new FormData();
    fd.append("image", file);
    try {
      const res = await fetch("/api/vision-triage", { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      setResult(await res.json());
    } catch (e: any) {
      setErr(e?.message || "上傳失敗");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section className="card">
        <h3 className="font-semibold mb-3">1. 選擇照片</h3>
        <label
          className="block border-2 border-dashed border-slate-300 rounded-lg p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/50"
        >
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => handlePick(e.target.files?.[0] ?? null)}
          />
          <div className="text-4xl mb-2">📷</div>
          <div className="text-sm text-slate-600">點此選擇 / 拍攝照片</div>
          <div className="text-xs text-slate-400 mt-1">支援 JPG / PNG / WebP</div>
        </label>

        {preview && (
          <div className="mt-4">
            <img
              src={preview}
              alt="preview"
              className="w-full max-h-80 object-contain bg-slate-50 rounded border border-slate-200"
            />
            <div className="text-xs text-slate-500 mt-1">
              {file?.name} · {(file?.size ?? 0 / 1024).toFixed(0)} bytes
            </div>
          </div>
        )}

        <button
          onClick={submit}
          disabled={!file || loading}
          className="btn btn-primary w-full mt-4"
        >
          {loading ? <span className="spinner mr-2 align-middle" /> : null}
          {loading ? "Qwen2-VL 分析中..." : "🩺 開始分析"}
        </button>

        {err && <div className="mt-3 text-sm text-red-600">{err}</div>}
      </section>

      <section className="card">
        <h3 className="font-semibold mb-3">2. AI 場景分析結果</h3>
        {!result ? (
          <p className="text-sm text-slate-400">上傳照片後，這裡會顯示 Qwen2-VL 的分析。</p>
        ) : (
          <VisionResultView r={result} />
        )}
      </section>
    </div>
  );
}

function VisionResultView({ r }: { r: VisionResponse }) {
  const v = r.result;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <span
          className={`tag ${
            v.esi_level === 1 ? "tag-esi-1" : v.esi_level === 2 ? "tag-esi-2" : "tag-esi-3"
          }`}
        >
          ESI {v.esi_level}
        </span>
        <span className={`tag ${v.priority === "P1" ? "tag-p1" : "tag-p2"}`}>
          {v.priority}
        </span>
        <span className="tag bg-violet-100 text-violet-700 border border-violet-200">
          {v.suspected_condition}
        </span>
        <span className="tag bg-slate-100 text-slate-700 border border-slate-200">
          信心: {v.confidence}
        </span>
        <SourceBadge source={v._source || r.source} />
      </div>

      {v._note && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
          ℹ️ {v._note}
        </div>
      )}

      <Block label="🖼 場景描述">{v.scene_description}</Block>

      {v.visible_red_flags.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-slate-600">🚩 可見紅旗</div>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {v.visible_red_flags.map((rf, i) => (
              <li
                key={i}
                className="px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 text-xs"
              >
                {rf}
              </li>
            ))}
          </ul>
        </div>
      )}

      {v.activation !== "無" && (
        <Block label="🚨 建議啟動">
          <span className="font-semibold text-violet-700">{v.activation}</span>
        </Block>
      )}

      {v.next_steps.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-slate-600">📋 建議下一步處置</div>
          <ol className="mt-1 list-decimal list-inside text-sm space-y-0.5">
            {v.next_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </div>
      )}

      <Block label="📝 AI 推理">{v.reasoning}</Block>
    </div>
  );
}

// ============================================================ 語音
function VoiceTab() {
  const [file, setFile] = useState<File | Blob | null>(null);
  const [audioURL, setAudioURL] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [result, setResult] = useState<VoiceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRec = async () => {
    setErr(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      recRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setFile(blob);
        setAudioURL(URL.createObjectURL(blob));
        stream.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      setRecording(true);
    } catch (e: any) {
      setErr("無法存取麥克風: " + (e?.message || ""));
    }
  };

  const stopRec = () => {
    recRef.current?.stop();
    setRecording(false);
  };

  const handlePick = (f: File | null) => {
    if (!f) return;
    setFile(f);
    setAudioURL(URL.createObjectURL(f));
    setResult(null);
    setErr(null);
  };

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setErr(null);
    const fd = new FormData();
    fd.append("audio", file, "voice.webm");
    try {
      const res = await fetch("/api/voice-triage", { method: "POST", body: fd });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      setResult(await res.json());
    } catch (e: any) {
      setErr(e?.message || "上傳失敗");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <section className="card">
        <h3 className="font-semibold mb-3">1. 錄音或上傳音檔</h3>

        <div className="flex gap-2 mb-4">
          {!recording ? (
            <button onClick={startRec} className="btn btn-primary flex-1">
              🎤 開始錄音
            </button>
          ) : (
            <button onClick={stopRec} className="btn bg-red-600 text-white hover:bg-red-700 flex-1">
              ⏹ 停止錄音
            </button>
          )}
        </div>

        <label className="block border-2 border-dashed border-slate-300 rounded-lg p-4 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/50">
          <input
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={(e) => handlePick(e.target.files?.[0] ?? null)}
          />
          <div className="text-sm text-slate-600">或上傳音檔 (mp3 / wav / m4a / webm)</div>
        </label>

        {audioURL && (
          <div className="mt-4">
            <audio src={audioURL} controls className="w-full" />
          </div>
        )}

        <button
          onClick={submit}
          disabled={!file || loading || recording}
          className="btn btn-primary w-full mt-4"
        >
          {loading ? <span className="spinner mr-2 align-middle" /> : null}
          {loading ? "Whisper 轉錄 + Qwen 分析中..." : "🩺 開始分析"}
        </button>

        {err && <div className="mt-3 text-sm text-red-600">{err}</div>}
      </section>

      <section className="card">
        <h3 className="font-semibold mb-3">2. AI 語音轉錄 + 分級</h3>
        {!result ? (
          <p className="text-sm text-slate-400">錄音或上傳後，這裡會顯示 Whisper 轉錄與 Qwen 分級。</p>
        ) : (
          <VoiceResultView r={result} />
        )}
      </section>
    </div>
  );
}

function VoiceResultView({ r }: { r: VoiceResponse }) {
  const t = r.triage;
  const e = t.extracted;
  return (
    <div className="space-y-3">
      <Block label="🗣 Whisper 轉錄">
        <div className="text-sm leading-relaxed">{r.transcript || "（無內容）"}</div>
        {r.asr._note && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mt-1">
            ℹ️ {r.asr._note}
          </div>
        )}
      </Block>

      <Block label="🧬 萃取出的病患資料">
        <div className="text-sm grid grid-cols-2 gap-x-3">
          <span>年齡: {e.age ?? "—"}</span>
          <span>性別: {e.sex ?? "—"}</span>
          <span className="col-span-2">主訴: {e.chief_complaint || "—"}</span>
          <span className="col-span-2">疑似病症: {e.suspected_condition}</span>
        </div>
      </Block>

      <div className="flex flex-wrap gap-2 items-center">
        <span
          className={`tag ${
            t.esi_level === 1 ? "tag-esi-1" : t.esi_level === 2 ? "tag-esi-2" : "tag-esi-3"
          }`}
        >
          ESI {t.esi_level}
        </span>
        <span className={`tag ${t.priority === "P1" ? "tag-p1" : "tag-p2"}`}>{t.priority}</span>
        {t.activation !== "無" && (
          <span className="tag bg-violet-100 text-violet-700 border border-violet-200">
            {t.activation}
          </span>
        )}
        <SourceBadge source={t._source || r.source} />
      </div>

      {t.red_flags.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-slate-600">🚩 紅旗</div>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {t.red_flags.map((rf, i) => (
              <li
                key={i}
                className="px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200 text-xs"
              >
                {rf}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Block label="📝 推理">{t.reasoning}</Block>

      {r.retrieved.length > 0 && (
        <details className="text-xs text-slate-600">
          <summary className="cursor-pointer hover:text-slate-900">
            📚 RAG 檢索結果 ({r.retrieved.length} 筆)
          </summary>
          <div className="mt-2 space-y-2">
            {r.retrieved.map((d, i) => (
              <div
                key={i}
                className="p-2 bg-slate-50 rounded border border-slate-200"
              >
                <div className="flex justify-between mb-1">
                  <span className="font-mono text-[10px]">{d.id}</span>
                  <span className="text-[10px]">{d.score.toFixed(3)}</span>
                </div>
                <pre className="whitespace-pre-wrap text-[11px] font-sans">{d.text}</pre>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold text-slate-600">{label}</div>
      <div className="text-sm text-slate-800 mt-1 leading-relaxed">{children}</div>
    </div>
  );
}

function SourceBadge({ source }: { source: string }) {
  if (source.startsWith("qwen2-vl"))
    return <span className="tag tag-ai">🤖 Qwen2-VL-7B</span>;
  if (source.startsWith("qwen"))
    return <span className="tag tag-ai">🤖 Qwen 7B + RAG</span>;
  if (source.startsWith("mlx-whisper"))
    return <span className="tag tag-ai">🎤 Whisper</span>;
  return (
    <span className="tag bg-slate-100 text-slate-600 border border-slate-200">
      📐 fallback (模型未載入)
    </span>
  );
}
