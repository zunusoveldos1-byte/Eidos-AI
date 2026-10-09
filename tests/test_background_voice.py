import sys
import time
from pathlib import Path
from threading import Event, Timer
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def wait(app, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate()


def config(**kwargs):
    return SimpleNamespace(tts_provider='edge', tts_voice='ru-RU-SvetlanaNeural',
                           tts_rate=10, tts_volume=40, voice_response_brief=False,
                           sapi_voice='', **kwargs)


def test_speech_removes_code_urls_and_limits_complete_sentences():
    from eidos.modules.voice.speech_text import prepare_speech, split_sentences
    original = '# Ответ\n**Привет.** [Далее](https://example.com).\n```python\nsecret()\n```\nhttps://secret.test\nЕщё предложение. Последнее.'
    cleaned = prepare_speech(original, brief=True)
    assert 'secret' not in cleaned
    assert '*' not in cleaned and '#' not in cleaned
    assert cleaned == 'Ответ Привет. Далее. Ещё предложение.'
    assert split_sentences('Дата 10.10.2026. Цена 3.5 руб. Всё готово!') == ['Дата 10.10.2026.', 'Цена 3.5 руб. Всё готово!']


class Player(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.paths = []
        self.path = None
        self.volume = None

    def play(self, path):
        assert self.path is None
        self.paths.append(path)
        self.path = path

    def set_volume(self, volume):
        self.volume = volume

    def stop(self):
        if self.path:
            self.path.unlink(missing_ok=True)
        self.path = None

    def complete(self):
        self.stop()
        self.finished.emit()


def test_queue_serial_playback_cancel_and_shutdown(app, monkeypatch, tmp_path):
    from eidos.modules.voice import speech
    calls = []

    class Provider:
        def synthesize(self, text, voice, cancel, *, rate=0, volume=100):
            calls.append((text, rate, volume))
            path = tmp_path / f'{len(calls)}.mp3'
            path.write_bytes(b'audio')
            return path

    monkeypatch.setattr(speech, 'EdgeTTS', Provider)
    player = Player()
    queue = speech.SpeechQueue(None, player)
    try:
        assert queue.enqueue('Первое. Второе.', config())
        assert queue.active
        wait(app, lambda: len(player.paths) == 1)
        assert calls == [('Первое.', 10, 100)]
        assert player.volume == 40
        player.complete()
        wait(app, lambda: len(player.paths) == 2)
        queue.stop()
        assert not queue.active
        assert not list(tmp_path.iterdir())
        assert not queue.enqueue('```code```', config())
        assert not queue.enqueue('Да. ' * 100, config())
    finally:
        queue.shutdown()
        wait(app, lambda: not queue.is_running)


def test_shutdown_discards_late_synthesis(app, monkeypatch, tmp_path):
    from eidos.modules.voice import speech
    entered, release = Event(), Event()
    path = tmp_path / 'late.mp3'

    class Provider:
        def synthesize(self, text, voice, cancel, **kwargs):
            entered.set()
            release.wait(2)
            path.write_bytes(b'audio')
            return path

    monkeypatch.setattr(speech, 'EdgeTTS', Provider)
    player = Player()
    queue = speech.SpeechQueue(None, player)
    assert queue.enqueue('Ответ.', config())
    wait(app, entered.is_set)
    queue.shutdown()
    release.set()
    wait(app, lambda: not queue.is_running and not path.exists())
    assert player.paths == []


def test_voice_enumeration_uses_worker_and_discards_shutdown_result(app, monkeypatch):
    from eidos.modules.voice import speech
    from PyQt6.QtCore import QThread
    entered, release = Event(), Event()

    class Provider:
        def list_voices(self):
            assert QThread.currentThread() is not app.thread()
            entered.set()
            release.wait(2)
            return [('installed-id', 'Installed Russian')]

    monkeypatch.setattr(speech, 'SapiTTS', Provider)
    queue = speech.SpeechQueue(None, Player())
    results = []
    try:
        queue.voices_ready.connect(results.append)
        assert queue.refresh_voices()
        wait(app, entered.is_set)
        queue.shutdown()
        release.set()
        wait(app, lambda: not queue.is_running)
        app.processEvents()
        assert results == []
        assert not queue.refresh_voices()
    finally:
        release.set()
        queue.shutdown()
        wait(app, lambda: not queue.is_running)


def test_voice_enumeration_delivers_installed_ids(app, monkeypatch):
    from eidos.modules.voice import speech

    class Provider:
        def list_voices(self):
            return [('installed-id', 'Installed Russian')]

    monkeypatch.setattr(speech, 'SapiTTS', Provider)
    queue = speech.SpeechQueue(None, Player())
    results = []
    try:
        queue.voices_ready.connect(results.append)
        assert queue.refresh_voices()
        wait(app, lambda: bool(results))
        assert results == [[('installed-id', 'Installed Russian')]]
        assert not queue.active
    finally:
        queue.shutdown()
        wait(app, lambda: not queue.is_running)


def test_wake_missing_key_does_not_import_or_open_microphone(app):
    from eidos.modules.voice.wake import WakeController
    wake = WakeController(None, SimpleNamespace(get=lambda _: None))
    messages = []
    wake.status.connect(messages.append)
    wake.configure(SimpleNamespace(wake_word_enabled=True, wake_keyword_path='',
                                   wake_model_path='', microphone=None, wake_sensitivity=.5))
    assert not wake.is_running
    assert messages and 'AccessKey' in messages[-1]
    wake.shutdown()


def test_edge_settings_and_old_call_remain_supported(monkeypatch, tmp_path):
    from eidos.modules.voice.tts import EdgeTTS
    calls = []

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def save(self, filename):
            Path(filename).write_bytes(b'audio')

    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(Communicate=Communicate))
    provider = EdgeTTS()
    paths = [provider.synthesize('Текст', 'voice', Event(), rate=-25, volume=80),
             provider.synthesize('Текст', 'voice', Event())]
    try:
        assert calls[0] == ('Текст', 'voice', {'rate': '-25%', 'volume': '-20%'})
        assert paths[0].exists() and paths[1].exists()
    finally:
        for path in paths:
            path.unlink(missing_ok=True)


def test_wake_busy_releases_stream_and_pause_prevents_restart(app, monkeypatch, tmp_path):
    from eidos.modules.voice.wake import WakeController
    opened, closed = [], []
    model, keyword = tmp_path / 'ru.pv', tmp_path / 'eidos.ppn'
    model.touch()
    keyword.touch()

    class Engine:
        sample_rate, frame_length = 16000, 512

        def process(self, samples):
            return -1

        def delete(self):
            closed.append('engine')

    class Stream:
        def __init__(self, **kwargs):
            opened.append('stream')

        def start(self):
            pass

        def read(self, count):
            time.sleep(.01)
            return b'\0\0' * count, False

        def abort(self):
            closed.append('abort')

        def close(self):
            closed.append('stream')

    monkeypatch.setitem(sys.modules, 'pvporcupine', SimpleNamespace(create=lambda **_: Engine()))
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream))
    wake = WakeController(None, SimpleNamespace(get=lambda _: 'secret'))
    cfg = SimpleNamespace(wake_word_enabled=True, wake_keyword_path=str(keyword),
                          wake_model_path=str(model), microphone=None, wake_sensitivity=.5)
    released = []
    wake.stopped.connect(lambda: released.append(list(closed)))
    try:
        wake.configure(cfg)
        wait(app, lambda: bool(opened))
        wake.configure(cfg)  # unrelated UI persistence must not interrupt the microphone.
        deadline = time.monotonic() + .1
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        assert closed == []
        wake.set_busy(True)
        wait(app, lambda: bool(released))
        assert released[0] == ['abort', 'stream', 'engine']
        wake.set_busy(False)
        wake.pause(True)
        deadline = time.monotonic() + .5
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        assert len(opened) == 1 and not wake.is_running
    finally:
        wake.shutdown()
        wait(app, lambda: not wake.is_running)


