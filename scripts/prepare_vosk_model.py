"""Explicit, bounded preparation of the official small Russian Vosk model."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import urllib.request
import zipfile

URL = 'https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip'
MODEL = 'vosk-model-small-ru-0.22'
MAX_DOWNLOAD = 80 * 1024 ** 2
MAX_EXPANDED = 200 * 1024 ** 2


def prepare(directory):
    directory = directory.resolve()
    destination = directory / MODEL
    if (destination / 'am' / 'final.mdl').is_file() and (destination / 'conf' / 'model.conf').is_file():
        return destination
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory, prefix='vosk-download-') as temporary:
        root = Path(temporary)
        archive = root / 'model.zip'
        digest = hashlib.sha256()
        received = 0
        deadline = time.monotonic() + 360
        print('Explicit download: Vosk small Russian 0.22 (~45 MB), official source', flush=True)
        with urllib.request.urlopen(URL, timeout=10) as response, archive.open('wb') as target:
            if response.geturl() != URL:
                raise ValueError('Unexpected model download redirect')
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError(f'Model download exceeded 360 seconds ({received} bytes received)')
                block = response.read(65536)
                if not block:
                    break
                received += len(block)
                if received > MAX_DOWNLOAD:
                    raise ValueError('Model archive exceeds 80 MB')
                digest.update(block)
                target.write(block)
                if received % (4 * 1024 ** 2) < len(block):
                    print(f'Downloaded {received // 1024 ** 2} MB', flush=True)
        with zipfile.ZipFile(archive) as source:
            if sum(info.file_size for info in source.infolist()) > MAX_EXPANDED:
                raise ValueError('Expanded model exceeds 200 MB')
            for info in source.infolist():
                path = (root / info.filename).resolve()
                if not path.is_relative_to(root) or not path.is_relative_to(root / MODEL):
                    raise ValueError('Unsafe archive member')
                if info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError('Archive symlinks are not accepted')
            source.extractall(root)
        extracted = root / MODEL
        if not (extracted / 'am' / 'final.mdl').is_file() or not (extracted / 'conf' / 'model.conf').is_file():
            raise ValueError('Incomplete model archive')
        if destination.exists():
            raise FileExistsError('Existing incomplete model preserved; choose another directory')
        extracted.replace(destination)
        # The publisher does not publish a checksum on the model list. This
        # observed digest records the exact artifact, not a signature claim.
        (destination / 'eidos-artifact.json').write_text(json.dumps(
            dict(url=URL, version=MODEL, bytes=received, observed_sha256=digest.hexdigest(),
                 checksum_source='computed after HTTPS download; no publisher checksum'), indent=2), encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path('.cache/voice-models'))
    args = parser.parse_args()
    print(prepare(args.directory), flush=True)
