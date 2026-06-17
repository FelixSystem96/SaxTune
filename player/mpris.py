import os
import dbus
import dbus.service
from gi.repository import GLib

BUS_NAME   = 'org.mpris.MediaPlayer2.reproductor'
OBJ_PATH   = '/org/mpris/MediaPlayer2'
IFACE_APP  = 'org.mpris.MediaPlayer2'
IFACE_PLAY = 'org.mpris.MediaPlayer2.Player'
IFACE_PROP = 'org.freedesktop.DBus.Properties'
ART_TMP    = '/tmp/reproductor_art_mpris'


class MprisService(dbus.service.Object):
    def __init__(self, window, bus):
        self._win = window
        bus_name = dbus.service.BusName(BUS_NAME, bus)
        super().__init__(bus_name, OBJ_PATH)

    # ── org.mpris.MediaPlayer2 ────────────────────────────────────────────────

    @dbus.service.method(IFACE_APP)
    def Raise(self):
        self._win.present()

    @dbus.service.method(IFACE_APP)
    def Quit(self):
        self._win.close()

    @dbus.service.method(IFACE_PROP, in_signature='ss', out_signature='v')
    def Get(self, iface, prop):
        return self._get_all(iface).get(prop, '')

    @dbus.service.method(IFACE_PROP, in_signature='s', out_signature='a{sv}')
    def GetAll(self, iface):
        return self._get_all(iface)

    @dbus.service.method(IFACE_PROP, in_signature='ssv')
    def Set(self, iface, prop, value):
        if iface == IFACE_PLAY:
            if prop == 'Volume':
                v = max(0.0, min(1.0, float(value)))
                self._win.audio.set_volume(v)
                GLib.idle_add(self._win.vol_scale.set_value, v * 100)
            elif prop == 'Shuffle':
                self._win.shuffle_on = bool(value)
                GLib.idle_add(self._win.btn_shuffle.set_active, bool(value))
            elif prop == 'LoopStatus':
                modes = {'None': 0, 'Playlist': 1, 'Track': 2}
                if str(value) in modes:
                    self._win._set_repeat(modes[str(value)])

    @dbus.service.signal(IFACE_PROP, signature='sa{sv}as')
    def PropertiesChanged(self, iface, changed, invalidated):
        pass

    # ── org.mpris.MediaPlayer2.Player ─────────────────────────────────────────

    @dbus.service.method(IFACE_PLAY)
    def Next(self):
        GLib.idle_add(self._win._next)

    @dbus.service.method(IFACE_PLAY)
    def Previous(self):
        GLib.idle_add(self._win._prev)

    @dbus.service.method(IFACE_PLAY)
    def Pause(self):
        if self._win.is_playing and not self._win.is_paused:
            GLib.idle_add(self._win._toggle_play)

    @dbus.service.method(IFACE_PLAY)
    def Play(self):
        if not self._win.is_playing or self._win.is_paused:
            GLib.idle_add(self._win._toggle_play)

    @dbus.service.method(IFACE_PLAY)
    def PlayPause(self):
        GLib.idle_add(self._win._toggle_play)

    @dbus.service.method(IFACE_PLAY)
    def Stop(self):
        GLib.idle_add(self._win._stop)

    @dbus.service.method(IFACE_PLAY, in_signature='x')
    def Seek(self, offset_us):
        pos = self._win.audio.get_pos() + offset_us / 1_000_000
        pos = max(0.0, min(pos, self._win.audio.duration))
        GLib.idle_add(self._win.audio.set_pos, pos)

    @dbus.service.method(IFACE_PLAY, in_signature='ox')
    def SetPosition(self, track_id, position_us):
        GLib.idle_add(self._win.audio.set_pos, position_us / 1_000_000)

    @dbus.service.method(IFACE_PLAY, in_signature='s')
    def OpenUri(self, uri):
        pass

    @dbus.service.signal(IFACE_PLAY, signature='x')
    def Seeked(self, position):
        pass

    # ── Propiedades ───────────────────────────────────────────────────────────

    def _get_all(self, iface):
        if iface == IFACE_APP:
            return {
                'CanQuit':             dbus.Boolean(True),
                'CanRaise':            dbus.Boolean(True),
                'HasTrackList':        dbus.Boolean(False),
                'Identity':            dbus.String('Reproductor de Música'),
                'SupportedUriSchemes': dbus.Array(['file'], signature='s'),
                'SupportedMimeTypes':  dbus.Array(['audio/mpeg'], signature='s'),
            }
        if iface == IFACE_PLAY:
            return {
                'PlaybackStatus': dbus.String(self._playback_status()),
                'LoopStatus':     dbus.String(self._loop_status()),
                'Rate':           dbus.Double(1.0),
                'Shuffle':        dbus.Boolean(self._win.shuffle_on),
                'Metadata':       dbus.Dictionary(self._metadata(), signature='sv'),
                'Volume':         dbus.Double(self._win.audio.volume),
                'Position':       dbus.Int64(int(self._win.audio.get_pos() * 1_000_000)),
                'MinimumRate':    dbus.Double(1.0),
                'MaximumRate':    dbus.Double(1.0),
                'CanGoNext':      dbus.Boolean(len(self._win.playlist) > 1),
                'CanGoPrevious':  dbus.Boolean(len(self._win.playlist) > 1),
                'CanPlay':        dbus.Boolean(len(self._win.playlist) > 0),
                'CanPause':       dbus.Boolean(self._win.is_playing),
                'CanSeek':        dbus.Boolean(self._win.audio.duration > 0),
                'CanControl':     dbus.Boolean(True),
            }
        return {}

    def _playback_status(self):
        if self._win.is_playing and not self._win.is_paused:
            return 'Playing'
        if self._win.is_paused:
            return 'Paused'
        return 'Stopped'

    def _loop_status(self):
        return ['None', 'Playlist', 'Track'][self._win.repeat_mode]

    def _metadata(self):
        win = self._win
        no_track = dbus.ObjectPath('/org/mpris/MediaPlayer2/TrackList/NoTrack')
        if win.current_idx < 0 or win.current_idx >= len(win.playlist):
            return {'mpris:trackid': no_track}

        path = win.playlist[win.current_idx]
        name = os.path.splitext(os.path.basename(path))[0]
        artist, album = win.audio.get_metadata(path)

        meta = {
            'mpris:trackid': dbus.ObjectPath(
                f'/org/mpris/MediaPlayer2/Track/{win.current_idx}'),
            'xesam:title':   dbus.String(name),
            'mpris:length':  dbus.Int64(int(win.audio.duration * 1_000_000)),
        }
        if artist:
            meta['xesam:artist'] = dbus.Array([artist], signature='s')
        if album:
            meta['xesam:album'] = dbus.String(album)

        art_data = win.audio.get_cover_art(path)
        if art_data:
            try:
                with open(ART_TMP, 'wb') as f:
                    f.write(art_data)
                meta['mpris:artUrl'] = dbus.String(f'file://{ART_TMP}')
            except Exception:
                pass

        return meta

    # ── Notificaciones al panel ───────────────────────────────────────────────

    def notify(self, *props):
        all_props = self._get_all(IFACE_PLAY)
        changed = {p: all_props[p] for p in props if p in all_props}
        if changed:
            self.PropertiesChanged(IFACE_PLAY, changed, [])


def setup(window):
    try:
        bus = dbus.SessionBus()
        return MprisService(window, bus)
    except Exception as e:
        print(f'MPRIS no disponible: {e}')
        return None
