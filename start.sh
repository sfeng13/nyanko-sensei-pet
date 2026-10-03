#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -n "${NYANKO_PYTHON:-}" ]]; then
  PYTHON_BIN="$NYANKO_PYTHON"
elif [[ -x .venv/bin/python ]]; then
  PYTHON_BIN="$PWD/.venv/bin/python"
elif [[ -x "$HOME/PET/dsh-pet-indesktop/.venv/bin/python" ]]; then
  PYTHON_BIN="$HOME/PET/dsh-pet-indesktop/.venv/bin/python"
else
  echo '找不到运行环境。请运行 bash install-ubuntu.sh，或设置 NYANKO_PYTHON。' >&2
  exit 1
fi
export PYTHONUTF8=1
exec "$PYTHON_BIN" launch.pyw "$@"
