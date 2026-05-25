# 急診分級 AI 輔助 POC

> 期末專題：以 **Qwen2.5-7B-Instruct + RAG** 解決「醫療人員負擔不來」與「爭取救護時間」兩大急救痛點。

---

## 1. 系統概觀

```
┌────────────────────────────────────────────────────┐
│  Next.js 15 + React 19 + Tailwind  (port 7301)     │
│   ・案件列表 (P1/P2 篩選)                            │
│   ・案件詳情 + 三大 AI 模組                          │
└────────────────────────────────────────────────────┘
                    │
                    ▼  fetch
┌────────────────────────────────────────────────────┐
│  FastAPI + Python 3.10  (port 7302)                │
│   ・/api/cases               案件清單與詳情          │
│   ・/api/triage/{id}         AI 分級助手             │
│   ・/api/recommend/{id}      AI 醫院推薦解釋         │
│   ・/api/sbar                AI SBAR 通報摘要        │
└────────────────────────────────────────────────────┘
        │                          │
        ▼                          ▼
┌──────────────────┐    ┌──────────────────────────┐
│ Qwen2.5-7B 4bit  │    │ RAG (in-memory)          │
│  (mlx-lm, HF)    │    │  ・5 個 protocol 規則    │
│  Apple Silicon   │    │  ・~200 件歷史案例摘要   │
│  原生加速        │    │  bge-small-zh embedding  │
│                  │    │  numpy cosine similarity │
└──────────────────┘    └──────────────────────────┘
                              ▲
                              │
                  老師資料集 (14 張 CSV)
                  ../期末專題參考資料集/
```

**冷門 port** 7301 / 7302 避開 Docker 與常見服務的預設 port。

---

## 2. 安裝與啟動

### 2.1 後端 (FastAPI + RAG)

```bash
cd poc/backend
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 7302 --reload
```

**首次啟動** 會自動從 HuggingFace Hub 下載 `BAAI/bge-small-zh-v1.5` (~100MB) 並建立 RAG 索引（~30 秒），結果 cache 在 `backend/cache/`，第二次秒開。

### 2.2 前端 (Next.js)

```bash
cd poc/frontend
npm install
npm run dev
```

開啟瀏覽器：**http://localhost:7301**

### 2.3 模型安裝（可選 — 都有 fallback 不裝也能 demo）

POC 在模型未載入時會自動 fallback，**UI 流程一定能跑**。要看到真的 AI 輸出：

```bash
cd poc/backend

# 文字分級 — Qwen2.5-7B-Instruct-4bit (~5GB)
.venv/bin/pip install mlx-lm

# 拍照分析 — Qwen2-VL-7B-Instruct-4bit (~5GB)
.venv/bin/pip install mlx-vlm

# 語音轉文字 — whisper-large-v3-turbo (~1.5GB)
.venv/bin/pip install mlx-whisper
```

三個模型都是 HF Hub 公開、不需登入，第一次呼叫對應 endpoint 時自動下載到 `~/.cache/huggingface/`。

健康檢查：
```bash
curl http://127.0.0.1:7302/api/health
# {"ok":true,"llm_available":true,"vision_available":true,"audio_available":true,...}
```

可改用其他模型：
```bash
export QWEN_MODEL="mlx-community/Qwen2.5-7B-Instruct-4bit"
export QWEN_VL_MODEL="mlx-community/Qwen2-VL-7B-Instruct-4bit"
export WHISPER_MODEL="mlx-community/whisper-large-v3-turbo"
```

---

### 2.4 兩種輸入方式

**A. 從現有案件分析**（首頁 → 點 case_id → 看 AI 三模組）
- 適合展示 RAG 檢索能力、SBAR 通報、醫院推薦解釋

**B. 拍照 / 語音 直接分級**（首頁 → 📥 拍照/語音輸入 → 上傳）
- 📸 一張照片 → Qwen2-VL 看圖 → 場景描述 + 紅旗 + ESI 分級
- 🎤 一段語音 → Whisper 轉文字 → Qwen + RAG → 萃取資料 + 分級
- 適合展示 multimodal、現場零摩擦輸入

---

## 3. Demo 腳本（建議展示順序）

### 場景 1：敗血症 **`E0000001`**

> 痛點：發燒+血壓低+意識變差的非典型敗血症，分流護理師容易低估嚴重度。

1. 開 http://localhost:7301，看到全部 50 件案件，篩 `P1` 看高優先級
2. 點 `E0000001` 進詳情頁
3. 「**📈 救護車端生命徵象趨勢**」看到 SBP 從 112 → 92 持續下滑，HR 高
4. 按「**🩺 開始 AI 分級**」
   - 看 RAG 抓到 4 件同症狀的敗血症歷史案例（cosine 0.86+）
   - Qwen 輸出：ESI 1 / P1 / Sepsis Bundle，紅旗包含 qSOFA=2、HR 124、體溫 40.3、RR 35