def test_wake_errors_hide_key_and_do_not_retry(app, monkeypatch, tmp_path):
    from eidos.modules.voice.wake import WakeController
    keyword, model = tmp_path / 'word.ppn', tmp_path / 'lang.pv'
    keyword.touch()
    model.touch()
    calls = []

    def broken(**kwargs):
        calls.append(True)
        raise RuntimeError('invalid key SECRET-KEY')

    monkeypatch.setitem(sys.modules, 'pvporcupine', SimpleNamespace(create=broken))
    wake = WakeController(None, SimpleNamespace(get=lambda _: 'SECRET-KEY'))
    messages = []
    wake.status.connect(messages.append)
    wake.configure(SimpleNamespace(wake_word_enabled=True, wake_keyword_path=str(keyword),
                                   wake_model_path=str(model), microphone=None, wake_sensitivity=.5))
    wait(app, lambda: messages and not wake.is_running)
    assert 'SECRET-KEY' not in ' '.join(messages)
    for _ in range(5):
        wake.set_busy(False)
        app.processEvents()
    assert len(calls) == 1
    wake.shutdown()


def test_common_spoken_dates_and_symbols_are_explicit():
    from eidos.modules.voice.speech_text import prepare_speech
    assert prepare_speech('Срок 10.10.2026, № 5.') == 'Срок 10 октября 2026 года, номер 5.'
    assert prepare_speech('Некорректная дата 31.02.2026.') == 'Некорректная дата 31.02.2026.'


