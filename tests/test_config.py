import json

import pytest

from src.config import DEFAULT_CONFIG, ConfigManager
from src.time_estimator import MODEL_VERSION


def test_defaults_applied_to_fresh_install(tmp_path):
    config = ConfigManager(base_dir=tmp_path)
    assert config.get("quality_level") == "media"
    assert config.get("confirm_before_start") is True
    assert config.get("recent_images") == []


def test_set_and_reload_round_trip(tmp_path):
    ConfigManager(base_dir=tmp_path).set("quality_level", "alta")
    assert ConfigManager(base_dir=tmp_path).get("quality_level") == "alta"


def test_unknown_keys_from_the_file_are_preserved(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"future_option": 7}), encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("future_option") == 7


@pytest.mark.parametrize(
    "key, stored, expected",
    [
        ("speed", 500, 100),
        ("speed", -3, 1),
        ("speed", "nonsense", DEFAULT_CONFIG["speed"]),
        ("quality_level", "ULTRA", "media"),
        ("quality_level", "ALTA", "alta"),
        ("mode", "sideways", "contour"),
        ("aspect_mode", "squish", "keep_aspect"),
        ("simplify_image", "yes", True),
    ],
)
def test_invalid_values_are_coerced(tmp_path, key, stored, expected):
    (tmp_path / "config.json").write_text(json.dumps({key: stored}), encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get(key) == expected


@pytest.mark.parametrize(
    "area",
    [
        {"x": 1, "y": 2, "w": 0, "h": 5},      # zero width
        {"x": 1, "y": 2, "w": 10},             # missing key
        {"x": "a", "y": 2, "w": 10, "h": 5},   # wrong type
        "not-a-dict",
        [1, 2, 3, 4],
    ],
)
def test_malformed_last_area_is_discarded(tmp_path, area):
    (tmp_path / "config.json").write_text(json.dumps({"last_area": area}), encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("last_area") is None


@pytest.mark.parametrize("stored, expected", [(99.0, 5.0), (0.0, 0.2), (-1, 0.2), ("x", 1.0)])
def test_calibration_factor_is_clamped(tmp_path, stored, expected):
    (tmp_path / "config.json").write_text(
        json.dumps({"calibration_factor": stored, "estimator_model": MODEL_VERSION}),
        encoding="utf-8",
    )
    assert ConfigManager(base_dir=tmp_path).get("calibration_factor") == pytest.approx(expected)


def test_valid_last_area_survives(tmp_path):
    area = {"x": 10, "y": 20, "w": 300, "h": 200}
    (tmp_path / "config.json").write_text(json.dumps({"last_area": area}), encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("last_area") == area


def test_corrupt_json_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").write_text("{ this is not json", encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("speed") == DEFAULT_CONFIG["speed"]


def test_non_object_json_falls_back_to_defaults(tmp_path):
    (tmp_path / "config.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("quality_level") == "media"


def test_legacy_skip_confirmation_becomes_confirm_before_start(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"skip_confirmation": True}), encoding="utf-8")
    config = ConfigManager(base_dir=tmp_path)
    assert config.get("confirm_before_start") is False
    assert "skip_confirmation" not in config.config


def test_legacy_quality_slider_key_is_dropped(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"quality": 42}), encoding="utf-8")
    assert "quality" not in ConfigManager(base_dir=tmp_path).config


def test_recent_images_are_deduplicated_and_capped(tmp_path):
    config = ConfigManager(base_dir=tmp_path)
    paths = []
    for i in range(7):
        path = tmp_path / f"img{i}.png"
        path.write_bytes(b"x")
        paths.append(str(path))
        config.add_recent_image(str(path))

    config.add_recent_image(paths[0])
    recent = config.get("recent_images")
    assert len(recent) == 5
    assert recent[0] == paths[0]
    assert len(set(recent)) == len(recent)


def test_missing_files_are_not_added_to_recents(tmp_path):
    config = ConfigManager(base_dir=tmp_path)
    config.add_recent_image(str(tmp_path / "ghost.png"))
    assert config.get("recent_images") == []


def test_set_many_writes_once(tmp_path, monkeypatch):
    config = ConfigManager(base_dir=tmp_path)
    writes = []
    monkeypatch.setattr(ConfigManager, "save_config", lambda self: writes.append(1))

    config.set_many({"speed": 70, "mode": "bw", "simplify_image": True})
    assert len(writes) == 1
    assert config.get("speed") == 70 and config.get("mode") == "bw"


def test_setting_an_unchanged_value_skips_the_write(tmp_path, monkeypatch):
    config = ConfigManager(base_dir=tmp_path)
    config.set("speed", 70)
    writes = []
    monkeypatch.setattr(ConfigManager, "save_config", lambda self: writes.append(1))

    config.set("speed", 70)
    assert writes == []
    config.set("speed", 71)
    assert len(writes) == 1


def test_save_leaves_no_temp_files_behind(tmp_path):
    config = ConfigManager(base_dir=tmp_path)
    config.set("speed", 33)
    assert list(tmp_path.glob("config-*.tmp")) == []
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["speed"] == 33


def test_failed_save_keeps_the_previous_file_intact(tmp_path, monkeypatch):
    config = ConfigManager(base_dir=tmp_path)
    config.set("speed", 44)
    before = (tmp_path / "config.json").read_text(encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("src.config.os.replace", boom)
    config.set("speed", 99)  # must not raise

    assert (tmp_path / "config.json").read_text(encoding="utf-8") == before
    assert list(tmp_path.glob("config-*.tmp")) == []


def test_stale_calibration_is_discarded_when_the_model_changes(tmp_path):
    """A factor measured against an older cost model would compound the error."""
    (tmp_path / "config.json").write_text(
        json.dumps({"calibration_factor": 1.65, "estimator_model": 1}), encoding="utf-8"
    )
    config = ConfigManager(base_dir=tmp_path)
    assert config.get("calibration_factor") == 1.0
    assert config.get("estimator_model") == MODEL_VERSION


def test_calibration_survives_when_the_model_is_current(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"calibration_factor": 1.4, "estimator_model": MODEL_VERSION}), encoding="utf-8"
    )
    assert ConfigManager(base_dir=tmp_path).get("calibration_factor") == pytest.approx(1.4)


def test_pre_versioning_configs_are_reset(tmp_path):
    """Configs written before the key existed carry an unknown-model factor."""
    (tmp_path / "config.json").write_text(json.dumps({"calibration_factor": 2.2}), encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("calibration_factor") == 1.0
