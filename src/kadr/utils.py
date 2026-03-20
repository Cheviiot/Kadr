import os
import hashlib
import threading
import subprocess

from gi.repository import GLib, GdkPixbuf, Gdk

import requests

_image_cache = {}
_cache_dir = None
_download_sem = threading.Semaphore(6)


def _get_cache_dir():
    global _cache_dir
    if _cache_dir is None:
        base = os.environ.get(
            'XDG_CACHE_HOME', os.path.expanduser('~/.cache')
        )
        _cache_dir = os.path.join(base, 'kadr', 'images')
        os.makedirs(_cache_dir, exist_ok=True)
    return _cache_dir


def load_image_async(url, width, height, callback):
    """Load image from URL asynchronously with disk + memory cache."""
    if not url:
        GLib.idle_add(callback, None)
        return

    cache_key = f'{width}x{height}:{url}'

    if cache_key in _image_cache:
        GLib.idle_add(callback, _image_cache[cache_key])
        return

    def _worker():
        try:
            file_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
            cache_path = os.path.join(_get_cache_dir(), file_hash)

            data = None
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    data = f.read()
                if len(data) < 100:
                    data = None
                    os.remove(cache_path)

            if data is None:
                _download_sem.acquire()
                try:
                    for _attempt in range(4):
                        try:
                            resp = requests.get(
                                url, timeout=(4, 10),
                                headers={'User-Agent': 'Mozilla/5.0'},
                            )
                            resp.raise_for_status()
                            data = resp.content
                            break
                        except (requests.ConnectionError, requests.Timeout):
                            if _attempt == 3:
                                raise
                            import time
                            time.sleep(0.3 * (_attempt + 1))
                finally:
                    _download_sem.release()
                with open(cache_path, 'wb') as f:
                    f.write(data)

            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            if pixbuf and width > 0 and height > 0:
                pixbuf = pixbuf.scale_simple(
                    width, height, GdkPixbuf.InterpType.BILINEAR
                )

            if pixbuf:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                _image_cache[cache_key] = texture
                GLib.idle_add(callback, texture)
            else:
                GLib.idle_add(callback, None)
        except Exception:
            GLib.idle_add(callback, None)

    threading.Thread(target=_worker, daemon=True).start()


def run_async(func, callback, *args):
    """Run func(*args) in background thread, call callback(result, error) on main thread."""
    def _worker():
        try:
            result = func(*args)
            GLib.idle_add(callback, result, None)
        except Exception as e:
            GLib.idle_add(callback, None, e)

    threading.Thread(target=_worker, daemon=True).start()


def copy_to_clipboard(text):
    """Copy text to clipboard using system tools."""
    for cmd in (
        ['xclip', '-selection', 'clipboard'],
        ['xsel', '--clipboard', '--input'],
        ['wl-copy'],
    ):
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            if proc.returncode == 0:
                return
        except FileNotFoundError:
            continue
    raise RuntimeError('Не найдена утилита буфера обмена (xclip/xsel/wl-copy)')
