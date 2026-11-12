"""Parser for `iw dev <if> scan` output."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from .channels import freq_to_band, freq_to_channel, in_scope
from .models import AccessPoint

_BSS_RE = re.compile(r"^BSS\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})")
_SIGNAL_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*dBm")


def decode_iw_ssid(value: str) -> str:
    """Undo the escaping iw applies to SSIDs (\\xNN and \\\\)."""
    out = bytearray()
    i, n = 0, len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 3 < n and value[i + 1] == "x":
            try:
                out.append(int(value[i + 2 : i + 4], 16))
                i += 4
                continue
            except ValueError:
                pass
        if ch == "\\" and i + 1 < n and value[i + 1] == "\\":
            out.append(0x5C)
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    text = out.decode("utf-8", errors="replace")
    text = text.replace("\x00", "")
    # An SSID of only whitespace/NULs is a hidden network.
    return text if text.strip("\x00 ") != "" else ""


def _akm_flags(akm: str) -> Tuple[bool, bool, bool, bool]:
    tokens = akm.replace("IEEE 802.1X", "EAP").split()
    eap = any("EAP" in t for t in tokens)
    psk = any("PSK" in t for t in tokens)
    sae = any("SAE" in t for t in tokens)
    owe = any("OWE" in t for t in tokens)
    return eap, psk, sae, owe


def _akm_name(eap: bool, psk: bool, sae: bool, owe: bool) -> str:
    names = [n for n, on in (("EAP", eap), ("PSK", psk), ("SAE", sae), ("OWE", owe)) if on]
    return "+".join(names) if names else "UNK"


def _cipher(block: Dict) -> str:
    pairwise = block.get("pairwise") or []
    if pairwise:
        return "+".join(pairwise)
    return block.get("group") or "UNK"


def derive_security(raw: Dict) -> Tuple[str, str]:
    """Return (WiGLE-style auth string, short label)."""
    tags: List[str] = []
    label = ""
    rsn, wpa = raw.get("RSN"), raw.get("WPA")
    if wpa is not None:
        eap, psk, sae, owe = _akm_flags(wpa.get("akm", ""))
        tags.append(f"[WPA-{_akm_name(eap, psk, sae, owe)}-{_cipher(wpa)}]")
        label = "WPA"
    if rsn is not None:
        eap, psk, sae, owe = _akm_flags(rsn.get("akm", ""))
        cipher = _cipher(rsn)
        if owe and not (psk or sae or eap):
            tags.append(f"[OWE-{cipher}]")
            rsn_label = "OWE"
        elif sae and not psk and not eap:
            tags.append(f"[WPA3-SAE-{cipher}]")
            rsn_label = "WPA3"
        else:
            tags.append(f"[WPA2-{_akm_name(eap, psk, sae, owe)}-{cipher}]")
            if sae and psk:
                rsn_label = "WPA2/3"
            elif eap:
                rsn_label = "WPA2-EAP"
            else:
                rsn_label = "WPA2"
        label = f"WPA/{rsn_label}" if label else rsn_label
    if not tags:
        if raw.get("privacy"):
            tags.append("[WEP]")
            label = "WEP"
        else:
            label = "Open"
    tags.append("[IBSS]" if raw.get("ibss") else "[ESS]")
    return "".join(tags), label


def _new_raw(bssid: str) -> Dict:
    return {
        "bssid": bssid.upper(),
        "freq": None,
        "rssi": None,
        "ssid": "",
        "privacy": False,
        "ibss": False,
        "RSN": None,
        "WPA": None,
    }


def _build(raw: Dict) -> Optional[AccessPoint]:
    freq = raw["freq"]
    if freq is None or not in_scope(freq):
        return None
    auth, label = derive_security(raw)
    rssi = raw["rssi"] if raw["rssi"] is not None else -100
    return AccessPoint(
        bssid=raw["bssid"],
        ssid=raw["ssid"],
        freq=freq,
        channel=freq_to_channel(freq),
        band=freq_to_band(freq) or "",
        rssi=int(round(rssi)),
        auth=auth,
        security=label,
    )


def parse_iw_scan(text: str) -> List[AccessPoint]:
    aps: List[AccessPoint] = []
    cur: Optional[Dict] = None
    section: Optional[str] = None

    def finish() -> None:
        if cur is not None:
            ap = _build(cur)
            if ap is not None:
                aps.append(ap)

    for raw_line in text.splitlines():
        if raw_line.startswith("BSS "):
            finish()
            m = _BSS_RE.match(raw_line)
            cur = _new_raw(m.group(1)) if m else None
            section = None
            continue
        if cur is None or not raw_line.startswith("\t"):
            continue
        if raw_line.startswith("\t\t"):
            if section in ("RSN", "WPA"):
                body = raw_line.strip().lstrip("*").strip()
                key, _, val = body.partition(":")
                key, val = key.strip().lower(), val.strip()
                blk = cur[section]
                if key == "group cipher":
                    blk["group"] = val
                elif key == "pairwise ciphers":
                    blk["pairwise"] = val.split()
                elif key == "authentication suites":
                    blk["akm"] = val
            continue
        key, _, val = raw_line.strip().partition(":")
        key, val = key.strip(), val.strip()
        section = None
        if key == "freq":
            m = re.match(r"(\d+)", val)
            if m:
                cur["freq"] = int(m.group(1))
        elif key == "signal":
            m = _SIGNAL_RE.search(val)
            if m:
                cur["rssi"] = float(m.group(1))
        elif key == "SSID":
            cur["ssid"] = decode_iw_ssid(val)
        elif key == "capability":
            tokens = val.split()
            cur["privacy"] = "Privacy" in tokens
            cur["ibss"] = "IBSS" in tokens
        elif key in ("RSN", "WPA"):
            section = key
            cur[key] = {"group": "", "pairwise": [], "akm": ""}
    finish()
    return aps
