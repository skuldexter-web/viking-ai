from spejari.adapters import parse_iw_dev, parse_phy_freqs

IW_DEV = """\
phy#1
\tInterface wlan1
\t\tifindex 4
\t\twdev 0x100000001
\t\taddr 00:c0:ca:11:22:33
\t\ttype managed
\t\ttxpower 20.00 dBm
phy#0
\tUnnamed/non-netdev interface
\t\twdev 0x2
\t\taddr 02:00:00:00:00:01
\t\ttype P2P-device
\tInterface wlan0
\t\tifindex 3
\t\taddr dc:a6:32:00:00:01
\t\ttype managed
\tInterface mon0
\t\taddr dc:a6:32:00:00:02
\t\ttype monitor
"""

PHY_INFO = """\
Wiphy phy1
\tBand 1:
\t\tFrequencies:
\t\t\t* 2412 MHz [1] (20.0 dBm)
\t\t\t* 2467 MHz [12] (20.0 dBm) (no IR)
\t\t\t* 2484 MHz [14] (disabled)
\t\tBitrates (non-HT):
\t\t\t* 1.0 Mbps
\tBand 2:
\t\tFrequencies:
\t\t\t* 5180 MHz [36] (23.0 dBm)
\t\t\t* 5260 MHz [52] (23.0 dBm) (no IR, radar detection)
\tBand 4:
\t\tFrequencies:
\t\t\t* 5955 MHz [1] (12.0 dBm)
"""


def test_parse_iw_dev():
    items = parse_iw_dev(IW_DEV)
    assert [(i["ifname"], i["phy"], i["type"]) for i in items] == [
        ("wlan1", "phy1", "managed"),
        ("wlan0", "phy0", "managed"),
        ("mon0", "phy0", "monitor"),
    ]
    assert items[0]["addr"] == "00:c0:ca:11:22:33"


def test_parse_phy_freqs():
    assert parse_phy_freqs(PHY_INFO) == [2412, 2467, 5180, 5260]
