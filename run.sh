#!/usr/bin/env bash
# Launch Spejari with the right interpreter and root privileges.
#   ./run.sh           choose CLI or GUI at start-up
#   ./run.sh --cli     terminal dashboard
#   ./run.sh --gui     desktop window (CustomTkinter)
cd "$(dirname "$(readlink -f "$0")")" || exit 1
PY=".venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

if [ "$(id -u)" -ne 0 ]; then
    want_cli=0
    for arg in "$@"; do [ "$arg" = "--cli" ] && want_cli=1; done
    # The GUI runs as root (scanning needs it): allow root to use this desktop session.
    if [ "$want_cli" -eq 0 ] && [ -n "${DISPLAY:-}" ] && command -v xhost >/dev/null 2>&1; then
        xhost +SI:localuser:root >/dev/null 2>&1 || true
    fi
    exec sudo --preserve-env=DISPLAY,XAUTHORITY,WAYLAND_DISPLAY,XDG_RUNTIME_DIR,DBUS_SESSION_BUS_ADDRESS \
        "$PY" main.py "$@"
fi
exec "$PY" main.py "$@"
