#!/usr/bin/env bash
set -euo pipefail
set -o errtrace

trap 'echo "[pre-push] ERROR at line ${LINENO}: ${BASH_COMMAND}" >&2' ERR

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[pre-push] repo: $ROOT_DIR"

UNAME_S="$(uname -s || true)"

is_wsl() {
  grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null
}

select_venv_dir() {
  if [ -n "${SOCIAL_BOOSTER_TEST_VENV:-}" ]; then
    echo "$SOCIAL_BOOSTER_TEST_VENV"
    return 0
  fi

  case "$UNAME_S" in
    MINGW*|MSYS*|CYGWIN*)
      echo "$ROOT_DIR/.venv"
      ;;
    *)
      if is_wsl; then
        echo "$ROOT_DIR/.venv-wsl"
      else
        echo "$ROOT_DIR/.venv"
      fi
      ;;
  esac
}

resolve_venv_python() {
  case "$UNAME_S" in
    MINGW*|MSYS*|CYGWIN*)
      echo "$VENV_DIR/Scripts/python.exe"
      ;;
    *)
      echo "$VENV_DIR/bin/python"
      ;;
  esac
}

is_venv_python_healthy() {
  local venv_py="$1"
  [ -f "$venv_py" ] || return 1
  "$venv_py" -c "import sys; print(sys.executable)" >/dev/null 2>&1
}

bootstrap_venv() {
  local venv_py
  venv_py="$(resolve_venv_python)"
  if is_venv_python_healthy "$venv_py"; then
    echo "$venv_py"
    return 0
  fi

  if [ -e "$venv_py" ]; then
    echo "[pre-push] WARN: existing venv is invalid; recreating: $VENV_DIR" >&2
    rm -rf "$VENV_DIR"
  fi

  echo "[pre-push] INFO: creating project venv at $VENV_DIR ..." >&2
  case "$UNAME_S" in
    MINGW*|MSYS*|CYGWIN*)
      # CRITICAL: Git Bash may resolve python3 to MSYS Python, which can create a broken Windows venv.
      if command -v py.exe >/dev/null 2>&1; then
        py.exe -3 -m venv "$VENV_DIR"
      elif [ -x "/c/Windows/py.exe" ]; then
        /c/Windows/py.exe -3 -m venv "$VENV_DIR"
      elif command -v python.exe >/dev/null 2>&1; then
        python.exe -m venv "$VENV_DIR"
      elif command -v py >/dev/null 2>&1; then
        py -3 -m venv "$VENV_DIR"
      else
        echo "[pre-push] ERROR: no Windows Python launcher found (py.exe/python.exe)." >&2
        exit 1
      fi
      ;;
    *)
      if command -v python3 >/dev/null 2>&1; then
        python3 -m venv "$VENV_DIR"
      elif command -v python >/dev/null 2>&1; then
        python -m venv "$VENV_DIR"
      else
        echo "[pre-push] ERROR: no bootstrap Python found (python3/python)." >&2
        exit 1
      fi
      ;;
  esac

  if ! is_venv_python_healthy "$venv_py"; then
    echo "[pre-push] ERROR: failed to initialize project venv: $VENV_DIR" >&2
    exit 1
  fi
  echo "$venv_py"
}

pip_install_or_fail() {
  local why="$1"
  shift
  if "$VENV_PY" -m pip install "$@"; then
    return 0
  fi
  echo "[pre-push] ERROR: failed to install dependency ($why): $*" >&2
  exit 1
}

VENV_DIR="$(select_venv_dir)"
VENV_PY="$(bootstrap_venv)"
echo "[pre-push] python: $VENV_PY"

if [ -f "scripts/requirements.txt" ]; then
  echo "[pre-push] ensuring Python requirements from scripts/requirements.txt"
  pip_install_or_fail "required by repo validation" -r scripts/requirements.txt
fi

echo "[pre-push] running repo validation gate"
"$VENV_PY" scripts/validate_repo.py

echo "[pre-push] PASS"
