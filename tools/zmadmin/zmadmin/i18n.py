"""The interface language of ZmClient and of the zmadmin parts it shares (widgets, server queries, map labels).

The texts in the code are English. French comes from tables keyed by the English text, which each module adds with
add_french(). tr() is applied where a text is shown, never where it is defined: the language can change while the
program runs (ZmClient's Launch view), and the modules are imported before the profile that holds it is read.
ZmAdmin stays French: its main() calls set_language("fr").
"""

LANGUAGES = ("en", "fr")

_language = "en"
_french = {}


def set_language(lang):
    global _language
    if lang not in LANGUAGES:
        raise ValueError(f"unknown language {lang!r}")
    _language = lang


def language():
    return _language


def add_french(table):
    """Adds English -> French pairs. The same English text given two different translations is a mistake: the
    first module's text would change under the second one's feet."""
    for en, fr in table.items():
        old = _french.get(en)
        if old is not None and old != fr:
            raise ValueError(f"two French texts for {en!r}: {old!r} and {fr!r}")
        _french[en] = fr


def french_table():
    """All the pairs, for the tests."""
    return dict(_french)


def tr(text):
    if _language == "fr" and isinstance(text, str):
        return _french.get(text, text)
    return text


class TrDict(dict):
    """A table of texts (labels, help lines) whose values translate when read."""

    def __getitem__(self, key):
        return tr(super().__getitem__(key))

    def get(self, key, default=None):
        return tr(super().get(key, default))

    def values(self):
        return [tr(v) for v in super().values()]

    def items(self):
        return [(k, tr(v)) for k, v in super().items()]


from .fr_shared import FR as _SHARED_FR  # noqa: E402
add_french(_SHARED_FR)
