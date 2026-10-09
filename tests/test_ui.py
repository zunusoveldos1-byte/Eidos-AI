import os
import threading
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from eidos.core.config import AppConfig, ConfigStore
from eidos.modules.voice.worker import VoiceWorker
from eidos.modules.voice.controller import VoiceController
from eidos.ui.main_window import MainWindow


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert predicate(), 'Qt signal did not arrive before timeout'


class WaitingRecorder:
    def __init__(self):
        self.calls = 0

    def record(self, device, stop, cancel, started):
        self.calls += 1
        started()
        while not stop.wait(0.01) and not cancel.is_set():
            pass
        return None


def test_controller_prevents_repeat_and_closes_recording(app, tmp_path):
    recorder = WaitingRecorder()
    controller = VoiceController(tmp_path, worker=VoiceWorker(recorder=recorder))
    closed = []
    controller.closed.connect(lambda: closed.append(True))
    controller.start(AppConfig(speak=False))
    controller.start(AppConfig(speak=False))
    wait_until(app, lambda: recorder.calls == 1)
    controller.shutdown()
    wait_until(app, lambda: bool(closed))
    assert not controller.thread.isRunning()


def test_window_smoke_and_config_save(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    window.show()
    assert window.pages.count() == 5
    assert [button.accessibleName() for button in window.sidebar.buttons] == ['Главная', 'Голос', 'Жесты', 'Перевод', 'Настройки']
    window.voice.speak.setChecked(False)
    assert ConfigStore(tmp_path / 'config.json').load().speak is False
    window.close()
    wait_until(app, lambda: not window.controller.thread.isRunning())
    app.processEvents()


def test_playback_error_after_worker_finishes_allows_retry(app, tmp_path):
    from eidos.core.state import State

    controller = VoiceController(tmp_path, worker=VoiceWorker(recorder=WaitingRecorder()))
    try:
        for state in [State.STARTING, State.RECORDING, State.TRANSCRIBING, State.SYNTHESIZING, State.PLAYING]:
            controller.machine.transition(state)
        controller._error('Нет устройства воспроизведения')
        controller.start(AppConfig(speak=False))
        assert controller.active
    finally:
        controller.shutdown()
        wait_until(app, lambda: not controller.thread.isRunning())


@pytest.mark.parametrize('stage', ['stt', 'tts'])
def test_shutdown_waits_for_inflight_engine_and_removes_audio(app, tmp_path, stage):
    import numpy as np
    gate, entered = threading.Event(), threading.Event()
    output = tmp_path / 'late.mp3'

    class Recorder:
        def record(self, device, stop, cancel, started):
            started()
            return np.ones(16000, dtype=np.float32)

    class STT:
        def transcribe(self, audio, config, cache, progress, cancel):
            progress('loading', 'Подготовка модели')
            if stage == 'stt':
                entered.set()
                gate.wait(2)
            progress('transcribing', 'Распознавание')
            return 'Привет'

    class TTS:
        def synthesize(self, *_):
            entered.set()
            gate.wait(2)
            output.write_bytes(b'late')
            return output

    controller = VoiceController(tmp_path, worker=VoiceWorker(recorder=Recorder(), stt=STT(), tts=TTS()))
    closed = []
    controller.closed.connect(lambda: closed.append(True))
    try:
        controller.start(AppConfig())
        wait_until(app, entered.is_set)
        controller.shutdown()
        app.processEvents()
        assert controller.thread.isRunning()
        assert not closed
    finally:
        gate.set()
        controller.shutdown()
        wait_until(app, lambda: bool(closed))
    assert not output.exists()


def test_tts_cancellation_removes_temporary_file(monkeypatch, tmp_path):
    import asyncio
    from eidos.modules.voice.tts import EdgeTTS

    engine = EdgeTTS()
    cancel = threading.Event()
    monkeypatch.setattr('tempfile.tempdir', str(tmp_path))

    async def cancelled(text, voice, path, event):
        path.write_bytes(b'partial')
        event.set()
        return False

    monkeypatch.setattr(engine, '_save', cancelled)
    assert engine.synthesize('Привет', 'test', cancel) is None
    assert list(tmp_path.iterdir()) == []
