"""Read-only audit and synthetic policy probes; never read native credentials.

Run from the repository root with .venv/Scripts/python.exe.
Only synthetic files under .cache/audit-2026-10-13 are written by probes.
 --osv sends ONLY the fixed public-package allowlist below to OSV.
"""
import argparse
import ast
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache' / 'audit-2026-10-13'
OSV_PUBLIC_PACKAGES = frozenset({
    'pyqt6', 'pyqt6-qt6', 'pillow', 'tesserocr', 'numpy', 'sounddevice',
    'faster-whisper', 'ctranslate2', 'edge-tts', 'comtypes', 'httpx', 'httpcore',
    'h11', 'python-docx', 'openpyxl', 'pypdf', 'reportlab', 'pycaw', 'psutil',
    'keyring', 'mediapipe', 'opencv-contrib-python', 'cv2-enumerate-cameras',
    'aiohttp', 'av', 'lxml', 'onnxruntime', 'huggingface-hub', 'tokenizers',
    'setuptools', 'pip', 'pyyaml', 'protobuf', 'certifi', 'idna', 'urllib3',
})


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def inventory():
    result = {}
    for directory in ('eidos', 'tests', 'scripts', 'JARVIS-main'):
        paths = sorted((ROOT / directory).rglob('*.py'))
        paths = [p for p in paths if '__pycache__' not in p.parts]
        sizes = []
        errors = []
        for path in paths:
            source = path.read_text(encoding='utf-8-sig')
            sizes.append({'file': path.relative_to(ROOT).as_posix(), 'lines': len(source.splitlines())})
            try:
                ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                errors.append({'file': path.relative_to(ROOT).as_posix(), 'line': exc.lineno, 'message': exc.msg})
        result[directory] = {'files': len(paths), 'lines': sum(s['lines'] for s in sizes),
                             'largest': sorted(sizes, key=lambda s: s['lines'], reverse=True)[:8],
                             'syntax_errors': errors}
    return result


def runtime():
    import psutil
    from eidos.core.config import data_dir
    from eidos.agent.providers import request_json
    result = {'python': sys.version, 'hardware': {'logical_cpus': psutil.cpu_count(),
              'ram_total_gib': round(psutil.virtual_memory().total / 2**30, 2),
              'ram_available_gib': round(psutil.virtual_memory().available / 2**30, 2)},
              'data_directory': str(data_dir())}
    app_fields = ('whisper_model', 'device', 'speak', 'tts_provider', 'tts_voice', 'continuous_listening',
                  'wake_word_enabled', 'close_to_tray', 'floating_enabled', 'gesture_mode', 'gesture_fps')
    agent_fields = ('provider', 'model', 'cloud_model', 'context_size', 'memory_enabled',
                    'onboarding_done', 'telegram_enabled', 'discord_enabled', 'search_provider', 'timezone')
    root = data_dir()
    if (root / 'profiles.json').exists():
        from hashlib import sha256
        selection = json.loads((root / 'profiles.json').read_text(encoding='utf-8-sig'))
        active = selection.get('active', 'Основной')
        result['profile_count'] = len(selection.get('names', []))
        if active != 'Основной':
            root = root / 'profiles' / sha256(active.encode('utf-8')).hexdigest()[:20]
    for name, path, allowed in [('app', data_dir() / 'config.json', app_fields), ('agent', root / 'agent.json', agent_fields)]:
        if path.exists():
            values = json.loads(path.read_text(encoding='utf-8-sig'))
            result[name] = {key: values[key] for key in allowed if key in values}
            if name == 'agent':
                result['agent']['approved_app_count'] = len(values.get('approved_apps', {}))
                result['agent']['remote_permissions'] = values.get('remote_permissions', [])
                result['agent']['allowlist_counts'] = {k: len(values.get(k, [])) for k in
                      ('telegram_users', 'telegram_channels', 'discord_users', 'discord_channels')}
            else:
                result['wake_model_readiness'] = {key: bool(values.get(key)) and Path(values[key]).is_file()
                                                for key in ('wake_keyword_path', 'wake_model_path')}
        else:
            result[name] = {'saved_configuration': False}
    for endpoint in ('version', 'tags', 'ps'):
        try:
            result['ollama_' + endpoint] = request_json('GET', 'http://127.0.0.1:11434/api/' + endpoint)
        except Exception as exc:
            result['ollama_' + endpoint] = {'available': False, 'error_type': type(exc).__name__}
    try:
        result['porcupine_package'] = metadata.version('pvporcupine')
    except metadata.PackageNotFoundError:
        result['porcupine_package'] = None
    try:
        result['ollama_listeners'] = [{'ip': c.laddr.ip, 'port': c.laddr.port} for c in psutil.net_connections('tcp')
                                     if c.status == 'LISTEN' and c.laddr.port == 11434]
    except (psutil.AccessDenied, RuntimeError, OSError) as exc:
        result['ollama_listeners'] = {'available': False, 'error_type': type(exc).__name__}
    return result


