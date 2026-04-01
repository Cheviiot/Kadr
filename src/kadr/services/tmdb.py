import requests
import urllib.parse

TMDB_API_KEY = '4ef0d7355d9ffb5151e987764708ce96'

TMDB_PROXIES = {
    'direct': {
        'name': 'TMDB Direct',
        'api_url': 'https://api.themoviedb.org',
        'image_url': 'https://image.tmdb.org',
    },
    'apn_render': {
        'name': 'APN Render',
        'api_url': 'https://apn-latest.onrender.com/https://api.themoviedb.org',
        'image_url': 'https://apn-latest.onrender.com/https://image.tmdb.org',
    },
}


class TMDBService:
    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Origin': 'https://kadr.app',
        })
        self._healthy_proxy = None

    def _resolve_proxy_id(self):
        """Return the proxy_id to use: pinned or first healthy."""
        chosen = self.settings.get('tmdb_proxy', 'auto')
        if chosen != 'auto':
            return chosen
        if self._healthy_proxy:
            return self._healthy_proxy
        for pid in TMDB_PROXIES:
            if self.check_health(pid):
                self._healthy_proxy = pid
                return pid
        return 'direct'

    @property
    def _proxy(self):
        pid = self._resolve_proxy_id()
        return TMDB_PROXIES.get(pid, TMDB_PROXIES['direct'])

    def _api_url(self, path, **params):
        params['api_key'] = TMDB_API_KEY
        params.setdefault('language', 'ru-RU')
        qs = urllib.parse.urlencode(params)
        return f"{self._proxy['api_url']}/3{path}?{qs}"

    def image_url(self, path, size='w342'):
        if not path:
            return None
        return f"{self._proxy['image_url']}/t/p/{size}{path}"

    def _fetch(self, path, timeout=10, **params):
        url = self._api_url(path, **params)
        resp = self.session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def search_movies(self, query, page=1):
        return self._fetch('/search/movie', query=query, page=page)

    def search_tv(self, query, page=1):
        return self._fetch('/search/tv', query=query, page=page)

    def popular_movies(self, page=1):
        return self._fetch('/movie/popular', page=page)

    def popular_tv(self, page=1):
        return self._fetch('/tv/popular', page=page)

    def movie_details(self, movie_id):
        return self._fetch(f'/movie/{int(movie_id)}')

    def tv_details(self, tv_id):
        return self._fetch(f'/tv/{int(tv_id)}')

    def movie_credits(self, movie_id):
        return self._fetch(f'/movie/{int(movie_id)}/credits')

    def tv_credits(self, tv_id):
        return self._fetch(f'/tv/{int(tv_id)}/credits')

    def genres(self, media_type='movie'):
        return self._fetch(f'/genre/{media_type}/list').get('genres', [])

    def check_health(self, proxy_id):
        proxy = TMDB_PROXIES.get(proxy_id)
        if not proxy:
            return False
        try:
            url = f"{proxy['api_url']}/3/movie/popular?api_key={TMDB_API_KEY}&language=ru-RU&page=1"
            resp = self.session.get(url, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
