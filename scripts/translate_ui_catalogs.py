"""Translate ONLY the static ru.json catalogue explicitly approved by the user.

Development tool, never called by the application. Runtime settings, user data,
memory and other source files are not read. Secrets are rejected before HTTP.
"""
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
from eidos.modules.ocr.engine import OnlineTranslator

DIRECTORY = ROOT / 'eidos' / 'assets' / 'i18n'


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def batch_translate(language, batch):
    protected = {}
    def protect(match):
        token = f'ZXPH{len(protected)}XZ'
        protected[token] = match.group()
        return token
    encoded = [re.sub(r'\{\d+\}|<[^>]+>', protect, text.replace('\n', ' ZXNLXZ ')) for _, text in batch]
    payload = '\n'.join(f'ZXID{index}XZ {text}' for index, text in enumerate(encoded))
    require_public_text(payload)
    translated = OnlineTranslator().translate(payload, 'ru', language)
    markers = list(re.finditer(r'ZXID\s*(\d+)\s*XZ', translated, re.I))
    if len(markers) != len(batch):
        if len(batch) > 1:
            result = {}
            for item in batch:
                result.update(batch_translate(language, [item]))
            return result
        raise ValueError('Translation markers changed')
    result = {}
    for index, match in enumerate(markers):
        ordinal = int(match.group(1))
        end = markers[index + 1].start() if index + 1 < len(markers) else len(translated)
        value = translated[match.end():end].strip()
        value = re.sub(r'ZXNL\s*XZ', '\n', value, flags=re.I)
        for token, original in protected.items():
            pattern = r'\s*'.join(re.escape(character) for character in token)
            value = re.sub(pattern, lambda _: original, value, flags=re.I)
        original = batch[ordinal][1]
        if not value or set(re.findall(r'\{\d+\}', value)) != set(re.findall(r'\{\d+\}', original)):
            if len(batch) > 1:
                result.update(batch_translate(language, [batch[ordinal]]))
                continue
            raise ValueError('Translation placeholders changed')
        value = original[:len(original) - len(original.lstrip())] + value + original[len(original.rstrip()):]
        result[batch[ordinal][0]] = value
    return result


def main():
    path = DIRECTORY / 'ru.json'
    source = json.loads(path.read_text(encoding='utf-8'))
    report = ROOT / '.cache' / 'catalogue-api-run.json'
    save(report, {'source': 'eidos/assets/i18n/ru.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'provider': 'Google, explicitly approved in chat', 'keys': len(source)})
    catalogs, jobs = {}, []
    for language in ('en', 'ky', 'uz', 'kk'):
        target = DIRECTORY / f'{language}.json'
        catalogs[language] = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        batch, size = [], 0
        for ident, text in source.items():
            if ident in catalogs[language]:
                continue
            if batch and size + len(text) + 30 > 1000:
                jobs.append((language, batch))
                batch, size = [], 0
            batch.append((ident, text))
            size += len(text) + 30
        if batch:
            jobs.append((language, batch))
    failures = []
    print(f'Approved static catalogue: {len(source)} keys; {len(jobs)} batches', flush=True)
    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {executor.submit(batch_translate, language, batch): (language, batch) for language, batch in jobs}
        for number, future in enumerate(as_completed(futures), 1):
            language, batch = futures[future]
            try:
                catalogs[language].update(future.result())
            except Exception as exc:
                failures.append((language, [ident for ident, _ in batch], type(exc).__name__))
                print(f'{language}: {type(exc).__name__}; source content not logged', flush=True)
            save(DIRECTORY / f'{language}.json', catalogs[language])
            if number % 20 == 0:
                print(f'{number}/{len(jobs)} batches', flush=True)
    metadata = json.loads(report.read_text(encoding='utf-8'))
    metadata.update(missing={language: sorted(source.keys() - catalog.keys()) for language, catalog in catalogs.items()},
                    failures=failures)
    save(report, metadata)
    print({language: len(source.keys() - catalog.keys()) for language, catalog in catalogs.items()}, flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
