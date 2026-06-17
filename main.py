#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

try:
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
except Exception:
    pass

from gi.repository import Adw
from player.ui import PlayerWindow
from player.config import load as config_load


def on_activate(app):
    cfg = config_load()
    scheme = cfg.get('color_scheme', 'dark')
    style = Adw.StyleManager.get_default()
    style.set_color_scheme(
        Adw.ColorScheme.FORCE_DARK if scheme == 'dark' else Adw.ColorScheme.FORCE_LIGHT
    )
    win = PlayerWindow(app)
    win.present()


def main():
    app = Adw.Application(application_id='com.felix.reproductor')
    app.connect('activate', on_activate)
    app.run()


if __name__ == '__main__':
    main()
