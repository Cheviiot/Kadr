import time
import requests
import urllib.parse

JACKETT_SERVERS = [
    {'id': 'jacred_xyz', 'name': 'Jacred.xyz', 'url': 'jacred.xyz', 'key': ''},
    {'id': 'jac_red_ru', 'name': 'Jac-red.ru', 'url': 'jac-red.ru', 'key': ''},
    {'id': 'jac_red', 'name': 'Jac.red', 'url': 'jac.red', 'key': ''},
]


def format_bytes(size):
    if size <= 0:
        return '0 B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if abs(size) < 1024:
            return f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} PB'


class JackettService:
    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers['User-Agent'] = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self._healthy_server = None

    @property
    def servers(self):
        return list(JACKETT_SERVERS)

    def _get_server(self, server_id):
        for s in JACKETT_SERVERS:
            if s['id'] == server_id:
                return s
        return None

    def resolve_server_id(self):
        """Return the server_id to use: pinned or first healthy."""
        chosen = self.settings.get('selected_server', 'auto')
        if chosen != 'auto':
            return chosen
        if self._healthy_server:
            return self._healthy_server
        for s in JACKETT_SERVERS:
            if self.check_health(s['id']):
                self._healthy_server = s['id']
                return s['id']
        return JACKETT_SERVERS[0]['id']

    def check_health(self, server_id):
        server = self._get_server(server_id)
        if not server:
            return False
        api_path = '/api/v2.0/indexers/status:healthy/results'
        for proto in ('https', 'http'):
            try:
                url = f"{proto}://{server['url']}{api_path}?apikey={server['key']}"
                resp = self.session.get(url, timeout=5)
                if resp.status_code in (200, 401):
                    return True
            except Exception:
                continue
        return False

    def search(self, server_id, query):
        server = self._get_server(server_id)
        if not server:
            raise ValueError(f'Сервер не найден: {server_id}')

        api_path = '/api/v2.0/indexers/status:healthy/results'
        encoded = urllib.parse.quote(query)

        last_err = None
        for attempt in range(3):
            if attempt > 0:
                time.sleep(attempt * 2)

            for proto in ('https', 'http'):
                try:
                    url = (
                        f"{proto}://{server['url']}{api_path}"
                        f"?apikey={server['key']}&Query={encoded}"
                    )
                    resp = self.session.get(url, timeout=30)

                    if resp.status_code == 429:
                        last_err = 'Сервер перегружен (429). Попробуйте другой сервер.'
                        break

                    resp.raise_for_status()
                    data = resp.json()

                    results = []
                    for r in data.get('Results', []):
                        seeders = r.get('Seeders', 0)
                        peers = r.get('Peers', 0)
                        results.append({
                            'title': r.get('Title', ''),
                            'size': r.get('Size', 0),
                            'size_str': format_bytes(r.get('Size', 0)),
                            'seeders': seeders,
                            'leechers': max(0, peers - seeders),
                            'magnet_uri': r.get('MagnetUri', ''),
                            'link': r.get('Link', ''),
                            'tracker': r.get('Tracker', ''),
                            'publish_date': r.get('PublishDate', ''),
                            'category': r.get('CategoryDesc', ''),
                        })

                    results.sort(key=lambda x: x['seeders'], reverse=True)
                    return results

                except requests.RequestException as e:
                    last_err = str(e)
                    continue

        raise ConnectionError(last_err or 'Не удалось подключиться к серверу')
