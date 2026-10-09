"""One bounded speech queue, one worker and the application's shared player."""

from collections import deque
from copy import copy
from pathlib import Path
from threading import Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from .speech_text import prepare_speech, split_sentences
from .tts import EdgeTTS, SapiTTS


class _SynthesisWorker(QObject):
    result = pyqtSignal(object, object, str)
    voices = pyqtSignal(object, str)

    @pyqtSlot()
    def list_voices(self):
        try:
            self.voices.emit(SapiTTS().list_voices(), '')
        except Exception as exc:
            self.voices.emit([], f'Не удалось получить голоса Windows: {exc}')

    @pyqtSlot(object)
    def synthesize(self, job):
        text, config, cancel = job
        path, error = None, ''
        try:
            if not cancel.is_set():
                provider_name = getattr(config, 'tts_provider', 'edge')
                if provider_name not in ('edge', 'sapi'):
                    raise ValueError('Неизвестный провайдер речи.')
                provider = SapiTTS() if provider_name == 'sapi' else EdgeTTS()
                voice = getattr(config, 'sapi_voice', '') if provider_name == 'sapi' else config.tts_voice
                path = provider.synthesize(text, voice, cancel,
                                           rate=getattr(config, 'tts_rate', 0), volume=100)
        except Exception as exc:
            error = f'Не удалось озвучить ответ: {exc}'
        if cancel.is_set() and path:
            Path(path).unlink(missing_ok=True)
            path = None
        self.result.emit(cancel, path, error)


class SpeechQueue(QObject):
    state_changed = pyqtSignal(str, str)
    closed = pyqtSignal()
    voices_ready = pyqtSignal(object)
    voices_error = pyqtSignal(str)
    _request = pyqtSignal(object)
    _voices_request = pyqtSignal()
    MAX_SENTENCES = 32
    MAX_CHARACTERS = 24000

    def __init__(self, parent: QObject | None, playback) -> None:
        super().__init__(parent)
        self.playback = playback
        self._pending = deque()
        self._inflight = None
        self._playing = False
        self._closing = False
        self._thread = QThread(self)
        self._worker = _SynthesisWorker()
        self._worker.moveToThread(self._thread)
        self._request.connect(self._worker.synthesize)
        self._voices_request.connect(self._worker.list_voices)
        self._worker.result.connect(self._result)
        self._worker.voices.connect(self._voices_result)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self.closed)
        playback.finished.connect(self._finished)
        playback.error.connect(self._error)
        self._thread.start()
        self._listing_voices = False

    def refresh_voices(self) -> bool:
        if self._closing or self._listing_voices:
            return False
        self._listing_voices = True
        self._voices_request.emit()
        return True

    @pyqtSlot(object, str)
    def _voices_result(self, voices, error) -> None:
        self._listing_voices = False
        if self._closing:
            return
        if error:
            self.voices_error.emit(error)
        else:
            self.voices_ready.emit(voices)

    @property
    def active(self) -> bool:
        return bool(self._pending or self._playing or
                    (self._inflight and not self._inflight.is_set()))

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def enqueue(self, text: str, config) -> bool:
        if self._closing or len(text) > self.MAX_CHARACTERS:
            return False
        sentences = split_sentences(prepare_speech(text, getattr(config, 'voice_response_brief', False)))
        outstanding = len(self._pending) + int(self._inflight is not None) + int(self._playing)
        if not sentences or outstanding + len(sentences) > self.MAX_SENTENCES:
            return False
        snapshot = copy(config)
        self._pending.extend((sentence, snapshot) for sentence in sentences)
        self._start_next()
        return True

    def _start_next(self) -> None:
        if self._closing or self._inflight is not None or self._playing or not self._pending:
            return
        text, config = self._pending.popleft()
        self._inflight = Event()
        self._current_config = config
        self.state_changed.emit('synthesizing', 'Подготовка речи…')
        self._request.emit((text, config, self._inflight))

    @pyqtSlot(object, object, str)
    def _result(self, cancel, path, error) -> None:
        if cancel is not self._inflight or cancel.is_set() or self._closing:
            if path:
                Path(path).unlink(missing_ok=True)
            if cancel is self._inflight:
                self._inflight = None
            self._start_next()
            return
        self._inflight = None
        if error:
            self._error(error)
            return
        if path:
            if hasattr(self.playback, 'set_volume'):
                self.playback.set_volume(max(0, min(100, getattr(self._current_config, 'tts_volume', 100))))
            self._playing = True
            self.state_changed.emit('playing', 'Говорю…')
            self.playback.play(Path(path))
        else:
            self._finished()

    def _finished(self) -> None:
        self._playing = False
        self._start_next()
        if not self.active and not self._closing:
            self.state_changed.emit('idle', 'Готов')

    def _error(self, message: str) -> None:
        self.stop()
        self.state_changed.emit('error', message)

    def stop(self) -> None:
        self._pending.clear()
        if self._inflight:
            self._inflight.set()
        self._playing = False
        self.playback.stop()
        self.state_changed.emit('idle', 'Готов')

    def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.stop()
        self._thread.quit()
