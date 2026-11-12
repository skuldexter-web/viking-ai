import pytest

from spejari.geo import haversine_m
from spejari.config import GpsConfig
from spejari.gps import GpsMonitor, NmeaState, nmea_checksum_ok


def with_checksum(body: str) -> str:
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    return f"${body}*{calc:02X}"


GGA = with_checksum("GNGGA,123519.00,5213.7806,N,02100.7367,E,1,08,0.9,110.4,M,34.0,M,,")
RMC = with_checksum("GNRMC,123519.00,A,5213.7806,N,02100.7367,E,10.0,84.4,091126,,,A")
GSA = with_checksum("GNGSA,A,3,01,02,03,04,05,06,07,08,,,,,1.6,0.9,1.3,1")


def test_checksum():
    assert nmea_checksum_ok(GGA)
    assert not nmea_checksum_ok(GGA[:-1] + "0")
    assert not nmea_checksum_ok("garbage")


def test_gga_rmc_gsa():
    st = NmeaState()
    assert st.feed(GGA)
    assert st.has_fix and st.mode == 3
    assert st.lat == pytest.approx(52.229677, abs=1e-6)
    assert st.lon == pytest.approx(21.012278, abs=1e-6)
    assert st.alt == pytest.approx(110.4)
    assert st.sats_used == 8
    assert st.feed(RMC)
    assert st.speed_mps == pytest.approx(5.14444, abs=1e-4)
    assert st.utc.year == 2026 and st.utc.month == 11 and st.utc.day == 9
    st.feed(GSA)
    assert st.hdop == pytest.approx(0.9)


def test_no_fix_sentence():
    st = NmeaState()
    assert st.feed(with_checksum("GPGGA,123519.00,,,,,0,00,99.99,,,,,,"))
    assert not st.has_fix and st.mode == 1


def test_haversine():
    assert haversine_m(52.0, 21.0, 52.0, 21.0) == 0
    assert haversine_m(52.0, 21.0, 52.001, 21.0) == pytest.approx(111.2, abs=0.5)


def test_distance_tracker_filters_jitter_and_jumps():
    mon = GpsMonitor(GpsConfig(source="none"))
    t = 1000.0
    lat = 52.0
    for i in range(10):  # ~11 m steps, 1 s apart
        mon._track_distance(lat + i * 0.0001, 21.0, t + i)
    covered = mon._fix.distance_m
    assert covered == pytest.approx(100.0, abs=5.0)
    mon._track_distance(lat + 0.00091, 21.00003, t + 10)  # jitter (<5 m) ignored
    assert mon._fix.distance_m == covered
    mon._track_distance(lat + 1.0, 21.0, t + 11)  # 111 km in 1 s: rejected
    assert mon._fix.distance_m == covered
