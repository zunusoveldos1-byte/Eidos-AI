import re
from urllib.parse import urlencode, urlsplit

SITES = {'ютуб': ('YouTube', 'https://www.youtube.com/'), 'youtube': ('YouTube', 'https://www.youtube.com/'),
    'ютюб': ('YouTube', 'https://www.youtube.com/'), 'гитхаб': ('GitHub', 'https://github.com/'),
    'github': ('GitHub', 'https://github.com/'), 'гугл': ('Google', 'https://www.google.com/')}


def number(text):
    if text.isdigit(): return int(text)
    units = dict(zip('ноль один два три четыре пять шесть семь восемь девять десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать'.split(), range(20)))
    tens = dict(zip('двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто'.split(), range(20, 100, 10)))
    if text in {**units, **tens, 'сто': 100}: return {**units, **tens, 'сто': 100}[text]
    parts = text.split()
    if len(parts) == 2 and parts[0] in tens and 0 < units.get(parts[1], 0) < 10:
        return tens[parts[0]] + units[parts[1]]
    return None


def navigation_url(value):
    value = value.strip()
    if '://' not in value: value = 'https://' + value
    parsed = urlsplit(value)
    try: port = parsed.port
    except ValueError: raise ValueError('Некорректный адрес сайта') from None
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password
            or any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value
            or port not in (None, 80, 443)):
        raise ValueError('Нужен HTTP/HTTPS-адрес без учётных данных')
    host = parsed.hostname.encode('idna').decode('ascii')
    if '.' not in host and host != 'localhost': raise ValueError('Уточните адрес сайта, например example.com')
    return parsed._replace(netloc=host + (':' + str(port) if port else '')).geturl()


def search_url(query, provider):
    base, key = {'google': ('https://www.google.com/search', 'q'),
        'bing': ('https://www.bing.com/search', 'q'),
        'duckduckgo': ('https://duckduckgo.com/', 'q'),
        'brave': ('https://search.brave.com/search', 'q')}.get(provider, ('https://www.google.com/search', 'q'))
    return base + '?' + urlencode({key: query})


def parse(text):
    raw = text.strip().rstrip('.!?')
    normalized = ' '.join(re.sub(r'[^\w\s]', ' ', raw.lower().replace('ё', 'е')).split())
    if ('громкость' in normalized or 'звук' in normalized) and re.search(r'(?:[-−]\s*\d|\d[.,]\d)', raw):
        return 'refuse', {'text': 'Укажите целое значение от 0 до 100 процентов.'}
    fixed = {
        'сделай скриншот': ('screenshot', {'mode': 'primary'}),
        'сфотографируй экран': ('screenshot', {'mode': 'primary'}), 'заскринь': ('screenshot', {'mode': 'primary'}),
        'сделай скриншот области': ('screenshot', {'mode': 'region'}),
        'сделай скриншот всех экранов': ('screenshot', {'mode': 'all'}),
        'сохрани скриншот': ('screenshot', {'mode': 'save'}),
        'сверни все окна': ('desktop', {}), 'покажи рабочий стол': ('desktop', {}),
        'заблокируй экран': ('lock', {}),
        'выключи компьютер': ('power', {'action': 'shutdown'}), 'перезагрузи компьютер': ('power', {'action': 'restart'}),
        'подтверждаю выключение': ('power_confirm', {'action': 'shutdown'}),
        'подтверждаю перезагрузку': ('power_confirm', {'action': 'restart'}),
        'отмена': ('power_cancel', {}),
        'сохрани сессию': ('session_save', {}), 'восстанови сессию': ('session_restore', {}),
        'открой прошлые приложения': ('session_restore', {}), 'верни то что было открыто': ('session_restore', {}),
        'какие планы на сегодня': ('today', {}), 'что у нас сегодня': ('today', {}),
        'покажи задачи на сегодня': ('today', {}), 'покажи расписание': ('schedule', {}),
        'открой браузер': ('browser', {}), 'запусти интернет': ('browser', {}),
        'сделай громче': ('volume', {'mode': 'up', 'value': 10}), 'прибавь звук': ('volume', {'mode': 'up', 'value': 10}),
        'сделай тише': ('volume', {'mode': 'down', 'value': 10}), 'убавь звук': ('volume', {'mode': 'down', 'value': 10}),
        'мут': ('mute', {'enabled': True}), 'какая сейчас громкость': ('volume_status', {}),
        'выключи звук': ('mute', {'enabled': True}), 'включи звук': ('mute', {'enabled': False}),
        'сделай звук потише': ('volume', {'mode': 'down', 'value': 10}),
        'сделай звук погромче': ('volume', {'mode': 'up', 'value': 10}),
    }
    if normalized in fixed: return fixed[normalized]
    if re.search(r'\b(?:выключ|перезагру|заблокир|скриншот|сверни|откро|откры|запуст|запуск|громк|звук)\w*', normalized) and re.search(r'\b(?:не|как|зачем|если|можно|почему)\b', normalized):
        return 'refuse', {'text': 'Действие не выполняю. Для выполнения нужна явная команда.'}
    match = re.fullmatch(r'(установи|сделай|прибавь|увеличь|убавь|уменьши) (?:громкость|звук)(?: на)? (.+?)(?: процент(?:ов|а)?)?', normalized)
    if match:
        value = number(match[2])
        if value is not None:
            if not 0 <= value <= 100: return 'refuse', {'text': 'Укажите значение от 0 до 100 процентов.'}
            mode = 'set' if match[1] in ('установи', 'сделай') else 'up' if match[1] in ('прибавь', 'увеличь') else 'down'
            return 'volume', {'mode': mode, 'value': value}
    match = re.fullmatch(r'(?:найди в интернете|гугли)\s+(.+)', raw, re.I)
    if match: return 'search_browser', {'query': match[1]}
    match = re.fullmatch(r'добавь задачу (.+) на сегодня', raw, re.I)
    if match: return 'task_add', {'title': match[1]}
    match = re.fullmatch(r'(?:открой|запусти|включи)\s+(.+)', raw, re.I)
    if match:
        target = match[1].strip()
        if target.lower() in SITES:
            title, url = SITES[target.lower()]
            return 'site', {'title': title, 'url': url}
        if target.lower().startswith('сайт '):
            return 'site', {'title': target[5:], 'url': navigation_url(target[5:])}
        if '.' in target and ' ' not in target:
            return 'site', {'title': target, 'url': navigation_url(target)}
        if normalized not in ('открой настройки', 'открой настройки звука', 'открой блокнот', 'запусти блокнот'):
            return 'application', {'name': target}
    return None
