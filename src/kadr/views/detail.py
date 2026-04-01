import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from kadr.utils import run_async, load_image_async


def _fmt_runtime(minutes):
    if not minutes:
        return ''
    h, m = divmod(int(minutes), 60)
    return f'{h} ч {m} мин' if h else f'{m} мин'


class DetailView:
    """Detail view styled as a streaming platform page."""

    def __init__(self, window, media_type, data):
        self.window = window
        self.media_type = media_type
        self.data = data
        self._build()
        self._load_details()

    @property
    def page(self):
        return self._page

    # ── Build UI ──────────────────────────────────────────────

    def _build(self):
        from kadr.widgets.media_card import _resolve_title
        title, year_str = _resolve_title(self.data, self.media_type)
        self._title = title
        self._year_str = year_str

        self._page = Adw.NavigationPage(title=title)
        toolbar_view = Adw.ToolbarView()
        self._page.set_child(toolbar_view)

        header = Adw.HeaderBar()
        header.add_css_class('flat')
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled.set_child(content)

        # ── Hero section (backdrop + gradient + poster + info) ──
        hero_overlay = Gtk.Overlay()
        hero_overlay.set_size_request(-1, 420)
        content.append(hero_overlay)

        # Backdrop image
        self._backdrop = Gtk.Picture()
        self._backdrop.set_content_fit(Gtk.ContentFit.COVER)
        self._backdrop.set_size_request(-1, 420)
        self._backdrop.add_css_class('detail-backdrop')
        hero_overlay.set_child(self._backdrop)

        backdrop_path = self.data.get('backdrop_path', '')
        if backdrop_path:
            url = self.window.tmdb.image_url(backdrop_path, 'w1280')
            load_image_async(url, 1280, 720, self._on_backdrop_loaded)

        # Gradient overlay
        gradient = Gtk.Box()
        gradient.add_css_class('detail-hero-gradient')
        gradient.set_vexpand(True)
        gradient.set_hexpand(True)
        hero_overlay.add_overlay(gradient)

        # Hero content (poster + info)
        hero_content = Gtk.Box(spacing=24, valign=Gtk.Align.END)
        hero_content.set_margin_start(32)
        hero_content.set_margin_end(32)
        hero_content.set_margin_bottom(32)
        hero_overlay.add_overlay(hero_content)

        # Poster
        poster_frame = Gtk.Frame()
        poster_frame.add_css_class('detail-poster-frame')
        poster_frame.set_overflow(Gtk.Overflow.HIDDEN)
        poster_frame.set_valign(Gtk.Align.END)
        self._poster = Gtk.Picture()
        self._poster.set_size_request(180, 270)
        self._poster.set_content_fit(Gtk.ContentFit.COVER)
        poster_frame.set_child(self._poster)
        hero_content.append(poster_frame)

        poster_path = self.data.get('poster_path', '')
        if poster_path:
            url = self.window.tmdb.image_url(poster_path, 'w500')
            load_image_async(url, 180, 270, self._on_poster_loaded)

        # Hero info column
        hero_info = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            hexpand=True,
            valign=Gtk.Align.END,
        )
        hero_content.append(hero_info)

        # Title
        title_label = Gtk.Label(label=title, xalign=0, wrap=True)
        title_label.add_css_class('detail-title')
        hero_info.append(title_label)

        # Tagline placeholder (filled by _load_details)
        self._tagline_label = Gtk.Label(xalign=0, wrap=True, visible=False)
        self._tagline_label.add_css_class('detail-tagline')
        hero_info.append(self._tagline_label)

        # Metadata chips row
        self._meta_flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=20,
            min_children_per_line=1,
            row_spacing=6,
            column_spacing=6,
            homogeneous=False,
        )
        self._meta_flow.set_halign(Gtk.Align.START)
        hero_info.append(self._meta_flow)

        # Initial chips from search result data
        rating = self.data.get('vote_average', 0)
        if rating > 0:
            self._add_chip(f'★ {rating:.1f}', 'chip-rating')
        if year_str:
            self._add_chip(year_str)

        # ── Action buttons ────────────────────────────────────
        actions_row = Gtk.Box(spacing=12)
        actions_row.set_margin_top(16)
        hero_info.append(actions_row)

        watch_btn = Gtk.Button(label='Смотреть')
        watch_btn.add_css_class('suggested-action')
        watch_btn.add_css_class('pill')
        watch_btn.set_icon_name('media-playback-start-symbolic')
        watch_btn.connect('clicked', self._on_watch_clicked)
        actions_row.append(watch_btn)

        # ── Body content (below hero) ─────────────────────────
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        body.set_margin_start(32)
        body.set_margin_end(32)
        body.set_margin_top(24)
        body.set_margin_bottom(32)
        content.append(body)

        # Overview
        overview = self.data.get('overview', '')
        if overview:
            overview_label = Gtk.Label(
                label=overview, xalign=0, wrap=True,
                max_width_chars=100,
            )
            overview_label.add_css_class('detail-overview')
            body.append(overview_label)

        # Cast section placeholder
        self._cast_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, visible=False,
        )
        body.append(self._cast_section)

        cast_title = Gtk.Label(label='Актёры', xalign=0)
        cast_title.add_css_class('title-3')
        self._cast_section.append(cast_title)

        cast_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        cast_scroll.set_min_content_height(180)
        self._cast_section.append(cast_scroll)

        self._cast_box = Gtk.Box(spacing=12)
        cast_scroll.set_child(self._cast_box)

    # ── Chip helpers ──────────────────────────────────────────

    def _add_chip(self, text, extra_class=None):
        lbl = Gtk.Label(label=text)
        lbl.add_css_class('detail-chip')
        if extra_class:
            lbl.add_css_class(extra_class)
        child = Gtk.FlowBoxChild()
        child.set_child(lbl)
        self._meta_flow.append(child)

    # ── Navigation ────────────────────────────────────────────

    def _on_watch_clicked(self, _btn):
        from kadr.views.torrents import TorrentsView
        view = TorrentsView(
            self.window, self.media_type, self.data, self._title,
        )
        self.window.nav_view.push(view.page)

    # ── Load full details + credits ───────────────────────────

    def _load_details(self):
        media_id = self.data.get('id')
        if not media_id:
            return
        run_async(self._fetch_details, self._on_details_loaded, media_id)

    def _fetch_details(self, media_id):
        tmdb = self.window.tmdb
        if self.media_type == 'movie':
            details = tmdb.movie_details(media_id)
            credits = tmdb.movie_credits(media_id)
        else:
            details = tmdb.tv_details(media_id)
            credits = tmdb.tv_credits(media_id)
        return details, credits

    def _on_details_loaded(self, result, error):
        if error or not result:
            return
        details, credits = result

        # Tagline
        tagline = details.get('tagline', '')
        if tagline:
            self._tagline_label.set_label(tagline)
            self._tagline_label.set_visible(True)

        # Additional chips: runtime / seasons, genres
        if self.media_type == 'movie':
            runtime = details.get('runtime')
            if runtime:
                self._add_chip(_fmt_runtime(runtime))
        else:
            seasons = details.get('number_of_seasons')
            if seasons:
                s = 'сезон' if seasons == 1 else ('сезона' if 2 <= seasons <= 4 else 'сезонов')
                self._add_chip(f'{seasons} {s}')
            episodes = details.get('number_of_episodes')
            if episodes:
                self._add_chip(f'{episodes} эп.')

        genres = details.get('genres', [])
        for g in genres[:4]:
            self._add_chip(g.get('name', ''))

        # Cast
        cast = credits.get('cast', [])[:15]
        if cast:
            self._cast_section.set_visible(True)
            for person in cast:
                self._build_cast_card(person)

    def _build_cast_card(self, person):
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        card.set_size_request(100, -1)

        # Avatar
        avatar_frame = Gtk.Frame()
        avatar_frame.set_overflow(Gtk.Overflow.HIDDEN)
        avatar_frame.add_css_class('cast-avatar-frame')
        avatar = Gtk.Picture()
        avatar.set_size_request(80, 80)
        avatar.set_content_fit(Gtk.ContentFit.COVER)
        avatar_frame.set_child(avatar)
        card.append(avatar_frame)

        profile = person.get('profile_path', '')
        if profile:
            url = self.window.tmdb.image_url(profile, 'w185')
            load_image_async(url, 80, 80, lambda tex, pic=avatar: pic.set_paintable(tex) if tex else None)

        name_label = Gtk.Label(
            label=person.get('name', ''),
            xalign=0.5,
            wrap=True,
            max_width_chars=12,
            lines=2,
        )
        name_label.add_css_class('caption')
        card.append(name_label)

        role = person.get('character', '')
        if role:
            role_label = Gtk.Label(
                label=role,
                xalign=0.5,
                wrap=True,
                max_width_chars=12,
                lines=1,
            )
            role_label.add_css_class('dim-label')
            role_label.add_css_class('caption')
            card.append(role_label)

        self._cast_box.append(card)

    # ── Image callbacks ────────────────────────────────────────

    def _on_backdrop_loaded(self, texture):
        if texture:
            self._backdrop.set_paintable(texture)

    def _on_poster_loaded(self, texture):
        if texture:
            self._poster.set_paintable(texture)
