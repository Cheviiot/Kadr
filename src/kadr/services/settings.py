import os
import json

DEFAULTS = {
    'selected_server': 'auto',
    'tmdb_proxy': 'auto',
    'download_client': 'auto',
}


class SettingsManager:
    def __init__(self):
        config_dir = os.environ.get(
            'XDG_CONFIG_HOME', os.path.expanduser('~/.config')
        )
        self._dir = os.path.join(config_dir, 'Kadr')
        self._path = os.path.join(self._dir, 'settings.json')
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(self._path) as f:
                self._data.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        os.makedirs(self._dir, exist_ok=True)
        with open(self._path, 'w') as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()
