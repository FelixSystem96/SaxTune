import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

try:
    from mutagen.mp3 import MP3
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

Gst.init(None)


class AudioPlayer:
    def __init__(self):
        self.volume = 0.7
        self.duration = 0.0
        self._eos = False
        self._player = Gst.ElementFactory.make('playbin', 'player')
        self._player.set_property('volume', self.volume)
        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect('message::eos', self._on_eos)
        bus.connect('message::error', self._on_error)

    def _on_eos(self, bus, msg):
        self._eos = True

    def _on_error(self, bus, msg):
        err, _ = msg.parse_error()
        print(f'GStreamer: {err}')

    def load(self, path):
        self._eos = False
        self._player.set_state(Gst.State.NULL)
        self._player.set_property('uri', GLib.filename_to_uri(path))
        self.duration = 0.0
        if MUTAGEN_OK:
            try:
                self.duration = MP3(path).info.length
            except Exception:
                pass
        return self.duration

    def play(self):
        self._eos = False
        self._player.set_property('volume', self.volume)
        self._player.set_state(Gst.State.PLAYING)

    def pause(self):
        self._player.set_state(Gst.State.PAUSED)

    def unpause(self):
        self._player.set_state(Gst.State.PLAYING)

    def stop(self):
        self._player.set_state(Gst.State.NULL)
        self._eos = False

    def get_pos(self):
        ok, pos = self._player.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else 0.0

    def set_pos(self, seconds):
        self._player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(seconds * Gst.SECOND),
        )

    def set_volume(self, v):
        self.volume = v
        self._player.set_property('volume', v)

    def is_busy(self):
        if self._eos:
            return False
        _, state, pending = self._player.get_state(0)
        return state == Gst.State.PLAYING or pending == Gst.State.PLAYING

    def get_metadata(self, path):
        if not MUTAGEN_OK:
            return '', ''
        try:
            audio = MP3(path)
            tags = audio.tags
            if tags is None:
                return '', ''
            artist = str(tags.get('TPE1', '')).strip()
            album = str(tags.get('TALB', '')).strip()
            return artist, album
        except Exception:
            return '', ''

    def get_cover_art(self, path):
        if not MUTAGEN_OK:
            return None
        try:
            from mutagen.id3 import ID3
            tags = ID3(path)
            for key in tags.keys():
                if key.startswith('APIC'):
                    return tags[key].data
        except Exception:
            pass
        return None
