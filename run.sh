#!/bin/sh
mkdir -p po/locale/es/LC_MESSAGES
msgfmt po/es.po -o po/locale/es/LC_MESSAGES/saxtune.mo 2>/dev/null || true
PYTHONPATH=src python3 -c "
import locale, gettext
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass
gettext.bindtextdomain('saxtune', 'po/locale')
gettext.textdomain('saxtune')
from saxtune.main import main
main()
"
