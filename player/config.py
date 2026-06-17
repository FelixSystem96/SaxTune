import json
import os

_PATH = os.path.expanduser('~/.config/reproductor-gtk/config.json')


def load():
    try:
        with open(_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save(data):
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    try:
        with open(_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
