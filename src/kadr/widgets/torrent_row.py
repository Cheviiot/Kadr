import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class TorrentRow(Gtk.ListBoxRow):
    """Row widget displaying a torrent search result."""

    def __init__(self, torrent, on_download, on_copy):
        super().__init__()
        self.torrent = torrent

        box = Gtk.Box(spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        self.set_child(box)

        # Info column
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        box.append(info)

        # Title
        title = Gtk.Label(
            label=torrent['title'],
            xalign=0,
            wrap=True,
            max_width_chars=80,
        )
        title.add_css_class('heading')
        info.append(title)

        # Meta row
        meta = Gtk.Box(spacing=16)
        info.append(meta)

        size_lbl = Gtk.Label(label=torrent['size_str'])
        size_lbl.add_css_class('dim-label')
        meta.append(size_lbl)

        seeders_lbl = Gtk.Label(label=f'▲ {torrent["seeders"]}')
        seeders_lbl.add_css_class('success-label')
        meta.append(seeders_lbl)

        leechers_lbl = Gtk.Label(label=f'▼ {torrent["leechers"]}')
        leechers_lbl.add_css_class('dim-label')
        meta.append(leechers_lbl)

        if torrent.get('tracker'):
            tracker_lbl = Gtk.Label(label=torrent['tracker'])
            tracker_lbl.add_css_class('dim-label')
            meta.append(tracker_lbl)

        # Actions column
        actions = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        box.append(actions)

        dl_btn = Gtk.Button(
            icon_name='folder-download-symbolic',
            tooltip_text='Скачать',
        )
        dl_btn.add_css_class('suggested-action')
        dl_btn.connect('clicked', lambda *_: on_download(torrent))
        actions.append(dl_btn)

        copy_btn = Gtk.Button(
            icon_name='edit-copy-symbolic',
            tooltip_text='Копировать магнет',
        )
        copy_btn.connect('clicked', lambda *_: on_copy(torrent))
        actions.append(copy_btn)
