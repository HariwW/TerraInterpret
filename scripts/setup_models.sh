#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${TERRAINTERPRET_MODEL_BOOTSTRAP_PYTHON:-python3.12}"
MODEL_VENV="${PROJECT_ROOT}/.venv-models"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python 3.12 is required for the isolated model runtime." >&2
  exit 1
fi

"${PYTHON_BIN}" -m venv "${MODEL_VENV}"
"${MODEL_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel
"${MODEL_VENV}/bin/python" -m pip install \
  "torch==2.14.0" \
  "torchvision==0.29.0" \
  "ftfy==6.3.1" \
  "regex==2026.9.3" \
  "ultralytics==8.4.138" \
  "mmengine==0.10.7" \
  "mmcv-lite==2.1.0" \
  "mmsegmentation==1.2.2"

if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Portable models installed. Open-CD Changer remains disabled on macOS because it requires compiled MMCV operators."
else
  echo "Portable models installed. For Open-CD, install a CUDA-matched mmcv build and Open-CD 1.1 in this environment."
fi

echo "Model runtime: ${MODEL_VENV}/bin/python"
