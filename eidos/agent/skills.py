"""Honest metadata, never a substitute for registry permissions."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    purpose: str
    tools: tuple[str, ...]
    requirements: str
    permissions: tuple[str, ...]
    status: str


def catalog(model_connected=False, search_ready=True):
    ai = 'Доступен' if model_connected else 'Требуется подключение'
    return [
        Skill('Поиск и краткое изложение', 'Brave API возвращает источники; DuckDuckGo/Bing открывают поиск в браузере. Чтение публичной страницы и изложение через модель.', ('web_search','web_read'), 'Модель; интернет; Brave key для поиска через API', ('browser.open','browser.read'), ai if search_ready else 'Требуется подключение'),
        Skill('Программирование', 'Объяснение и подготовка кода в диалоге. Автоматический запуск кода отсутствует.', (), 'Ollama или OpenAI', (), ai),
        Skill('Тексты и письма', 'Подготовка черновика. Отправка только через подключённого бота с подтверждением.', ('document_write',), 'Модель для составления', ('documents.write',), ai),
        Skill('Документы', 'Чтение выбранного файла; создание TXT/MD/DOCX/PDF, новой версии текста.', ('document_read','document_write'), 'Файл / рабочая папка выбраны пользователем', ('documents.read','documents.write'), 'Доступен'),
        Skill('Таблицы', 'Чтение XLSX (200 строк на лист); создание новой таблицы из TSV без формул.', ('document_read','document_write'), 'Выбран файл / папка', ('documents.read','documents.write'), 'Доступен'),
        Skill('PDF', 'Извлечение текстового слоя и создание текстового PDF. Скан без OCR не распознаётся.', ('document_read','document_write'), 'Выбран файл / папка', ('documents.read','documents.write'), 'Доступен'),
        Skill('Перевод текста', 'Перевод введённого текста через модель. Перевод экрана пока не подключён.', (), 'Ollama или OpenAI', (), ai),
        Skill('Планирование', 'Текстовый план в диалоге и локальные события.', ('calendar_list','calendar_change'), 'Модель для плана', ('calendar.read','calendar.write'), ai),
        Skill('Календарь', 'Локальные события и напоминания, без внешней синхронизации.', ('calendar_list','calendar_change'), 'Приложение открыто для напоминаний', ('calendar.read','calendar.write'), 'Доступен'),
        Skill('Поиск файлов', 'Только имена в выбранной папке, максимум 3000 файлов.', ('file_search',), 'Выбрана конкретная папка', ('documents.read',), 'Доступен'),
        Skill('Запуск приложений', 'Только EXE, добавленные пользователем в список.', ('open_app','windows_settings'), 'Разрешённый список приложений', ('windows.apps','windows.settings'), 'Доступен'),
        Skill('Управление звуком', 'Громкость и mute через Windows Core Audio, проверка чтением.', ('volume','mute'), 'Windows и аудиовыход', ('windows.audio',), 'Доступен'),
        Skill('Дизайн и обработка фото', 'Советы по рабочему процессу через диалог. Автоматическая обработка изображений отсутствует.', (), 'Модель для советов', (), ai),
        Skill('Голосовые команды', 'Существующий ручной цикл записи / Whisper / ответа / TTS.', ('volume','mute','windows_settings'), 'Микрофон; модель Whisper, интернет для TTS', ('windows.audio','windows.settings'), 'Доступен'),
        Skill('Жесты и OCR экрана', 'Интерфейсы будущих модулей; камера и захват экрана не включаются.', (), 'Следующий этап', (), 'Пока не реализован'),
    ]
