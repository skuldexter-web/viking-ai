"""Channel maths and the multi-adapter load-balancing algorithm."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

BAND_2G = "2.4"
BAND_5G = "5"


def freq_to_band(freq: int) -> Optional[str]:
    if 2400 <= freq <= 2500:
        return BAND_2G
    if 5150 <= freq <= 5895:
        return BAND_5G
    return None


def in_scope(freq: int) -> bool:
    """Spejari scans 2.4 GHz and 5 GHz only (6 GHz is out of scope)."""
    return freq_to_band(freq) is not None


def freq_to_channel(freq: int) -> int:
    if freq == 2484:
        return 14
    if 2400 <= freq <= 2500:
        return (freq - 2407) // 5
    if 5150 <= freq <= 5895:
        return (freq - 5000) // 5
    return 0


def channel_to_freq(channel: int) -> int:
    """Channel numbers are unambiguous inside the supported bands (1-14, 32+)."""
    if channel == 14:
        return 2484
    if 1 <= channel <= 13:
        return 2407 + 5 * channel
    return 5000 + 5 * channel


def is_dfs(freq: int) -> bool:
    return 5250 <= freq <= 5730


def select_channels(supported: Iterable[int], scan_cfg) -> List[int]:
    """Filter an adapter's supported frequencies by the user's configuration."""
    excluded = {channel_to_freq(int(c)) for c in scan_cfg.exclude_channels}
    out: List[int] = []
    for freq in sorted(set(supported)):
        band = freq_to_band(freq)
        if band is None:
            continue
        if band == BAND_2G and not scan_cfg.band_2g:
            continue
        if band == BAND_5G and not scan_cfg.band_5g:
            continue
        if scan_cfg.skip_dfs and is_dfs(freq):
            continue
        if freq in excluded:
            continue
        out.append(freq)
    return out


def distribute(capabilities: Dict[str, List[int]]) -> Dict[str, List[int]]:
    """Split channels across adapters as evenly as their capabilities allow.

    * 1 adapter  -> it gets 100 % of its channels.
    * N adapters -> every channel is handed to the least-loaded adapter that
      supports it. Channels with the fewest capable adapters are placed first, so
      single-band adapters never end up starved by dual-band ones. With identical
      adapters this degrades to an interleaved round-robin (A, B, A, B, ...).

    The result is deterministic for a given input.
    """
    names = sorted(capabilities)
    plan: Dict[str, List[int]] = {n: [] for n in names}
    universe = sorted({f for freqs in capabilities.values() for f in freqs})
    capable = {f: [n for n in names if f in capabilities[n]] for f in universe}
    order = sorted(universe, key=lambda f: (len(capable[f]), f))
    for freq in order:
        target = min(capable[freq], key=lambda n: (len(plan[n]), names.index(n)))
        plan[target].append(freq)
    for n in names:
        plan[n].sort()
    return plan


def describe_channels(freqs: Iterable[int]) -> str:
    """Compact, exact channel list, e.g. '2.4G:1,6,11  5G:36,40,44'."""
    ordered = sorted(freqs)
    g2 = [str(freq_to_channel(f)) for f in ordered if freq_to_band(f) == BAND_2G]
    g5 = [str(freq_to_channel(f)) for f in ordered if freq_to_band(f) == BAND_5G]
    parts = []
    if g2:
        parts.append("2.4G:" + ",".join(g2))
    if g5:
        parts.append("5G:" + ",".join(g5))
    return "  ".join(parts) if parts else "-"
