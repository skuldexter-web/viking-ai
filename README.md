```
╔═╗╔═╗╔═╗ ╦╔═╗╦═╗╦
╚═╗╠═╝║╣  ║╠═╣╠╦╝║
╚═╝╩  ╚═╝╚╝╩ ╩╩╚═╩
ᛋ  scout of the 2.4 / 5 GHz airwaves  ᛋ
```

# Spejari

**Spejari** (Old Norse *spæjari*, "scout") is a war-driving tool for Debian-based Linux and Raspberry Pi with **two interfaces: a terminal dashboard (CLI) and a desktop window (GUI, CustomTkinter)**. It drives **up to ten external Wi-Fi adapters at once**, splits the 2.4 GHz and 5 GHz channels between them automatically, tags every network with GPS coordinates from a **u-blox** receiver, shows everything in a live dashboard and, when you stop the session, writes a **WiGLE-format CSV** (compatible with WiGLE and wdgwars.pl-style uploads).

- **Pick your interface:** `./run.sh --cli` (terminal, works over SSH) or `./run.sh --gui` (buttons, drop-down menus, live tables) - or choose at start-up
- 2.4 GHz and 5 GHz Wi-Fi only (6 GHz is intentionally out of scope)
- Passive-by-design data: SSID, BSSID, RSSI, channel, security type - nothing is ever connected to, attacked or decrypted
- 1 adapter scans 100 % of the channels; N adapters share them equally; **hot-plug re-balances live**
- GPS through `gpsd` or straight from `/dev/ttyACM*` / `/dev/ttyUSB*` (NMEA), with fix status, coordinates and kilometres driven
- Results are always saved as lowercase `.csv` (never `.CSV`)
- Crash-safe: every logged sighting is journalled to disk and can be recovered with `--recover`
- Python 3.9+; dependencies: `rich` (CLI) and `customtkinter` (GUI, optional)

---

## Table of contents

