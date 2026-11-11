"""Gemini GenerateContent REST adapter; async transport runs in AgentWorker."""
import asyncio
from copy import deepcopy
import json
import time

from .memory import require_public_payload


class GeminiProvider:
    BASE = 'https://generativelanguage.googleapis.com/v1beta/models/'

    def __init__(self, settings, secrets):
        settings.validate()
        self.settings, self.secrets = settings, secrets
        self.metrics = {}

    def _body(self, messages, tools):
        contents, system, call_names = [], [], {}
        for msg in messages:
            role = msg['role']
            if role == 'system':
                system.append({'text': str(msg.get('content', ''))})
                continue
            if role == 'tool':
                name, server_id = call_names.get(msg.get('tool_call_id'), (msg.get('tool_name'), None))
                if not name:
                    raise ValueError('Gemini: результат инструмента без имени.')
                response = {'name': name, 'response': {'result': msg.get('content', '')}}
                if server_id:
                    response['id'] = server_id
                parts = [{'functionResponse': response}]
            elif role == 'assistant':
                parts = deepcopy(msg.get('_gemini_parts', []))
                if not parts:
                    if msg.get('content'):
                        parts.append({'text': str(msg['content'])})
                    for call in msg.get('tool_calls', []):
                        fn = call['function']
                        args = fn['arguments']
                        parts.append({'functionCall': {'name': fn['name'],
                            'args': json.loads(args) if isinstance(args, str) else args}})
                wire_calls = [p['functionCall'] for p in parts if 'functionCall' in p]
                for call, wire in zip(msg.get('tool_calls', []), wire_calls):
                    call_names[call.get('id')] = (wire['name'], wire.get('id'))
            elif role == 'user':
                parts = [{'text': str(msg.get('content', ''))}]
            else:
                raise ValueError('Gemini: неизвестная роль сообщения.')
            if not parts:
                continue
            target = 'model' if role == 'assistant' else 'user'
            if contents and contents[-1]['role'] == target:
                contents[-1]['parts'].extend(parts)
            else:
                contents.append({'role': target, 'parts': parts})
        body = {'contents': contents, 'generationConfig': {'maxOutputTokens': 2048, 'temperature': .2}}
        if system:
            body['systemInstruction'] = {'parts': system}
        if tools:
            body['tools'] = [{'functionDeclarations': [{'name': t['function']['name'],
                'description': t['function'].get('description', ''),
                'parametersJsonSchema': deepcopy(t['function']['parameters'])} for t in tools]}]
        return body

    def chat(self, messages, tools, context):
        context.check()
        key = self.secrets.get('gemini')
        if not key:
            raise ValueError('Введите ключ Gemini API во вкладке «Модель».')
        body = self._body(messages, tools)
        require_public_payload(body, (*context.secret_values, key))
        started = time.perf_counter()
        model = self.settings.gemini_model.removeprefix('models/')
        data = asyncio.run(self._request('POST', model + ':generateContent', context, body))
        context.check()
        candidates = data.get('candidates') or []
        if not candidates:
            raise RuntimeError('Gemini не вернул ответ. Возможна блокировка запроса фильтром сервиса.')
        candidate = candidates[0]
        if candidate.get('finishReason') not in (None, 'STOP', 'MAX_TOKENS'):
            raise RuntimeError('Gemini остановил ответ. Повторите запрос или измените формулировку.')
        parts = candidate.get('content', {}).get('parts', [])
        result = {'role': 'assistant', 'content': ''.join(p.get('text', '') for p in parts if not p.get('thought'))}
        calls = []
        for part in parts:
            if 'functionCall' in part:
                fn = part['functionCall']
                if not isinstance(fn.get('args', {}), dict) or not isinstance(fn.get('name'), str):
                    raise ValueError('Gemini вернул некорректный вызов инструмента.')
                calls.append({'id': fn.get('id') or f'gemini-{len(calls)}', 'type': 'function',
                              'function': {'name': fn['name'], 'arguments': fn.get('args', {})}})
        if calls:
            if candidate.get('finishReason') == 'MAX_TOKENS':
                raise RuntimeError('Gemini обрезал вызов инструмента. Действие не выполнено.')
            result['tool_calls'] = calls
            # Preserve signed parts exactly for the next tool round. Never put
            # thought signatures in the UI or persistent conversation history.
            result['_gemini_parts'] = deepcopy(parts)
        if not calls and not result['content'].strip():
            raise RuntimeError('Gemini вернул пустой текст ответа.')
        self.metrics = {'wall_seconds': round(time.perf_counter() - started, 3)}
        return result

    def check_connection(self, context):
        model = self.settings.gemini_model.removeprefix('models/')
        data = asyncio.run(self._request('GET', model, context))
        if 'generateContent' not in data.get('supportedGenerationMethods', []):
            raise ValueError('Gemini: выбранная модель не поддерживает текстовые запросы.')
        return 'Gemini · ключ принят · ' + model + '. Проверьте ответ модели для проверки генерации и квоты.'

    async def _request(self, method, suffix, context, body=None):
        import httpx
        key = self.secrets.get('gemini')
        if not key:
            raise ValueError('Введите ключ Gemini API во вкладке «Модель».')
        async def receive():
            timeout = httpx.Timeout(min(60, context.remaining), connect=5)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                async with client.stream(method, self.BASE + suffix, json=body,
                                         headers={'x-goog-api-key': key}) as response:
                    if response.status_code >= 400:
                        hint = {400: 'Проверьте ключ и параметры модели.', 401: 'Проверьте API-ключ.',
                                403: 'Проверьте доступ API, ограничения ключа и регион.',
                                404: 'Модель недоступна для этого ключа. Выберите другую модель.',
                                429: 'Исчерпана квота или лимит запросов.'}.get(response.status_code, 'Сервис временно недоступен.')
                        raise RuntimeError(f'Gemini: HTTP {response.status_code}. {hint}')
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        context.check()
                        payload.extend(chunk)
                        if len(payload) > 4 * 1024 * 1024:
                            raise ValueError('Ответ Gemini слишком велик.')
                    try:
                        return json.loads(payload)
                    except (ValueError, UnicodeError):
                        raise RuntimeError('Gemini вернул некорректный ответ.') from None
        task = asyncio.create_task(receive())
        try:
            while not task.done():
                context.check()
                await asyncio.wait({task}, timeout=.05)
            context.check()
            return await task
        except httpx.HTTPError:
            raise ConnectionError('Gemini недоступен или истёк сетевой таймаут.') from None
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
