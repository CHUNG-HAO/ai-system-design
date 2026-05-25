#!/usr/bin/env bash
# 一鍵啟動 backend + frontend
# 用法：./start.sh

set -e
cd "$(dirname "$0")"

echo "==> 啟動 backend (FastAPI on :7302)"
if [ ! -d backend/.venv ]; then
  echo "  ! backend/.venv 不存在，先建立"
  /opt/homebrew/bin/python3.10 -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements.txt
fi

(cd backend && .venv/bin/uvicorn main:app --port 7302 --host 127.0.0.1) &
BACKEND_PID=$!
echo "  backend pid=$BACKEND_PID"

echo "==> 啟動 frontend (Next.js on :7301)"
if [ ! -d frontend/node_modules ]; then
  echo "  ! frontend/node_modules 不存在，先安裝"
  (cd frontend && npm install)
fi

(cd frontend && npm run dev) &
FRONTEND_PID=$!
echo "  frontend pid=$FRONTEND_PID"

trap "echo '==> 收尾'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM

echo ""
echo "============================================================"
echo "  Backend:  http://127.0.0.1:7302/api/health"
echo "  Frontend: http://127.0.0.1:7301"
echo "  Demo:     http://127.0.0.1:7301/cases/E0000001"
echo "============================================================"
echo "Ctrl+C 結束"
wait
