import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from src.logger import app_dir, get_logger
from src.time_estimator import MODEL_VERSION

log = get_logger("config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "recent_images": [],
    "last_area": None,  # dict: {"x": 100, "y": 100, "w": 400, "h": 300}
    "mode": "contour",  # 'contour' or 'bw'
    "quality_level": "media",  # 'baixa', 'media', 'alta'
    "aspect_mode": "keep_aspect",  # 'keep_aspect', 'fill', 'stretch'
    "speed": 50,  # 1 to 100
    "simplify_image": False,
    "confirm_before_start": True,
    "show_progress": True,
    "sound_on_finish": True,
    "warn_above_points": 300_000,  # heads-up before very long drawings
    "calibration_factor": 1.0,  # Auto-calibrated time estimation multiplier
}

# Deliberately absent from DEFAULT_CONFIG: a config file written before this
# key existed must be detectable, and merging a default in would hide that.
ESTIMATOR_MODEL_KEY = "estimator_model"

VALID_MODES = ("contour", "bw")
VALID_QUALITY = ("baixa", "media", "alta")
VALID_ASPECT = ("keep_aspect", "fill", "stretch")


class ConfigManager:
    """Manages persistent application settings and user preferences."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.app_dir = Path(base_dir) if base_dir else app_dir()
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.app_dir / "config.json"
        self.config: Dict[str, Any] = self.load_config()

    # ---------------- persistence ----------------

    def load_config(self) -> Dict[str, Any]:
        config = DEFAULT_CONFIG.copy()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
                else:
                    log.warning("Config root is %s, not an object; using defaults", type(data).__name__)
            except (OSError, json.JSONDecodeError) as e:
                log.warning("Could not read config (%s); using defaults", e)
        return self._sanitize(config)

    def save_config(self) -> None:
        """Writes the config atomically so a crash mid-write cannot corrupt it."""
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.app_dir, prefix="config-", suffix=".tmp", delete=False
            ) as tmp:
                tmp_name = tmp.name
                json.dump(self.config, tmp, indent=4, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.config_path)
            tmp_name = None
        except OSError as e:
            log.error("Could not save config: %s", e)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    # ---------------- validation ----------------

    @staticmethod
    def _sanitize(config: Dict[str, Any]) -> Dict[str, Any]:
        """Coerces persisted values back into their expected shape and range."""
        # Legacy keys: 'skip_confirmation' was the inverse of 'confirm_before_start',
        # and 'quality' was the pre-V2 slider replaced by 'quality_level'.
        if "skip_confirmation" in config:
            if config.pop("skip_confirmation"):
                config["confirm_before_start"] = False
        config.pop("quality", None)

        recent = config.get("recent_images")
        config["recent_images"] = [p for p in recent if isinstance(p, str)][:5] if isinstance(recent, list) else []

        area = config.get("last_area")
        config["last_area"] = area if _is_valid_area(area) else None

        if config.get("mode") not in VALID_MODES:
            config["mode"] = DEFAULT_CONFIG["mode"]
        if str(config.get("quality_level", "")).lower() not in VALID_QUALITY:
            config["quality_level"] = DEFAULT_CONFIG["quality_level"]
        else:
            config["quality_level"] = str(config["quality_level"]).lower()
        if config.get("aspect_mode") not in VALID_ASPECT:
            config["aspect_mode"] = DEFAULT_CONFIG["aspect_mode"]

        config["speed"] = _clamp_int(config.get("speed"), 1, 100, DEFAULT_CONFIG["speed"])
        config["warn_above_points"] = _clamp_int(
            config.get("warn_above_points"), 0, 100_000_000, DEFAULT_CONFIG["warn_above_points"]
        )
        config["calibration_factor"] = _clamp_float(
            config.get("calibration_factor"), 0.2, 5.0, DEFAULT_CONFIG["calibration_factor"]
        )

        # A calibration factor only corrects the model it was measured against,
        # so a model change has to discard it rather than compound onto it.
        if config.get(ESTIMATOR_MODEL_KEY) != MODEL_VERSION:
            if config.get("calibration_factor") != 1.0:
                log.info(
                    "Estimator model changed (%s -> %s); resetting calibration from %.2f",
                    config.get(ESTIMATOR_MODEL_KEY, "unversioned"), MODEL_VERSION,
                    config["calibration_factor"],
                )
            config["calibration_factor"] = 1.0
            config[ESTIMATOR_MODEL_KEY] = MODEL_VERSION

        for flag in ("simplify_image", "confirm_before_start", "show_progress", "sound_on_finish"):
            config[flag] = bool(config.get(flag, DEFAULT_CONFIG[flag]))

        return config

    # ---------------- accessors ----------------

    def add_recent_image(self, image_path: str) -> None:
        recent = [p for p in self.config.get("recent_images", []) if p != image_path]
        if os.path.exists(image_path):
            recent.insert(0, image_path)
            self.config["recent_images"] = recent[:5]
            self.save_config()

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        """Sets a value; pass save=False to batch several changes before one write."""
        if self.config.get(key) == value and key in self.config:
            return  # avoid rewriting the file when nothing actually changed
        self.config[key] = value
        if save:
            self.save_config()

    def set_many(self, values: Dict[str, Any]) -> None:
        """Applies several settings with a single disk write."""
        changed = False
        for key, value in values.items():
            if self.config.get(key) != value or key not in self.config:
                self.config[key] = value
                changed = True
        if changed:
            self.save_config()


def _is_valid_area(area: Any) -> bool:
    if not isinstance(area, dict):
        return False
    try:
        return all(isinstance(area.get(k), int) for k in ("x", "y", "w", "h")) and area["w"] > 0 and area["h"] > 0
    except (TypeError, KeyError):
        return False


def _clamp_int(value: Any, lo: int, hi: int, fallback: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return fallback


def _clamp_float(value: Any, lo: float, hi: float, fallback: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return fallback
