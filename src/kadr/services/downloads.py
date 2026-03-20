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

    def _load_history(self):
        try:
            with open(self._data_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_history(self):
        os.makedirs(self._data_dir, exist_ok=True)
        with open(self._data_file, 'w') as f:
            json.dump(self._history, f, indent=2, ensure_ascii=False)

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
        subprocess.Popen([client['command'], magnet_uri])

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

        tmp_dir = os.path.join(tempfile.gettempdir(), 'kadr_torrents')
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, safe_name)

        with open(path, 'wb') as f:
            f.write(resp.content)

        subprocess.Popen([client['command'], path])

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
