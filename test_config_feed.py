from spejari.config import HARD_MAX_ADAPTERS, Config, load_config
from spejari.models import FeedEntry, FeedLog


def test_ten_adapter_limit():
    assert HARD_MAX_ADAPTERS == 10
    cfg = Config()
    cfg.scan.max_adapters = 99
    cfg.normalise()
    assert cfg.scan.max_adapters == 10
    cfg.scan.max_adapters = 0
    cfg.normalise()
    assert cfg.scan.max_adapters == 1


def test_ui_mode_validation():
    cfg = Config()
    cfg.ui.default_mode = "GUI"
    cfg.normalise()
    assert cfg.ui.default_mode == "gui"
    cfg.ui.default_mode = "bogus"
    cfg.normalise()
    assert cfg.ui.default_mode == "ask" and cfg.warnings


def test_default_config_file_loads_cleanly():
    cfg = load_config()
    assert cfg.warnings == []
    assert cfg.ui.default_mode == "ask"


def test_feed_since_is_incremental():
    feed = FeedLog(maxlen=5)
    items, total = feed.since(0)
    assert items == [] and total == 0
    for i in range(3):
        feed.add(FeedEntry(ts=i, kind="SYS", message=str(i)))
    items, total = feed.since(0)
    assert [e.message for e in items] == ["0", "1", "2"] and total == 3
    feed.add(FeedEntry(ts=9, kind="SYS", message="3"))
    items, total = feed.since(total)
    assert [e.message for e in items] == ["3"] and total == 4
