import json
import os
from pathlib import Path
from typing import Dict, Any, List

DEFAULT_CONFIG: Dict[str, Any] = {
    "recent_images": [],
    "last_area": None,  # dict: {"x": 100, "y": 100, "w": 400, "h": 300}
    "mode": "contour",  # 'contour' or 'bw'
    "quality_level": "media",  # 'baixa', 'media', 'alta'
    "aspect_mode": "keep_aspect",  # 'keep_aspect', 'fill', 'stretch'
    "speed": 50,  # 1 to 100
    "simplify_image": False,
    "skip_confirmation": False,
    "confirm_before_start": True,
    "show_progress": True,
    "sound_on_finish": True,
    "calibration_factor": 1.0  # Auto-calibrated time estimation multiplier
}


class ConfigManager:
    """Manages persistent application settings and user preferences."""
    def __init__(self):
        self.app_dir = Path.home() / ".autodraw"
        self.app_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.app_dir / "config.json"
        self.config: Dict[str, Any] = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config = DEFAULT_CONFIG.copy()
                    config.update(data)
                    return config
            except Exception as e:
                print(f"[ConfigManager] Error reading config: {e}")
        return DEFAULT_CONFIG.copy()

    def save_config(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")

    def add_recent_image(self, image_path: str) -> None:
        recent = self.config.get("recent_images", [])
        if image_path in recent:
            recent.remove(image_path)
        if os.path.exists(image_path):
            recent.insert(0, image_path)
            self.config["recent_images"] = recent[:5]
            self.save_config()

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.save_config()
