import sys
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest
from test_ui import app, wait_until

from eidos.core.config import AppConfig, ConfigStore


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch):
    # Unit tests never read the user's Windows Vault.
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.get', lambda *a: None)


def test_pause_keeps_source_position_and_stop_releases_memory(app, tmp_path):
    from eidos.modules.voice.playback import AudioPlayback
    from eidos.modules.voice.pcm import PCMAudio
    class Sink:
        def __init__(self): self.calls = []; self.position = 1250
        def suspend(self): self.calls.append('pause')
        def resume(self): self.calls.append('play')
        def stop(self): self.calls.append('stop')
        def deleteLater(self): pass
    playback = AudioPlayback()
    sink = playback._output = Sink()
    playback._audio = PCMAudio(bytes(1024))
    playback.pause()
    assert playback.active and playback.paused
    playback.resume()
    assert not playback.paused and sink.position == 1250
    assert sink.calls == ['pause', 'play']
    playback.stop()
    assert not playback.active and playback._audio is None
    assert sink.calls[-1] == 'stop'


@pytest.mark.parametrize('phrase,expected', [
    ('Эйдос, открой YouTube', 'открой YouTube'),
    ('Эй дос! Сделай звук потише', 'Сделай звук потише'),
    ('Эйдус прочитай перевод', 'прочитай перевод'),
    ('Eidos, да да открой блокнот', 'да да открой блокнот'),
    ('расскажи про Эйдос', 'расскажи про Эйдос'),
])
def test_wake_prefix_preserves_command_and_repeated_words(phrase, expected):
    from eidos.modules.voice.intents import strip_wake_prefix
    assert strip_wake_prefix(phrase) == expected


def test_deterministic_voice_synonyms():
    from eidos.agent.harness import deterministic_call
    assert deterministic_call('сделай звук потише') == ('volume', {'mode': 'down', 'value': 10})
    assert deterministic_call('открой YouTube') == ('open_url', {'url': 'https://www.youtube.com/'})
    assert deterministic_call('запусти блокнот') == ('open_notepad', {})


def test_wake_capture_keeps_same_phrase_and_bounds_preroll():
    from eidos.modules.voice.wake import RingCapture
    capture = RingCapture(16000, sensitivity=.5, max_seconds=10)
    frame = np.full(1600, .05, dtype=np.float32)
    for _ in range(60): capture.feed(frame, detected=False)
    assert capture.buffered_samples <= 24000
    capture.feed(frame, detected=True)
    for _ in range(5): capture.feed(frame, detected=False)
    for _ in range(12): capture.feed(np.zeros(1600, dtype=np.float32), detected=False)
    assert capture.done
    assert np.count_nonzero(capture.audio()) >= 6 * 1600
    assert capture.audio().size <= 160000


def test_uncertain_stt_never_executes_and_repeats_are_preserved(tmp_path):
    from eidos.modules.voice.stt import WhisperSTT
    engine = WhisperSTT()
    engine._key = ('base', 'cpu')
    engine._model = SimpleNamespace(transcribe=lambda *a, **k: (iter([
        SimpleNamespace(text='открой блокнот', no_speech_prob=.9, avg_logprob=-1.5)
    ]), None))
    audio = np.tile(np.array([.1, -.1], dtype=np.float32), 8000)
    with pytest.raises(ValueError, match='Не удалось разобрать речь'):
        engine.transcribe(audio, AppConfig(), tmp_path, lambda *a: None, Event())
    engine._model = SimpleNamespace(transcribe=lambda *a, **k: (iter([
        SimpleNamespace(text='да да повтори повтори', no_speech_prob=.01, avg_logprob=-.1)
    ]), None))
    assert engine.transcribe(audio, AppConfig(), tmp_path, lambda *a: None, Event()) == 'да да повтори повтори'


