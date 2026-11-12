from spejari.parser import decode_iw_ssid, parse_iw_scan

SAMPLE = """\
BSS aa:bb:cc:00:00:01(on wlan1)
\tlast seen: 1234.5s [boottime]
\tTSF: 1 usec
\tfreq: 2412
\tbeacon interval: 100 TUs
\tcapability: ESS Privacy ShortSlotTime (0x0411)
\tsignal: -52.00 dBm
\tlast seen: 120 ms ago
\tSSID: HomeNet
\tDS Parameter set: channel 1
\tRSN:\t * Version: 1
\t\t * Group cipher: CCMP
\t\t * Pairwise ciphers: CCMP
\t\t * Authentication suites: PSK
\t\t * Capabilities: 16-PTKSA-RC 1-GTKSA-RC (0x000c)
BSS aa:bb:cc:00:00:02(on wlan1) -- associated
\tfreq: 5180
\tcapability: ESS Privacy (0x0411)
\tsignal: -71.00 dBm
\tSSID: Caf\\xc3\\xa9 [red]WiFi\\x00
\tRSN:\t * Version: 1
\t\t * Group cipher: CCMP
\t\t * Pairwise ciphers: CCMP
\t\t * Authentication suites: SAE
BSS aa:bb:cc:00:00:03(on wlan1)
\tfreq: 2437
\tcapability: ESS (0x0401)
\tsignal: -80.00 dBm
\tSSID: FreeWifi
BSS aa:bb:cc:00:00:04(on wlan1)
\tfreq: 2462
\tcapability: ESS Privacy (0x0411)
\tsignal: -90.00 dBm
\tSSID: \\x00\\x00\\x00
\tWPA:\t * Version: 1
\t\t * Group cipher: TKIP
\t\t * Pairwise ciphers: TKIP CCMP
\t\t * Authentication suites: PSK
\tRSN:\t * Version: 1
\t\t * Group cipher: TKIP
\t\t * Pairwise ciphers: CCMP TKIP
\t\t * Authentication suites: IEEE 802.1X
BSS aa:bb:cc:00:00:05(on wlan1)
\tfreq: 5955
\tsignal: -60.00 dBm
\tSSID: SixGhz
BSS aa:bb:cc:00:00:06(on wlan1)
\tfreq: 2442
\tcapability: ESS Privacy (0x0411)
\tsignal: -66.00 dBm
\tSSID: OldWep
"""


def by_bssid():
    return {ap.bssid: ap for ap in parse_iw_scan(SAMPLE)}


def test_counts_and_scope():
    aps = by_bssid()
    assert len(aps) == 5  # the 6 GHz entry is ignored
    assert "AA:BB:CC:00:00:05" not in aps


def test_wpa2_psk():
    ap = by_bssid()["AA:BB:CC:00:00:01"]
    assert (ap.ssid, ap.channel, ap.band, ap.rssi) == ("HomeNet", 1, "2.4", -52)
    assert ap.auth == "[WPA2-PSK-CCMP][ESS]"
    assert ap.security == "WPA2"


def test_wpa3_and_ssid_escapes():
    ap = by_bssid()["AA:BB:CC:00:00:02"]
    assert ap.ssid == "Café [red]WiFi"
    assert (ap.channel, ap.band) == (36, "5")
    assert ap.auth == "[WPA3-SAE-CCMP][ESS]"
    assert ap.security == "WPA3"


def test_open_and_wep():
    aps = by_bssid()
    assert aps["AA:BB:CC:00:00:03"].auth == "[ESS]"
    assert aps["AA:BB:CC:00:00:03"].security == "Open"
    assert aps["AA:BB:CC:00:00:06"].auth == "[WEP][ESS]"


def test_mixed_wpa_wpa2_enterprise_hidden():
    ap = by_bssid()["AA:BB:CC:00:00:04"]
    assert ap.hidden
    assert ap.auth == "[WPA-PSK-TKIP+CCMP][WPA2-EAP-CCMP+TKIP][ESS]"
    assert ap.security == "WPA/WPA2-EAP"


def test_decode_ssid():
    assert decode_iw_ssid("a\\\\b") == "a\\b"
    assert decode_iw_ssid("\\x00\\x00") == ""
    assert decode_iw_ssid("\\xe2\\x9c\\x93 ok") == "✓ ok"
