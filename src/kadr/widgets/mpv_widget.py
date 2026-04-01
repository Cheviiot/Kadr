"""GTK4 widget that renders mpv video via OpenGL (Gtk.GLArea + MpvRenderContext).

Inspired by the Cine project (github.com/diegopvlk/Cine).
"""

import ctypes

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

try:
    import mpv
    MPV_AVAILABLE = True
except ImportError:
    mpv = None
    MPV_AVAILABLE = False

# EGL / GL helpers for the render context
_libegl = None
_egl_get_proc = None
_libgl = None
_glGetIntegerv = None
_GL_FRAMEBUFFER_BINDING = 0x8CA6


def _ensure_gl_libs():
    global _libegl, _egl_get_proc, _libgl, _glGetIntegerv
    if _libegl is not None:
        return
    _libegl = ctypes.CDLL('libEGL.so.1')
    _egl_get_proc = _libegl.eglGetProcAddress
    _egl_get_proc.restype = ctypes.c_void_p
    _egl_get_proc.argtypes = [ctypes.c_char_p]

    _libgl = ctypes.CDLL('libGL.so.1')
    _glGetIntegerv = _libgl.glGetIntegerv
    _glGetIntegerv.argtypes = [ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]


def _get_display_param():
    """Return wl_display / x11_display pointer for mpv render context."""
    display = Gdk.Display.get_default()
    if display is None:
        return {}

    _gtk = ctypes.CDLL('libgtk-4.so.1')

    def _ptr(obj):
        ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
        ctypes.pythonapi.PyCapsule_GetPointer.argtypes = (ctypes.py_object,)
        return ctypes.pythonapi.PyCapsule_GetPointer(obj.__gpointer__, None)

    try:
        gi.require_version('GdkWayland', '4.0')
        from gi.repository import GdkWayland
        if isinstance(display, GdkWayland.WaylandDisplay):
            _gtk.gdk_wayland_display_get_wl_display.restype = ctypes.c_void_p
            _gtk.gdk_wayland_display_get_wl_display.argtypes = [ctypes.c_void_p]
            ptr = _gtk.gdk_wayland_display_get_wl_display(_ptr(display))
            if ptr:
                return {'wl_display': ptr}
    except (ValueError, ImportError):
        pass

    try:
        gi.require_version('GdkX11', '4.0')
        from gi.repository import GdkX11
        if isinstance(display, GdkX11.X11Display):
            _gtk.gdk_x11_display_get_xdisplay.restype = ctypes.c_void_p
            _gtk.gdk_x11_display_get_xdisplay.argtypes = [ctypes.c_void_p]
            ptr = _gtk.gdk_x11_display_get_xdisplay(_ptr(display))
            if ptr:
                return {'x11_display': ptr}
    except (ValueError, ImportError):
        pass

    return {}


class MpvWidget(Gtk.GLArea):
    """A Gtk.GLArea that renders an mpv player via OpenGL."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not MPV_AVAILABLE:
            raise RuntimeError('python-mpv не установлен')

        _ensure_gl_libs()

        self._mpv = mpv.MPV(
            vo='libmpv',
            ao='pulse,alsa',
            osc='no',
            keep_open='yes',
            keep_open_pause='no',
            input_default_bindings=False,
            input_vo_keyboard=False,
            terminal=False,
            config=False,
            load_scripts=False,
            ytdl=False,
            cache='yes',
            force_seekable='yes',
            demuxer_max_bytes=150 * 1024 * 1024,
            demuxer_readahead_secs=120,
            cache_pause_wait=3,
        )

        self._ctx = None
        self._fbo = ctypes.c_int()
        self._on_file_loaded_cb = None
        self._on_eof_cb = None
        self._log_cb = None

        self.connect('realize', self._on_realize)
        self.connect('render', self._on_render)
        self.connect('unrealize', self._on_unrealize)

    @property
    def player(self):
        return self._mpv

    def load(self, path):
        """Load and play a video file."""
        self._log(f'mpv_widget: load({path})')
        self._mpv.loadfile(path)

    def set_on_file_loaded(self, cb):
        """cb() called on GTK thread when file finishes loading."""
        self._on_file_loaded_cb = cb

    def set_on_eof(self, cb):
        """cb() called on GTK thread when playback reaches end."""
        self._on_eof_cb = cb

    def set_log_callback(self, cb):
        """cb(msg: str) called for mpv log messages."""
        self._log_cb = cb

    def _log(self, msg):
        cb = self._log_cb
        if cb:
            cb(msg)

    def shutdown(self):
        """Clean up mpv resources."""
        self._log('mpv_widget: shutdown()')
        if self._ctx:
            self._ctx.free()
            self._ctx = None
        if self._mpv:
            self._mpv.terminate()
            self._mpv = None

    # ── GL callbacks ──────────────────────────────────────────

    def _on_realize(self, area):
        self._log('mpv_widget: realize')
        area.make_current()

        proc_fn = mpv.MpvGlGetProcAddressFn(
            lambda _inst, name: _egl_get_proc(name),
        )

        display_param = _get_display_param()
        self._log(f'mpv_widget: display_param={display_param}')

        try:
            self._ctx = mpv.MpvRenderContext(
                self._mpv,
                'opengl',
                opengl_init_params={'get_proc_address': proc_fn},
                **display_param,
            )
            self._log('mpv_widget: MpvRenderContext created OK')
        except Exception as exc:
            self._log(f'mpv_widget: MpvRenderContext FAILED: {exc}')
            raise

        self._ctx.update_cb = lambda: GLib.idle_add(
            self.queue_render,
            priority=GLib.PRIORITY_HIGH_IDLE,
        )

        # Observe events
        @self._mpv.event_callback('file-loaded')
        def _on_loaded(_evt):
            self._log('mpv: file-loaded')
            if self._on_file_loaded_cb:
                GLib.idle_add(self._on_file_loaded_cb)

        @self._mpv.property_observer('eof-reached')
        def _on_eof(_name, value):
            self._log(f'mpv: eof-reached={value}')
            if value and self._on_eof_cb:
                GLib.idle_add(self._on_eof_cb)

    def _on_render(self, area, _gl_ctx):
        if not self._ctx:
            return
        try:
            _glGetIntegerv(_GL_FRAMEBUFFER_BINDING, self._fbo)
            scale = area.props.scale_factor
            w = int(area.get_width() * scale)
            h = int(area.get_height() * scale)
            self._ctx.render(
                flip_y=True,
                opengl_fbo={'w': w, 'h': h, 'fbo': self._fbo.value},
            )
        except Exception as exc:
            self._log(f'mpv_widget: render error: {exc}')

    def _on_unrealize(self, _area):
        self._log('mpv_widget: unrealize')
        self.shutdown()
