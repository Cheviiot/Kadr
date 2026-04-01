"""Full-screen player view with embedded mpv, transport controls, and download overlay."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
from gi.repository import Adw, Gdk, GLib, Gtk

from kadr.widgets.mpv_widget import MpvWidget


def _fmt_time(seconds):
    """Format seconds as H:MM:SS or M:SS."""
    s = max(0, int(seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


class PlayerView:
    """Navigation page containing an embedded mpv video player with controls."""

    def __init__(self, window, title=''):
        self.window = window
        self._seeking = False
        self._hiding_id = 0
        self._seek_timeout_id = 0
        self._end_seek_id = 0
        self._controls_visible = True

        # ── Page ──
        self._page = Adw.NavigationPage(title=title or 'Плеер')

        toolbar_view = Adw.ToolbarView()
        self._page.set_child(toolbar_view)

        # Header bar (integrated into overlay, auto-hides)
        self._header = Adw.HeaderBar()
        self._header.add_css_class('osd')
        toolbar_view.add_top_bar(self._header)

        # ── Main overlay ──
        overlay = Gtk.Overlay()
        toolbar_view.set_content(overlay)

        # mpv render area
        self._mpv_widget = MpvWidget()
        self._mpv_widget.set_hexpand(True)
        self._mpv_widget.set_vexpand(True)
        overlay.set_child(self._mpv_widget)

        # Download info banner (top)
        self._dl_label = Gtk.Label(
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
        )
        self._dl_label.set_margin_top(8)
        self._dl_label.set_margin_end(12)
        self._dl_label.add_css_class('osd')
        self._dl_label.add_css_class('caption')
        overlay.add_overlay(self._dl_label)

        # ── Controls bottom bar ──
        controls_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.END,
        )
        controls_box.add_css_class('osd')
        controls_box.add_css_class('toolbar')
        overlay.add_overlay(controls_box)
        self._controls_box = controls_box

        # Progress slider
        self._progress_adj = Gtk.Adjustment(lower=0, upper=1, step_increment=5)
        self._progress_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self._progress_adj,
            draw_value=False,
            hexpand=True,
        )
        self._progress_scale.set_margin_start(12)
        self._progress_scale.set_margin_end(12)
        self._progress_scale.connect('change-value', self._on_change_value)
        controls_box.append(self._progress_scale)

        # Transport row
        transport = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        transport.set_margin_bottom(8)
        transport.set_margin_top(4)
        controls_box.append(transport)

        # Time label
        self._time_label = Gtk.Label(label='0:00 / 0:00')
        self._time_label.add_css_class('caption')
        self._time_label.set_width_chars(17)
        transport.append(self._time_label)

        # Play / Pause
        self._play_btn = Gtk.Button(icon_name='media-playback-pause-symbolic')
        self._play_btn.connect('clicked', self._toggle_pause)
        transport.append(self._play_btn)

        # Volume
        vol_adj = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=5)
        vol_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=vol_adj,
            draw_value=False,
        )
        vol_scale.set_size_request(100, -1)
        vol_adj.connect('value-changed', lambda a: self._set_volume(a.get_value()))
        transport.append(vol_scale)

        # Fullscreen
        fs_btn = Gtk.Button(icon_name='view-fullscreen-symbolic')
        fs_btn.connect('clicked', self._toggle_fullscreen)
        transport.append(fs_btn)

        # ── Motion controller (auto-hide controls) ──
        motion = Gtk.EventControllerMotion()
        motion.connect('motion', self._on_motion)
        overlay.add_controller(motion)

        click = Gtk.GestureClick(button=1)
        click.connect('released', self._on_click)
        overlay.add_controller(click)

        # ── mpv callbacks ──
        self._mpv_widget.set_on_file_loaded(self._on_file_loaded)
        self._mpv_widget.set_on_eof(self._on_eof)

        # Observe time-pos and duration
        self._duration = 0
        self._setup_observers()

    @property
    def page(self):
        return self._page

    @property
    def mpv_widget(self):
        return self._mpv_widget

    def play(self, path):
        """Load a file and start playback."""
        self._mpv_widget.load(path)

    def set_log_callback(self, cb):
        """Connect mpv_widget logging to external log collector."""
        self._mpv_widget.set_log_callback(cb)

    def shutdown(self):
        """Release mpv resources."""
        if self._hiding_id:
            GLib.source_remove(self._hiding_id)
            self._hiding_id = 0
        if self._seek_timeout_id:
            GLib.source_remove(self._seek_timeout_id)
            self._seek_timeout_id = 0
        if self._end_seek_id:
            GLib.source_remove(self._end_seek_id)
            self._end_seek_id = 0
        self._mpv_widget.shutdown()

    def set_download_info(self, text):
        """Update the download progress overlay text."""
        self._dl_label.set_label(text)

    # ── Observers ─────────────────────────────────────────────

    def _setup_observers(self):
        player = self._mpv_widget.player
        if not player:
            return

        @player.property_observer('time-pos')
        def _on_time(_name, value):
            if value is not None:
                GLib.idle_add(self._update_time, float(value))

        @player.property_observer('duration')
        def _on_duration(_name, value):
            if value is not None:
                self._duration = float(value)
                GLib.idle_add(self._update_duration, float(value))

        @player.property_observer('pause')
        def _on_pause(_name, paused):
            icon = ('media-playback-start-symbolic' if paused
                    else 'media-playback-pause-symbolic')
            GLib.idle_add(self._play_btn.set_icon_name, icon)

    def _update_time(self, pos):
        if self._seeking:
            return
        self._progress_adj.set_value(pos)
        dur = self._duration
        self._time_label.set_label(f'{_fmt_time(pos)} / {_fmt_time(dur)}')

    def _update_duration(self, dur):
        self._progress_adj.set_upper(dur)

    # ── User actions ──────────────────────────────────────────

    def _on_change_value(self, scale, scroll_type, value):
        """Handle user-initiated slider interaction (drag / click / keyboard)."""
        self._seeking = True
        # Cancel any pending end-seek reset
        if self._end_seek_id:
            GLib.source_remove(self._end_seek_id)
            self._end_seek_id = 0
        # Show target time immediately
        dur = self._duration
        self._time_label.set_label(f'{_fmt_time(value)} / {_fmt_time(dur)}')
        # Debounce the actual seek (avoid spamming during drag)
        if self._seek_timeout_id:
            GLib.source_remove(self._seek_timeout_id)
        self._seek_timeout_id = GLib.timeout_add(150, self._do_seek, value)
        return False  # let the scale update its visual position

    def _do_seek(self, value):
        """Perform the debounced seek."""
        self._seek_timeout_id = 0
        player = self._mpv_widget.player
        if player:
            player.seek(value, reference='absolute')
        # Re-enable time-pos updates after mpv stabilises
        self._end_seek_id = GLib.timeout_add(500, self._end_seek)
        return False

    def _end_seek(self):
        """Resume time-pos → slider updates."""
        self._end_seek_id = 0
        self._seeking = False
        return False

    def _toggle_pause(self, _btn):
        player = self._mpv_widget.player
        if player:
            player.pause = not player.pause

    def _set_volume(self, vol):
        player = self._mpv_widget.player
        if player:
            player.volume = vol

    def _toggle_fullscreen(self, _btn):
        win = self._page.get_root()
        if win and hasattr(win, 'is_fullscreen'):
            if win.is_fullscreen():
                win.unfullscreen()
            else:
                win.fullscreen()

    def _on_file_loaded(self):
        pass

    def _on_eof(self):
        pass

    # ── Auto-hide controls ────────────────────────────────────

    def _on_motion(self, _ctrl, _x, _y):
        self._show_controls()
        self._schedule_hide()

    def _on_click(self, _gesture, _n, _x, _y):
        player = self._mpv_widget.player
        if player:
            player.pause = not player.pause

    def _show_controls(self):
        if not self._controls_visible:
            self._controls_box.set_visible(True)
            self._header.set_visible(True)
            self._controls_visible = True

    def _schedule_hide(self):
        if self._hiding_id:
            GLib.source_remove(self._hiding_id)
        self._hiding_id = GLib.timeout_add_seconds(3, self._hide_controls)

    def _hide_controls(self):
        self._hiding_id = 0
        player = self._mpv_widget.player
        if player and not player.pause:
            self._controls_box.set_visible(False)
            self._header.set_visible(False)
            self._controls_visible = False
        return False
