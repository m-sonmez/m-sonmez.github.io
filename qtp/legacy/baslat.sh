#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

pick_python() {
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
        echo "$cand"
        return 0
      fi
    fi
  done
  return 1
}

if ! PY_CMD="$(pick_python)"; then
  echo "[HATA] Python 3.9+ bulunamadı. Lütfen Python 3 yükleyin." >&2
  exit 1
fi

MODE="${1:-web}"
PORT="${QTP_PORT:-8765}"

case "$MODE" in
  gui)
    echo "[QTP] Python Masaüstü Arayüzü başlatılıyor..."
    "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --install-qtp >/dev/null 2>&1 || true
    "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --start-qtp >/dev/null 2>&1 || true
    exec "$PY_CMD" "$SCRIPT_DIR/qtp_manager.py"
    ;;
  qtp)
    "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --install-qtp
    exec "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --start-qtp
    ;;
  check|status)
    exec "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --status
    ;;
  sync)
    exec "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --sync
    ;;
  web|*)
    echo "=============================================================="
    echo " QTP & Hazır Cevaplar Full-Stack Paneli Başlatılıyor"
    echo " Adres: http://127.0.0.1:${PORT}/"
    echo " Kullanım: ./baslat.sh [web|gui|qtp|check|sync]"
    echo "=============================================================="
    exec "$PY_CMD" "$SCRIPT_DIR/qtp_server.py" --work-dir "$WORK_DIR" --port "$PORT" --ensure-qtp --open-browser
    ;;
esac
