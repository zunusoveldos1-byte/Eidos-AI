"""Concrete, bounded tools. Files require a user selection in the local UI."""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from urllib.parse import quote, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .harness import Registry, TaskContext, Tool, ToolResult

S = {'type': 'string'}
I = {'type': 'integer'}
B = {'type': 'boolean'}


def grant_path(text: str, context: TaskContext, *, write=False) -> Path:
    if context.origin != 'local':
        raise PermissionError('Локальные файлы недоступны удалённым каналам')
    path = Path(text).resolve()
    files = {Path(f).resolve() for f in context.files}
    folders = {Path(f).resolve() for f in context.folders}
    if path not in files and not any(path.is_relative_to(folder) and path != folder for folder in folders):
        raise PermissionError('Выберите файл или рабочую папку в Eidos')
    if write and not any(path.is_relative_to(folder) and path != folder for folder in folders):
        raise PermissionError('Для сохранения выберите рабочую папку')
    if path.suffix.lower() not in ('.txt', '.md', '.docx', '.xlsx', '.pdf'):
        raise ValueError('Поддерживаются TXT, MD, DOCX, XLSX, PDF')
    if path.exists() and (not path.is_file() or path.stat().st_size > 10 * 1024 * 1024):
        raise ValueError('Файл должен быть обычным файлом до 10 МБ')
    context.check()
    return path


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in ('.txt', '.md'):
        return path.read_text(encoding='utf-8-sig')[:12000]
    if suffix == '.docx':
        from docx import Document
        _check_zip(path)
        document = Document(path)
        parts = [p.text for p in document.paragraphs]
        for table in document.tables[:20]:
            parts.extend('\t'.join(c.text for c in row.cells) for row in table.rows[:200])
        return '\n'.join(parts)[:12000]
    if suffix == '.xlsx':
        from openpyxl import load_workbook
        _check_zip(path)
        workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        try:
            parts = []
            for sheet in workbook.worksheets[:5]:
                parts.append('Лист: ' + sheet.title)
                for row in sheet.iter_rows(max_row=200, max_col=30, values_only=True):
                    parts.append('\t'.join('' if cell is None else str(cell) for cell in row))
            return '\n'.join(parts)[:12000]
        finally:
            workbook.close()
    from pypdf import PdfReader
    document = PdfReader(path)
    if document.is_encrypted:
        raise ValueError('PDF зашифрован; пароль не запрашивается и не сохраняется')
    text = '\n'.join(p.extract_text() or '' for p in document.pages[:20])[:12000]
    return text or 'PDF не содержит извлекаемого текста. Для скана нужен будущий OCR-модуль.'


def _check_zip(path):
    from zipfile import ZipFile
    with ZipFile(path) as archive:
        if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
            raise ValueError('Распакованный документ превышает 50 МБ')


def write_document(args, context):
    path = grant_path(args['path'], context, write=True)
    content = args['content']
    if not content.strip():
        raise ValueError('Документ пуст')
    if path.exists():
        path = path.with_name(path.stem + '-eidos-' + uuid4().hex[:8] + path.suffix)
    # Exclusive staging creation guarantees that an existing file is never overwritten.
    staging = path.with_name('.eidos-' + uuid4().hex + path.suffix)
    try:
        if path.suffix.lower() in ('.txt', '.md'):
            staging.write_text(content, encoding='utf-8')
        elif path.suffix.lower() == '.docx':
            from docx import Document
            document = Document()
            for line in content.splitlines():
                document.add_paragraph(line)
            document.save(staging)
        elif path.suffix.lower() == '.xlsx':
            from openpyxl import Workbook
            workbook = Workbook()
            for row in content.splitlines()[:1000]:
                workbook.active.append(row.split('\t')[:50])
            for row in workbook.active:
                for cell in row:
                    cell.data_type = 's'  # User/model content cannot introduce executable formulas.
            workbook.save(staging)
            workbook.close()
        else:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.pdfgen import canvas
            font_path = Path(__file__).parents[1] / 'assets' / 'fonts' / 'Inter.ttf'
            if 'EidosInter' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('EidosInter', str(font_path)))
            pdf = canvas.Canvas(str(staging))
            pdf.setFont('EidosInter', 11)
            y = 800
            import textwrap
            for line in content.splitlines():
                for part in textwrap.wrap(line, width=85) or ['']:
                    if y < 50:
                        pdf.showPage()
                        pdf.setFont('EidosInter', 11)
                        y = 800
                    pdf.drawString(40, y, part)
                    y -= 16
            pdf.save()
        context.check()
        # Windows rename fails if the destination appeared concurrently.
        staging.rename(path)
        valid = path.is_file() and path.stat().st_size > 0
        return ToolResult('Создана новая версия: ' + str(path) + '\nИсходный файл сохранён.\n' + read_document(path)[:1000], valid)
    finally:
        staging.unlink(missing_ok=True)