def test_recording_id_dedup_allows_intentional_repetition(tmp_path):
    from eidos.modules.voice.worker import VoiceWorker
    class STT:
        def transcribe(self, *a): return 'Привет'
    worker = VoiceWorker(stt=STT())
    replies = []
    worker.reply.connect(replies.append)
    cfg = AppConfig(speak=False)
    audio = np.ones(16000, dtype=np.float32)
    worker.run_audio(cfg, tmp_path, audio, 'record-1', False)
    worker.run_audio(cfg, tmp_path, audio, 'record-1', False)
    worker.run_audio(cfg, tmp_path, audio, 'record-2', False)
    assert len(replies) == 2


def test_cancel_recording_is_not_submit(app, tmp_path):
    from eidos.modules.voice.controller import VoiceController
    from eidos.modules.voice.worker import VoiceWorker
    from test_ui import WaitingRecorder
    recorder = WaitingRecorder()
    controller = VoiceController(tmp_path, worker=VoiceWorker(recorder=recorder))
    try:
        controller.start(AppConfig(speak=False))
        wait_until(app, lambda: recorder.calls == 1)
        controller.cancel()
        assert controller.worker.cancel_event.is_set() and controller.worker.stop_event.is_set()
        wait_until(app, lambda: not controller.active)
    finally:
        controller.shutdown()
        wait_until(app, lambda: not controller.thread.isRunning())


