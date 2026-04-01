"""Torrent streaming service — sequential download + embedded mpv playback."""

import http.server
import os
import shutil
import socketserver
import tempfile
import threading
import time
from datetime import datetime

import requests
from gi.repository import GLib


class StreamLog:
    """Thread-safe log collector for streaming diagnostics."""

    def __init__(self):
        self._lines = []
        self._lock = threading.Lock()
        self._on_update = None

    def set_on_update(self, cb):
        """cb(line: str) called on GTK main thread for each new line."""
        self._on_update = cb

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        line = f'[{ts}] {msg}'
        with self._lock:
            self._lines.append(line)
        cb = self._on_update
        if cb:
            GLib.idle_add(cb, line)

    def text(self):
        with self._lock:
            return '\n'.join(self._lines)

    def clear(self):
        with self._lock:
            self._lines.clear()

_VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.webm', '.ts', '.m4v'}

# Minimum bytes buffered before launching player
_BUFFER_THRESHOLD = 20 * 1024 * 1024  # 20 MB


class _StreamingHandler(http.server.BaseHTTPRequestHandler):
    """Serves a growing video file, blocking reads past the download frontier."""

    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        srv = self.server
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(srv.total_size))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()

    def do_GET(self):
        srv = self.server
        total = srv.total_size
        if total <= 0:
            self.send_error(404)
            return

        start, end = 0, total - 1
        range_hdr = self.headers.get('Range')
        if range_hdr and range_hdr.startswith('bytes='):
            try:
                rng = range_hdr[6:]
                s, e = rng.split('-', 1)
                start = int(s) if s else 0
                end = int(e) if e else total - 1
            except ValueError:
                pass
            start = max(0, min(start, total - 1))
            end = max(start, min(end, total - 1))

        # If the request starts beyond the download frontier, wait briefly
        # then fail — this handles mpv probing the end of file for index data
        # (moov atom in MP4, Cues in MKV) without deadlocking.
        if start >= srv.available and not srv.complete:
            waited = 0.0
            while srv.available <= start and not srv.stopped and waited < 3.0:
                if srv.complete:
                    break
                time.sleep(0.3)
                waited += 0.3
            if srv.available <= start and not srv.complete:
                self.send_response(416)
                self.send_header(
                    'Content-Range', f'bytes */{total}',
                )
                self.end_headers()
                return

        if range_hdr:
            self.send_response(206)
            self.send_header(
                'Content-Range', f'bytes {start}-{end}/{total}',
            )
        else:
            self.send_response(200)

        length = end - start + 1
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(length))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()

        chunk_size = 128 * 1024
        pos = start
        try:
            with open(srv.video_path, 'rb') as f:
                f.seek(pos)
                while pos <= end:
                    # Wait for data to become available (sequential download)
                    need = pos + 1
                    waited = 0.0
                    while srv.available < need and not srv.stopped:
                        if srv.complete:
                            break
                        time.sleep(0.3)
                        waited += 0.3
                        # Timeout for non-sequential reads (30s)
                        if waited > 30.0:
                            return
                    if srv.stopped:
                        return
                    # Read up to available data or chunk_size
                    readable = min(srv.available - pos, chunk_size, end - pos + 1)
                    if srv.complete:
                        readable = min(chunk_size, end - pos + 1)
                    if readable <= 0:
                        readable = min(chunk_size, end - pos + 1)
                    data = f.read(readable)
                    if not data:
                        break
                    self.wfile.write(data)
                    pos += len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class _StreamingServer(socketserver.ThreadingTCPServer):
    """Local HTTP server that serves a torrent video file as it downloads."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), _StreamingHandler)
        self.video_path = ''
        self.total_size = 0
        self.available = 0
        self.complete = False
        self.stopped = False

    @property
    def url(self):
        port = self.server_address[1]
        return f'http://127.0.0.1:{port}/video'

    def configure(self, path, total_size, initial_available):
        self.video_path = path
        self.total_size = total_size
        self.available = initial_available
        self.complete = False
        self.stopped = False

    def start_serving(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def stop_serving(self):
        self.stopped = True
        try:
            self.shutdown()
        except Exception:
            pass


try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    lt = None
    LIBTORRENT_AVAILABLE = False


class TorrentStreamer:
    """Manages a single torrent streaming session (download only)."""

    def __init__(self):
        cache_base = os.environ.get(
            'XDG_CACHE_HOME', os.path.expanduser('~/.cache'),
        )
        self._save_dir = os.path.join(cache_base, 'kadr', 'streaming')
        self._session = None
        self._handle = None
        self._monitor_thread = None
        self._stopping = False
        self._status_cb = None
        self._lock = threading.Lock()
        self._server = None
        self.log = StreamLog()

    @property
    def is_active(self):
        with self._lock:
            return self._handle is not None and not self._stopping

    def start(self, magnet_uri, status_cb=None, torrent_link=None):
        """Start streaming from a magnet URI or .torrent link.

        If *torrent_link* is provided, attempts to download the .torrent file
        first (avoids the slow DHT metadata phase).  Falls back to magnet.

        status_cb(state: str, detail: str) is called on the GTK main thread.
        States: 'metadata', 'buffering', 'ready', 'downloading', 'error', 'stopped'.
        The 'ready' state carries the video file path as detail.
        """
        if not LIBTORRENT_AVAILABLE:
            raise RuntimeError('libtorrent не установлен')
        if self.is_active:
            self.stop()

        self._stopping = False
        self._status_cb = status_cb
        self.log.clear()
        self.log.log(f'start: magnet={bool(magnet_uri)} link={bool(torrent_link)}')
        self.log.log(f'save_dir={self._save_dir}')
        os.makedirs(self._save_dir, exist_ok=True)

        self._session = lt.session({
            'listen_interfaces': '0.0.0.0:6881,[::]:6891',
            'alert_mask': (
                lt.alert.category_t.status_notification
                | lt.alert.category_t.dht_notification
                | lt.alert.category_t.error_notification
            ),
            'enable_dht': True,
            'enable_lsd': True,
            'dht_bootstrap_nodes': (
                'router.bittorrent.com:6881,'
                'router.utorrent.com:6881,'
                'dht.transmissionbt.com:6881,'
                'dht.libtorrent.org:25401'
            ),
        })
        self._session.apply_settings({
            'active_downloads': 1,
            'active_seeds': 0,
        })

        # Try .torrent file first (already contains metadata → instant start)
        self.log.log(f'trying .torrent link: {torrent_link[:120] if torrent_link else "(none)"}')
        atp = self._atp_from_link(torrent_link) if torrent_link else None

        if atp is not None:
            self.log.log('torrent file parsed — metadata available immediately')
        elif magnet_uri:
            self.log.log('falling back to magnet URI')
            atp = lt.parse_magnet_uri(magnet_uri)
            self._emit('metadata', 'Получение метаданных…')
        else:
            self.log.log('ERROR: no link and no magnet')

        if atp is None:
            self._emit('error', 'Нет ссылки для загрузки')
            return

        atp.save_path = self._save_dir
        self._handle = self._session.add_torrent(atp)
        self._handle.set_sequential_download(True)
        self._handle.force_reannounce()
        self.log.log('torrent added to session, monitor starting')

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True,
        )
        self._monitor_thread.start()

    def stop(self):
        """Stop streaming and clean up."""
        self.log.log('stop() called')
        with self._lock:
            if self._stopping:
                self.log.log('stop() — already stopping')
                return
            self._stopping = True

        if self._server:
            self._server.stop_serving()
            self._server = None

        if self._session and self._handle:
            try:
                self._session.remove_torrent(self._handle)
            except Exception:
                pass
        self._handle = None
        self._session = None
        self._emit('stopped', '')

    def cleanup_files(self):
        """Remove cached streaming files."""
        if os.path.isdir(self._save_dir):
            for name in os.listdir(self._save_dir):
                path = os.path.join(self._save_dir, name)
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
                except OSError:
                    pass

    # ── Internal ──────────────────────────────────────────────

    def _atp_from_link(self, link):
        """Download a .torrent file from *link* and return add_torrent_params, or None."""
        try:
            resp = requests.get(link, timeout=15)
            resp.raise_for_status()
            data = resp.content
            self.log.log(f'torrent download: {len(data)} bytes, status={resp.status_code}')
            if not data or data[0:1] != b'd':
                self.log.log(f'torrent data invalid: starts with {data[:10]!r}')
                return None
            ti = lt.torrent_info(lt.bdecode(data))
            self.log.log(f'torrent parsed: "{ti.name()}", {ti.files().num_files()} files')
            atp = lt.add_torrent_params()
            atp.ti = ti
            return atp
        except Exception as exc:
            self.log.log(f'torrent download failed: {exc}')
            return None

    def _emit(self, state, detail):
        self.log.log(f'emit: state={state} detail={detail}')
        cb = self._status_cb
        if cb:
            GLib.idle_add(cb, state, detail)

    def _find_video_file(self, torrent_info):
        """Return (file_index, file_entry) for the largest video file."""
        best_idx, best_size = -1, 0
        fs = torrent_info.files()
        for i in range(fs.num_files()):
            path = fs.file_path(i)
            ext = os.path.splitext(path)[1].lower()
            if ext in _VIDEO_EXTENSIONS and fs.file_size(i) > best_size:
                best_idx = i
                best_size = fs.file_size(i)
        return best_idx

    def _prioritize_video(self, torrent_info, video_idx):
        """Set only the video file to highest priority, skip others."""
        num_files = torrent_info.files().num_files()
        priorities = [0] * num_files
        priorities[video_idx] = 7
        self._handle.prioritize_files(priorities)

    def _start_server(self, path, total_size, initial_available):
        """Create and start the local HTTP streaming server."""
        self._server = _StreamingServer()
        self._server.configure(path, total_size, initial_available)
        self._server.start_serving()
        self.log.log(f'HTTP streaming: {self._server.url} (size={total_size})')

    def _monitor_loop(self):
        ready_emitted = False
        video_idx = -1
        video_path = None
        video_size = 0

        while not self._stopping:
            time.sleep(1)

            if not self._handle or not self._handle.is_valid():
                break

            status = self._handle.status()

            # ── Waiting for metadata ──
            if not status.has_metadata:
                self.log.log(f'waiting metadata: peers={status.num_peers}')
                self._emit('metadata', 'Получение метаданных…')
                continue

            # ── Find video file once ──
            if video_idx < 0:
                ti = self._handle.torrent_file()
                video_idx = self._find_video_file(ti)
                if video_idx < 0:
                    self._emit('error', 'Видеофайл не найден в торренте')
                    self.stop()
                    return
                self._prioritize_video(ti, video_idx)
                video_path = os.path.join(
                    self._save_dir, ti.files().file_path(video_idx),
                )
                video_size = ti.files().file_size(video_idx)
                self.log.log(f'video file idx={video_idx} size={video_size} path={video_path}')

            # ── Buffering / downloading stats ──
            done = status.total_wanted_done
            rate = status.download_rate
            rate_str = f'{rate / 1024:.0f} КБ/с' if rate > 0 else ''
            pct = status.progress * 100

            if not ready_emitted:
                exists = os.path.exists(video_path)
                self.log.log(f'buffer: done={done} threshold={_BUFFER_THRESHOLD} exists={exists}')
                if done >= _BUFFER_THRESHOLD and exists:
                    self._start_server(video_path, video_size, done)
                    self._emit('ready', self._server.url)
                    ready_emitted = True
                else:
                    buf_pct = min(100, done * 100 // _BUFFER_THRESHOLD) if _BUFFER_THRESHOLD else 100
                    self._emit(
                        'buffering',
                        f'Буферизация {buf_pct}%  {rate_str}',
                    )
                    continue

            # ── Update streaming server with download progress ──
            if self._server:
                self._server.available = done
                if pct >= 100:
                    self._server.complete = True

            # ── Downloading (player is active in UI) ──
            self._emit('downloading', f'{pct:.1f}%  {rate_str}')

            if status.state in (lt.torrent_status.seeding, lt.torrent_status.finished):
                self._emit('downloading', '100%')
                # Keep session alive; UI will call stop() when user navigates back
                while not self._stopping:
                    time.sleep(1)
                return

        # Thread exits when stopping
        if not self._stopping:
            self.stop()
