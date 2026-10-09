"""Derive spoken text without changing the full answer shown on screen."""

import re
from datetime import date


def _spoken_date(match) -> str:
    day, month, year = map(int, match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return match.group()
    months = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
              'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря')
    return f'{day} {months[month - 1]} {year} года'


def split_sentences(text: str) -> list[str]:
    # A decimal/date dot or known abbreviation is not a sentence boundary.
    result, start = [], 0
    for match in re.finditer(r'[.!?]+(?:[»”"\']*)\s+|[.!?]+$', text):
        end = match.end()
        before = text[start:match.start()]
        if match.group().startswith('.') and re.search(r'\b(?:руб|г|т|д|др|им|ул|стр|рис|см)$', before, re.I):
            continue
        fragment = text[start:end].strip()
        if fragment:
            result.append(fragment)
        start = end
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result


def prepare_speech(text: str, brief: bool = False) -> str:
    text = re.sub(r'```.*?(?:```|$)', ' ', text, flags=re.S)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)]\s+)', '', text, flags=re.M)
    text = re.sub(r'[`*_~|]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # Explicit common abbreviations; do not guess ambiguous dates or numbers.
    text = re.sub(r'\bт\.\s*е\.', 'то есть', text, flags=re.I)
    text = re.sub(r'\bт\.\s*д\.', 'так далее', text, flags=re.I)
    text = re.sub(r'\b(\d{2})\.(\d{2})\.(\d{4})\b', _spoken_date, text)
    text = re.sub(r'№\s*(?=\d)', 'номер ', text)
    sentences = split_sentences(text)
    return ' '.join(sentences[:3] if brief else sentences)
