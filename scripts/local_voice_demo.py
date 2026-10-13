"""Opt-in microphone/STT probe. Does not run tools or type into other windows.

Run from the Eidos root: python -m scripts.local_voice_demo
"""
import argparse
from pathlib import Path
import re
from threading import Event
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from eidos.core.config import AppConfig
from eidos.modules.voice.local_input import InputOptions, LocalAudioInput, WindowsPushToTalk
from eidos.modules.voice.stt import WhisperSTT


def resolve_whisper_cache(model, cache=None):
    """Find an already downloaded model without making a network request."""
    from faster_whisper.utils import download_model
    from huggingface_hub.constants import HF_HUB_CACHE
    from huggingface_hub.errors import LocalEntryNotFoundError
    candidates = ([Path(cache)] if cache is not None else
                  [Path('.cache/whisper'), Path(HF_HUB_CACHE)])
    searched = []
    for candidate in candidates:
        root = candidate.resolve()
        if root in searched:
            continue
        searched.append(root)
        try:
            download_model(model, cache_dir=str(root), local_files_only=True)
            return root
        except LocalEntryNotFoundError:
            continue
    raise RuntimeError(
        f'Локальная модель Whisper {model!r} не найдена. Проверены: '
        + '; '.join(map(str, searched))
        + '. Укажите корень существующего кеша через --cache. '
          'Для новой модели нужна однократная загрузка; демо не скачивает её автоматически.')


class Transcriber(QObject):
    requested = pyqtSignal(object, str, str)
    result = pyqtSignal(str, str, str)
    failed = pyqtSignal(str, str)
    done = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, cache, model):
        super().__init__()
        self.cache = cache
        self.resolved_cache = None
        self.config = AppConfig(whisper_model=model, device='cpu', speak=False)
        self.engine = WhisperSTT()
        self.cancel = Event()

    @pyqtSlot(object, str, str)
    def transcribe(self, audio, ident, source):
        try:
            # The existing adapter may download a missing model. Reject it here:
            # the microphone demo never needs a network connection.
            if self.resolved_cache is None:
                self.resolved_cache = resolve_whisper_cache(self.config.whisper_model, self.cache)
            if self.cancel.is_set():
                return
            started = time.monotonic()
            text = self.engine.transcribe(audio, self.config, self.resolved_cache,
                                          lambda stage, message: self.progress.emit(message), self.cancel)
            if source != 'ptt':
                text = re.sub(r'^\s*(?:эйдос|эйла|ейдос|ейла|эй\s+дос|eidos|eyla)\b[\s,.:!—-]*',
                              '', text, flags=re.IGNORECASE)
            if not self.cancel.is_set():
                self.result.emit(ident, text, f'STT: {time.monotonic() - started:.2f} с')
        except Exception as exc:
            if not self.cancel.is_set():
                self.failed.emit(ident, str(exc))
        finally:
            self.done.emit(ident)


class Probe(QWidget):
    def __init__(self, args):
        super().__init__()
        self.setWindowTitle('Эйдос · локальный аудиовход и Whisper')
        self.resize(620, 380)
        layout = QVBoxLayout(self)
        self.label = QLabel('Запуск · удерживайте Ctrl+Space для записи')
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.mute = QPushButton('Отключить микрофон')
        for widget in (self.label, self.text, self.mute):
            layout.addWidget(widget)
        self.allowed = True
        self.closing = False
        self.can_close = False
        self.input = LocalAudioInput(InputOptions(
            microphone_name=args.microphone, wake_models=tuple(args.wake_model),
            mel_model=args.mel_model, embedding_model=args.embedding_model), self)
        self.transcriber = Transcriber(args.cache, args.whisper_model)
        self.stt_thread = QThread(self)
        self.transcriber.moveToThread(self.stt_thread)
        self.transcriber.requested.connect(self.transcriber.transcribe)
        self.transcriber.result.connect(self._result)
        self.transcriber.failed.connect(self._failed)
        self.transcriber.progress.connect(self.label.setText)
        self.transcriber.done.connect(self._done)
        self.stt_thread.finished.connect(self.transcriber.deleteLater)
        self.input.audio_ready.connect(self._audio)
        self.input.status.connect(self.label.setText)
        self.input.error.connect(self.text.append)
        self.mute.clicked.connect(self._mute)
        self.ptt = WindowsPushToTalk(self.input.set_ptt)
        self.stt_thread.start()
        self.ptt.start()
        self.input.start()
        self.close_timer = QTimer(self)
        self.close_timer.setInterval(50)
        self.close_timer.timeout.connect(self._finish_close)

    @pyqtSlot(object, str, str)
    def _audio(self, audio, ident, source):
        if not self.closing and self.allowed and self.input.is_current(ident):
            self.label.setText('Распознавание локально…')
            self.transcriber.requested.emit(audio, ident, source)

    @pyqtSlot(str, str, str)
    def _result(self, ident, text, timing):
        if self.input.is_current(ident) and not self.closing:
            self.text.append(text or '[после имени команда отсутствует]')
            self.label.setText(timing)

    @pyqtSlot(str, str)
    def _failed(self, ident, message):
        if self.input.is_current(ident) and not self.closing:
            self.text.append('Ошибка STT: ' + message)

    @pyqtSlot(str)
    def _done(self, ident):
        if not self.closing:
            # Only one STT job is allowed; unblock even if mute invalidated its ID.
            self.input.set_blocked(False)

    def _mute(self):
        self.allowed = not self.allowed
        self.input.set_enabled(self.allowed)
        self.mute.setText('Отключить микрофон' if self.allowed else 'Включить микрофон')
        self.label.setText('Ожидание Ctrl+Space' if self.allowed else 'Микрофон отключён')

    def closeEvent(self, event):
        if self.can_close:
            event.accept()
            return
        event.ignore()
        if not self.closing:
            self.closing = True
            self.mute.setEnabled(False)
            self.label.setText('Завершение фоновых операций…')
            self.ptt.stop()
            self.input.shutdown()
            self.transcriber.cancel.set()
            self.stt_thread.quit()
            self.close_timer.start()

    def _finish_close(self):
        if not self.input.isRunning() and not self.stt_thread.isRunning():
            self.close_timer.stop()
            self.can_close = True
            self.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--microphone', help='Точное имя устройства sounddevice')
    parser.add_argument('--wake-model', action='append', default=[], help='Путь к своей ONNX wake-модели; можно дважды')
    parser.add_argument('--mel-model')
    parser.add_argument('--embedding-model')
    parser.add_argument('--whisper-model', default='base')
    parser.add_argument('--cache', help='Корень кеша; по умолчанию поиск в проекте и Hugging Face')
    args = parser.parse_args()
    app = QApplication([])
    window = Probe(args)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
