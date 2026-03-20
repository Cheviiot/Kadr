import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from kadr.utils import run_async
from kadr.services.tmdb import TMDB_PROXIES
from kadr.services.jackett import JACKETT_SERVERS
from kadr.services.downloads import DOWNLOAD_CLIENTS


class SettingsDialog(Adw.PreferencesWindow):
    """Application settings dialog."""

    def __init__(self, window):
        super().__init__(
            title='Настройки',
            transient_for=window,
            modal=True,
        )
        self.window = window
        self._server_statuses = {}
        self._proxy_statuses = {}
        self._build_servers_page()
        self._build_clients_page()

    # ── Servers page ──────────────────────────────────────────

    def _build_servers_page(self):
        page = Adw.PreferencesPage(
            title='Серверы',
            icon_name='network-server-symbolic',
        )
        self.add(page)

        # ── Jackett server combo ──
        server_group = Adw.PreferencesGroup(
            title='Торрент сервер',
            description='Публичные Jackett серверы для поиска',
        )
        page.add(server_group)

        self._server_ids = ['auto'] + [s['id'] for s in JACKETT_SERVERS]
        server_names = ['Автоматически'] + [s['name'] for s in JACKETT_SERVERS]
        server_model = Gtk.StringList.new(server_names)

        current_server = self.window.settings_manager.get('selected_server')
        server_idx = (
            self._server_ids.index(current_server)
            if current_server in self._server_ids else 0
        )

        server_combo = Adw.ComboRow(
            title='Сервер',
            model=server_model,
        )
        server_combo.set_selected(server_idx)
        server_combo.connect('notify::selected', self._on_server_selected)
        server_group.add(server_combo)

        # Compact health status row
        self._server_status_row = Adw.ActionRow(title='Доступность')
        self._server_status_box = Gtk.Box(
            spacing=8, valign=Gtk.Align.CENTER,
        )
        self._server_status_row.add_suffix(self._server_status_box)
        server_group.add(self._server_status_row)

        for server in JACKETT_SERVERS:
            item = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
            label = Gtk.Label(label=server['name'])
            label.add_css_class('caption')
            item.append(label)
            spinner = Gtk.Spinner(spinning=True)
            spinner.set_size_request(12, 12)
            item.append(spinner)
            icon = Gtk.Image(visible=False)
            item.append(icon)
            self._server_status_box.append(item)
            self._server_statuses[server['id']] = (spinner, icon)

            run_async(
                self.window.jackett.check_health,
                lambda ok, err, sid=server['id']: self._set_inline_status(
                    self._server_statuses.get(sid), ok and not err,
                ),
                server['id'],
            )

        # ── TMDB proxy combo ──
        proxy_group = Adw.PreferencesGroup(
            title='TMDB прокси',
            description='Прокси для доступа к базе фильмов',
        )
        page.add(proxy_group)

        self._proxy_ids = ['auto'] + list(TMDB_PROXIES.keys())
        proxy_names = ['Автоматически'] + [
            p['name'] for p in TMDB_PROXIES.values()
        ]
        proxy_model = Gtk.StringList.new(proxy_names)

        current_proxy = self.window.settings_manager.get('tmdb_proxy')
        proxy_idx = (
            self._proxy_ids.index(current_proxy)
            if current_proxy in self._proxy_ids else 0
        )

        proxy_combo = Adw.ComboRow(
            title='Прокси',
            model=proxy_model,
        )
        proxy_combo.set_selected(proxy_idx)
        proxy_combo.connect('notify::selected', self._on_proxy_selected)
        proxy_group.add(proxy_combo)

        # Compact health status row
        self._proxy_status_row = Adw.ActionRow(title='Доступность')
        self._proxy_status_box = Gtk.Box(
            spacing=8, valign=Gtk.Align.CENTER,
        )
        self._proxy_status_row.add_suffix(self._proxy_status_box)
        proxy_group.add(self._proxy_status_row)

        for proxy_id, proxy in TMDB_PROXIES.items():
            item = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
            label = Gtk.Label(label=proxy['name'])
            label.add_css_class('caption')
            item.append(label)
            spinner = Gtk.Spinner(spinning=True)
            spinner.set_size_request(12, 12)
            item.append(spinner)
            icon = Gtk.Image(visible=False)
            item.append(icon)
            self._proxy_status_box.append(item)
            self._proxy_statuses[proxy_id] = (spinner, icon)

            run_async(
                self.window.tmdb.check_health,
                lambda ok, err, pid=proxy_id: self._set_inline_status(
                    self._proxy_statuses.get(pid), ok and not err,
                ),
                proxy_id,
            )

    # ── Download clients page ─────────────────────────────────

    def _build_clients_page(self):
        page = Adw.PreferencesPage(
            title='Загрузки',
            icon_name='folder-download-symbolic',
        )
        self.add(page)

        group = Adw.PreferencesGroup(
            title='Торрент-клиент',
            description='Выберите клиент для загрузки торрентов',
        )
        page.add(group)

        available = self.window.downloads.available_clients()
        available_ids = {c['id'] for c in available}

        self._client_ids = ['auto'] + [c['id'] for c in DOWNLOAD_CLIENTS]
        client_names = ['Автоматически'] + [
            c['name'] + ('' if c['id'] in available_ids else ' (не найден)')
            for c in DOWNLOAD_CLIENTS
        ]
        client_model = Gtk.StringList.new(client_names)

        current = self.window.settings_manager.get('download_client', 'auto')
        client_idx = (
            self._client_ids.index(current)
            if current in self._client_ids else 0
        )

        client_combo = Adw.ComboRow(
            title='Клиент',
            subtitle='Приложение для загрузки торрентов',
            model=client_model,
        )
        client_combo.set_selected(client_idx)
        client_combo.connect('notify::selected', self._on_client_selected)
        group.add(client_combo)

    # ── Status helpers ────────────────────────────────────────

    @staticmethod
    def _set_inline_status(pair, is_online):
        if not pair:
            return
        spinner, icon = pair
        spinner.set_spinning(False)
        spinner.set_visible(False)
        icon.set_visible(True)
        if is_online:
            icon.set_from_icon_name('emblem-ok-symbolic')
            icon.add_css_class('success-label')
        else:
            icon.set_from_icon_name('process-stop-symbolic')
            icon.add_css_class('error-label')

    # ── Callbacks ─────────────────────────────────────────────

    def _on_server_selected(self, combo, _pspec):
        idx = combo.get_selected()
        if 0 <= idx < len(self._server_ids):
            self.window.settings_manager.set('selected_server', self._server_ids[idx])

    def _on_proxy_selected(self, combo, _pspec):
        idx = combo.get_selected()
        if 0 <= idx < len(self._proxy_ids):
            self.window.settings_manager.set('tmdb_proxy', self._proxy_ids[idx])

    def _on_client_selected(self, combo, _pspec):
        idx = combo.get_selected()
        if 0 <= idx < len(self._client_ids):
            self.window.settings_manager.set('download_client', self._client_ids[idx])
