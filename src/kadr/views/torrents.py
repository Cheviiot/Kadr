"""Torrents page — search, download, and stream torrents for a title."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from kadr.utils import run_async, copy_to_clipboard
from kadr.widgets.torrent_row import TorrentRow
from kadr.services.streamer import LIBTORRENT_AVAILABLE
from kadr.widgets.mpv_widget import MPV_AVAILABLE


class TorrentsView:
    """Navigation page for browsing and streaming torrents."""

    def __init__(self, window, media_type, data, title):
        self.window = window
        self.media_type = media_type
        self.data = data
        self._player_view = None
        self._build(title)
        self._search_torrents()

    @property
    def page(self):
        return self._page

    # ── Build UI ──────────────────────────────────────────────

    def _build(self, title):
        self._page = Adw.NavigationPage(title='Просмотр')
        self._page.connect('hidden', self._on_page_hidden)

        toolbar_view = Adw.ToolbarView()
        self._page.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title='Просмотр', subtitle=title))
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=16,
        )
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(24)
        scrolled.set_child(content)

        # ── Streaming status banner ──
        self._stream_banner = Adw.Banner(revealed=False)
        self._stream_banner.set_button_label('Остановить')
        self._stream_banner.connect(
            'button-clicked', lambda *_: self._stop_stream(),
        )
        content.append(self._stream_banner)

        # ── Torrents header ──
        torrents_header = Gtk.Box(spacing=12)
        content.append(torrents_header)

        torrents_title = Gtk.Label(
            label='Торренты', xalign=0, hexpand=True,
        )
        torrents_title.add_css_class('title-3')
        torrents_header.append(torrents_title)

        refresh_btn = Gtk.Button(
            icon_name='view-refresh-symbolic',
            tooltip_text='Обновить',
        )
        refresh_btn.add_css_class('flat')
        refresh_btn.connect('clicked', lambda *_: self._search_torrents())
        torrents_header.append(refresh_btn)

        # Spinner
        self._torrents_spinner = Gtk.Spinner(
            spinning=True, halign=Gtk.Align.CENTER,
        )
        self._torrents_spinner.set_size_request(32, 32)
        self._torrents_spinner.set_margin_top(16)
        self._torrents_spinner.set_margin_bottom(16)
        content.append(self._torrents_spinner)

        # Status label
        self._status_label = Gtk.Label(
            halign=Gtk.Align.CENTER, visible=False,
        )
        self._status_label.add_css_class('dim-label')
        content.append(self._status_label)

        # Torrent list
        self._torrent_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            visible=False,
        )
        self._torrent_list.add_css_class('boxed-list')
        content.append(self._torrent_list)

        # ── Stream log panel ──
        self._log_expander = Gtk.Expander(label='Лог стриминга', expanded=False)
        self._log_expander.set_visible(False)
        content.append(self._log_expander)

        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._log_expander.set_child(log_box)

        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_min_content_height(200)
        log_scroll.set_max_content_height(400)
        log_box.append(log_scroll)

        self._log_textview = Gtk.TextView(
            editable=False,
            monospace=True,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=4,
            bottom_margin=4,
            left_margin=8,
            right_margin=8,
        )
        self._log_textview.add_css_class('card')
        log_scroll.set_child(self._log_textview)

        copy_log_btn = Gtk.Button(label='Скопировать лог', halign=Gtk.Align.END)
        copy_log_btn.set_margin_top(4)
        copy_log_btn.connect('clicked', self._copy_log)
        log_box.append(copy_log_btn)

    # ── Torrent search ────────────────────────────────────────

    def _search_torrents(self):
        self._torrents_spinner.set_visible(True)
        self._torrents_spinner.set_spinning(True)
        self._status_label.set_visible(False)
        self._torrent_list.set_visible(False)
        self._clear_list()

        queries = self._build_queries()
        run_async(
            self._search_with_fallback,
            self._on_torrents_loaded,
            queries,
        )

    def _build_queries(self):
        queries = []
        if self.media_type == 'movie':
            orig = self.data.get('original_title', '')
            title = self.data.get('title', '')
            date = self.data.get('release_date', '')
        else:
            orig = self.data.get('original_name', '')
            title = self.data.get('name', '')
            date = self.data.get('first_air_date', '')

        year = date[:4] if date and len(date) >= 4 else ''

        if orig:
            queries.append(orig)
        if title and title != orig:
            queries.append(title)
        if orig and year:
            queries.append(f'{orig} {year}')

        return queries or [title or orig]

    def _search_with_fallback(self, queries):
        server_id = self.window.jackett.resolve_server_id()
        last_err = None
        for query in queries:
            try:
                results = self.window.jackett.search(server_id, query)
                if results:
                    return results
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err
        return []

    def _on_torrents_loaded(self, results, error):
        self._torrents_spinner.set_visible(False)
        self._torrents_spinner.set_spinning(False)

        if error:
            self._status_label.set_label(f'Ошибка: {error}')
            self._status_label.set_visible(True)
            return

        if not results:
            self._status_label.set_label('Торренты не найдены')
            self._status_label.set_visible(True)
            return

        self._torrent_list.set_visible(True)
        can_stream = LIBTORRENT_AVAILABLE and MPV_AVAILABLE
        for torrent in results:
            row = TorrentRow(
                torrent=torrent,
                on_download=self._on_download,
                on_copy=self._on_copy_magnet,
                on_stream=self._on_stream if can_stream else None,
            )
            self._torrent_list.append(row)

    # ── Torrent actions ───────────────────────────────────────

    def _on_download(self, torrent):
        magnet = torrent.get('magnet_uri', '')
        link = torrent.get('link', '')
        name = torrent.get('title', '')

        try:
            if magnet:
                client = self.window.downloads.send_magnet(magnet, name)
            elif link:
                client = self.window.downloads.send_torrent_url(link, name)
            else:
                self.window.show_toast('Нет ссылки для скачивания')
                return
            self.window.show_toast(f'Отправлено в {client}')
        except Exception as e:
            self.window.show_toast(str(e))

    def _on_copy_magnet(self, torrent):
        magnet = torrent.get('magnet_uri', '')
        if not magnet:
            self.window.show_toast('Магнет-ссылка недоступна')
            return
        try:
            copy_to_clipboard(magnet)
            self.window.show_toast('Магнет-ссылка скопирована')
        except Exception as e:
            self.window.show_toast(str(e))

    # ── Streaming ─────────────────────────────────────────────

    def _on_stream(self, torrent):
        magnet = torrent.get('magnet_uri', '')
        link = torrent.get('link', '')
        if not magnet and not link:
            self.window.show_toast('Нет ссылки для воспроизведения')
            return

        self._log_expander.set_visible(True)
        self._log_expander.set_expanded(True)
        buf = self._log_textview.get_buffer()
        buf.set_text('')
        self.window.streamer.log.clear()
        self.window.streamer.log.set_on_update(self._on_log_line)
        try:
            self.window.streamer.start(
                magnet, self._on_stream_status, torrent_link=link,
            )
        except Exception as e:
            self.window.show_toast(str(e))

    def _on_stream_status(self, state, detail):
        if state == 'error':
            self._stream_banner.set_revealed(False)
            self._cleanup_player()
            self.window.show_toast(detail)
            return
        if state == 'stopped':
            self._stream_banner.set_revealed(False)
            return
        if state == 'ready':
            self._stream_banner.set_revealed(False)
            self._open_player(detail)
            return
        if state == 'downloading' and self._player_view:
            self._player_view.set_download_info(detail)
            return
        label_map = {
            'metadata': f'⏳ {detail}',
            'buffering': f'⏳ {detail}',
        }
        self._stream_banner.set_title(label_map.get(state, detail))
        self._stream_banner.set_revealed(True)

    def _open_player(self, video_path):
        from kadr.views.player import PlayerView
        slog = self.window.streamer.log
        slog.log(f'opening player: {video_path}')
        self._player_view = PlayerView(
            self.window, title=self._page.get_title(),
        )
        self._player_view.set_log_callback(slog.log)
        self._player_view.page.connect(
            'hidden', lambda _: self._on_player_closed(),
        )
        self.window.nav_view.push(self._player_view.page)
        self._player_view.play(video_path)

    def _on_player_closed(self):
        if self._player_view:
            self._player_view.shutdown()
            self._player_view = None
        self.window.streamer.stop()

    def _cleanup_player(self):
        if self._player_view:
            self._player_view.shutdown()
            self._player_view = None
            self.window.nav_view.pop_to_page(self._page)

    def _stop_stream(self):
        self.window.streamer.stop()
        self._stream_banner.set_revealed(False)
        self._cleanup_player()

    def _on_page_hidden(self, _page):
        if self._player_view is not None:
            return
        self._stop_stream()

    # ── Helpers ───────────────────────────────────────────────

    def _on_log_line(self, line):
        buf = self._log_textview.get_buffer()
        end_iter = buf.get_end_iter()
        if buf.get_char_count() > 0:
            buf.insert(end_iter, '\n')
            end_iter = buf.get_end_iter()
        buf.insert(end_iter, line)
        end_mark = buf.create_mark(None, buf.get_end_iter(), False)
        self._log_textview.scroll_mark_onscreen(end_mark)
        buf.delete_mark(end_mark)

    def _copy_log(self, _btn):
        text = self.window.streamer.log.text()
        if not text:
            self.window.show_toast('Лог пуст')
            return
        try:
            copy_to_clipboard(text)
            self.window.show_toast('Лог скопирован')
        except Exception as e:
            self.window.show_toast(str(e))

    def _clear_list(self):
        while True:
            child = self._torrent_list.get_first_child()
            if child is None:
                break
            self._torrent_list.remove(child)
