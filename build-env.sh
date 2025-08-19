#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./build_env.sh 3.13
#   ./build_env.sh py313
#   ./build_env.sh 313
#
# Derives:
#   - Python version (e.g., 3.13)
#   - Tag digits (e.g., 313)
#   - Conda env name: opensesame-py{digits} (e.g., opensesame-py313)

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <python-version-or-tag>"
  echo "Examples: $0 3.13 | $0 py313 | $0 313"
  exit 1
fi

ARG="$1"
digits=""
version=""

if [[ "$ARG" =~ ^[Pp][Yy]([0-9]{2,3})$ ]]; then
  # py313 or py310
  digits="${BASH_REMATCH[1]}"
  major="${digits:0:1}"
  minor="${digits:1}"
  version="${major}.${minor}"
elif [[ "$ARG" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
  # 3.13 or 3.10
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  version="${major}.${minor}"
  digits="${major}${minor}"
elif [[ "$ARG" =~ ^([0-9]{2,3})$ ]]; then
  # 313 or 310
  digits="${BASH_REMATCH[1]}"
  major="${digits:0:1}"
  minor="${digits:1}"
  version="${major}.${minor}"
else
  echo "Error: argument must look like 3.13, py313, or 313" >&2
  exit 1
fi

ENV_NAME="opensesame-py${digits}"

echo "Config:"
echo "  Python version: ${version}"
echo "  Tag digits:     ${digits}"
echo "  Conda env name: ${ENV_NAME}"
echo

# Source conda initialization
if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
else
  echo "Could not find conda.sh at \$HOME/miniconda3/etc/profile.d/conda.sh" >&2
  echo "Make sure Miniconda is installed there or update the path in this script." >&2
  exit 1
fi

# Remove existing env if present (ignore error if it doesn't exist)
conda env remove -n "${ENV_NAME}" -y || true

# Create and populate environment
conda create -n "${ENV_NAME}" "python=${version}" -y
conda activate "${ENV_NAME}"

python -m pip install -r requirements.txt
python -m pip install psychopy --ignore-requires-python --no-deps

conda deactivate