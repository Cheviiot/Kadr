"""Entry point for the Kadr application."""

import os
import sys


def _ensure_gi_available():
    """Add system site-packages to path if gi is not importable (e.g., in venv)."""
    try:
        __import__("gi")
        return
    except ImportError:
        pass

    candidates = [
        "/usr/lib64/python3/site-packages",
        "/usr/lib/python3/site-packages",
        "/usr/lib/python3/dist-packages",
        f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages",
    ]
    for path in candidates:
        if os.path.isdir(os.path.join(path, "gi")):
            sys.path.insert(0, path)
            return

    print(
        "Error: PyGObject (gi) not found.\n"
        "Install it with your package manager:\n"
        "  Fedora:  sudo dnf install python3-gobject gtk4 libadwaita\n"
        "  Ubuntu:  sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1\n"
        "  Arch:    sudo pacman -S python-gobject gtk4 libadwaita",
        file=sys.stderr,
    )
    sys.exit(1)


def main():
    _ensure_gi_available()

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Gdk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")

    from kadr.application import KadrApplication

    app = KadrApplication()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