1. [How it works](#how-it-works)
2. [Requirements and hardware recommendations](#requirements-and-hardware-recommendations)
3. [Installation](#installation)
4. [GPS setup](#gps-setup)
5. [Usage](#usage)
6. [Configuration](#configuration)
7. [Output format and uploading](#output-format-and-uploading)
8. [Project layout](#project-layout)
9. [Raspberry Pi tips](#raspberry-pi-tips)
10. [Troubleshooting](#troubleshooting)
11. [Development](#development)
12. [Publishing to GitHub](#publishing-to-github)
13. [Legal and ethics](#legal-and-ethics)
14. [License](#license)

---

## How it works

### Scanning

Spejari uses the kernel's own scan interface through `iw dev <iface> scan freq <MHz...>`, so **no monitor mode, no driver patches and no `airmon-ng` are needed**: any adapter that works as a normal Linux Wi-Fi client works here. Each adapter runs in its own worker thread and hops across *its* assigned channels, one scan per channel (configurable with `channels_per_scan`). Add `--passive` to never transmit probe requests.

The supported channels of every adapter are read from `iw phy <phy> info`, so the **regulatory domain is respected** (disabled channels are skipped) and single-band adapters only get channels they can actually hear.

### Dynamic multi-adapter clustering

| Adapters | Behaviour |
|---------:|-----------|
| 1 | Scans 100 % of the 2.4 / 5 GHz channels sequentially |
| 2 | Each adapter scans ~50 % (interleaved so both bands are covered by both) |
| 3-10 | The channels are divided as equally as the adapters' capabilities allow (10 adapters = ~3 channels each) |

The distribution is greedy and deterministic: channels that only some adapters support are placed first, then every channel goes to the least-loaded capable adapter. A 2.4 GHz-only dongle next to a dual-band one is therefore not starved. Every adapter's share is shown live in the dashboard.

**Hot-plug:** the adapter list is polled every 2 s. Plug a dongle in or pull one out and Spejari starts/stops its worker and recomputes the channel plan within a couple of seconds - the session keeps running. Several virtual interfaces on one radio are collapsed into one adapter; interfaces in monitor or AP mode are ignored. A hard limit of ten adapters applies (`--max-adapters`); extra adapters are listed as "over limit" and take over automatically if an active one is unplugged.

### GPS and distance

A background thread reads from `gpsd` (JSON protocol, no extra Python packages) or, if `gpsd` is not available, opens a u-blox serial device directly and parses NMEA (`GGA`, `RMC`, `GSA`, `GSV` with checksum verification). It tracks fix status (2D/3D), satellites, HDOP, speed, and the **cumulative distance** with a jitter filter (steps < 5 m are ignored) and a glitch filter (jumps implying > 250 km/h are rejected). GPS time is used for the `FirstSeen` timestamps, which matters on a Raspberry Pi without a real-time clock.

### Logging policy

Spejari de-duplicates by BSSID. A network is written to the CSV

1. the first time it is seen **with a valid GPS fix**,
2. again when you have moved at least `min_distance_m` (25 m) since its last logged position, or
3. when its signal is at least `rssi_improvement_db` (8 dB) stronger than anything logged so far.

That gives WiGLE-style services enough position samples to place each access point without writing a row for every beacon. Networks seen before the GPS has a fix still appear in the live feed and the SSID counter, but are not written (a CSV row without coordinates is useless).

---

## Requirements and hardware recommendations

### Software

- Debian-based Linux: Raspberry Pi OS, Debian 11+, Ubuntu 22.04+, Kali
- Python **3.9+**
- `iw` (the setup script installs it), `gpsd` (optional but recommended)
- Root privileges (the kernel only allows triggering scans as root)

### Wi-Fi adapters

Use adapters with **in-kernel drivers** and good scan behaviour. Verify against your kernel version before buying.

- **MediaTek mt76 family** - e.g. MT7612U / MT7610U based dual-band USB adapters (the ALFA AWUS036ACM is a popular MT7612U example) and MT7921-based USB/M.2 AX adapters: in-tree drivers, reliable 2.4 + 5 GHz scanning
- **Intel AX200 / AX210** in a laptop or mini-PC: excellent, in-tree
- Realtek USB adapters often need out-of-tree DKMS drivers; they can work but are the most common source of trouble
- The Raspberry Pi's onboard Wi-Fi (brcmfmac) scans both bands, but it is usually your SSH link - exclude it with `--exclude wlan0`
- Mix and match is fine: Spejari reads each adapter's capabilities separately

Prefer **adapters with external antennas** and, for more than two adapters, **powered USB hubs** (a USB Wi-Fi adapter can draw 300-500 mA each, so ten adapters need several amps - use quality hubs with their own supply, ideally spread over more than one host port; a Pi 4/5 or a laptop is recommended over older Pis for ten adapters). Spread the antennas apart and keep them away from the GPS puck.

### GPS

- Any **u-blox** USB receiver (u-blox 7 / 8 / 9 dongles such as the common "G-Mouse" style pucks, or u-blox NEO-M8N / ZED-F9P modules exposing USB-CDC). They appear as `/dev/ttyACM0` with USB vendor id `1546`.
- Put the receiver on the dashboard or roof with a clear view of the sky; a cold start can take a few minutes.

### Computer

- Raspberry Pi 4 / 5 (3B+ works with fewer adapters), a laptop, or any Debian box
- A 12 V to 5 V (3 A+) car power supply for the Pi, and a powered USB hub when running more than two adapters
- For headless use, run Spejari inside `tmux` over SSH (or a phone hotspot) and use `--auto-start`

---

## Installation

```bash
# 1. get the code
unzip spejari.zip && cd spejari          # or: git clone https://github.com/YOUR-USER/spejari.git

# 2. install system packages and create a virtualenv
./setup.sh                               # add --configure-gpsd to wire up a u-blox dongle; --no-gui for CLI-only

# 3. check what Spejari sees
./run.sh --list-adapters

# 4. go - choose the interface when asked, or pick it directly
./run.sh            # asks: [1] CLI  [2] GUI
./run.sh --cli      # terminal dashboard
./run.sh --gui      # desktop window
```

`setup.sh` installs `iw`, `gpsd`, `python3-venv`, `python3-tk` (for the GUI) and friends via `apt`, creates `.venv/` and installs `requirements.txt` (including CustomTkinter). Use `./setup.sh --no-apt` to only build the virtualenv.

Manual installation:

```bash
sudo apt install python3 python3-venv python3-tk iw gpsd gpsd-clients
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
sudo .venv/bin/python main.py
```

---

## GPS setup

**Option A - gpsd (recommended).** Works with any receiver and lets other programs share the GPS.

```bash
./setup.sh --configure-gpsd              # detects the u-blox dongle and writes /etc/default/gpsd
cgps -s                                  # verify: you should see a fix outdoors
```

By hand, `/etc/default/gpsd` should contain:

```
START_DAEMON="true"
GPSD_OPTIONS="-n"
DEVICES="/dev/ttyACM0"
USBAUTO="true"
```

then `sudo systemctl enable --now gpsd.socket`.

**Option B - direct serial.** If gpsd is not running, Spejari (`--gps auto`, the default) probes `/dev/ttyACM*` / `/dev/ttyUSB*` devices **whose USB vendor id is u-blox (1546)** and reads their NMEA output. Pin a device with `--gps-device /dev/ttyACM0`. Other serial devices are only probed when `probe_other_ports = true`, because opening an unrelated serial port can reset some microcontroller boards.

Do **not** run gpsd and direct serial on the same device at the same time; `auto` handles this by preferring gpsd.

---

## Usage

Spejari has two front-ends that share the same engine (same scanning, GPS and CSV export):

| | CLI | GUI |
|---|---|---|
| Start | `./run.sh --cli` | `./run.sh --gui` |
| Best for | SSH, headless Pi, `tmux` | Laptop / Pi with a screen |
| Options | command-line flags + `config/spejari.toml` | buttons, drop-down menus, switches |

Run `./run.sh` without a flag and Spejari asks which one you want (set `default_mode = "cli"` or `"gui"` in `[ui]` to skip the question).

```bash
./run.sh                                  # choose CLI or GUI
./run.sh --cli                            # terminal dashboard
./run.sh --gui                            # desktop window
./run.sh --exclude wlan0                  # leave the onboard Wi-Fi (SSH link) alone
./run.sh -i wlan1 -i wlan2                # use only these adapters
./run.sh --band 5 --skip-dfs              # 5 GHz only, skip radar channels
./run.sh --gps-device /dev/ttyACM0 --auto-start
./run.sh --list-adapters                  # adapters, channel split preview, serial devices
./run.sh --recover                        # rebuild CSVs from journals of crashed sessions
```

### GUI

```bash
./run.sh --gui
```

- **Start session / Stop & export CSV** button (the same button toggles)
- **Drop-down menus:** band (2.4 + 5 GHz / 2.4 only / 5 GHz only), scan type (active / passive), max adapters (1-10), GPS source (auto / gpsd / serial / none), serial GPS device (detected u-blox ports), required fix quality (2D / 3D)
- **Switch:** skip 5 GHz DFS channels
- **Output:** *Browse...* picks the export folder, *Open folder* shows your CSV files
- **Adapters table:** one row per adapter with a **Use** checkbox - untick to exclude an adapter on the fly, tick it again to bring it back; channels are re-balanced within seconds. Shows driver, channel share, the channel being scanned, hits and state
- **Cards:** session timer, unique SSIDs, BSSIDs, rows logged, distance (km), GPS status; below them live coordinates, altitude, speed and satellites
- **Live feed table:** newest sightings at the bottom (green = new, grey = update, red = open/WEP network)
- Closing the window while a session runs asks to stop, export and quit

Band, scan type, max adapters, DFS and adapter ticks apply live; GPS and output settings are locked while a session runs. Because scanning requires root, the GUI runs as root: `run.sh` keeps your desktop session variables through `sudo` and runs `xhost +SI:localuser:root` (local root only) so the window can open. On Wayland desktops this goes through XWayland.

### Keys (CLI)

| Key | Action |
|-----|--------|
| `S` | Start a session (begins scanning + logging) / stop it (compiles and exports the CSV) |
| `Q` | Quit - a running session is stopped and exported first |
| `Ctrl-C` / `SIGTERM` | Same as `Q` |

### Dashboard

```
 ᛋ SPEJARI  v1.0.0  Wi-Fi war-driving · 2.4 / 5 GHz · 23:02:53 UTC
╭──── Status & Metrics ────╮╭──────────────── Adapters (2/6) ────────────────╮
│   Session ● SCANNING ... ││ Iface  Driver   Ch  Assigned channels   Now ... │
│     SSIDs 88             ││ wlan1  mt76x2u  15  2.4G:1,3,5 ...  5G:...      │
│    BSSIDs 91 (hidden 3)  ││ wlan2  mt7921u  15  2.4G:2,4,6 ...  5G:...      │
│       GPS 3D FIX         │╰────────────────────────────────────────────────╯
│  Position +52.2296, ...  │
│  Distance 3.482 km       │
╰──────────────────────────╯
╭─────────────────────────────── Live Feed ───────────────────────────────────╮
│ Time      Evt  SSID           BSSID              Ch Band RSSI Security Iface │
│ 23:02:53  NEW  CoffeeShop     AA:BB:CC:00:00:17   6 2.4G  -63 WPA2     wlan1 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

- **Top-left:** session state and timer, unique SSID counter, unique BSSIDs, rows logged, GPS status, live coordinates, altitude/speed, GPS source and **distance driven in km**
- **Top-right:** connected adapters, their driver, **channel assignment**, the channel being scanned right now, hits and state
- **Bottom:** live scrolling feed - `NEW` for a first sighting, `UPD` for refreshed signals; RSSI is colour-coded and open/WEP networks are highlighted

### Command-line options

| Option | Description |
|--------|-------------|
| `--cli` / `--gui` | Choose the terminal dashboard or the desktop window (default: ask at start-up) |
| `-c, --config FILE` | Use a specific TOML config |
| `-i, --interface IF` | Use only this adapter (repeatable) |
| `-x, --exclude IF` | Never use this adapter (repeatable) |
| `-n, --max-adapters N` | Adapter limit, 1-10 |
| `-b, --band {both,2.4,5}` | Restrict bands |
| `--skip-dfs` | Skip 5 GHz DFS channels (52-144) |
| `--passive` | Passive scans only |
| `--gps {auto,gpsd,serial,none}` | GPS source |
| `--gps-device DEV` | Serial GPS device (implies `--gps serial`) |
| `--gpsd HOST:PORT` | gpsd address |
| `-o, --output-dir DIR` | Export directory |
| `--auto-start` | Start scanning immediately (also automatic when there is no TTY) |
| `--list-adapters` | Show adapters, channel split and serial devices, then exit |
| `--recover` | Convert unfinished-session journals to CSV, then exit |

---

## Configuration

All defaults live in [`config/spejari.toml`](config/spejari.toml) with comments. CLI flags override the file. Sections: `[scan]`, `[log]`, `[gps]`, `[ui]` (`default_mode = "ask" | "cli" | "gui"`).

---

## Output format and uploading

On stop, Spejari writes `exports/Spejari_YYYY-MM-DD_HH-MM-SS.csv` (the extension is always lowercase `.csv`) (timestamp = session start, local time). Files created under `sudo` are handed back to your user. The format is **WigleWifi-1.4**:

```
WigleWifi-1.4,appRelease=Spejari 1.0.0,model=Raspberry Pi 4 Model B Rev 1.4,release=6.6.31+rpt-rpi-v8,device=raspberrypi,display=,board=aarch64,brand=Spejari
MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,CurrentLatitude,CurrentLongitude,AltitudeMeters,AccuracyMeters,Type
AA:BB:CC:00:00:17,CoffeeShop,[WPA2-PSK-CCMP][ESS],2026-11-09 23:02:53,6,-63,52.22967700,21.01227800,110.4,4.5,WIFI
```

- `FirstSeen` is **UTC**, corrected with GPS time when available
- `AuthMode` uses the Android/WiGLE capability notation: `[WPA3-SAE-CCMP]`, `[WPA2-PSK-CCMP]`, `[WPA2-EAP-CCMP]`, `[WPA-PSK-TKIP]`, `[WEP]`, `[OWE-CCMP]`, `[ESS]` (open)
- Hidden networks are exported with an empty SSID

Upload the file at <https://wigle.net/uploads> or to wdgwars.pl. Spejari writes the standard WiGLE CSV that such importers expect; check the site's upload page for its current size limits and rules.

If the process is killed or the power drops, run `./run.sh --recover`: every logged sighting is flushed to `exports/.spejari_*.journal` as it happens and is turned back into a CSV.

---

## Project layout

```
spejari/
├── main.py               entry point (sudo ./run.sh)
├── run.sh                launcher: venv python + sudo
├── setup.sh              apt packages, venv, optional gpsd configuration
├── requirements.txt      rich, customtkinter (+ tomli on Python < 3.11)
├── config/spejari.toml   documented defaults
├── spejari/
│   ├── cli.py            argument parsing, --list-adapters, --recover
│   ├── app.py            controller shared by CLI and GUI: sessions, export, main loop
│   ├── scanner.py        scan workers + hot-plug aware cluster manager
│   ├── channels.py       channel maths and the load-balancing algorithm
│   ├── adapters.py       adapter detection and capability parsing (iw)
│   ├── parser.py         `iw scan` output -> access points, security detection
│   ├── gps.py            gpsd client, NMEA parser, serial reader, distance tracker
│   ├── session.py        de-duplication, logging policy, statistics
│   ├── exporter.py       WiGLE CSV writer, crash-safe journal, recovery
│   ├── ui.py             CLI: rich dashboard and keyboard handling
│   ├── gui.py            GUI: CustomTkinter window (buttons, drop-downs, tables)
│   ├── config.py         TOML config + defaults
│   ├── models.py         shared dataclasses
│   └── geo.py            haversine distance
└── tests/                pytest suite (channels, parser, GPS, exporter, adapters)
```

---

## Raspberry Pi tips

- Use a **powered USB hub** and a decent 5 V supply; brown-outs show up as adapters vanishing (Spejari will re-balance, but you lose coverage).
- Set your regulatory domain so legal channels are enabled: `sudo iw reg set PL` (use your country code; persist it in `/etc/default/crda` or `raspi-config`).
- The Pi has no battery-backed clock - that is fine, Spejari timestamps with GPS time.
- Keep the session in `tmux`: `tmux new -s spejari ./run.sh --exclude wlan0 --auto-start`.
- Write exports to a USB stick or SD card with space: `-o /media/usb/spejari`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Scanning needs root privileges` | Start with `./run.sh` (it uses sudo) |
| GUI: `Cannot open a display` / `no display name` | Start from a desktop session (not plain SSH), use `./run.sh --gui` (keeps `DISPLAY`/`XAUTHORITY` through sudo), or run `xhost +SI:localuser:root` first |
| GUI: `No module named tkinter` / `customtkinter` | `sudo apt install python3-tk` and `.venv/bin/pip install customtkinter` (or re-run `./setup.sh`); the CLI works without them |
| `No scan-capable wireless adapter detected` | `./run.sh --list-adapters`; check `iw dev`, `rfkill list` (`sudo rfkill unblock wifi`), driver/firmware |
| State shows `busy` constantly | NetworkManager / wpa_supplicant is scanning on the same adapter: `sudo nmcli device set wlan1 managed no` |
| Scan disconnects my SSH session | You are scanning the interface that carries it - use `--exclude wlan0` |
| Fewer channels than expected | Regulatory domain: `sudo iw reg set <CC>`; or `--skip-dfs` / config excludes are active |
| GPS shows `NO FIX` | Move the antenna outdoors / near a window and wait for a cold start; check `cgps -s` |
| `No GPS found` | Check `ls /dev/ttyACM*`, `systemctl status gpsd`, or pin `--gps-device`; non-u-blox devices need `probe_other_ports = true` |
| Networks listed but nothing exported | There was no GPS fix while scanning - rows without coordinates are never written |
| Hidden networks missing | Don't use `--passive` if you want probe-response based discovery of hidden SSIDs |

---

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

The test suite covers channel distribution (1-10 adapters, mixed capabilities), `iw` output parsing, security detection, NMEA parsing, distance filtering, CSV format and journal recovery. The scanner only shells out to `iw`, which makes it easy to run against a fake `iw` script for integration testing. The GUI can be exercised headlessly with `xvfb-run`.

---

## Publishing to GitHub

```bash
unzip spejari.zip && cd spejari
git init -b main
git add .
git commit -m "Initial commit: Spejari 1.0.0"

# with the GitHub CLI
gh repo create spejari --public --source=. --remote=origin --push

# or manually: create an empty repo named "spejari" on github.com, then
git remote add origin git@github.com:YOUR-USER/spejari.git
git push -u origin main
```

Uploading through the GitHub web UI does not unzip archives: extract the zip first and drag the **contents** of the `spejari/` folder into *Add file -> Upload files*. The bundled `.gitignore` keeps your drive data (`exports/*.csv`, journals) out of the repository - **never commit your wardriving logs**, they contain location data.

---

## Legal and ethics

Spejari only listens to the beacon and probe-response frames that access points broadcast publicly; it does not connect to, attack, decrypt or interfere with any network. Laws on wireless collection and on recording location data differ by country and region - know yours, drive safely (set it up before you move, never operate it while driving), and publish data responsibly. Consider whether uploading your own home or neighbours' networks to a public database is appropriate. You are responsible for how you use this software.

---

## License

MIT - see [LICENSE](LICENSE). A SKALDSEC project.
