import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "急診分級 POC | EMS Triage AI",
  description: "AI + RAG 急診分級輔助系統 — 減輕醫療人員負擔，爭取救護時間",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant">
      <body>
        <header className="bg-white border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-2xl">🚑</span>
              <div>
                <div className="font-semibold text-slate-900">急診分級 AI 輔助</div>
                <div className="text-xs text-slate-500">Qwen 7B + RAG · POC</div>
              </div>
            </Link>
            <nav className="flex gap-4 text-sm text-slate-600">
              <Link href="/" className="hover:text-blue-600">案件列表</Link>
              <Link href="/intake" className="hover:text-blue-600">📥 拍照/語音輸入</Link>
              <Link href="/about" className="hover:text-blue-600">關於</Link>
            </nav>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
