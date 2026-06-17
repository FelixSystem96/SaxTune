#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

try:
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
except Exception:
    pass

import os
from gi.repository import Adw, Gdk, Gtk
from player.ui import PlayerWindow
from player.config import load as config_load


def on_activate(app):
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
    display = Gdk.Display.get_default()
    if display:
        Gtk.IconTheme.get_for_display(display).add_search_path(assets_dir)

    cfg = config_load()
    scheme = cfg.get('color_scheme', 'dark')
    style = Adw.StyleManager.get_default()
    style.set_color_scheme(
        Adw.ColorScheme.FORCE_DARK if scheme == 'dark' else Adw.ColorScheme.FORCE_LIGHT
    )
    win = PlayerWindow(app)
    win.present()


def main():
    app = Adw.Application(application_id='com.felix.saxtune')
    app.connect('activate', on_activate)
    app.run()


if __name__ == '__main__':
    main()