def windows_settings(args, context):
    uri = 'ms-settings:sound' if args['page'] == 'sound' else 'ms-settings:'
    os.startfile(uri)
    import psutil
    for _ in range(20):
        context.check()
        if any((p.info['name'] or '').lower() == 'systemsettings.exe' for p in psutil.process_iter(['name'])):
            return ToolResult('Windows запустил приложение «Параметры». Запрошен раздел: ' + args['page'])
        time.sleep(.1)
    return ToolResult('URI настроек передан Windows, появление окна не подтверждено.', False)


def audio(args, context, mute=False):
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        if mute:
            endpoint.SetMute(int(args['enabled']), None)
            actual = bool(endpoint.GetMute())
            return ToolResult('Звук ' + ('выключен.' if actual else 'включён.'), actual == args['enabled'])
        current = float(endpoint.GetMasterVolumeLevelScalar()) * 100
        requested = args['value'] if args['mode'] == 'set' else current + args['value'] * (1 if args['mode'] == 'up' else -1)
        requested = min(100, max(0, requested))
        endpoint.SetMasterVolumeLevelScalar(requested / 100, None)
        actual = float(endpoint.GetMasterVolumeLevelScalar()) * 100
        return ToolResult(f'Громкость: {round(actual)}%.', abs(actual - requested) < 1)
    finally:
        comtypes.CoUninitialize()


