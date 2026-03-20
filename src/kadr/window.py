import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from kadr.services.settings import SettingsManager
from kadr.services.tmdb import TMDBService
from kadr.services.jackett import JackettService
from kadr.services.downloads import DownloadManager


class KadrWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(870, 800)
        self.set_title("Kadr")

        # Backend services
        self.settings_manager = SettingsManager()
        self.tmdb = TMDBService(self.settings_manager)
        self.jackett = JackettService(self.settings_manager)
        self.downloads = DownloadManager(self.settings_manager)

        # Toast overlay (wraps everything for notifications)
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        # Navigation
        self.nav_view = Adw.NavigationView()
        self.toast_overlay.set_child(self.nav_view)

        # Home page
        from kadr.views.home import HomeView
        self.home = HomeView(self)
        self.nav_view.push(self.home.page)

    def show_detail(self, media_type, data):
        from kadr.views.detail import DetailView
        detail = DetailView(self, media_type, data)
        self.nav_view.push(detail.page)

    def show_toast(self, message):
        from gi.repository import GLib
        safe = GLib.markup_escape_text(str(message))
        self.toast_overlay.add_toast(Adw.Toast(title=safe))

    def toggle_search(self):
        if hasattr(self, 'home'):
            self.home.toggle_search()
