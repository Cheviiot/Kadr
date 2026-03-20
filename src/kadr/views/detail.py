import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from kadr.utils import run_async, load_image_async, copy_to_clipboard
from kadr.widgets.torrent_row import TorrentRow


class DetailView:
    """Detail view showing movie/TV info and torrent search results."""

    def __init__(self, window, media_type, data):
        self.window = window
        self.media_type = media_type
        self.data = data
        self._build()
        self._search_torrents()

    @property
    def page(self):
        return self._page

    # ── Build UI ──────────────────────────────────────────────

    def _build(self):
        from kadr.widgets.media_card import _resolve_title
        title, year_str = _resolve_title(self.data, self.media_type)
        self._page = Adw.NavigationPage(title=title)

        toolbar_view = Adw.ToolbarView()
        self._page.set_child(toolbar_view)

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        scrolled.set_child(content)

        # ── Info section (poster + details) ───────────────────

        info_box = Gtk.Box(spacing=24)
        content.append(info_box)

        # Poster
        poster_frame = Gtk.Frame()
        poster_frame.add_css_class('card')
        poster_frame.set_overflow(Gtk.Overflow.HIDDEN)
        self._poster = Gtk.Picture()
        self._poster.set_size_request(240, 360)
        self._poster.set_content_fit(Gtk.ContentFit.COVER)
        poster_frame.set_child(self._poster)
        info_box.append(poster_frame)

        poster_path = self.data.get('poster_path', '')
        if poster_path:
            url = self.window.tmdb.image_url(poster_path, 'w500')
            load_image_async(url, 240, 360, self._on_poster_loaded)

        # Details column
        details = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            hexpand=True,
            valign=Gtk.Align.START,
        )
        info_box.append(details)

        # Title
        title_label = Gtk.Label(label=title, xalign=0, wrap=True)
        title_label.add_css_class('title-1')
        details.append(title_label)

        # Meta (rating, year)
        meta = Gtk.Box(spacing=12)
        details.append(meta)

        rating = self.data.get('vote_average', 0)
        if rating > 0:
            rating_lbl = Gtk.Label(label=f'★ {rating:.1f}')
            rating_lbl.add_css_class('rating-badge')
            meta.append(rating_lbl)

        if year_str:
            year_lbl = Gtk.Label(label=year_str)
            year_lbl.add_css_class('dim-label')
            meta.append(year_lbl)

        # Overview
        overview = self.data.get('overview', '')
        if overview:
            desc = Gtk.Label(
                label=overview, xalign=0, wrap=True, max_width_chars=80,
            )
            desc.set_valign(Gtk.Align.START)
            details.append(desc)

        # ── Torrents section ──────────────────────────────────

        content.append(Gtk.Separator())

        torrents_header = Gtk.Box(spacing=12)
        content.append(torrents_header)

        torrents_title = Gtk.Label(
            label='Торренты', xalign=0, hexpand=True,
        )
        torrents_title.add_css_class('title-2')
        torrents_header.append(torrents_title)

        refresh_btn = Gtk.Button(
            icon_name='view-refresh-symbolic',
            tooltip_text='Обновить',
        )
        refresh_btn.connect('clicked', lambda *_: self._search_torrents())
        torrents_header.append(refresh_btn)

        self._torrents_spinner = Gtk.Spinner(
            spinning=True,
            halign=Gtk.Align.CENTER,
        )
        self._torrents_spinner.set_size_request(32, 32)
        self._torrents_spinner.set_margin_top(24)
        self._torrents_spinner.set_margin_bottom(24)
        content.append(self._torrents_spinner)

        self._status_label = Gtk.Label(
            halign=Gtk.Align.CENTER, visible=False,
        )
        self._status_label.add_css_class('dim-label')
        content.append(self._status_label)

        self._torrent_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.NONE,
            visible=False,
        )
        self._torrent_list.add_css_class('boxed-list')
        content.append(self._torrent_list)

    # ── Poster callback ───────────────────────────────────────

    def _on_poster_loaded(self, texture):
        if texture:
            self._poster.set_paintable(texture)

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
        for torrent in results:
            row = TorrentRow(
                torrent=torrent,
                on_download=self._on_download,
                on_copy=self._on_copy_magnet,
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

    # ── Helpers ───────────────────────────────────────────────

    def _clear_list(self):
        while True:
            child = self._torrent_list.get_first_child()
            if child is None:
                break
            self._torrent_list.remove(child)
