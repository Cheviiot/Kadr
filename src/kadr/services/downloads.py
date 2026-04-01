import os
import shutil
import subprocess
import json
import time
import threading
import tempfile

import requests

DOWNLOAD_CLIENTS = [
    {'id': 'fdm', 'name': 'Free Download Manager', 'command': 'fdm'},
    {'id': 'qbittorrent', 'name': 'qBittorrent', 'command': 'qbittorrent'},
    {'id': 'transmission', 'name': 'Transmission', 'command': 'transmission-gtk'},
    {'id': 'deluge', 'name': 'Deluge', 'command': 'deluge'},
    {'id': 'ktorrent', 'name': 'KTorrent', 'command': 'ktorrent'},
]

_HISTORY_MAX = 100


class DownloadManager:
    def __init__(self, settings=None):
        self._settings = settings
        config_dir = os.environ.get(
            'XDG_CONFIG_HOME', os.path.expanduser('~/.config')
        )
        self._data_dir = os.path.join(config_dir, 'Kadr')
        self._data_file = os.path.join(self._data_dir, 'downloads.json')
        self._history = self._load_history()
        self._lock = threading.Lock()
        self._tmp_dir = os.path.join(tempfile.gettempdir(), 'kadr_torrents')
        self._cleanup_temp()

    def _load_history(self):
        try:
            with open(self._data_file) as f:
                data = json.load(f)
                return data[-_HISTORY_MAX:] if len(data) > _HISTORY_MAX else data
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_history(self):
        os.makedirs(self._data_dir, exist_ok=True)
        self._history = self._history[-_HISTORY_MAX:]
        with open(self._data_file, 'w') as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False)

    def _cleanup_temp(self):
        """Remove stale temp torrent files older than 1 hour."""
        if not os.path.isdir(self._tmp_dir):
            return
        cutoff = time.time() - 3600
        for name in os.listdir(self._tmp_dir):
            path = os.path.join(self._tmp_dir, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass

    def _launch_client(self, client, arg):
        """Launch torrent client and raise on failure."""
        try:
            subprocess.Popen([client['command'], arg])
        except OSError as e:
            raise RuntimeError(
                f'Не удалось запустить {client["name"]}: {e}'
            )

    def available_clients(self):
        return [c for c in DOWNLOAD_CLIENTS if shutil.which(c['command'])]

    def find_client(self):
        preferred = (
            self._settings.get('download_client', 'auto')
            if self._settings else 'auto'
        )
        clients = self.available_clients()
        if not clients:
            return None
        if preferred != 'auto':
            for c in clients:
                if c['id'] == preferred:
                    return c
        return clients[0]

    def send_magnet(self, magnet_uri, name=''):
        client = self.find_client()
        if not client:
            raise RuntimeError(
                'Торрент-клиент не найден. '
                'Установите qBittorrent, Transmission или другой клиент.'
            )

        self._launch_client(client, magnet_uri)

        entry = {
            'name': name,
            'magnet': magnet_uri,
            'client': client['name'],
            'time': int(time.time()),
        }
        with self._lock:
            self._history.append(entry)
            self._save_history()
        return client['name']

    def send_torrent_url(self, url, name=''):
        client = self.find_client()
        if not client:
            raise RuntimeError(
                'Торрент-клиент не найден. '
                'Установите qBittorrent, Transmission или другой клиент.'
            )

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        safe_name = ''.join(
            c if c.isalnum() or c in ' .-_' else '_' for c in name
        )
        if not safe_name.lower().endswith('.torrent'):
            safe_name += '.torrent'

        tmp_dir = self._tmp_dir
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, safe_name)

        with open(path, 'wb') as f:
            f.write(resp.content)

        self._launch_client(client, path)

        entry = {
            'name': name,
            'torrent_url': url,
            'client': client['name'],
            'time': int(time.time()),
        }
        with self._lock:
            self._history.append(entry)
            self._save_history()
        return client['name']

    @property
    def history(self):
        with self._lock:
            return list(self._history)

    def clear_history(self):
        with self._lock:
            self._history = []
            self._save_history()
