"""Cancellable download of a versioned official model, verified before use."""

import hashlib
from pathlib import Path
import urllib.request
import os
import tempfile
import time

URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
SIZE = 7819105


def verified(path):
    try:
        return (
            path.stat().st_size == SIZE
            and hashlib.sha256(path.read_bytes()).hexdigest() == SHA256
        )
    except OSError:
        return False


def ensure_model(directory, stop, progress):
    path = Path(directory) / "hand_landmarker.task"
    if verified(path):
        return path
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    progress("Загружаю модель руки: 0% · скачивается модель, видео не передаётся")
    fd, name = tempfile.mkstemp(dir=directory, suffix=".download")
    temporary = Path(name)
    try:
        with (
            os.fdopen(fd, "wb") as target,
            urllib.request.urlopen(URL, timeout=8) as source,
        ):
            received = 0
            last = -1
            deadline = time.monotonic() + 120
            while not stop.is_set():
                if time.monotonic() > deadline:
                    raise TimeoutError("Загрузка модели заняла больше двух минут")
                chunk = source.read(65536)
                if not chunk:
                    break
                received += len(chunk)
                if received > SIZE:
                    raise ValueError("Некорректный размер модели")
                target.write(chunk)
                percent = received * 100 // SIZE
                if percent != last:
                    progress(f"Загружаю модель руки: {percent}%")
                    last = percent
        if stop.is_set():
            raise InterruptedError("Загрузка отменена")
        if not verified(temporary):
            raise ValueError(
                "Контрольная сумма модели не совпала. Повторите включение камеры"
            )
        temporary.replace(path)
        return path
    finally:
        temporary.unlink(missing_ok=True)
