import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio, Pango, GdkPixbuf, Gdk
import os
import random
from .audio import AudioPlayer
from .config import load as config_load, save as config_save
from .mpris import setup as mpris_setup


def fmt_time(seconds):
    if seconds <= 0:
        return '0:00'
    m, s = divmod(int(seconds), 60)
    return f'{m}:{s:02d}'


class PlayerWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self._config = config_load()
        self._mpris = None
        self.set_title('SaxTune')
        self.set_default_size(580, 560)
        self.set_size_request(480, 460)
        self.connect('notify::maximized', self._on_maximized_changed)

        self.playlist = []
        self.current_idx = -1
        self.is_playing = False
        self.is_paused = False
        self.shuffle_on = False
        self.repeat_mode = 0   # 0=off  1=all  2=one
        self._shuffle_played = set()
        self._muted = False
        self._volume_before_mute = 0.7
        self.seek_dragging = False
        self._updating_seek = False
        self._seek_debounce_id = None
        self._timer_id = None
        self.audio = AudioPlayer()
        self._build_ui()
        self._restore_session()
        self._mpris = mpris_setup(self)
        self.connect('close-request', self._on_close_request)
        GLib.timeout_add(600, self._poll_end)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)

        header = Adw.HeaderBar()

        btn_files = Gtk.Button(label='＋ Archivos')
        btn_files.add_css_class('flat')
        btn_files.connect('clicked', lambda _: self._add_files())
        header.pack_start(btn_files)

        btn_folder = Gtk.Button(label='＋ Carpeta')
        btn_folder.add_css_class('flat')
        btn_folder.connect('clicked', lambda _: self._add_folder())
        header.pack_start(btn_folder)

        btn_settings = Gtk.MenuButton()
        btn_settings.set_icon_name('open-menu-symbolic')
        btn_settings.add_css_class('flat')
        btn_settings.set_popover(self._build_settings_popover())
        header.pack_end(btn_settings)

        outer.append(header)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(230)
        paned.set_resize_start_child(False)
        paned.set_shrink_start_child(False)
        paned.set_start_child(self._build_sidebar())
        paned.set_end_child(self._build_player())
        outer.append(paned)

    def _build_sidebar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_size_request(220, -1)

        self.lbl_count = Gtk.Label(label='0 canciones')
        self.lbl_count.add_css_class('dim-label')
        self.lbl_count.add_css_class('caption')
        self.lbl_count.set_halign(Gtk.Align.START)
        self.lbl_count.set_margin_start(12)
        self.lbl_count.set_margin_top(10)
        self.lbl_count.set_margin_bottom(6)
        box.append(self.lbl_count)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class('navigation-sidebar')
        self.listbox.connect('row-activated', self._on_row_activated)
        scroll.set_child(self.listbox)
        box.append(scroll)

        btn_clear = Gtk.Button(label='Limpiar lista')
        btn_clear.add_css_class('flat')
        btn_clear.connect('clicked', lambda _: self._clear_playlist())
        btn_clear.set_margin_top(4)
        btn_clear.set_margin_bottom(8)
        btn_clear.set_margin_start(8)
        btn_clear.set_margin_end(8)
        box.append(btn_clear)

        return box

    def _build_player(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_vexpand(True)
        box.set_halign(Gtk.Align.FILL)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(16)
        box.set_margin_bottom(16)

        # Metadata at top
        meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        meta.set_hexpand(True)

        self.lbl_title = Gtk.Label(label='Sin reproducción')
        self.lbl_title.add_css_class('title-3')
        self.lbl_title.set_halign(Gtk.Align.START)
        self.lbl_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.lbl_title.set_xalign(0)
        meta.append(self.lbl_title)

        self.lbl_artist = Gtk.Label(label='—')
        self.lbl_artist.add_css_class('dim-label')
        self.lbl_artist.add_css_class('caption')
        self.lbl_artist.set_halign(Gtk.Align.START)
        self.lbl_artist.set_xalign(0)
        self.lbl_artist.set_ellipsize(Pango.EllipsizeMode.END)
        meta.append(self.lbl_artist)

        box.append(meta)

        # Album art — stack switches between fallback icon and actual picture
        self.art_stack = Gtk.Stack()
        self.art_stack.set_vexpand(True)
        self.art_stack.set_margin_top(12)
        self.art_stack.set_margin_bottom(12)
        self.art_stack.set_margin_start(12)
        self.art_stack.set_margin_end(12)
        self.art_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.art_stack.set_transition_duration(150)

        art_icon = Gtk.Image.new_from_icon_name('audio-headphones-symbolic')
        art_icon.set_pixel_size(100)
        art_icon.add_css_class('dim-label')
        art_icon.set_valign(Gtk.Align.CENTER)
        art_icon.set_vexpand(True)
        self.art_stack.add_named(art_icon, 'icon')

        self.art_picture = Gtk.Picture()
        self.art_picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.art_picture.set_hexpand(True)
        self.art_picture.set_vexpand(True)
        self.art_stack.add_named(self.art_picture, 'art')

        box.append(self.art_stack)

        # Progress
        prog = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.lbl_elapsed = Gtk.Label(label='0:00')
        self.lbl_elapsed.add_css_class('dim-label')
        self.lbl_elapsed.add_css_class('caption')
        time_row.append(self.lbl_elapsed)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        time_row.append(spacer)

        self.lbl_total = Gtk.Label(label='0:00')
        self.lbl_total.add_css_class('dim-label')
        self.lbl_total.add_css_class('caption')
        time_row.append(self.lbl_total)
        prog.append(time_row)

        self.seek_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 0.1)
        self.seek_scale.set_draw_value(False)
        self.seek_scale.set_hexpand(True)

        self.seek_scale.connect('value-changed', self._on_seek_value_changed)

        prog.append(self.seek_scale)
        box.append(prog)
        box.append(self._gap(8))

        # Controls
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl.set_halign(Gtk.Align.CENTER)

        self.btn_shuffle = Gtk.ToggleButton()
        self.btn_shuffle.set_icon_name('media-playlist-shuffle-symbolic')
        self.btn_shuffle.add_css_class('flat')
        self.btn_shuffle.add_css_class('circular')
        self.btn_shuffle.set_tooltip_text('Orden aleatorio: desactivado')
        self.btn_shuffle.connect('toggled', self._on_shuffle_toggled)
        ctrl.append(self.btn_shuffle)

        btn_prev = Gtk.Button()
        btn_prev.set_icon_name('media-skip-backward-symbolic')
        btn_prev.add_css_class('flat')
        btn_prev.add_css_class('circular')
        btn_prev.connect('clicked', lambda _: self._prev())
        ctrl.append(btn_prev)

        self.btn_play = Gtk.Button()
        self.btn_play.set_icon_name('media-playback-start-symbolic')
        self.btn_play.add_css_class('suggested-action')
        self.btn_play.add_css_class('circular')
        self.btn_play.set_size_request(52, 52)
        self.btn_play.connect('clicked', lambda _: self._toggle_play())
        ctrl.append(self.btn_play)

        btn_next = Gtk.Button()
        btn_next.set_icon_name('media-skip-forward-symbolic')
        btn_next.add_css_class('flat')
        btn_next.add_css_class('circular')
        btn_next.connect('clicked', lambda _: self._next())
        ctrl.append(btn_next)

        self.btn_repeat = Gtk.Button()
        self.btn_repeat.set_icon_name('media-playlist-repeat-symbolic')
        self.btn_repeat.add_css_class('flat')
        self.btn_repeat.add_css_class('circular')
        self.btn_repeat.set_tooltip_text('Repetición: desactivada')
        self.btn_repeat.connect('clicked', self._cycle_repeat)
        ctrl.append(self.btn_repeat)

        box.append(ctrl)
        box.append(self._gap(6))

        # Volume
        vol = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol.set_halign(Gtk.Align.CENTER)

        self.btn_mute = Gtk.Button()
        self.btn_mute.set_icon_name('audio-volume-medium-symbolic')
        self.btn_mute.add_css_class('flat')
        self.btn_mute.add_css_class('circular')
        self.btn_mute.connect('clicked', self._toggle_mute)
        vol.append(self.btn_mute)

        self.vol_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.set_draw_value(False)
        self.vol_scale.set_size_request(180, -1)
        self.vol_scale.set_value(70)
        self.vol_scale.connect('value-changed', self._on_volume_change)
        vol.append(self.vol_scale)

        self.lbl_vol = Gtk.Label(label='70%')
        self.lbl_vol.add_css_class('caption')
        self.lbl_vol.set_width_chars(4)
        vol.append(self.lbl_vol)

        box.append(vol)
        return box

    def _gap(self, px):
        w = Gtk.Box()
        w.set_size_request(-1, px)
        return w

    # ── Ajustes ───────────────────────────────────────────────────────────────

    def _build_settings_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(14)
        box.set_margin_end(14)

        lbl_heading = Gtk.Label(label='Carpeta por defecto')
        lbl_heading.add_css_class('heading')
        lbl_heading.set_halign(Gtk.Align.START)
        box.append(lbl_heading)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.lbl_default_folder = Gtk.Label()
        self.lbl_default_folder.set_hexpand(True)
        self.lbl_default_folder.set_halign(Gtk.Align.START)
        self.lbl_default_folder.set_ellipsize(Pango.EllipsizeMode.START)
        self._refresh_folder_label()
        row.append(self.lbl_default_folder)

        btn_change = Gtk.Button(label='Cambiar')
        btn_change.add_css_class('flat')
        btn_change.connect('clicked', lambda _: self._pick_default_folder(popover))
        row.append(btn_change)

        box.append(row)

        sep = Gtk.Separator()
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        box.append(sep)

        theme_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        is_dark = self._config.get('color_scheme', 'dark') == 'dark'
        self.lbl_theme = Gtk.Label(label='Oscuro' if is_dark else 'Claro')
        self.lbl_theme.set_hexpand(True)
        self.lbl_theme.set_halign(Gtk.Align.START)
        theme_row.append(self.lbl_theme)

        self.theme_switch = Gtk.Switch()
        self.theme_switch.set_active(is_dark)
        self.theme_switch.connect('notify::active', self._on_theme_switched)
        theme_row.append(self.theme_switch)

        box.append(theme_row)

        sep2 = Gtk.Separator()
        sep2.set_margin_top(4)
        sep2.set_margin_bottom(4)
        box.append(sep2)

        playlist_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        lbl_playlist = Gtk.Label(label='Guardar playlist al cerrar')
        lbl_playlist.set_hexpand(True)
        lbl_playlist.set_halign(Gtk.Align.START)
        playlist_row.append(lbl_playlist)

        self.playlist_switch = Gtk.Switch()
        self.playlist_switch.set_active(self._config.get('save_playlist', True))
        self.playlist_switch.connect('notify::active', self._on_playlist_switch)
        playlist_row.append(self.playlist_switch)

        box.append(playlist_row)
        popover.set_child(box)
        return popover

    def _refresh_folder_label(self):
        folder = self._config.get('default_folder', '')
        if folder:
            self.lbl_default_folder.set_label(folder)
            self.lbl_default_folder.remove_css_class('dim-label')
        else:
            self.lbl_default_folder.set_label('No configurada')
            self.lbl_default_folder.add_css_class('dim-label')

    def _pick_default_folder(self, popover):
        popover.popdown()
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Carpeta de música por defecto')
        current = self._config.get('default_folder')
        if current and os.path.isdir(current):
            dialog.set_initial_folder(Gio.File.new_for_path(current))
        dialog.select_folder(self, None, self._on_default_folder_ready)

    def _on_theme_switched(self, switch, _):
        is_dark = switch.get_active()
        scheme = 'dark' if is_dark else 'light'
        self.lbl_theme.set_label('Oscuro' if is_dark else 'Claro')
        self._config['color_scheme'] = scheme
        config_save(self._config)
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if is_dark else Adw.ColorScheme.FORCE_LIGHT
        )

    def _on_playlist_switch(self, switch, _):
        self._config['save_playlist'] = switch.get_active()
        config_save(self._config)

    def _on_default_folder_ready(self, dialog, result):
        try:
            f = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        path = f.get_path()
        if path:
            self._config['default_folder'] = path
            config_save(self._config)
            self._refresh_folder_label()

    # ── Sesión ────────────────────────────────────────────────────────────────

    def _restore_session(self):
        paths = [p for p in self._config.get('playlist', []) if os.path.isfile(p)]
        for path in paths:
            self._append_song(path)
        self._update_count()
        idx = self._config.get('current_index', -1)
        if 0 <= idx < len(self.playlist):
            self._preview_index(idx)

        if self._config.get('shuffle', False):
            self.shuffle_on = True
            self.btn_shuffle.set_active(True)

        repeat = self._config.get('repeat', 0)
        if repeat > 0:
            self._set_repeat(repeat)

    def _preview_index(self, idx):
        self.current_idx = idx
        path = self.playlist[idx]
        name = os.path.splitext(os.path.basename(path))[0]
        row = self.listbox.get_row_at_index(idx)
        if row:
            self.listbox.select_row(row)
        self.lbl_title.set_label(name)
        artist, album = self.audio.get_metadata(path)
        parts = [p for p in [artist, album] if p]
        self.lbl_artist.set_label('  ·  '.join(parts) if parts else '—')
        art_data = self.audio.get_cover_art(path)
        if art_data:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(art_data)
                loader.close()
                texture = Gdk.Texture.new_for_pixbuf(loader.get_pixbuf())
                self.art_picture.set_paintable(texture)
                self.art_stack.set_visible_child_name('art')
            except Exception:
                self.art_stack.set_visible_child_name('icon')
        else:
            self.art_stack.set_visible_child_name('icon')
        try:
            duration = self.audio.load(path)
        except Exception:
            duration = 0.0
        self.lbl_total.set_label(f'-{fmt_time(duration)}' if duration > 0 else '0:00')

    def _on_maximized_changed(self, *_):
        if not self.is_maximized():
            GLib.idle_add(self._restore_default_size)

    def _restore_default_size(self):
        self.set_default_size(580, 560)
        return False

    def _on_close_request(self, *_):
        if self._config.get('save_playlist', True):
            self._config['playlist'] = self.playlist[:]
            self._config['current_index'] = self.current_idx
        else:
            self._config['playlist'] = []
            self._config['current_index'] = -1
        self._config['shuffle'] = self.shuffle_on
        self._config['repeat'] = self.repeat_mode
        config_save(self._config)
        return False

    # ── Diálogos de archivo ───────────────────────────────────────────────────

    def _add_files(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Seleccionar archivos MP3')
        f = Gtk.FileFilter()
        f.set_name('Archivos MP3')
        f.add_pattern('*.mp3')
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dialog.set_filters(store)
        default = self._config.get('default_folder')
        if default and os.path.isdir(default):
            dialog.set_initial_folder(Gio.File.new_for_path(default))
        dialog.open_multiple(self, None, self._on_files_ready)

    def _on_files_ready(self, dialog, result):
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        for i in range(files.get_n_items()):
            path = files.get_item(i).get_path()
            if path and path not in self.playlist:
                self._append_song(path)
        self._update_count()

    def _add_folder(self):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Seleccionar carpeta de música')
        default = self._config.get('default_folder')
        if default and os.path.isdir(default):
            dialog.set_initial_folder(Gio.File.new_for_path(default))
        dialog.select_folder(self, None, self._on_folder_ready)

    def _on_folder_ready(self, dialog, result):
        try:
            folder_file = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        folder = folder_file.get_path()
        if not folder:
            return
        for root_dir, _, files in os.walk(folder):
            for name in sorted(files):
                if name.lower().endswith('.mp3'):
                    path = os.path.join(root_dir, name)
                    if path not in self.playlist:
                        self._append_song(path)
        self._update_count()

    def _append_song(self, path):
        self.playlist.append(path)
        name = os.path.splitext(os.path.basename(path))[0]
        label = Gtk.Label(label=name)
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_margin_start(8)
        label.set_margin_end(8)
        label.set_margin_top(4)
        label.set_margin_bottom(4)
        row = Gtk.ListBoxRow()
        row.set_child(label)
        self.listbox.append(row)

    def _clear_playlist(self):
        self._stop()
        self.playlist.clear()
        self._shuffle_played.clear()
        while (row := self.listbox.get_row_at_index(0)) is not None:
            self.listbox.remove(row)
        self.current_idx = -1
        self.lbl_title.set_label('Sin reproducción')
        self.lbl_artist.set_label('—')
        self.lbl_elapsed.set_label('0:00')
        self.lbl_total.set_label('0:00')
        self.seek_scale.set_value(0)
        self.art_stack.set_visible_child_name('icon')
        self._update_count()

    def _update_count(self):
        n = len(self.playlist)
        self.lbl_count.set_label(f"{n} canción{'es' if n != 1 else ''}")

    def _on_row_activated(self, listbox, row):
        self._play_index(row.get_index())

    # ── Reproducción ──────────────────────────────────────────────────────────

    def _play_index(self, idx):
        if idx < 0 or idx >= len(self.playlist):
            return
        self.current_idx = idx
        path = self.playlist[idx]
        name = os.path.splitext(os.path.basename(path))[0]

        row = self.listbox.get_row_at_index(idx)
        if row:
            self.listbox.select_row(row)
            row.grab_focus()

        self.lbl_title.set_label(name)
        artist, album = self.audio.get_metadata(path)
        parts = [p for p in [artist, album] if p]
        self.lbl_artist.set_label('  ·  '.join(parts) if parts else '—')

        art_data = self.audio.get_cover_art(path)
        if art_data:
            try:
                loader = GdkPixbuf.PixbufLoader()
                loader.write(art_data)
                loader.close()
                texture = Gdk.Texture.new_for_pixbuf(loader.get_pixbuf())
                self.art_picture.set_paintable(texture)
                self.art_stack.set_visible_child_name('art')
            except Exception:
                self.art_stack.set_visible_child_name('icon')
        else:
            self.art_stack.set_visible_child_name('icon')

        try:
            duration = self.audio.load(path)
        except Exception as e:
            self._show_error(f'No se puede reproducir:\n{os.path.basename(path)}\n\n{e}')
            return
        self.lbl_total.set_label(f'-{fmt_time(duration)}' if duration > 0 else '0:00')
        self.seek_scale.set_value(0)
        self.lbl_elapsed.set_label('0:00')

        try:
            self.audio.play()
            self.is_playing = True
            self.is_paused = False
            self.btn_play.set_icon_name('media-playback-pause-symbolic')
            self._start_timer()
            if self._mpris:
                self._mpris.notify('PlaybackStatus', 'Metadata', 'CanPause',
                                   'CanSeek', 'CanGoNext', 'CanGoPrevious')
        except Exception as e:
            self._show_error(str(e))

    def _toggle_play(self):
        if not self.playlist:
            return
        if self.current_idx == -1:
            self._play_index(0)
            return
        if self.is_playing and not self.is_paused:
            self.audio.pause()
            self.is_paused = True
            self.btn_play.set_icon_name('media-playback-start-symbolic')
            if self._mpris:
                self._mpris.notify('PlaybackStatus', 'CanPause')
        elif self.is_paused:
            self.audio.unpause()
            self.is_paused = False
            self.btn_play.set_icon_name('media-playback-pause-symbolic')
            if self._mpris:
                self._mpris.notify('PlaybackStatus', 'CanPause')
        else:
            self._play_index(self.current_idx)

    def _stop(self):
        self.audio.stop()
        self.is_playing = False
        self.is_paused = False
        self.btn_play.set_icon_name('media-playback-start-symbolic')
        self._cancel_timer()
        if self._mpris:
            self._mpris.notify('PlaybackStatus', 'CanPause', 'CanSeek')

    def _prev(self):
        if not self.playlist:
            return
        idx = self.current_idx - 1
        if idx < 0:
            idx = len(self.playlist) - 1
        self._play_index(idx)

    def _next(self):
        if not self.playlist:
            return
        if self.shuffle_on:
            self._shuffle_played.add(self.current_idx)
            unplayed = [i for i in range(len(self.playlist)) if i not in self._shuffle_played]
            if not unplayed:
                if self.repeat_mode >= 1:
                    self._shuffle_played.clear()
                    unplayed = [i for i in range(len(self.playlist)) if i != self.current_idx]
                else:
                    self._stop()
                    return
            idx = random.choice(unplayed)
        else:
            idx = self.current_idx + 1
            if idx >= len(self.playlist):
                if self.repeat_mode >= 1:
                    idx = 0
                else:
                    self._stop()
                    return
        self._play_index(idx)

    # ── Controles de modo ─────────────────────────────────────────────────────

    def _on_shuffle_toggled(self, btn):
        self.shuffle_on = btn.get_active()
        self._shuffle_played.clear()
        self.btn_shuffle.set_tooltip_text(
            'Orden aleatorio: activado' if self.shuffle_on else 'Orden aleatorio: desactivado'
        )
        if self._mpris:
            self._mpris.notify('Shuffle')

    def _cycle_repeat(self, btn):
        self._set_repeat((self.repeat_mode + 1) % 3)

    def _set_repeat(self, mode):
        self.repeat_mode = mode
        icons = [
            'media-playlist-repeat-symbolic',
            'media-playlist-repeat-symbolic',
            'media-playlist-repeat-song-symbolic',
        ]
        tooltips = [
            'Repetición: desactivada',
            'Repetición: toda la lista',
            'Repetición: canción actual',
        ]
        self.btn_repeat.set_icon_name(icons[mode])
        self.btn_repeat.set_tooltip_text(tooltips[mode])
        if mode > 0:
            self.btn_repeat.remove_css_class('flat')
            self.btn_repeat.add_css_class('suggested-action')
        else:
            self.btn_repeat.remove_css_class('suggested-action')
            self.btn_repeat.add_css_class('flat')
        if self._mpris:
            self._mpris.notify('LoopStatus')

    def _on_volume_change(self, scale):
        v = scale.get_value()
        if self._muted:
            self._muted = False
            self.vol_scale.set_opacity(1.0)
        self.audio.set_volume(v / 100)
        self.lbl_vol.set_label(f'{int(v)}%')
        self._update_vol_icon(v)

    def _update_vol_icon(self, v):
        if v == 0:
            icon = 'audio-volume-muted-symbolic'
        elif v < 35:
            icon = 'audio-volume-low-symbolic'
        elif v < 70:
            icon = 'audio-volume-medium-symbolic'
        else:
            icon = 'audio-volume-high-symbolic'
        self.btn_mute.set_icon_name(icon)

    def _toggle_mute(self, _):
        if self._muted:
            self._muted = False
            self.audio.set_volume(self._volume_before_mute)
            self.vol_scale.set_value(self._volume_before_mute * 100)
            self._update_vol_icon(self._volume_before_mute * 100)
            self.vol_scale.set_opacity(1.0)
        else:
            self._volume_before_mute = self.audio.volume
            self._muted = True
            self.audio.set_volume(0)
            self.btn_mute.set_icon_name('audio-volume-muted-symbolic')
            self.vol_scale.set_opacity(0.35)

    # ── Seek ──────────────────────────────────────────────────────────────────

    def _on_seek_value_changed(self, scale):
        if self._updating_seek:
            return
        if self.audio.duration > 0 and self.is_playing:
            pos = scale.get_value() / 100 * self.audio.duration
            self.seek_dragging = True
            self.lbl_elapsed.set_label(fmt_time(pos))
            remaining = max(0.0, self.audio.duration - pos)
            self.lbl_total.set_label(f'-{fmt_time(remaining)}')
            if self._seek_debounce_id:
                GLib.source_remove(self._seek_debounce_id)
            self._seek_debounce_id = GLib.timeout_add(150, self._do_seek, pos)

    def _do_seek(self, pos):
        self._seek_debounce_id = None
        self.audio.set_pos(pos)
        GLib.timeout_add(400, self._clear_seek_dragging)
        return False

    def _clear_seek_dragging(self):
        self.seek_dragging = False
        return False

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _start_timer(self):
        self._cancel_timer()
        self._timer_id = GLib.timeout_add(500, self._tick)

    def _cancel_timer(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _tick(self):
        if self.is_playing and not self.is_paused and not self.seek_dragging:
            if self.audio.duration == 0.0:
                self.audio.query_duration()
                if self.audio.duration > 0:
                    self.lbl_total.set_label(f'-{fmt_time(self.audio.duration)}')
            elapsed = self.audio.get_pos()
            self.lbl_elapsed.set_label(fmt_time(elapsed))
            if self.audio.duration > 0:
                remaining = max(0.0, self.audio.duration - elapsed)
                self.lbl_total.set_label(f'-{fmt_time(remaining)}')
                pct = min(elapsed / self.audio.duration * 100, 100)
                self._updating_seek = True
                self.seek_scale.set_value(pct)
                self._updating_seek = False
        return True

    def _poll_end(self):
        if self.is_playing and not self.is_paused:
            if not self.audio.is_busy():
                self._on_track_end()
        return True

    def _on_track_end(self):
        if not self.is_playing:
            return
        self.is_playing = False
        if self.repeat_mode == 2:
            self._play_index(self.current_idx)
        else:
            self._next()

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _show_error(self, msg):
        dialog = Adw.MessageDialog(transient_for=self, heading='Error', body=msg)
        dialog.add_response('ok', 'OK')
        dialog.present()
