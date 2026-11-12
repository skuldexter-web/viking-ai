from spejari.channels import (
    channel_to_freq,
    describe_channels,
    distribute,
    freq_to_channel,
    select_channels,
)
from spejari.config import ScanConfig

CH_2G = [2407 + 5 * c for c in range(1, 14)]
CH_5G = [5000 + 5 * c for c in (36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 149, 153, 157, 161, 165)]
ALL = CH_2G + CH_5G


def test_freq_channel_roundtrip():
    for freq in ALL + [2484]:
        assert channel_to_freq(freq_to_channel(freq)) == freq


def test_single_adapter_gets_everything():
    plan = distribute({"wlan0": ALL})
    assert plan["wlan0"] == sorted(ALL)


def test_two_adapters_split_evenly():
    plan = distribute({"wlan0": ALL, "wlan1": ALL})
    assert abs(len(plan["wlan0"]) - len(plan["wlan1"])) <= 1
    assert sorted(plan["wlan0"] + plan["wlan1"]) == sorted(ALL)
    assert not set(plan["wlan0"]) & set(plan["wlan1"])


def test_up_to_ten_adapters_cover_all_channels_once():
    for n in range(1, 11):
        plan = distribute({f"wlan{i}": ALL for i in range(n)})
        merged = [f for chans in plan.values() for f in chans]
        assert sorted(merged) == sorted(ALL)
        sizes = [len(v) for v in plan.values()]
        assert max(sizes) - min(sizes) <= 1


def test_capability_aware_split():
    # wlan0 is 2.4 GHz only, wlan1 is dual band
    plan = distribute({"wlan0": CH_2G, "wlan1": ALL})
    assert set(plan["wlan0"]) <= set(CH_2G)
    assert sorted(plan["wlan0"] + plan["wlan1"]) == sorted(ALL)
    # wlan1 alone can hear the 15 five-GHz channels, so 13 / 15 is the best possible split
    assert (len(plan["wlan0"]), len(plan["wlan1"])) == (13, 15)


def test_rebalance_on_removal():
    three = distribute({f"w{i}": ALL for i in range(3)})
    two = distribute({f"w{i}": ALL for i in range(2)})
    assert sum(len(v) for v in three.values()) == sum(len(v) for v in two.values()) == len(ALL)


def test_select_channels_filters():
    cfg = ScanConfig(band_5g=False)
    assert select_channels(ALL, cfg) == CH_2G
    cfg = ScanConfig(skip_dfs=True, exclude_channels=[1])
    out = select_channels(ALL, cfg)
    assert 2412 not in out and 5260 not in out and 5180 in out


def test_describe_channels():
    assert describe_channels([2412, 2437, 5180]) == "2.4G:1,6  5G:36"
    assert describe_channels([]) == "-"
