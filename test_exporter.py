import csv
from datetime import datetime, timezone
from pathlib import Path

from spejari.exporter import (
    COLUMNS,
    Journal,
    export_filename,
    read_journal,
    recover_journals,
    write_wigle_csv,
)
from spejari.models import Observation


def obs(bssid, ssid, sec=0):
    return Observation(
        bssid=bssid,
        ssid=ssid,
        auth="[WPA2-PSK-CCMP][ESS]",
        seen_utc=datetime(2026, 11, 9, 12, 0, sec, tzinfo=timezone.utc),
        channel=6,
        rssi=-55,
        lat=52.229677,
        lon=21.012278,
        alt=110.4,
        accuracy=4.5,
    )


def test_filename():
    assert export_filename(datetime(2026, 1, 2, 3, 4, 5)) == "Spejari_2026-01-02_03-04-05.csv"


def test_csv_format(tmp_path: Path):
    path = tmp_path / "out.csv"
    n = write_wigle_csv([obs("AA:BB:CC:00:00:02", 'Odd, "name"', 5), obs("AA:BB:CC:00:00:01", "Net", 1)], path)
    assert n == 2
    lines = path.read_text().splitlines()
    assert lines[0].startswith("WigleWifi-1.4,appRelease=Spejari")
    rows = list(csv.reader(lines[1:]))
    assert rows[0] == COLUMNS
    assert rows[1][0] == "AA:BB:CC:00:00:01"  # sorted by time
    assert rows[2][1] == 'Odd, "name"'
    assert rows[1][3] == "2026-11-09 12:00:01"
    assert rows[1][6] == "52.22967700"
    assert rows[1][-1] == "WIFI"


def test_journal_recovery(tmp_path: Path):
    j = Journal(tmp_path, datetime(2026, 11, 9, 12, 0, 0))
    j.write(obs("AA:BB:CC:00:00:01", "A"))
    j.write(obs("AA:BB:CC:00:00:02", "B", 2))
    j.close()
    with open(j.path, "a") as fh:
        fh.write('{"torn": ')  # simulated power cut mid-write
    assert len(read_journal(j.path)) == 2
    out = recover_journals(tmp_path)
    assert [p.name for p in out] == ["Spejari_2026-11-09_12-00-00.csv"]
    assert not j.path.exists()


def test_extension_is_always_lowercase_csv(tmp_path: Path):
    from spejari.exporter import normalize_csv_path

    assert normalize_csv_path(Path("a/Spejari_x.CSV")).name == "Spejari_x.csv"
    assert normalize_csv_path(Path("a/Spejari_x.Csv")).name == "Spejari_x.csv"
    assert normalize_csv_path(Path("a/Spejari_x")).name == "Spejari_x.csv"
    n = write_wigle_csv([obs("AA:BB:CC:00:00:01", "A")], tmp_path / "Drive.CSV")
    assert n == 1
    assert [p.name for p in tmp_path.iterdir()] == ["Drive.csv"]
