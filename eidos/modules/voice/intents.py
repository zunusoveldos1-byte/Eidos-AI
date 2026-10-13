"""Small explicit voice grammar. It never rewrites repeated words in a request."""
import re

RETRY_SPEECH = 'Не удалось разобрать речь. Подойдите ближе к микрофону и повторите'


def strip_wake_prefix(text: str) -> str:
    return re.sub(r'^\s*(?:эй\s*д[оуа]с|эйдос|ейдос|эйдус|эйдоз|эдос|айдос|eidos|aidos)\b[\s,.:!—-]*',
                  '', text, count=1, flags=re.IGNORECASE).strip()


def ui_intent(text: str) -> str | None:
    normalized = ' '.join(re.sub(r'[^\w\s]', ' ', text.lower().replace('ё', 'е')).split())
    return {
        'переведи область экрана': 'translate_region', 'переведи область': 'translate_region',
        'переведи выделенную область': 'translate_region', 'переведи экран': 'translate_region',
        'прочитай оригинал': 'read_original', 'прочитай исходный текст': 'read_original',
        'прочитай перевод': 'read_translation', 'озвучь перевод': 'read_translation',
    }.get(normalized)
