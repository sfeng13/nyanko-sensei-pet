#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if ! command -v python3 >/dev/null; then
  echo '请先安装 python3、python3-venv、python3-pip 和 libxcb-cursor0。' >&2
  exit 1
fi
# Never clear an existing virtual environment or modify the whale environment.
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-ubuntu.txt
echo '安装完成。运行 bash start.sh；Codex 联动是可选的，见 docs/UBUNTU.md。'
