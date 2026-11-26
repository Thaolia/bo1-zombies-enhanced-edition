"""ZmClient's French texts, keyed by the English text the code shows (zmadmin/i18n.py)."""
from zmadmin.i18n import add_french

from . import app, help, views

for _module in (app, help, views):
    add_french(_module.FR)