def test_compact_and_orb_keyboard(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from eidos.ui.floating import FloatingMascot
    widget = FloatingMascot()
    try:
        assert (widget.width(), widget.height()) == (360, 470)
        actions = []
        widget.start_requested.connect(lambda: actions.append(True))
        widget.show()
        widget.start_button.setFocus()
        QTest.keyClick(widget.start_button, Qt.Key.Key_Space)
        assert actions == [True]
        widget.set_status('paused', 'Озвучка на паузе')
        assert not widget.mascot.visual_timer.isActive()
    finally:
        widget.close()


def test_main_orb_is_not_compressed_by_global_button_style(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window.show()
        window.navigate(1)
        app.processEvents()
        orb = window.voice.mascot
        assert (orb.width(), orb.height()) == (250, 250)
        assert orb.parentWidget().rect().contains(orb.geometry())
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_gui_translation_and_full_read_bridge(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        calls = []
        monkeypatch.setattr(window.translation, 'start_capture', lambda: calls.append('capture'))
        window.voice_bridge.execute('translate_region')
        assert calls == ['capture']
        window.translation.original.text.setPlainText('Original. Second. Third. Fourth.')
        window.translation.translated.text.setPlainText('Перевод. Второе. Третье. Четвёртое.')
        assert window.voice_bridge.execute('read_original').startswith('Original.')
        assert window.voice_bridge.execute('read_translation').endswith('Четвёртое.')
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_profiles_keep_independent_onboarding_and_memory(tmp_path):
    from eidos.agent.service import AgentService
    service = AgentService(tmp_path)
    service.save_settings(replace(service.settings, onboarding_done=True, name='Первый'))
    service.memory.add('profile', 'Первый профиль', 'test')
    service.activate_profile('Второй')
    assert not service.settings.onboarding_done and not service.settings.name
    assert service.memory.items('profile') == []
    service.save_settings(replace(service.settings, onboarding_done=True))
    service.activate_profile('Основной')
    assert service.settings.onboarding_done and service.settings.name == 'Первый'
    assert service.memory.items('profile')
    service.activate_profile('Второй')
    assert service.settings.onboarding_done


def test_voice_preferences_roundtrip_and_validation(tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    config = replace(AppConfig(), communication_style='friendly', voice_sensitivity=.8, voice_max_seconds=45)
    store.save(config)
    assert store.load() == config
    for values in [{'voice_max_seconds': 0}, {'voice_sensitivity': float('nan')}, {'communication_style': 'magic'}]:
        with pytest.raises(ValueError): replace(config, **values).validate()


def test_configured_120_seconds_is_not_reduced_to_30(monkeypatch):
    from eidos.modules.voice.recorder import Recorder
    stop = Event()
    class Stream:
        active = True
        def __init__(self, **kw): self.callback = kw['callback']
        def start(self):
            # A alternating waveform avoids DC-only test audio.
            frame = np.tile(np.array([3276, -3276], dtype='<i2'), 16384).tobytes()
            for _ in range(20): self.callback(frame, 32768, None, False)
            stop.set()
        def abort(self): pass
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream,
        query_devices=lambda *a: {'default_samplerate': 16000}, check_input_settings=lambda **kw: None))
    recorder = Recorder()
    class VAD:
        def reset(self): pass
        def __call__(self, data): return 1.
    recorder.vad = VAD()
    recorder.configure(replace(AppConfig(), voice_max_seconds=120))
    audio = recorder.record(None, stop, Event(), lambda: None)
    assert audio.size == 20 * 32768


def test_wake_reconfigures_command_limit_and_vad_sensitivity(app, tmp_path):
    from eidos.modules.voice.wake import WakeController
    wake = WakeController(None, SimpleNamespace(get=lambda *a: None))
    try:
        wake.configure(AppConfig())
        wake.configure(replace(AppConfig(), voice_sensitivity=.9, voice_max_seconds=120))
        assert wake._config.voice_sensitivity == .9
        assert wake._config.voice_max_seconds == 120
    finally:
        wake.shutdown()


def test_corrupt_wake_phrase_never_reaches_agent(tmp_path):
    from eidos.modules.voice.worker import VoiceWorker
    worker = VoiceWorker(stt=SimpleNamespace(transcribe=lambda *a: 'и этот открою youtube'))
    called, errors = [], []
    worker.commands = SimpleNamespace(handle=lambda text: called.append(text))
    worker.error.connect(errors.append)
    worker.run_audio(AppConfig(speak=False), tmp_path, np.ones(16000), 'corrupt-wake', True)
    assert not called and errors and 'Не удалось разобрать речь' in errors[0]


def test_stop_suppresses_agent_answer_queued_before_cancel(app, tmp_path, monkeypatch):
    from threading import Thread
    from eidos.ui.main_window import MainWindow
    from eidos.agent.harness import TaskContext
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        controller = window.agent_controller
        controller.context = TaskContext()
        controller.active = True
        spoken, delivered = [], []
        monkeypatch.setattr(window.background, 'speak', lambda text, **kw: spoken.append(text))
        controller.data.connect(lambda *args: delivered.append(args))
        thread = Thread(target=lambda: (controller.worker.answer.emit('Поздний ответ'),
                                        controller.worker.data.emit('tool', 'Поздние данные')))
        thread.start(); thread.join()
        window.background.stop_action()
        app.processEvents()
        assert spoken == [] and delivered == []
        assert 'Поздний ответ' not in window.assistant.history.toPlainText()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_orb_pause_is_enabled_when_synthesis_becomes_playable(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        player = window.controller.playback
        monkeypatch.setattr(player, 'play', lambda path: setattr(player, '_audio', path))
        queue = window.background.speech
        from eidos.modules.voice.pcm import PCMAudio
        path = PCMAudio(bytes(1024))
        queue._inflight = Event()
        queue._current_config = window.config
        queue._result(queue._inflight, path, '')
        assert player.active
        assert not window.voice.action_button.isEnabled()
        assert not window.background.floating.start_button.isEnabled()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_stop_cancels_pending_input_and_paused_speech(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        background = window.background
        background.pending_voice = True
        background._pending_audio = (np.ones(16000), 'pending')
        from eidos.modules.voice.pcm import PCMAudio
        path = PCMAudio(bytes(1024))
        window.controller.playback._audio = path
        window.controller.playback._output = SimpleNamespace(suspend=lambda: None, resume=lambda: None, stop=lambda: None, deleteLater=lambda: None)
        window.controller.playback.paused = True
        background.speech._playing = True
        background.stop_action()
        assert not background.pending_voice and background._pending_audio is None
        assert not background.speech.active and not window.controller.playback.active
        assert window.controller.playback._audio is None
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_wake_thread_captures_after_trigger_without_reopening(app, tmp_path, monkeypatch):
    from eidos.modules.voice.wake import WakeController
    keyword, model = tmp_path / 'eidos.ppn', tmp_path / 'ru.pv'
    keyword.touch(); model.touch()
    opened, closed, detections, audio = [], [], [], []
    class Engine:
        sample_rate, frame_length = 16000, 1600
        calls = 0
        def process(self, pcm):
            self.calls += 1
            return 0 if self.calls == 4 else -1
        def delete(self): closed.append('engine')
    class Stream:
        index = 0
        def __init__(self, **kwargs): opened.append(kwargs)
        def start(self): pass
        def read(self, count):
            import time
            time.sleep(.003)
            self.index += 1
            value = 3000 if self.index < 10 else 0
            return np.full(count, value, dtype=np.int16).tobytes(), False
        def abort(self): closed.append('abort')
        def close(self): closed.append('stream')
    monkeypatch.setitem(sys.modules, 'pvporcupine', SimpleNamespace(create=lambda **kw: Engine()))
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream))
    wake = WakeController(None, SimpleNamespace(get=lambda *a: 'fake-key'))
    wake.activated.connect(lambda: detections.append(True))
    wake.command_ready.connect(lambda pcm, ident: audio.append((pcm, ident)))
    try:
        wake.configure(replace(AppConfig(), wake_word_enabled=True, wake_keyword_path=str(keyword), wake_model_path=str(model)))
        wait_until(app, lambda: bool(audio) and not wake.is_running)
        assert len(opened) == 1 and detections == [True]
        assert np.count_nonzero(audio[0][0]) == 9 * 1600
        assert audio[0][1] and closed == ['abort', 'stream', 'engine']
        wake.set_busy(True)
        assert not wake._wanted()
    finally:
        wake.shutdown()
        wait_until(app, lambda: not wake.is_running)


def test_onboarding_skip_is_saved_per_profile(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window._show_onboarding()
        window._onboarding.reject()
        assert window.agent_service.settings.onboarding_done
        from eidos.agent.service import AgentService
        assert AgentService(tmp_path).settings.onboarding_done
        window._switch_profile('Другой')
        assert not window.agent_service.settings.onboarding_done
        window._onboarding.reject()
        assert AgentService(tmp_path).settings.onboarding_done
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_bridge_ignores_cancelled_gui_requests(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    from eidos.ui.voice_bridge import UIRequest
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        cancel = Event(); cancel.set()
        called = []
        monkeypatch.setattr(window.translation, 'start_capture', lambda: called.append(True))
        request = UIRequest('translate_region', cancel)
        window.voice_bridge._execute(request)
        assert request.done.is_set() and not called
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_muting_mic_preserves_playback_pause_state(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        from eidos.modules.voice.pcm import PCMAudio
        path = PCMAudio(bytes(1024))
        window.controller.playback._audio = path
        window.controller.playback._output = SimpleNamespace(suspend=lambda: None, resume=lambda: None, stop=lambda: None, deleteLater=lambda: None)
        window.background.speech._playing = True
        window.background.toggle_pause()
        assert not window.controller.playback.paused
        assert window.voice.mascot.state == 'speaking'
        assert window.voice.mascot.microphone_state == 'off'
        assert window.voice.mute_button.text() == 'Включить микрофон'
        window.controller.playback.paused = True
        window.background.toggle_pause()
        assert window.controller.playback.paused
        assert window.voice.mascot.state == 'paused'
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_speech_waits_until_wake_stream_is_closed(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    from eidos.modules.voice.wake import WakeController
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        running = [True]
        monkeypatch.setattr(WakeController, 'is_running', property(lambda self: running[0]))
        enqueued = []
        monkeypatch.setattr(window.background.speech, 'enqueue', lambda *a: enqueued.append(a) or True)
        assert window.background.speak('Ответ.')
        assert enqueued == []
        running[0] = False
        window.background._tick()
        assert len(enqueued) == 1
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_switch_profile_while_onboarding_keeps_old_answers_in_old_profile(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    from eidos.agent.service import AgentService
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window._show_onboarding()
        old = window._onboarding
        old.form.name.setText('Несохранённое имя')
        window._switch_profile('Новый')
        assert window._onboarding is not old
        assert not window.agent_service.settings.name
        window._onboarding.reject()
        service = AgentService(tmp_path)
        service.activate_profile('Основной')
        assert service.settings.onboarding_done
        assert not service.settings.name
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
