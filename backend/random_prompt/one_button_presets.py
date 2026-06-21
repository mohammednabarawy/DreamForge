import json
from pathlib import Path
import shutil

_RANDOM_PROMPT_ROOT = Path(__file__).resolve().parent


class OneButtonPresets:
    DEFAULT_OBP_FILE = _RANDOM_PROMPT_ROOT / "presets" / "obp_presets.default"
    OBP_FILE = _RANDOM_PROMPT_ROOT / "userfiles" / "obp_presets.json"
    CUSTOM_OBP = "Custom..."
    RANDOM_PRESET_OBP = "All (random)..."

    def __init__(self):
        self.opb_presets = self.load_obp_presets()

    def load_obp_presets(self):
        default_data = self._load_data(self.DEFAULT_OBP_FILE)
        data = self._load_data(self.OBP_FILE)

        for name, settings in default_data.items():
            if name not in data:
                data[name] = settings

        # Sanity check
        for name, settings in data.items():
            if settings['subject'] == '------ all':
                settings['subject'] = 'all'

        self._save_data(self.OBP_FILE, data)
        return data

    def _load_data(self, file_path):
        if not file_path.exists():
            if file_path == self.DEFAULT_OBP_FILE:
                raise FileNotFoundError(
                    f"Missing default One Button Prompt presets at {file_path}. "
                    "Re-run ./setup.sh or restore backend/random_prompt/presets/obp_presets.default."
                )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self.DEFAULT_OBP_FILE, file_path)
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)

    def _save_data(self, file_path, data):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def save_obp_preset(self, perf_options):
        with open(self.OBP_FILE, "w") as f:
            json.dump(perf_options, f, indent=2)
        self.opb_presets = self.load_obp_presets()

    def get_obp_preset(self, name):
        return self.opb_presets[name]
