import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango

from kadr.utils import load_image_async

POSTER_WIDTH = 155
POSTER_HEIGHT = 232


def _has_ru_title(data, media_type):
    """Return True if the entry has a Russian localised title."""
    lang = data.get('original_language') or ''
    if lang == 'ru':
        return True
    if media_type == 'movie':
        return (data.get('title') or '') != (data.get('original_title') or '')
    return (data.get('name') or '') != (data.get('original_name') or '')


def _resolve_title(data, media_type):
    """Return (display_title, year_str)."""
    if media_type == 'movie':
        local = data.get('title') or ''
        orig = data.get('original_title') or ''
        date = data.get('release_date') or ''
    else:
        local = data.get('name') or ''
        orig = data.get('original_name') or ''
        date = data.get('first_air_date') or ''

    title = local or orig
    year = date[:4] if len(date) >= 4 else ''
    return title, year


class MediaCard(Gtk.Overlay):
    """Card widget displaying a movie/TV show poster with title and rating."""

    def __init__(self, data, media_type, image_url, on_click):
        super().__init__()
        self.data = data
        self.media_type = media_type
        self._on_click = on_click

        self.set_size_request(POSTER_WIDTH, POSTER_HEIGHT)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class('media-card')

        # Cover image fills the entire tile
        self._picture = Gtk.Picture()
        self._picture.set_content_fit(Gtk.ContentFit.COVER)
        self._picture.set_size_request(POSTER_WIDTH, POSTER_HEIGHT)
        self._picture.add_css_class('poster-image')
        self.set_child(self._picture)

        title, year_str = _resolve_title(data, media_type)

        # Bottom info overlay with gradient
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.add_css_class('card-info')
        info.set_valign(Gtk.Align.END)
        info.set_halign(Gtk.Align.FILL)

        label = Gtk.Label(label=title)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(18)
        label.set_lines(2)
        label.set_wrap(True)
        label.set_halign(Gtk.Align.START)
        label.add_css_class('card-title')
        info.append(label)

        # Year
        if year_str:
            year_label = Gtk.Label(label=year_str)
            year_label.set_halign(Gtk.Align.START)
            year_label.add_css_class('card-year')
            info.append(year_label)

        self.add_overlay(info)

        # Rating badge (top-left)
        rating = data.get('vote_average', 0)
        if rating > 0:
            badge = Gtk.Label(label=f'★ {rating:.1f}')
            badge.add_css_class('rating-badge')
            badge.set_halign(Gtk.Align.START)
            badge.set_valign(Gtk.Align.START)
            badge.set_margin_start(6)
            badge.set_margin_top(6)
            self.add_overlay(badge)

        # Click handler
        click = Gtk.GestureClick()
        click.connect('released', self._clicked)
        self.add_controller(click)

        # Load poster image
        if image_url:
            load_image_async(image_url, POSTER_WIDTH, POSTER_HEIGHT, self._on_image)

    def _on_image(self, texture):
        if texture:
            self._picture.set_paintable(texture)

    def _clicked(self, gesture, n_press, x, y):
        if n_press == 1:
            self._on_click(self.media_type, self.data)