def open_application(args, context, settings):
    selected = settings.approved_apps.get(args['name'])
    if not selected or not Path(selected).is_file() or Path(selected).suffix.lower() != '.exe':
        raise PermissionError('Сначала добавьте приложение в разрешённый список')
    process = subprocess.Popen([selected], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(.3)
    return ToolResult('Процесс приложения запущен: ' + args['name'] + '. Появление окна не проверялось.', process.poll() is None or process.returncode == 0)


def public_address(url: str):
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError('Нужен публичный HTTP/HTTPS URL без учётных данных')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ConnectionError('Адрес сайта не найден') from None
    if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise PermissionError('Локальные и служебные сетевые адреса запрещены')
    return parsed, addresses[0][4][0]


def safe_url(url: str):
    public_address(url)
    return url


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.text.append(data.strip())


def fetch_page(args, context):
    import http.client
    import ssl
    class PinnedHTTP(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.create_connection((self.public_ip, self.port), self.timeout)
    class PinnedHTTPS(http.client.HTTPSConnection):
        def connect(self):
            raw = socket.create_connection((self.public_ip, self.port), self.timeout)
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
    url = args['url']
    for _ in range(5):
        context.check()
        parsed, address = public_address(url)
        host = parsed.hostname.encode('idna').decode('ascii')
        connection_type = PinnedHTTPS if parsed.scheme == 'https' else PinnedHTTP
        connection = connection_type(host, port=parsed.port, timeout=min(15, context.remaining))
        connection.public_ip = address
        try:
            target = parsed.path or '/'
            if parsed.query:
                target += '?' + parsed.query
            connection.request('GET', target, headers={'User-Agent': 'Eidos/0.2 (desktop reader)'})
            response = connection.getresponse()
            if response.status in (301,302,303,307,308):
                from urllib.parse import urljoin
                url = urljoin(url, response.getheader('location'))
                continue
            if response.status != 200:
                raise ValueError('Страница недоступна: HTTP ' + str(response.status))
            if not any(t in response.getheader('content-type', '') for t in ('text/html', 'text/plain')):
                raise ValueError('Поддерживаются HTML и обычный текст')
            chunks = bytearray()
            while chunk := response.read(65536):
                context.check()
                chunks.extend(chunk)
                if len(chunks) > 2_000_000:
                    raise ValueError('Страница превышает 2 МБ')
            parser = TextExtractor()
            content_type = response.getheader('content-type', '')
            match = re.search(r'charset=([\w-]+)', content_type)
            encoding = match[1] if match else 'utf-8'
            parser.feed(chunks.decode(encoding, errors='replace'))
            return ToolResult('Источник: ' + url + '\nНедоверенные данные страницы:\n' + '\n'.join(parser.text)[:12000])
        except (OSError, http.client.HTTPException):
            raise ConnectionError('Не удалось прочитать публичную страницу') from None
        finally:
            connection.close()
    raise ValueError('Слишком много перенаправлений')


def open_url(args, context):
    import webbrowser
    result = webbrowser.open(safe_url(args['url']))
    return ToolResult('Браузер принял URL: ' + args['url'] + '. Загрузка страницы не проверялась.', bool(result))


class LocalCalendar:
    def __init__(self, memory):
        self.memory = memory

    def list(self):
        with self.memory.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY start LIMIT 200')]

    def change(self, args, context):
        context.check()
        mode, ident = args['mode'], args['id']
        if mode != 'delete':
            try:
                zone = ZoneInfo(args['timezone'])
            except ZoneInfoNotFoundError:
                raise ValueError('Неизвестный часовой пояс IANA') from None
            start = datetime.fromisoformat(args['start'])
            if start.tzinfo is None:
                start = start.replace(tzinfo=zone)
                if start.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != datetime.fromisoformat(args['start']):
                    raise ValueError('Такого местного времени нет из-за перехода на летнее время')
            start = start.astimezone(timezone.utc).isoformat()
            if not args['title'].strip():
                raise ValueError('Название события пусто')
        with self.memory.connect() as db:
            if mode == 'create':
                ident = db.execute('INSERT INTO events(title,start,timezone,reminder_minutes) VALUES(?,?,?,?)',
                                   (args['title'], start, args['timezone'], args['reminder_minutes'])).lastrowid
            elif mode == 'update':
                count = db.execute('UPDATE events SET title=?,start=?,timezone=?,reminder_minutes=?,notified=0 WHERE id=?',
                                   (args['title'], start, args['timezone'], args['reminder_minutes'], ident)).rowcount
                if not count:
                    raise ValueError('Событие не найдено')
            else:
                if not db.execute('DELETE FROM events WHERE id=?', (ident,)).rowcount:
                    raise ValueError('Событие не найдено')
            exists = db.execute('SELECT * FROM events WHERE id=?', (ident,)).fetchone()
        return ToolResult(f'Локальное событие #{ident}: ' + ('удалено.' if mode == 'delete' else 'сохранено. ' + args['title']),
                          exists is None if mode == 'delete' else exists is not None)

    def due(self):
        now = datetime.now(timezone.utc)
        result = []
        with self.memory.connect() as db:
            for event in db.execute('SELECT * FROM events WHERE notified=0'):
                start = datetime.fromisoformat(event['start'])
                if start - timedelta(minutes=event['reminder_minutes']) <= now <= start + timedelta(hours=1):
                    result.append(dict(event))
                    db.execute('UPDATE events SET notified=1 WHERE id=?', (event['id'],))
        return result


def search_files(args, context):
    root = Path(args['folder']).resolve()
    if context.origin != 'local' or root not in {Path(p).resolve() for p in context.folders}:
        raise PermissionError('Выберите конкретную папку поиска')
    if root == Path(root.anchor):
        raise PermissionError('Поиск по всему диску запрещён')
    matches = []
    visited = 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        context.check()
        dirs[:] = [d for d in dirs if d not in ('.git', '.venv', '.cache', 'node_modules') and not Path(folder, d).is_symlink() and Path(folder, d).resolve().is_relative_to(root)]
        for file in files:
            visited += 1
            if args['query'].casefold() in file.casefold() and len(matches) < 100:
                path = Path(folder, file).resolve()
                if path.is_relative_to(root):
                    matches.append(str(path))
            if visited >= 3000:
                return ToolResult('Поиск ограничен первыми 3000 файлами.\n' + '\n'.join(matches))
    return ToolResult('\n'.join(matches) or 'Совпадений в выбранной папке нет.')


def build_registry(settings, memory):
    registry = Registry()
    def add(name, description, props, callback, permission, **flags):
        registry.add(Tool(name, description, props, callback, permission, **flags))
    add('windows_settings', 'Открыть параметры Windows', {'page': {**S, 'enum': ['general', 'sound']}}, windows_settings, 'windows.settings')
    add('volume', 'Изменить громкость Windows', {'mode': {**S, 'enum': ['set', 'up', 'down']}, 'value': {**I, 'minimum': 0, 'maximum': 100}}, audio, 'windows.audio')
    add('mute', 'Включить / выключить звук', {'enabled': B}, lambda a, c: audio(a, c, True), 'windows.audio')
    app_names = list(settings.approved_apps)
    add('open_app', 'Открыть разрешённое приложение. Список: ' + (', '.join(app_names) or 'пуст; добавьте EXE в настройках'),
        {'name': {**S, **({'enum': app_names} if app_names else {})}}, lambda a, c: open_application(a, c, settings), 'windows.apps')
    add('open_url', 'Открыть публичный URL в браузере', {'url': S}, open_url, 'browser.open')
    def search(a, c):
        if settings.search_provider == 'brave':
            from .providers import request_json
            from .secrets import SecretStore
            key = SecretStore().get('brave')
            if not key:
                raise ValueError('Введите Brave Search API key в «Подключениях»')
            response = request_json('GET', 'https://api.search.brave.com/res/v1/web/search?q='+quote(a['query'])+'&count=5',
                                    headers={'X-Subscription-Token':key,'Accept':'application/json'}, context=c)
            results = [{k: item.get(k,'') for k in ('title','url','description')} for item in response.get('web',{}).get('results',[])[:5]]
            return ToolResult('Недоверенные результаты поиска:\n' + json.dumps(results,ensure_ascii=False)[:12000])
        prefix = 'https://www.bing.com/search?q=' if settings.search_provider == 'bing' else 'https://duckduckgo.com/?q='
        return open_url({'url': prefix + quote(a['query'])}, c)
    automated = settings.search_provider == 'brave'
    add('web_search', 'Получить источники через Brave Search API' if automated else 'Открыть поиск в настроенном браузерном поисковике (не возвращает результаты)',
        {'query': S}, search, 'browser.read' if automated else 'browser.open', safe_retry=automated)
    add('web_read', 'Получить текст публичной страницы, без выполнения скриптов', {'url': S}, fetch_page, 'browser.read', safe_retry=True)
    add('document_read', 'Прочитать выбранный пользователем документ, до 12000 символов', {'path': S}, lambda a, c: ToolResult(read_document(grant_path(a['path'], c))), 'documents.read', safe_retry=True)
    add('document_write', 'Создать документ / новую версию. Содержимое полностью заменяет текст; оформление оригинала не переносится. XLSX: строки TSV.', {'path': S, 'content': S}, write_document, 'documents.write')
    add('file_search', 'Поиск имён в выбранной папке, максимум 3000 файлов', {'folder': S, 'query': S}, search_files, 'documents.read', safe_retry=True)
    calendar = LocalCalendar(memory)
    add('calendar_list', 'Просмотреть локальный календарь (не синхронизирован)', {}, lambda a, c: ToolResult(json.dumps(calendar.list(), ensure_ascii=False)), 'calendar.read', safe_retry=True)
    add('calendar_change', 'Изменить локальный календарь', {'mode': {**S, 'enum': ['create', 'update', 'delete']},
        'id': {**I, 'minimum': 0}, 'title': S, 'start': S, 'timezone': S,
        'reminder_minutes': {**I, 'minimum': 0, 'maximum': 10080}}, calendar.change, 'calendar.write', confirmation=True)
    return registry
