"""Lazy HTTP adapters. API failures never expose URLs containing bot tokens."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import asyncio

from .harness import TaskContext


def request_json(method, url, *, body=None, headers=None, context=None):
    import httpx
    context = context or TaskContext(timeout=30)
    context.check()
    try:
        with httpx.Client(timeout=httpx.Timeout(min(30, context.remaining), connect=5), trust_env=False) as client:
            with client.stream(method, url, json=body, headers=headers) as response:
                if response.status_code >= 400:
                    raise RuntimeError(f'HTTP {response.status_code}: запрос отклонён')
                data = bytearray()
                for chunk in response.iter_bytes():
                    context.check()
                    data.extend(chunk)
                    if len(data) > 4 * 1024 * 1024:
                        raise ValueError('Ответ сервера слишком велик')
                return json.loads(data)
    except httpx.HTTPError:
        raise ConnectionError('Сервис недоступен или истёк сетевой таймаут') from None


class OllamaProvider:
    def __init__(self, settings):
        settings.validate()
        self.settings = settings
        self.metrics = {}

    def chat(self, messages, tools, context):
        context.check()
        started = time.monotonic()
        self.metrics = {}
        result = {'role': 'assistant', 'content': ''}
        body = {'model': self.settings.model, 'messages': messages, 'tools': tools,
                'think': False, 'stream': True, 'keep_alive': '2m',
                'options': {'num_ctx': self.settings.context_size, 'num_predict': 512, 'temperature': 0.2}}
        # This synchronous entry point is called only by workers / CLI probes.
        # Async I/O permits cancellation even before the first HTTP headers.
        return asyncio.run(self._chat_async(body, result, context, started))

    async def _chat_async(self, body, result, context, started):
        import httpx

        async def receive():
            timeout = httpx.Timeout(min(120, context.remaining), connect=5)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                async with client.stream('POST', self.settings.ollama_url.rstrip('/') + '/api/chat', json=body) as response:
                    if response.status_code != 200:
                        raise RuntimeError('Ollama: HTTP ' + str(response.status_code) + '. Проверьте наличие модели.')
                    pending = bytearray()
                    size = 0
                    async for data in response.aiter_bytes():
                        context.check()
                        size += len(data)
                        if size > 2_000_000:
                            raise ValueError('Ответ модели слишком велик')
                        pending.extend(data)
                        while b'\n' in pending:
                            line, _, rest = pending.partition(b'\n')
                            pending = bytearray(rest)
                            if self._consume(line, result):
                                return result
                    if pending and self._consume(pending, result):
                        return result
                    raise RuntimeError('Ollama прервал ответ до завершения. Повторите запрос.')

        task = asyncio.create_task(receive())
        try:
            while not task.done():
                context.check()
                await asyncio.wait({task}, timeout=.05)
            context.check()
            answer = await task
            self.metrics['wall_seconds'] = round(time.monotonic() - started, 3)
            return answer
        except httpx.HTTPError:
            context.check()
            raise ConnectionError('Ollama не отвечает или истёк таймаут загрузки. Проверьте сервис, модель и память.') from None
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def _consume(self, line, result):
        if not line.strip():
            return False
        chunk = json.loads(line)
        if chunk.get('error'):
            raise RuntimeError('Ollama не смог выполнить запрос. Проверьте модель и доступную память.')
        message = chunk.get('message', {})
        result['content'] += message.get('content', '')
        if message.get('tool_calls'):
            result.setdefault('tool_calls', []).extend(message['tool_calls'])
        if chunk.get('done'):
            self.metrics = {k: chunk.get(k) for k in ('total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')}
            return True
        return False


class OpenAIProvider:
    def __init__(self, settings, secrets):
        self.settings, self.secrets = settings, secrets

    def chat(self, messages, tools, context):
        key = self.secrets.get('openai')
        if not key:
            raise ValueError('Введите OpenAI API key в «Подключениях»')
        cleaned = []
        for msg in messages:
            current = dict(msg)
            if current.get('tool_calls'):
                for call in current['tool_calls']:
                    if isinstance(call['function']['arguments'], dict):
                        call['function']['arguments'] = json.dumps(call['function']['arguments'])
            if current['role'] == 'tool':
                current.pop('tool_name', None)
            cleaned.append(current)
        body = {'model': self.settings.cloud_model, 'messages': cleaned, 'max_completion_tokens': 512}
        if tools:
            body['tools'] = tools
        return request_json('POST', 'https://api.openai.com/v1/chat/completions', body=body,
                            headers={'Authorization': 'Bearer ' + key}, context=context)['choices'][0]['message']


def provider_for(settings, secrets):
    return OpenAIProvider(settings, secrets) if settings.provider == 'openai' else OllamaProvider(settings)


def start_ollama(project: Path):
    try:
        request_json('GET', 'http://127.0.0.1:11434/api/version')
        return 'Ollama уже работает.'
    except (ConnectionError, RuntimeError):
        pass
    portable = project / '.tools' / 'ollama' / 'ollama.exe'
    binary = str(portable) if portable.is_file() else shutil.which('ollama')
    if not binary:
        raise ValueError('Установите Ollama с ollama.com/download/windows')
    environment = os.environ.copy()
    environment['OLLAMA_HOST'] = '127.0.0.1:11434'
    environment['OLLAMA_MODELS'] = str(project / '.cache' / 'ollama-models')
    environment['OLLAMA_MAX_LOADED_MODELS'] = '1'
    environment['OLLAMA_NUM_PARALLEL'] = '1'
    subprocess.Popen([binary, 'serve'], env=environment, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(30):
        time.sleep(.2)
        try:
            request_json('GET', 'http://127.0.0.1:11434/api/version', context=TaskContext(timeout=2))
            return 'Ollama запущен на 127.0.0.1:11434.'
        except (ConnectionError, RuntimeError):
            continue
    raise RuntimeError('Ollama не запустился: проверьте runtime / порт 11434')


def pull_model(settings, context):
    import httpx
    with httpx.Client(timeout=httpx.Timeout(30, connect=5), trust_env=False) as client:
        with client.stream('POST', settings.ollama_url.rstrip('/') + '/api/pull', json={'model': settings.model}) as response:
            if response.status_code != 200:
                raise RuntimeError('Загрузка модели: HTTP ' + str(response.status_code))
            last = ''
            for line in response.iter_lines():
                context.check()
                if not line:
                    continue
                info = json.loads(line)
                if info.get('error'):
                    raise RuntimeError('Не удалось загрузить модель')
                status = info.get('status', '')
                percent = int(100 * info.get('completed', 0) / max(info.get('total', 1), 1))
                if 'total' in info:
                    text = f'Загрузка модели: {percent}%'
                else:
                    text = {'pulling manifest': 'Получение описания модели…',
                            'verifying sha256 digest': 'Проверка скачанных файлов…',
                            'writing manifest': 'Сохранение описания модели…',
                            'success': 'Модель загружена.'}.get(status, 'Подготовка модели…')
                if text != last:
                    context.progress('thinking', text)
                    last = text
    return 'Модель загрузилась. Доступна для локального диалога.'
