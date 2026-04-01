from gi.repository import Adw, Gtk, Gdk, Gio

from kadr import APP_ID, CSS_PATH, ICON_PATH, ICONS_DIR


class KadrApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._register_icons()
        self._load_css()
        self._setup_actions()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            from kadr.window import KadrWindow
            win = KadrWindow(application=self)
        win.present()

    def _register_icons(self):
        if ICONS_DIR:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            theme.add_search_path(str(ICONS_DIR))

    def _load_css(self):
        if not CSS_PATH:
            return
        provider = Gtk.CssProvider()
        provider.load_from_path(str(CSS_PATH))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _setup_actions(self):
        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action('app.quit', ['<Control>q'])

        search_action = Gio.SimpleAction.new('search', None)
        search_action.connect('activate', self._on_search_action)
        self.add_action(search_action)
        self.set_accels_for_action('app.search', ['<Control>f'])

        prefs_action = Gio.SimpleAction.new('preferences', None)
        prefs_action.connect('activate', self._on_preferences)
        self.add_action(prefs_action)
        self.set_accels_for_action('app.preferences', ['<Control>comma'])

        about_action = Gio.SimpleAction.new('about', None)
        about_action.connect('activate', self._on_about)
        self.add_action(about_action)

    def _on_search_action(self, action, param):
        win = self.props.active_window
        if win and hasattr(win, 'toggle_search'):
            win.toggle_search()

    def _on_preferences(self, action, param):
        win = self.props.active_window
        if win:
            from kadr.views.settings_dialog import SettingsDialog
            dialog = SettingsDialog(win)
            dialog.present()

    def _on_about(self, action, param):
        win = self.props.active_window
        if not win:
            return
        from kadr import __version__, APP_ID, APP_NAME
        about = Adw.AboutWindow(
            transient_for=win,
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=__version__,
            developer_name='Cheviiot',
            website='https://github.com/Cheviiot/Kadr',
            issue_url='https://github.com/Cheviiot/Kadr/issues',
            license_type=Gtk.License.GPL_3_0,
            developers=['Cheviiot'],
            copyright='© 2026 Cheviiot',
        )
        about.present()
