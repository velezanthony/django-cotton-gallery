"""Fail if any locale has fuzzy or untranslated entries.

A fuzzy entry is not an error for gettext: Django serves the previous
translation, so the page renders fine and says the old thing. Nothing tells
you until a user reads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import polib

LOCALES = ("es", "eu", "fr")
LOCALE_DIR = Path("src/django_cotton_gallery/locale")


def untranslated(entry: polib.POEntry) -> bool:
    """A plural entry keeps its translations in `msgstr_plural`, not `msgstr`."""
    if entry.obsolete:
        return False
    if entry.msgid_plural:
        return not all(entry.msgstr_plural.values())
    return not entry.msgstr


def main() -> int:
    failed = False
    for lang in LOCALES:
        po = polib.pofile(str(LOCALE_DIR / lang / "LC_MESSAGES" / "django.po"))
        fuzzy = [e for e in po if "fuzzy" in e.flags]
        missing = [e for e in po if untranslated(e)]
        if not fuzzy and not missing:
            continue
        failed = True
        print(f"{lang}: {len(fuzzy)} fuzzy, {len(missing)} untranslated")
        for entry in (fuzzy + missing)[:10]:
            print(f"    {entry.msgid[:70]}")
    if failed:
        print("\nRun `make messages`, translate, then `make compile-messages`.")
        return 1
    print(f"i18n OK — {', '.join(LOCALES)} fully translated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
