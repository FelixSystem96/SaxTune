import json
import os

_CONFIG_DIR = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
_PATH = os.path.join(_CONFIG_DIR, 'saxtune', 'config.json')


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
