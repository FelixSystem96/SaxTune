import pygame

try:
    from mutagen.mp3 import MP3
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False


class AudioPlayer:
    def __init__(self):
        pygame.mixer.init()
        self.volume = 0.7
        self.duration = 0.0

    def load(self, path):
        pygame.mixer.music.load(path)
        self.duration = 0.0
        if MUTAGEN_OK:
            try:
                self.duration = MP3(path).info.length
            except Exception:
                pass
        return self.duration

    def play(self):
        pygame.mixer.music.set_volume(self.volume)
        pygame.mixer.music.play()

    def pause(self):
        pygame.mixer.music.pause()

    def unpause(self):
        pygame.mixer.music.unpause()

    def stop(self):
        pygame.mixer.music.stop()

    def get_pos(self):
        ms = pygame.mixer.music.get_pos()
        return ms / 1000.0 if ms >= 0 else 0.0

    def set_pos(self, seconds):
        pygame.mixer.music.set_pos(seconds)

    def set_volume(self, v):
        self.volume = v
        pygame.mixer.music.set_volume(v)

    def is_busy(self):
        return pygame.mixer.music.get_busy()

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
