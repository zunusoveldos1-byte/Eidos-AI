"""Local keyed catalogues with Russian fallback; no network at runtime."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import weakref

LANGUAGES = {'ru': 'Русский', 'en': 'English', 'ky': 'кыргызча', 'uz': 'o‘zbekcha', 'kk': 'қазақша'}
DIRECTORY = Path(__file__).resolve().parents[1] / 'assets' / 'i18n'
_language = 'ru'
_catalogs = {}
_sources = {}
_templates = []
_fragments = []
_widgets = weakref.WeakSet()
_missing = set()


def language():
    return _language


def key(source):
    return 'msg.' + hashlib.sha256(source.encode()).hexdigest()[:16]


def load():
    global _catalogs, _sources, _templates, _fragments
    if _catalogs:
        return
    for language in LANGUAGES:
        path = DIRECTORY / f'{language}.json'
        _catalogs[language] = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    _sources = {source: ident for ident, source in _catalogs['ru'].items()}
    for source, ident in list(_sources.items()):
        if source.strip():
            _sources.setdefault(source.strip(), ident)
    _fragments = sorted((part for part in _sources if not re.search(r'\{\d+\}', part)
                         and len(part.strip()) >= 4), key=len, reverse=True)
    for source, ident in _sources.items():
        if re.search(r'\{\d+\}', source):
            fragments = re.split(r'(\{\d+\})', source)
            pattern = '^' + ''.join('(.+?)' if re.fullmatch(r'\{\d+\}', part) else re.escape(part)
                                    for part in fragments) + '$'
            tokens = re.findall(r'\{\d+\}', source)
            _templates.append((re.compile(pattern, re.DOTALL), ident, tokens))
    _templates.sort(key=lambda entry: len(_catalogs['ru'][entry[1]]), reverse=True)


def t(ident, **values):
    load()
    if ident not in _catalogs.get(_language, {}):
        _missing.add((_language, ident))
    result = _catalogs.get(_language, {}).get(ident, _catalogs['ru'].get(ident, ident))
    return result.format(**values) if values else result


@lru_cache(maxsize=2048)
def tr(source):
    if not isinstance(source, str) or not source or _language == 'ru':
        return source
    load()
    if source in _sources:
        ident = _sources[source]
        translated = t(ident)
        return translated.strip() if _catalogs['ru'][ident] != source else translated
    if source.strip() != source:
        left = source[:len(source) - len(source.lstrip())]
        right = source[len(source.rstrip()):]
        return left + tr(source.strip()) + right
    for pattern, ident, tokens in _templates:
        match = pattern.match(source)
        if match:
            text = t(ident)
            for token, value in zip(tokens, match.groups()):
                text = text.replace(token, tr(value))
            return text
    for separator in ('\n', ' · '):
        if separator in source:
            return separator.join(tr(part) for part in source.split(separator))
    # Concatenated operational messages: preserve dynamic file/model/device
    # names and translate known static prefixes/suffixes only.
    for part in _fragments:
        if source.startswith(part) and len(part) < len(source):
            return t(_sources[part]) + tr(source[len(part):])
    for prefix in ('●  ', '● ', '… ', '✓ ', '✕ '):
        if source.startswith(prefix):
            return prefix + tr(source[len(prefix):])
    if re.search('[А-Яа-яЁё]', source):
        _missing.add((_language, key(source)))
    return source


def set_language(language):
    global _language
    if language not in LANGUAGES:
        raise ValueError('Неизвестный язык интерфейса')
    load()
    if _language == language:
        return
    _language = language
    tr.cache_clear()
    for widget in list(_widgets):
        try:
            widget.retranslate()
        except RuntimeError:
            _widgets.discard(widget)


def register(widget):
    _widgets.add(widget)


def coverage():
    load()
    return {language: sorted(_catalogs['ru'].keys() - catalog.keys())
            for language, catalog in _catalogs.items()}


def missing():
    return sorted(_missing)