def test_recorder_end_of_speech_and_bounded_levels(monkeypatch):
    from eidos.modules.voice.recorder import Recorder
    stop = Event()
    closed, levels = [], []

    class Stream:
        active = True

        def __init__(self, **kwargs):
            self.callback = kwargs['callback']

        def start(self):
            for value in [0.] * 3 + [.1] * 4 + [0.] * 15:
                self.callback(np.full((1600, 1), value, dtype=np.float32), 1600, None, False)

        def abort(self):
            closed.append('abort')

        def close(self):
            closed.append('close')

    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(
        InputStream=Stream, query_devices=lambda *_: {'default_samplerate': 16000},
        check_input_settings=lambda **_: None))
    recorder = Recorder()
    recorder.end_of_speech = True
    recorder.level_callback = levels.append
    safety = Timer(.3, stop.set)
    safety.start()
    audio = recorder.record(None, stop, Event(), lambda: None)
    safety.cancel()
    assert stop.is_set()
    assert audio.size < 22 * 1600
    assert levels and all(0 <= level <= 1 for level in levels)
    assert closed == ['abort', 'close']


def test_recorder_onset_timeout_returns_empty_without_retaining_room_audio(monkeypatch):
    from eidos.modules.voice.recorder import Recorder
    stop = Event()

    class Stream:
        active = True

        def __init__(self, **kwargs):
            self.callback = kwargs['callback']

        def start(self):
            for _ in range(80):
                self.callback(np.zeros((1600, 1), dtype=np.float32), 1600, None, False)

        def abort(self):
            pass

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(
        InputStream=Stream, query_devices=lambda *_: {'default_samplerate': 16000},
        check_input_settings=lambda **_: None))
    recorder = Recorder()
    recorder.end_of_speech = True
    safety = Timer(.3, stop.set)
    safety.start()
    audio = recorder.record(None, stop, Event(), lambda: None)
    safety.cancel()
    assert audio.size == 0


def test_sapi_cancellation_purges_speech_closes_file_and_com(monkeypatch, tmp_path):
    from eidos.modules.voice import tts
    cancel = Event()
    events = []

    class Voice:
        Id = 'voice-id'

        def GetDescription(self):
            return 'Russian voice'

        def GetAttribute(self, name):
            return '419'

    class Voices:
        Count = 1

        def Item(self, index):
            return Voice()

    class Speaker:
        def GetVoices(self):
            return Voices()

        def Speak(self, text, flags):
            events.append(('speak', text, flags))

        def WaitUntilDone(self, timeout):
            cancel.set()
            return False

    class Stream:
        def Open(self, filename, mode, flag):
            Path(filename).write_bytes(b'wav')
            events.append('open')

        def Close(self):
            events.append('close')

    speaker = Speaker()
    monkeypatch.setitem(sys.modules, 'comtypes', SimpleNamespace(
        CoInitialize=lambda: events.append('init'), CoUninitialize=lambda: events.append('uninit')))
    monkeypatch.setitem(sys.modules, 'comtypes.client', SimpleNamespace(
        CreateObject=lambda name, **_: speaker if name == 'SAPI.SpVoice' else Stream()))
    original_mkstemp = tts.tempfile.mkstemp
    monkeypatch.setattr(tts.tempfile, 'mkstemp', lambda **kwargs: original_mkstemp(dir=tmp_path, **kwargs))
    assert tts.SapiTTS().synthesize('Ответ', '', cancel, rate=50, volume=80) is None
    assert events == ['init', 'open', ('speak', 'Ответ', 1), ('speak', '', 3), 'close', 'uninit']
    assert speaker.Rate == 5 and speaker.Volume == 80
    assert not list(tmp_path.iterdir())
