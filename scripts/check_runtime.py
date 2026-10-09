"""Manual diagnostics. Never opens a microphone or downloads a Whisper model."""

import argparse
import importlib
from pathlib import Path
import sys
from threading import Event


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--tts', action='store_true', help='Проверить онлайн-синтез нейтрального приветствия')
    parser.add_argument('--play', action='store_true', help='Воспроизвести тестовый ответ (включает --tts)')
    args = parser.parse_args()
    print('Python:', sys.version.split()[0])
    for name in ('PyQt6.QtWidgets', 'PyQt6.QtMultimedia', 'numpy', 'sounddevice', 'faster_whisper', 'edge_tts'):
        importlib.import_module(name)
        print('Import OK:', name)
    import ctranslate2
    from eidos.modules.voice.recorder import list_microphones

    print('CPU compute types:', sorted(ctranslate2.get_supported_compute_types('cpu')))
    print('Input devices:', len(list_microphones()))
    if not args.tts and not args.play:
        return 0
    from eidos.modules.voice.tts import EdgeTTS

    path: Path | None = None
    try:
        path = EdgeTTS().synthesize('Привет! Это проверка голоса Eidos.', 'ru-RU-SvetlanaNeural', Event())
        if path is None:
            raise RuntimeError('Синтез отменён')
        print('TTS OK: bytes =', path.stat().st_size)
        if args.play:
            from PyQt6.QtCore import QTimer
            from PyQt6.QtWidgets import QApplication
            from eidos.modules.voice.playback import AudioPlayback

            app = QApplication([])
            player = AudioPlayback()
            result = [1]
            def finished() -> None:
                print('QtMultimedia reached EndOfMedia. Подтвердите звук на слух самостоятельно.')
                result[0] = 0
                app.quit()
            player.finished.connect(finished)
            player.error.connect(lambda message: (print(message), app.quit()))
            QTimer.singleShot(15000, app.quit)
            QTimer.singleShot(0, lambda: player.play(path))
            app.exec()
            player.dispose()
            return result[0]
        return 0
    except Exception as exc:
        print('TTS/runtime error:', type(exc).__name__, str(exc)[:300])
        return 1
    finally:
        if path:
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
