#!/usr/bin/env bash
# Spejari setup for Debian, Ubuntu, Kali and Raspberry Pi OS.
#
#   ./setup.sh                      install packages, create .venv, install Python deps
#   ./setup.sh --no-apt             skip apt (only create the venv)
#   ./setup.sh --no-gui             CLI only: skip Tk / CustomTkinter (headless Pi Lite)
#   ./setup.sh --configure-gpsd     additionally point gpsd at a detected u-blox dongle
#   ./setup.sh --configure-gpsd /dev/ttyACM0
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

DO_APT=1
WITH_GUI=1
CONFIGURE_GPSD=0
GPS_DEV=""
while [ $# -gt 0 ]; do
    case "$1" in
        --no-apt) DO_APT=0 ;;
        --no-gui) WITH_GUI=0 ;;
        --configure-gpsd)
            CONFIGURE_GPSD=1
            if [ $# -gt 1 ] && [[ "$2" == /dev/* ]]; then GPS_DEV="$2"; shift; fi
            ;;
        -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

say() { printf '\033[1;36m[spejari]\033[0m %s\n' "$*"; }
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    command -v sudo >/dev/null || { echo "Run as root or install sudo." >&2; exit 1; }
    SUDO="sudo"
fi

if ! command -v python3 >/dev/null; then
    echo "python3 not found" >&2; exit 1
fi
python3 - <<'PY' || { echo "Python 3.9 or newer is required." >&2; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 9) else 1)
PY

if [ "$DO_APT" -eq 1 ]; then
    if command -v apt-get >/dev/null; then
        say "Installing system packages (iw, gpsd, python3-venv, ...)"
        $SUDO apt-get update
        $SUDO apt-get install -y python3 python3-venv python3-pip iw rfkill \
            wireless-regdb usbutils gpsd gpsd-clients
        if [ "$WITH_GUI" -eq 1 ]; then
            say "Installing GUI packages (python3-tk, xhost)"
            $SUDO apt-get install -y python3-tk x11-xserver-utils
        fi
    else
        say "apt-get not found - install iw, gpsd and python3-venv manually."
    fi
fi

say "Creating virtual environment (.venv)"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
if [ "$WITH_GUI" -eq 1 ]; then
    .venv/bin/python -m pip install -r requirements.txt
else
    grep -vi customtkinter requirements.txt > .requirements-cli.tmp
    .venv/bin/python -m pip install -r .requirements-cli.tmp
    rm -f .requirements-cli.tmp
fi

chmod +x run.sh setup.sh main.py
mkdir -p exports

if [ "$CONFIGURE_GPSD" -eq 1 ]; then
    if [ -z "$GPS_DEV" ]; then
        for dev in /dev/ttyACM* /dev/ttyUSB*; do
            [ -e "$dev" ] || continue
            vid="$(udevadm info -q property -n "$dev" 2>/dev/null | sed -n 's/^ID_VENDOR_ID=//p')"
            if [ "$vid" = "1546" ]; then GPS_DEV="$dev"; break; fi
        done
        [ -n "$GPS_DEV" ] || GPS_DEV="$(ls /dev/ttyACM* 2>/dev/null | head -n1 || true)"
    fi
    if [ -z "$GPS_DEV" ]; then
        say "No GPS device found - plug in the u-blox dongle and re-run with --configure-gpsd"
    else
        say "Configuring gpsd for $GPS_DEV"
        [ -f /etc/default/gpsd ] && $SUDO cp /etc/default/gpsd /etc/default/gpsd.spejari.bak
        $SUDO tee /etc/default/gpsd >/dev/null <<GPSD
# Written by Spejari setup.sh
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="$GPS_DEV"
USBAUTO="true"
GPSD
        $SUDO systemctl enable gpsd.socket >/dev/null 2>&1 || true
        $SUDO systemctl restart gpsd.socket gpsd >/dev/null 2>&1 || true
        say "gpsd restarted. Check the fix with: gpsmon  or  cgps -s"
    fi
fi

say "Done. Start Spejari with:  ./run.sh   (--cli for the terminal, --gui for the window)"
say "Tip: ./run.sh --list-adapters shows adapters, the channel split and GPS devices."
