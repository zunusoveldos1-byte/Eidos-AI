"""Development-only LOCAL catalogue translation. Never imported by Eidos.

Only static source literals are sent to the local Ollama at 127.0.0.1.
No external requests, runtime settings, memory, credentials, audio or images.
"""
import ast
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eidos.agent.memory import require_public_text

DIRECTORY = ROOT / '.cache' / 'catalog-proposals'


def sources():
    result = set()
    for path in sorted((ROOT / 'eidos').rglob('*.py')):
        if path.name == 'i18n.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if re.search('[А-Яа-яЁё]', value) and len(value.strip()) > 1 and len(value) < 2000:
                    # Exclude executable patterns, SQL and multi-line prompts.
                    if '\\' not in value and not any(word in value for word in ('CREATE TABLE', 'SELECT ', 'INSERT ', 'SYSTEM:')):
                        result.add(value)
            elif isinstance(node, ast.JoinedStr):
                value = ''.join(part.value if isinstance(part, ast.Constant) else '{' + str(index) + '}'
                                for index, part in enumerate(node.values))
                if re.search('[А-Яа-яЁё]', value) and len(value) < 2000:
                    result.add(value)
    return sorted(result)


def key(source):
    return 'msg.' + hashlib.sha256(source.encode()).hexdigest()[:16]


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def translate_batch(language, batch):
    import httpx
    originals = [text for _, text in batch]
    tokens = {}
    def protect(match):
        token = f'ZXPH{len(tokens)}XZ'
        tokens[token] = match.group()
        return token
    encoded = [re.sub(r'\{\d+\}', protect, text.replace('\n', ' ZXNLXZ ')) for text in originals]
    payload = json.dumps(encoded, ensure_ascii=False)
    require_public_text(payload)
    languages = {'en': 'English', 'ky': 'Kyrgyz (кыргызча, Kyrgyz Cyrillic)',
                 'uz': 'Uzbek (o‘zbekcha, Latin alphabet)', 'kk': 'Kazakh (қазақша, Kazakh Cyrillic)'}
    schema = {'type': 'array', 'items': {'type': 'string'}, 'minItems': len(batch), 'maxItems': len(batch)}
    body = {'model': 'qwen3:4b-instruct-2507-q4_K_M', 'stream': False, 'think': False,
            'keep_alive': '10m', 'format': schema,
            'system': f'Translate Russian desktop application UI strings into {languages[language]}. '
                      'Return a JSON array of translations in exactly the same order. '
                      'Preserve ZXPH0XZ and similar placeholder tokens, ZXNLXZ, product names and file extensions. '
                      'Use concise natural interface language. Translate every string; do not add explanations.',
            'prompt': payload, 'options': {'temperature': 0, 'num_ctx': 4096, 'num_predict': 1600}}
    with httpx.Client(timeout=httpx.Timeout(180, connect=3), trust_env=False) as client:
        response = client.post('http://127.0.0.1:11434/api/generate', json=body)
        response.raise_for_status()
        raw = response.json()['response']
        try:
            translated = json.loads(raw)
        except ValueError:
            failure_dir = ROOT / '.cache' / 'catalog-failures'
            failure_dir.mkdir(exist_ok=True)
            (failure_dir / f'{language}-{batch[0][0]}.json').write_text(
                json.dumps(dict(source=originals, response=raw), ensure_ascii=False), encoding='utf-8')
            raise
    if len(translated) != len(batch):
        raise ValueError('Translation array length changed')
    result = {}
    for ordinal, text in enumerate(translated):
        value = text.strip().replace('ZXNLXZ', '\n')
        for token, original in tokens.items():
            token_pattern = r'\s*'.join(re.escape(character) for character in token)
            value = re.sub(token_pattern, lambda _: original, value, flags=re.I)
        if not value or set(re.findall(r'\{\d+\}', value)) != set(re.findall(r'\{\d+\}', originals[ordinal])):
            raise ValueError('Translation placeholders were changed')
        # Preserve intentional leading/trailing whitespace on fragments.
        original = originals[ordinal]
        value = original[:len(original) - len(original.lstrip())] + value + original[len(original.rstrip()):]
        result[batch[ordinal][0]] = value
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--languages', nargs='+', choices=('en', 'ky', 'uz', 'kk'), default=['en', 'ky', 'uz', 'kk'])
    args = parser.parse_args()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    source = {key(text): text for text in sources()}
    save(DIRECTORY / 'ru.json', source)
    jobs = []
    catalogs = {}
    for language in args.languages:
        path = DIRECTORY / f'{language}.json'
        catalog = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        catalog = {key: value for key, value in catalog.items() if key in source}
        catalogs[language] = catalog
        batch, size = [], 0
        for ident, text in source.items():
            if ident in catalog:
                continue
            if batch and (size + len(text) + 30 > 750 or len(batch) >= 12):
                jobs.append((language, batch))
                batch, size = [], 0
            batch.append((ident, text))
            size += len(text) + 30
        if batch:
            jobs.append((language, batch))
    print(f'Static catalogue: {len(source)} keys; {len(jobs)} bounded batches', flush=True)
    failed = 0
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {executor.submit(translate_batch, language, batch): (language, batch) for language, batch in jobs}
        for number, future in enumerate(as_completed(futures), 1):
            language, batch = futures[future]
            try:
                catalogs[language].update(future.result())
            except Exception as exc:
                failed += 1
                print(f'Batch {number}: {language} {type(exc).__name__} (no source content logged)', flush=True)
            save(DIRECTORY / f'{language}.json', catalogs[language])
            if number % 20 == 0:
                print(f'{number}/{len(jobs)} batches; {failed} failed', flush=True)
    print({language: len(source.keys() - catalog.keys()) for language, catalog in catalogs.items()}, flush=True)
    return int(failed > 0)


if __name__ == '__main__':
    raise SystemExit(main())
