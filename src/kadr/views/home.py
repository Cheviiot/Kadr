import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gio, GObject, GLib

from kadr.utils import run_async
from kadr.widgets.media_card import MediaCard, _has_ru_title


class HomeView:
    """Home view with popular movies/TV grids and search."""

    def __init__(self, window):
        self.window = window
        self._movies_page = 1
        self._movies_total = 999
        self._tv_page = 1
        self._tv_total = 999
        self._loading_movies = False
        self._loading_tv = False
        self._search_mode = False
        self._search_query = ''
        self._search_movies_page = 1
        self._search_movies_total = 0
        self._search_tv_page = 1
        self._search_tv_total = 0
        self._seen_movie_ids = set()
        self._seen_tv_ids = set()
        self._build()
        self._load_popular_movies()
        self._load_popular_tv()

    @property
    def page(self):
        return self._page

    def toggle_search(self):
        active = self._search_btn.get_active()
        self._search_btn.set_active(not active)

    # ── Build UI ──────────────────────────────────────────────

    def _build(self):
        self._page = Adw.NavigationPage(title='Kadr')

        toolbar_view = Adw.ToolbarView()
        self._page.set_child(toolbar_view)

        # Header bar
        header = Adw.HeaderBar()

        self._search_btn = Gtk.ToggleButton(icon_name='system-search-symbolic')
        self._search_btn.set_tooltip_text('Поиск (Ctrl+F)')
        header.pack_start(self._search_btn)

        self._stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcherTitle(stack=self._stack)
        header.set_title_widget(switcher)

        menu = Gio.Menu()
        menu.append('Настройки', 'app.preferences')
        menu.append('О приложении', 'app.about')
        menu_btn = Gtk.MenuButton(
            icon_name='open-menu-symbolic',
            menu_model=menu,
            primary=True,
        )
        menu_btn.set_tooltip_text('Меню')
        header.pack_end(menu_btn)

        toolbar_view.add_top_bar(header)

        # Search bar
        self._search_bar = Gtk.SearchBar()
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_placeholder_text('Поиск фильмов и сериалов...')
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_btn.bind_property(
            'active', self._search_bar, 'search-mode-enabled',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self._search_entry.connect('activate', self._on_search)
        self._search_entry.connect('stop-search', self._on_search_stopped)
        toolbar_view.add_top_bar(self._search_bar)

        # Movies tab
        movies_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._movies_scroll = movies_scroll
        movies_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._movies_flow = Gtk.FlowBox(
            homogeneous=False,
            min_children_per_line=2,
            max_children_per_line=20,
            row_spacing=12,
            column_spacing=12,
            selection_mode=Gtk.SelectionMode.NONE,
        )
        self._movies_flow.set_valign(Gtk.Align.START)
        self._movies_flow.set_halign(Gtk.Align.CENTER)
        self._movies_flow.set_margin_start(16)
        self._movies_flow.set_margin_end(16)
        self._movies_flow.set_margin_top(16)
        self._movies_flow.set_margin_bottom(8)
        movies_content.append(self._movies_flow)

        self._movies_spinner = Gtk.Spinner(
            spinning=True,
            halign=Gtk.Align.CENTER,
        )
        self._movies_spinner.set_size_request(32, 32)
        self._movies_spinner.set_margin_top(16)
        self._movies_spinner.set_margin_bottom(24)
        movies_content.append(self._movies_spinner)

        movies_scroll.set_child(movies_content)
        movies_scroll.get_vadjustment().connect(
            'value-changed', self._on_movies_scroll,
        )
        page = self._stack.add_titled(movies_scroll, 'movies', 'Фильмы')
        page.set_icon_name('video-display-symbolic')

        # TV tab
        tv_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._tv_scroll = tv_scroll
        tv_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._tv_flow = Gtk.FlowBox(
            homogeneous=False,
            min_children_per_line=2,
            max_children_per_line=20,
            row_spacing=12,
            column_spacing=12,
            selection_mode=Gtk.SelectionMode.NONE,
        )
        self._tv_flow.set_valign(Gtk.Align.START)
        self._tv_flow.set_halign(Gtk.Align.CENTER)
        self._tv_flow.set_margin_start(16)
        self._tv_flow.set_margin_end(16)
        self._tv_flow.set_margin_top(16)
        self._tv_flow.set_margin_bottom(8)
        tv_content.append(self._tv_flow)

        self._tv_spinner = Gtk.Spinner(
            spinning=True,
            halign=Gtk.Align.CENTER,
        )
        self._tv_spinner.set_size_request(32, 32)
        self._tv_spinner.set_margin_top(16)
        self._tv_spinner.set_margin_bottom(24)
        tv_content.append(self._tv_spinner)

        tv_scroll.set_child(tv_content)
        tv_scroll.get_vadjustment().connect(
            'value-changed', self._on_tv_scroll,
        )
        page = self._stack.add_titled(tv_scroll, 'tv', 'Сериалы')
        page.set_icon_name('tv-symbolic')

        toolbar_view.set_content(self._stack)

    # ── Data loading ──────────────────────────────────────────

    @staticmethod
    def _viewport_not_filled(scroll):
        """Return True if content doesn't fill the visible area."""
        adj = scroll.get_vadjustment()
        return adj.get_upper() <= adj.get_page_size() + 100

    def _load_popular_movies(self):
        if self._loading_movies or self._movies_page > self._movies_total:
            return
        self._loading_movies = True
        self._movies_spinner.set_spinning(True)
        self._movies_spinner.set_visible(True)
        run_async(
            self.window.tmdb.popular_movies,
            self._on_movies_loaded,
            self._movies_page,
        )

    def _on_movies_loaded(self, data, error):
        self._loading_movies = False
        if error:
            self._movies_spinner.set_spinning(False)
            self._movies_spinner.set_visible(False)
            self.window.show_toast(f'Ошибка: {error}')
            return

        self._movies_total = data.get('total_pages', 1)
        results = data.get('results', [])

        for movie in results:
            mid = movie.get('id')
            if mid in self._seen_movie_ids:
                continue
            if not _has_ru_title(movie, 'movie'):
                continue
            self._seen_movie_ids.add(mid)
            card = MediaCard(
                data=movie,
                media_type='movie',
                image_url=self.window.tmdb.image_url(
                    movie.get('poster_path'), 'w342',
                ),
                on_click=self._on_card_clicked,
            )
            self._movies_flow.append(card)
        self._movies_page += 1

        has_more = self._movies_page <= self._movies_total
        self._movies_spinner.set_spinning(has_more)
        self._movies_spinner.set_visible(has_more)

        # Auto-load next page if viewport isn't filled yet
        if has_more:
            GLib.idle_add(self._maybe_load_more_movies)

    def _maybe_load_more_movies(self):
        if self._viewport_not_filled(self._movies_scroll):
            if self._search_mode:
                self._load_search_movies_next()
            else:
                self._load_popular_movies()
        return False

    def _load_popular_tv(self):
        if self._loading_tv or self._tv_page > self._tv_total:
            return
        self._loading_tv = True
        self._tv_spinner.set_spinning(True)
        self._tv_spinner.set_visible(True)
        run_async(
            self.window.tmdb.popular_tv,
            self._on_tv_loaded,
            self._tv_page,
        )

    def _on_tv_loaded(self, data, error):
        self._loading_tv = False
        if error:
            self._tv_spinner.set_spinning(False)
            self._tv_spinner.set_visible(False)
            self.window.show_toast(f'Ошибка: {error}')
            return

        self._tv_total = data.get('total_pages', 1)
        results = data.get('results', [])

        for show in results:
            sid = show.get('id')
            if sid in self._seen_tv_ids:
                continue
            if not _has_ru_title(show, 'tv'):
                continue
            self._seen_tv_ids.add(sid)
            card = MediaCard(
                data=show,
                media_type='tv',
                image_url=self.window.tmdb.image_url(
                    show.get('poster_path'), 'w342',
                ),
                on_click=self._on_card_clicked,
            )
            self._tv_flow.append(card)
        self._tv_page += 1

        has_more = self._tv_page <= self._tv_total
        self._tv_spinner.set_spinning(has_more)
        self._tv_spinner.set_visible(has_more)

        # Auto-load next page if viewport isn't filled yet
        if has_more:
            GLib.idle_add(self._maybe_load_more_tv)

    def _maybe_load_more_tv(self):
        if self._viewport_not_filled(self._tv_scroll):
            if self._search_mode:
                self._load_search_tv_next()
            else:
                self._load_popular_tv()
        return False

    # ── Infinite scroll ───────────────────────────────────────

    def _near_bottom(self, adj):
        return adj.get_value() + adj.get_page_size() >= adj.get_upper() - 800

    def _on_movies_scroll(self, adj):
        if self._near_bottom(adj):
            if self._search_mode:
                self._load_search_movies_next()
            elif not self._loading_movies:
                self._load_popular_movies()

    def _on_tv_scroll(self, adj):
        if self._near_bottom(adj):
            if self._search_mode:
                self._load_search_tv_next()
            elif not self._loading_tv:
                self._load_popular_tv()

    # ── Search ────────────────────────────────────────────────

    def _on_search(self, entry):
        query = entry.get_text().strip()
        if not query:
            return
        self._search_mode = True
        self._search_query = query
        self._search_movies_page = 1
        self._search_movies_total = 0
        self._search_tv_page = 1
        self._search_tv_total = 0
        self._seen_movie_ids.clear()
        self._seen_tv_ids.clear()
        self._clear_flow(self._movies_flow)
        self._clear_flow(self._tv_flow)
        self._movies_spinner.set_spinning(True)
        self._movies_spinner.set_visible(True)
        self._tv_spinner.set_spinning(True)
        self._tv_spinner.set_visible(True)
        self._loading_movies = True
        self._loading_tv = True

        run_async(
            self.window.tmdb.search_movies,
            self._on_search_movies_done,
            query,
        )
        run_async(
            self.window.tmdb.search_tv,
            self._on_search_tv_done,
            query,
        )

    def _on_search_movies_done(self, data, error):
        self._loading_movies = False
        if error:
            self._movies_spinner.set_spinning(False)
            self._movies_spinner.set_visible(False)
            self.window.show_toast(f'Ошибка поиска: {error}')
            return

        self._search_movies_total = data.get('total_pages', 1)
        for movie in data.get('results', []):
            mid = movie.get('id')
            if mid in self._seen_movie_ids:
                continue
            if not _has_ru_title(movie, 'movie'):
                continue
            self._seen_movie_ids.add(mid)
            card = MediaCard(
                data=movie,
                media_type='movie',
                image_url=self.window.tmdb.image_url(
                    movie.get('poster_path'), 'w342',
                ),
                on_click=self._on_card_clicked,
            )
            self._movies_flow.append(card)
        self._search_movies_page += 1

        has_more = self._search_movies_page <= self._search_movies_total
        self._movies_spinner.set_spinning(has_more)
        self._movies_spinner.set_visible(has_more)

        if has_more:
            GLib.idle_add(self._maybe_load_more_movies)

    def _on_search_tv_done(self, data, error):
        self._loading_tv = False
        if error:
            self._tv_spinner.set_spinning(False)
            self._tv_spinner.set_visible(False)
            self.window.show_toast(f'Ошибка поиска: {error}')
            return

        self._search_tv_total = data.get('total_pages', 1)
        for show in data.get('results', []):
            sid = show.get('id')
            if sid in self._seen_tv_ids:
                continue
            if not _has_ru_title(show, 'tv'):
                continue
            self._seen_tv_ids.add(sid)
            card = MediaCard(
                data=show,
                media_type='tv',
                image_url=self.window.tmdb.image_url(
                    show.get('poster_path'), 'w342',
                ),
                on_click=self._on_card_clicked,
            )
            self._tv_flow.append(card)
        self._search_tv_page += 1

        has_more = self._search_tv_page <= self._search_tv_total
        self._tv_spinner.set_spinning(has_more)
        self._tv_spinner.set_visible(has_more)

        if has_more:
            GLib.idle_add(self._maybe_load_more_tv)

    def _load_search_movies_next(self):
        if self._loading_movies:
            return
        if self._search_movies_page > self._search_movies_total:
            return
        self._loading_movies = True
        self._movies_spinner.set_spinning(True)
        self._movies_spinner.set_visible(True)
        run_async(
            self.window.tmdb.search_movies,
            self._on_search_movies_done,
            self._search_query,
            self._search_movies_page,
        )

    def _load_search_tv_next(self):
        if self._loading_tv:
            return
        if self._search_tv_page > self._search_tv_total:
            return
        self._loading_tv = True
        self._tv_spinner.set_spinning(True)
        self._tv_spinner.set_visible(True)
        run_async(
            self.window.tmdb.search_tv,
            self._on_search_tv_done,
            self._search_query,
            self._search_tv_page,
        )

    def _on_search_stopped(self, entry):
        self._search_btn.set_active(False)
        if self._search_mode:
            self._search_mode = False
            self._refresh_popular()

    def _refresh_popular(self):
        self._clear_flow(self._movies_flow)
        self._clear_flow(self._tv_flow)
        self._seen_movie_ids.clear()
        self._seen_tv_ids.clear()
        self._movies_page = 1
        self._movies_total = 999
        self._tv_page = 1
        self._tv_total = 999
        self._load_popular_movies()
        self._load_popular_tv()

    # ── Events ────────────────────────────────────────────────

    def _on_card_clicked(self, media_type, data):
        self.window.show_detail(media_type, data)

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _clear_flow(flow):
        while True:
            child = flow.get_child_at_index(0)
            if child is None:
                break
            flow.remove(child)