def probes():
    from eidos.agent.harness import Registry, TaskContext, Tool, ToolResult
    from eidos.agent.tools import build_registry
    from eidos.agent.settings import AgentSettings
    from eidos.agent.memory import Memory
    CACHE.mkdir(parents=True, exist_ok=True)
    workspace = CACHE / 'synthetic-documents'
    workspace.mkdir(exist_ok=True)
    memory = Memory(CACHE / 'synthetic-memory.sqlite')
    registry = build_registry(AgentSettings(), memory)
    confirmations = []
    context = TaskContext(folders=frozenset({str(workspace)}), confirm=lambda action: confirmations.append(action) or False)
    result = registry.execute('document_write', {'path': str(workspace / 'new-document.md'),
                                                'content': 'Synthetic audit content'}, context)
    probes = {'document_write_first_local_task': {'confirmation_calls': len(confirmations),
                                                 'write_verified': result.verified,
                                                 'scope': 'Raw registry only, not the normal chat path.'}}
    from eidos.agent.harness import Harness
    class Writer:
        def chat(self, *args):
            return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
                'name': 'document_write', 'arguments': {'path': str(workspace / 'chat-document.md'),
                                                     'content': 'Synthetic chat content'}}}]}
    chat_approvals = []
    try:
        Harness(registry, Writer()).run('Create a document', TaskContext(folders=frozenset({str(workspace)}),
            confirm=lambda action: chat_approvals.append(action) or False), facts='Selected workspace: ' + str(workspace))
        denied = False
    except PermissionError:
        denied = True
    probes['document_write_normal_chat_context'] = {'confirmation_calls': len(chat_approvals),
                                                  'denied_on_rejected_confirmation': denied}
    # Marker is synthetic. The mock replaces the entire network operation.
    marker = 'AUDIT_SYNTHETIC_PRIVATE_MARKER'
    captured = []
    from eidos.modules.ocr.engine import OnlineTranslator
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return b'[[["translated","source"]]]'
    def fake_open(request, **kwargs):
        captured.append(request.full_url)
        return FakeResponse()
    with patch('eidos.modules.ocr.engine.urlopen', fake_open):
        remote_context = TaskContext(secret_values=(marker,))
        registry.execute('text_translate', {'text': marker, 'source': 'en', 'target': 'ru', 'provider': 'google'}, remote_context)
    probes['translation_secret_egress'] = {'known_secret_in_outgoing_request': any(marker in url for url in captured),
                                         'real_network_called': False}
    # Unsafe retry flags permit actions after reading untrusted content without confirmation.
    retry_registry = Registry()
    executions = []
    retry_registry.add(Tool('read_style', 'Read-style synthetic tool', {},
                           lambda a, c: executions.append(True) or ToolResult('OK'), 'camera.read', safe_retry=True))
    retry_registry.execute('read_style', {}, TaskContext(untrusted_data=True, confirm=lambda _: False))
    probes['retry_policy'] = {'safe_retry_skips_untrusted_confirmation': bool(executions),
                             'note': 'Current camera_status is read-only; audit of future tool flags is required.'}
    for name in ('document_read', 'document_write', 'screen_read_text', 'calendar_list'):
        tool = registry.tools[name]
        probes['remote_denied_' + name] = not registry.allowed(tool, TaskContext(origin='telegram'))
    return probes


def osv(packages):
    checked = [p for p in packages if p['name'].lower().replace('_', '-') in OSV_PUBLIC_PACKAGES]
    pending = [(i, {'package': {'name': p['name'], 'ecosystem': 'PyPI'}, 'version': p['version']})
               for i, p in enumerate(checked)]
    found = {}
    while pending:
        payload = json.dumps({'queries': [q for _, q in pending]}).encode()
        request = Request('https://api.osv.dev/v1/querybatch', data=payload, headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=30) as response:
            results = json.load(response)['results']
        following = []
        for (i, query), result in zip(pending, results, strict=True):
            found.setdefault(i, []).extend(result.get('vulns', []))
            if result.get('next_page_token'):
                following.append((i, dict(query, page_token=result['next_page_token'])))
        pending = following
    return {'source': 'https://api.osv.dev/v1/querybatch', 'checked_packages': len(checked),
            'scope': 'Fixed allowlist of public libraries only; other distribution names were not sent.',
            'findings': [dict(checked[i], advisories=v) for i, v in found.items() if v],
            'limitation': 'PyPI names/versions only; native bundled libraries, binaries and model files are outside this check.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--osv', action='store_true')
    args = parser.parse_args()
    packages = sorted([{'name': d.metadata['Name'], 'version': d.version} for d in metadata.distributions()], key=lambda p: p['name'].lower())
    save('packages.json', packages)
    result = {'date': '2026-10-13', 'scope': 'Working tree, including uncommitted changes',
              'inventory': inventory(), 'runtime': runtime(), 'synthetic_probes': probes()}
    save('evidence.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.osv:
        try:
            findings = osv(packages)
        except Exception as exc:
            findings = {'completed': False, 'error_type': type(exc).__name__}
        save('dependency-advisories.json', findings)
        print(json.dumps(findings, ensure_ascii=False, indent=2))