5. 按「**🏥 產生 AI 解釋**」
   - 看推薦的 3 家醫院 + 自然語言解釋為什麼選北城醫學中心（ICU 6 床、距離 15.8 分）
6. 按「**📡 生成 SBAR**」
   - 看自動生成的 SBAR 通報訊息（給接收醫院的黑底綠字終端機畫面）

### 場景 2：STEMI **`E0001359`**

> 痛點：胸痛要不要 Code STEMI？救護車端 ECG 判讀 + 醫院端 PCI 量能要快速配對。

重點看：
- AI 自動判 P1 + Code STEMI
- RAG 抓到歷史 STEMI 案例
- 醫院推薦解釋會強調 PCI capable + 導管室可用

### 場景 3：到院前心跳停止 **`E0000002`**

> 痛點：OHCA 全部生命徵象都歸零，需要立刻啟動復甦團隊。

重點看：
- AI 分級紅旗會出現「心跳停止 HR=0」
- 啟動 OHCA Team
- SBAR 一行摘要直接告訴醫院「P1 OHCA, ETA X 分」

---

## 4. AI 模組設計細節

### 4.1 AI 分級助手 (`/api/triage/{id}`)

| 步驟 | 內容 |
|---|---|
| 1. RAG query | 以「疑似病症 + 主訴 + 生命徵象」為 query |
| 2. 檢索 | bge-small-zh embedding + cosine 找 top 4 |
| 3. Prompt | 把 5 個 protocol 與歷史案例摘要塞給 Qwen |
| 4. 輸出 | JSON: ESI 等級、優先級、啟動 protocol、紅旗、臨床推理 |
| 5. Fallback | 若 Qwen 未載入，走確定性規則引擎，依生命徵象判紅旗與 protocol |

### 4.2 AI 醫院推薦解釋 (`/api/recommend/{id}`)

- 從 `routing_recommendations` 取前 3 名醫院
- 查 `hospital_resource_snapshots` 取通報當下最近的資源快照
- Prompt 帶醫院能力、即時資源、距離、壅塞度
- Qwen 輸出 2-3 句自然語言解釋

### 4.3 AI SBAR 通報訊息 (`/api/sbar`)

- 帶上分級結果（紅旗 + 應啟動 protocol）
- Qwen 輸出 SBAR 四段 + 一行摘要
- 仿照 `alerts.message_summary` 的格式

---

## 5. 檔案結構

```
poc/
├── README.md                       本檔
├── backend/
│   ├── requirements.txt
│   ├── main.py                     FastAPI endpoints
│   ├── data.py                     CSV 載入 + 案件查詢
│   ├── rag.py                      bge embedding + cosine 檢索
│   ├── llm.py                      Qwen 7B 包裝 (mlx-lm)
│   ├── prompts.py                  Prompt 模板 + fallback 規則引擎
│   └── cache/                      RAG embedding cache
└── frontend/
    ├── package.json
    ├── next.config.ts              port 7302 rewrite
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                案件列表
    │   ├── cases/[id]/page.tsx     案件詳情 + AI 模組
    │   ├── about/page.tsx
    │   └── globals.css
    ├── components/
    │   ├── VitalsChart.tsx         生命徵象 recharts
    │   └── AIPanel.tsx             AI 三模組 client component
    └── lib/
        └── api.ts                  fetch 封裝
```

---

## 6. 學術說明：對映課程概念

| 課程概念 | 在本 POC 的對映 |
|---|---|
| 生成式 AI 系統 | Qwen2.5-7B-Instruct 4-bit (HF 公開模型) |
| RAG 檢索 | bge-small-zh embedding + cosine similarity |
| 知識庫設計 | 結構化的 5 個 protocol + 結構化歷史案例摘要 |
| Prompt Engineering | 三組任務型 prompt，固定 JSON 輸出格式 |
| 系統可靠性 | 規則引擎 fallback，Qwen 不可用時不停服 |
| 評估面向 | 與真實 outcome 對照（door-to-balloon、達標率）可作為後續評估 |

---

## 7. 已知限制

- 老師的資料是合成資料，不代表真實臨床情境。
- POC 沒有做使用者驗證、權限、稽核日誌——僅作為 demo。
- RAG corpus 只取 ~200 件歷史案例，正式系統應用全量並定期重建。
- Qwen 7B 4-bit 在 M4 16GB 上推論速度約 20-30 tok/s，第一次 demo 需預先 warm up。
