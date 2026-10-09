"""Protocol and cancellation tests use a tiny local server, never an AI model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from eidos.agent.harness import TaskContext
from eidos.agent.providers import OllamaProvider
from eidos.agent.settings import AgentSettings


@pytest.fixture
def endpoint():
    received = threading.Event()
    release = threading.Event()
    state = {'lines': [], 'block': False, 'body': None}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state['body'] = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.set()
            if state['block']:
                release.wait(5)
            payload = b''.join(json.dumps(line).encode() + b'\n' for line in state['lines'])
            try:
                self.send_response(200)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    provider = OllamaProvider(AgentSettings(ollama_url=f'http://127.0.0.1:{server.server_port}'))
    yield provider, state, received
    release.set()
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def test_stream_preserves_structured_tool_arguments(endpoint):
    provider, state, _ = endpoint
    call = {'function': {'name': 'calendar_list', 'arguments': {}}}
    state['lines'] = [
        {'message': {'content': 'Проверю ', 'tool_calls': [call]}, 'done': False},
        {'message': {'content': 'календарь.'}, 'done': True, 'eval_count': 3},
    ]
    response = provider.chat([{'role': 'user', 'content': 'Календарь'}], [], TaskContext())
    assert response['content'] == 'Проверю календарь.'
    assert response['tool_calls'] == [call]
    assert state['body']['stream'] and state['body']['think'] is False
    assert provider.metrics['eval_count'] == 3


@pytest.mark.parametrize('cancel', [True, False], ids=['cancel', 'deadline'])
def test_blocked_first_response_can_be_interrupted(endpoint, cancel):
    provider, state, received = endpoint
    state['block'] = True
    context = TaskContext(timeout=3 if cancel else .25)
    outcome = []

    def request():
        try:
            provider.chat([{'role': 'user', 'content': 'Ответ'}], [], context)
        except Exception as exc:
            outcome.append(exc)

    worker = threading.Thread(target=request)
    worker.start()
    assert received.wait(2)
    started = time.monotonic()
    if cancel:
        context.cancel.set()
    worker.join(timeout=2)
    assert not worker.is_alive(), 'Отмена должна прервать ожидание HTTP headers'
    assert time.monotonic() - started < 2
    assert isinstance(outcome[0], InterruptedError if cancel else TimeoutError)


def test_truncated_response_is_not_reported_as_success(endpoint):
    provider, state, _ = endpoint
    state['lines'] = [{'message': {'content': 'Незаконченный ответ'}, 'done': False}]
    with pytest.raises(RuntimeError, match='до завершения'):
        provider.chat([{'role': 'user', 'content': 'Ответ'}], [], TaskContext())
