# Статический аудит неиспользуемого кода — 17.10.2026

Исходники не изменялись и ничего не удалялось. Проверены eidos, JARVIS-main, scripts, examples, tests и исходники в docs. Исключены окружения, кеши, build, сторонний минифицированный crypto-js и бинарные ресурсы.

Метод: Ruff 0.17.1 (F401, F811, F841), Vulture 2.16 и AST/поиск ссылок. Ruff проверял JARVIS-main с target-version py314 согласно его pyproject.toml. Для AST синтаксис except Python 3.14 нормализован только в памяти, строки сохранены. Статический анализ не доказывает отсутствие динамических вызовов, внешних потребителей и использования селекторов. Тесты приложения не запускались.

Разобрано Python-файлов: 266; файлов исходников всего: 268. Ошибки AST: нет.

## Неиспользуемые импорты (100)

Кандидаты Ruff. Обычно можно удалить после проверки побочных эффектов импорта. Импорты проверки доступности библиотек и реэкспорты требуют отдельной оценки.

### eidos

- [eidos/agent/controller.py:12](C:/Users/Элдос/Desktop/Eidos/eidos/agent/controller.py:12) — `.harness.TaskContext` imported but unused.
- [eidos/agent/controller.py:12](C:/Users/Элдос/Desktop/Eidos/eidos/agent/controller.py:12) — `.harness.Harness` imported but unused.
- [eidos/agent/harness.py:3](C:/Users/Элдос/Desktop/Eidos/eidos/agent/harness.py:3) — `hashlib` imported but unused.
- [eidos/agent/memory.py:3](C:/Users/Элдос/Desktop/Eidos/eidos/agent/memory.py:3) — `json` imported but unused.
- [eidos/agent/service.py:1](C:/Users/Элдос/Desktop/Eidos/eidos/agent/service.py:1) — `dataclasses.asdict` imported but unused.
- [eidos/agent/settings.py:1](C:/Users/Элдос/Desktop/Eidos/eidos/agent/settings.py:1) — `dataclasses.asdict` imported but unused.
- [eidos/modules/vision/service.py:109](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/service.py:109) — `mediapipe` imported but unused.
- [eidos/ui/assistant_bindings.py:15](C:/Users/Элдос/Desktop/Eidos/eidos/ui/assistant_bindings.py:15) — `eidos.agent.harness.TaskContext` imported but unused.
- [eidos/ui/assistant_bindings.py:16](C:/Users/Элдос/Desktop/Eidos/eidos/ui/assistant_bindings.py:16) — `eidos.agent.memory.has_secret` imported but unused.
- [eidos/ui/assistant_bindings.py:426](C:/Users/Элдос/Desktop/Eidos/eidos/ui/assistant_bindings.py:426) — `eidos.core.i18n.tr` imported but unused.
- [eidos/ui/background.py:4](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:4) — `PyQt6.QtCore.Qt` imported but unused.
- [eidos/ui/background.py:7](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:7) — `.icons.icon` imported but unused.
- [eidos/ui/background.py:8](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:8) — `.mascot.Mascot` imported but unused.
- [eidos/ui/desktop_commands.py:2](C:/Users/Элдос/Desktop/Eidos/eidos/ui/desktop_commands.py:2) — `dataclasses.replace` imported but unused.
- [eidos/ui/floating.py:6](C:/Users/Элдос/Desktop/Eidos/eidos/ui/floating.py:6) — `.mascot.Mascot` imported but unused.
- [eidos/ui/floating.py:6](C:/Users/Элдос/Desktop/Eidos/eidos/ui/floating.py:6) — `.mascot.STATE_DESCRIPTIONS` imported but unused.
- [eidos/ui/hotkeys.py:10](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:10) — `eidos.core.shortcuts.ACTIONS` imported but unused.
- [eidos/ui/main_window.py:795](C:/Users/Элдос/Desktop/Eidos/eidos/ui/main_window.py:795) — `ctypes` imported but unused.
- [eidos/ui/pages/assistant.py:3](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/assistant.py:3) — `PyQt6.QtWidgets.QHBoxLayout` imported but unused.
- [eidos/ui/pages/settings_layout.py:2](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/settings_layout.py:2) — `PyQt6.QtWidgets.QSizePolicy` imported but unused.
- [eidos/ui/pages/settings_layout.py:5](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/settings_layout.py:5) — `..components.button` imported but unused.
- [eidos/ui/pages/translation.py:6](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/translation.py:6) — `eidos.modules.ocr.engine.WindowsOCR` imported but unused.
- [eidos/ui/screen_translation.py:7](C:/Users/Элдос/Desktop/Eidos/eidos/ui/screen_translation.py:7) — `PyQt6.QtCore.QRect` imported but unused.
- [eidos/ui/screen_translation.py:12](C:/Users/Элдос/Desktop/Eidos/eidos/ui/screen_translation.py:12) — `eidos.modules.ocr.engine.WindowsOCR` imported but unused.

### JARVIS-main

- [JARVIS-main/actions/background_monitor.py:11](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/background_monitor.py:11) — `pathlib.Path` imported but unused.
- [JARVIS-main/actions/computer_control.py:366](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_control.py:366) — `google.genai` imported but unused.
- [JARVIS-main/actions/computer_settings.py:127](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_settings.py:127) — `math` imported but unused.
- [JARVIS-main/actions/desktop.py:136](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/desktop.py:136) — `google.genai` imported but unused.
- [JARVIS-main/actions/file_processor.py:19](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/file_processor.py:19) — `os` imported but unused.
- [JARVIS-main/actions/file_processor.py:26](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/file_processor.py:26) — `datetime.datetime` imported but unused.
- [JARVIS-main/actions/flight_finder.py:9](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/flight_finder.py:9) — `config.is_linux` imported but unused.
- [JARVIS-main/actions/flight_finder.py:165](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/flight_finder.py:165) — `google.genai` imported but unused.
- [JARVIS-main/actions/open_app.py:7](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/open_app.py:7) — `psutil` imported but unused; consider using `importlib.util.find_spec` to test for availability.
- [JARVIS-main/actions/reminder.py:2](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/reminder.py:2) — `os` imported but unused.
- [JARVIS-main/actions/youtube_video.py:5](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/youtube_video.py:5) — `time` imported but unused.
- [JARVIS-main/actions/youtube_video.py:7](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/youtube_video.py:7) — `shutil` imported but unused.
- [JARVIS-main/actions/youtube_video.py:13](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/youtube_video.py:13) — `pyautogui` imported but unused; consider using `importlib.util.find_spec` to test for availability.
- [JARVIS-main/actions/youtube_video.py:20](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/youtube_video.py:20) — `numpy` imported but unused; consider using `importlib.util.find_spec` to test for availability.
- [JARVIS-main/actions/youtube_video.py:40](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/youtube_video.py:40) — `config.get_os` imported but unused.
- [JARVIS-main/config/__init__.py:2](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/config/__init__.py:2) — `os` imported but unused.
- [JARVIS-main/plugins/battery_dashboard.py:15](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/battery_dashboard.py:15) — `PyQt6.QtGui.QColor` imported but unused.
- [JARVIS-main/plugins/battery_dashboard.py:16](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/battery_dashboard.py:16) — `PyQt6.QtGui.QLinearGradient` imported but unused.
- [JARVIS-main/plugins/battery_dashboard.py:18](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/battery_dashboard.py:18) — `PyQt6.QtGui.QPainterPath` imported but unused.
- [JARVIS-main/plugins/disk_dashboard.py:10](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/disk_dashboard.py:10) — `shutil` imported but unused.
- [JARVIS-main/plugins/disk_dashboard.py:18](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/disk_dashboard.py:18) — `PyQt6.QtCore.QPointF` imported but unused.
- [JARVIS-main/plugins/network_dashboard.py:10](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/network_dashboard.py:10) — `math` imported but unused.
- [JARVIS-main/plugins/network_dashboard.py:20](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/network_dashboard.py:20) — `PyQt6.QtCore.QPointF` imported but unused.
- [JARVIS-main/plugins/network_dashboard.py:20](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/network_dashboard.py:20) — `PyQt6.QtCore.Qt` imported but unused.
- [JARVIS-main/plugins/trading_agent.py:15](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/trading_agent.py:15) — `math` imported but unused.
- [JARVIS-main/plugins/trading_agent.py:17](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/trading_agent.py:17) — `datetime.datetime` imported but unused.
- [JARVIS-main/plugins/trading_agent.py:17](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/trading_agent.py:17) — `datetime.timezone` imported but unused.
- [JARVIS-main/plugins/water_reminder.py:18](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/water_reminder.py:18) — `time` imported but unused.

### scripts

- [scripts/benchmark_agent.py:7](C:/Users/Элдос/Desktop/Eidos/scripts/benchmark_agent.py:7) — `dataclasses.replace` imported but unused.
- [scripts/benchmark_local_response.py:7](C:/Users/Элдос/Desktop/Eidos/scripts/benchmark_local_response.py:7) — `time` imported but unused.
- [scripts/benchmark_local_response.py:43](C:/Users/Элдос/Desktop/Eidos/scripts/benchmark_local_response.py:43) — `eidos.agent.providers` imported but unused.
- [scripts/benchmark_voice_stages.py:19](C:/Users/Элдос/Desktop/Eidos/scripts/benchmark_voice_stages.py:19) — `eidos.core.metrics.METRICS` imported but unused.
- [scripts/build_ui_catalogs.py:14](C:/Users/Элдос/Desktop/Eidos/scripts/build_ui_catalogs.py:14) — `time` imported but unused.
- [scripts/capture_wave_hover.py:11](C:/Users/Элдос/Desktop/Eidos/scripts/capture_wave_hover.py:11) — `PyQt6.QtCore.Qt` imported but unused.
- [scripts/check_background_native.py:5](C:/Users/Элдос/Desktop/Eidos/scripts/check_background_native.py:5) — `time` imported but unused.
- [scripts/check_background_native.py:6](C:/Users/Элдос/Desktop/Eidos/scripts/check_background_native.py:6) — `dataclasses.replace` imported but unused.
- [scripts/check_runtime.py:5](C:/Users/Элдос/Desktop/Eidos/scripts/check_runtime.py:5) — `pathlib.Path` imported but unused.
- [scripts/check_speech_native.py:2](C:/Users/Элдос/Desktop/Eidos/scripts/check_speech_native.py:2) — `os` imported but unused.
- [scripts/check_translation_native.py:13](C:/Users/Элдос/Desktop/Eidos/scripts/check_translation_native.py:13) — `PyQt6.QtCore.QPoint` imported but unused.
- [scripts/prepare_vosk_model.py:6](C:/Users/Элдос/Desktop/Eidos/scripts/prepare_vosk_model.py:6) — `shutil` imported but unused.
- [scripts/translate_ui_catalogs.py:12](C:/Users/Элдос/Desktop/Eidos/scripts/translate_ui_catalogs.py:12) — `time` imported but unused.
- [scripts/verify_gestures_native.py:15](C:/Users/Элдос/Desktop/Eidos/scripts/verify_gestures_native.py:15) — `PyQt6.QtCore.QTimer` imported but unused.
- [scripts/verify_gestures_native.py:54](C:/Users/Элдос/Desktop/Eidos/scripts/verify_gestures_native.py:54) — `ctypes.wintypes` imported but unused.
- [scripts/verify_voice_native.py:14](C:/Users/Элдос/Desktop/Eidos/scripts/verify_voice_native.py:14) — `PyQt6.QtCore.QCoreApplication` imported but unused.

### tests

- [tests/test_agent.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_agent.py:2) — `pathlib.Path` imported but unused.
- [tests/test_agent_tools.py:1](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:1) — `dataclasses.replace` imported but unused.
- [tests/test_agent_tools.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:2) — `datetime.datetime` imported but unused.
- [tests/test_agent_tools.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:2) — `datetime.timezone` imported but unused.
- [tests/test_agent_tools.py:3](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:3) — `threading` imported but unused.
- [tests/test_agent_tools.py:8](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:8) — `eidos.agent.harness.Harness` imported but unused.
- [tests/test_agent_ui.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:2) — `time` imported but unused.
- [tests/test_agent_ui.py:3](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:3) — `dataclasses.replace` imported but unused.
- [tests/test_async_voice_gemini_example.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_async_voice_gemini_example.py:2) — `pathlib.Path` imported but unused.
- [tests/test_background_voice.py:4](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:4) — `pathlib.Path` imported but unused.
- [tests/test_desktop_commands.py:1](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_commands.py:1) — `dataclasses.replace` imported but unused.
- [tests/test_desktop_commands.py:4](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_commands.py:4) — `pathlib.Path` imported but unused.
- [tests/test_desktop_ui.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_ui.py:2) — `types.SimpleNamespace` imported but unused.
- [tests/test_desktop_ui.py:4](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_ui.py:4) — `PyQt6.QtTest.QTest` imported but unused.
- [tests/test_gesture_ui.py:3](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:3) — `PyQt6.QtGui.QImage` imported but unused.
- [tests/test_minimal_screen_capture.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:2) — `PyQt6.QtCore.QPoint` imported but unused.
- [tests/test_minimal_voice.py:6](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:6) — `test_ui.wait_until` imported but unused.
- [tests/test_modernization_i18n.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_i18n.py:2) — `pathlib.Path` imported but unused.
- [tests/test_modernization_privacy.py:75](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_privacy.py:75) — `eidos.agent.harness.ToolResult` imported but unused.
- [tests/test_modernization_startup.py:1](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_startup.py:1) — `pathlib.Path` imported but unused.
- [tests/test_modernization_ui.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_ui.py:2) — `PyQt6.QtWidgets.QLabel` imported but unused.
- [tests/test_search_provider.py:1](C:/Users/Элдос/Desktop/Eidos/tests/test_search_provider.py:1) — `dataclasses.replace` imported but unused.
- [tests/test_secret_boundaries.py:2](C:/Users/Элдос/Desktop/Eidos/tests/test_secret_boundaries.py:2) — `eidos.agent.memory.Memory` imported but unused.
- [tests/test_ui.py:4](C:/Users/Элдос/Desktop/Eidos/tests/test_ui.py:4) — `pathlib.Path` imported but unused.
- [tests/test_ui.py:9](C:/Users/Элдос/Desktop/Eidos/tests/test_ui.py:9) — `PyQt6.QtCore.QTimer` imported but unused.
- [tests/test_ui.py:130](C:/Users/Элдос/Desktop/Eidos/tests/test_ui.py:130) — `asyncio` imported but unused.
- [tests/test_voice_indicator.py:3](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:3) — `threading.Event` imported but unused.
- [tests/test_voice_upgrade.py:3](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:3) — `pathlib.Path` imported but unused.

### docs

- [docs/audit-2026-10-13/collect_evidence.py:11](C:/Users/Элдос/Desktop/Eidos/docs/audit-2026-10-13/collect_evidence.py:11) — `os` imported but unused.
- [docs/audit-2026-10-13/collect_evidence.py:13](C:/Users/Элдос/Desktop/Eidos/docs/audit-2026-10-13/collect_evidence.py:13) — `subprocess` imported but unused.
- [docs/audit-2026-10-13/collect_evidence.py:15](C:/Users/Элдос/Desktop/Eidos/docs/audit-2026-10-13/collect_evidence.py:15) — `threading` imported but unused.
- [docs/audit-2026-10-13/collect_evidence.py:143](C:/Users/Элдос/Desktop/Eidos/docs/audit-2026-10-13/collect_evidence.py:143) — `eidos.modules.ocr.engine.OnlineTranslator` imported but unused.

## Неиспользуемые локальные переменные (11)

Можно убрать ненужное связывание имени. Вызов справа от присваивания может иметь побочные эффекты — удалять его автоматически нельзя.

### eidos

- [eidos/modules/voice/local_input.py:325](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/local_input.py:325) — Local variable `resampler` is assigned to but never used.
- [eidos/ui/background.py:216](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:216) — Local variable `window` is assigned to but never used.
- [eidos/ui/main_window.py:609](C:/Users/Элдос/Desktop/Eidos/eidos/ui/main_window.py:609) — Local variable `muted` is assigned to but never used.
- [eidos/ui/main_window.py:610](C:/Users/Элдос/Desktop/Eidos/eidos/ui/main_window.py:610) — Local variable `recording` is assigned to but never used.
- [eidos/ui/main_window.py:611](C:/Users/Элдос/Desktop/Eidos/eidos/ui/main_window.py:611) — Local variable `waking` is assigned to but never used.

### JARVIS-main

- [JARVIS-main/actions/code_helper.py:518](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/code_helper.py:518) — Local variable `image_base64` is assigned to but never used.
- [JARVIS-main/core/llm_client.py:88](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:88) — Local variable `e` is assigned to but never used.
- [JARVIS-main/plugins/battery_dashboard.py:468](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/battery_dashboard.py:468) — Local variable `exp` is assigned to but never used.
- [JARVIS-main/plugins/disk_dashboard.py:121](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/disk_dashboard.py:121) — Local variable `before` is assigned to but never used.
- [JARVIS-main/ui.py:1540](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:1540) — Local variable `thinking` is assigned to but never used.
- [JARVIS-main/ui.py:2785](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2785) — Local variable `cx` is assigned to but never used.

## Переопределения (2)

Проверить, нужна ли более ранняя версия определения; это не отдельные неиспользуемые функции.

### JARVIS-main

- [JARVIS-main/ui.py:382](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:382) — Redefinition of unused `current_palette` from line 286: `current_palette` redefined here.

### tests

- [tests/test_agent_tools.py:28](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_tools.py:28) — Redefinition of unused `Harness` from line 8: `Harness` redefined here.

## Файлы без входящих статических импортов

Это кандидаты, а не доказательство ненужности. Точки входа __main__, startup_launcher и __init__ исключены. Скрипты, тесты и плагины могут запускаться напрямую; отсутствие импорта для них нормально.

- [eidos/modules/calendar/interface.py:1](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:1) — модуль не импортируется другими проверенными Python-файлами.
- [eidos/modules/vision/interface.py:1](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:1) — модуль не импортируется другими проверенными Python-файлами.
- [eidos/ui/pages/activation.py:1](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/activation.py:1) — модуль не импортируется другими проверенными Python-файлами.

JARVIS-main — отдельный проект (Python >=3.14), не входит в пакет eidos по корневому pyproject.toml. Его actions и plugins загружаются динамически; всё дерево нельзя считать мусором только потому, что Eidos его не импортирует.

### Пустые файлы и временные ресурсы

- [JARVIS-main/dashboard/static/app.html:1](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/static/app.html:1) — файл 0 байт: недостающий интерфейс панели. Сервер читает его в server.py:549 и использует в :641. НЕ удалять как неиспользуемый.
- [eidos/assets/i18n/en.tmp:1](C:/Users/Элдос/Desktop/Eidos/eidos/assets/i18n/en.tmp:1) — временный файл 2 байта, ссылок в исходниках не найдено, в package-data включены только *.json. Кандидат на очистку.
- Пустые __init__.py в JARVIS-main/dashboard, memory и plugins — маркеры пакетов, оставить.

## Пустые и нереализованные функции

Ниже полный список простых тел: pass, ..., единственный return None или raise NotImplementedError. return None может быть штатным поведением. Протоколы и тестовые двойники сохранены отдельными группами.

### Основной код и вспомогательные скрипты — оценить назначение

- [docs/audit-2026-10-13/collect_evidence.py:146](C:/Users/Элдос/Desktop/Eidos/docs/audit-2026-10-13/collect_evidence.py:146) — `FakeResponse.__exit__`: `pass`.
- [eidos/modules/ocr/interface.py:21](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:21) — `DisconnectedOCR.recognize`: `raise NotImplementedError(self.status)`.
- [eidos/modules/ocr/interface.py:24](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:24) — `DisconnectedOCR.translate`: `raise NotImplementedError(self.status)`.
- [eidos/modules/vision/interface.py:13](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:13) — `DisconnectedVision.start`: `raise NotImplementedError(self.status)`.
- [eidos/modules/vision/interface.py:16](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:16) — `DisconnectedVision.stop`: `pass`.
- [eidos/modules/vision/interface.py:19](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:19) — `DisconnectedVision.poll_gesture`: `return None`.
- [eidos/ui/hotkeys.py:200](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:200) — `GestureEmergencyHotkey._focus_changed`: `pass`.
- [eidos/ui/hotkeys.py:201](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:201) — `GestureEmergencyHotkey._application_state`: `pass`.
- [eidos/ui/mascot_placement.py:168](C:/Users/Элдос/Desktop/Eidos/eidos/ui/mascot_placement.py:168) — `DesktopMascot.set_microphone_paused`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:501](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:501) — `Board.draw`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:504](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:504) — `Board.clicked`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:507](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:507) — `Board.on_open`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:510](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:510) — `Board.on_close`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:1553](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:1553) — `TradingBoard.on_open`: `pass`.
- [JARVIS-main/plugins/_live_panels_core.py:1556](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:1556) — `TradingBoard.on_close`: `pass`.
- [JARVIS-main/plugins/chat_takeover.py:412](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/chat_takeover.py:412) — `_RestEngine.close`: `pass`.
- [JARVIS-main/ui.py:9644](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9644) — `_RootShim.protocol`: `pass`.
- [scripts/verify_gestures_native.py:101](C:/Users/Элдос/Desktop/Eidos/scripts/verify_gestures_native.py:101) — `FakeActions.close`: `pass`.

### Объявления Protocol — оставить

- [eidos/core/commands.py:11](C:/Users/Элдос/Desktop/Eidos/eidos/core/commands.py:11) — `AssistantProvider.respond`: `...`.
- [eidos/modules/calendar/interface.py:7](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:7) — `CalendarProvider.list`: `...`.
- [eidos/modules/calendar/interface.py:8](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:8) — `CalendarProvider.change`: `...`.
- [eidos/modules/ocr/interface.py:14](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:14) — `ScreenTranslator.recognize`: `...`.
- [eidos/modules/ocr/interface.py:15](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:15) — `ScreenTranslator.translate`: `...`.
- [eidos/modules/vision/interface.py:5](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:5) — `GestureProvider.start`: `...`.
- [eidos/modules/vision/interface.py:6](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:6) — `GestureProvider.stop`: `...`.
- [eidos/modules/vision/interface.py:7](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:7) — `GestureProvider.poll_gesture`: `...`.

### Тестовые двойники — оставить

- [tests/test_async_voice_gemini_example.py:65](C:/Users/Элдос/Desktop/Eidos/tests/test_async_voice_gemini_example.py:65) — `Device.start`: `pass`.
- [tests/test_background_voice.py:228](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:228) — `Stream.start`: `pass`.
- [tests/test_background_voice.py:330](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:330) — `VAD.reset`: `pass`.
- [tests/test_background_voice.py:359](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:359) — `Stream.abort`: `pass`.
- [tests/test_background_voice.py:362](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:362) — `Stream.close`: `pass`.
- [tests/test_background_voice.py:370](C:/Users/Элдос/Desktop/Eidos/tests/test_background_voice.py:370) — `VAD.reset`: `pass`.
- [tests/test_gesture_runtime.py:101](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:101) — `Capture.set`: `pass`.
- [tests/test_gesture_runtime.py:139](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:139) — `Detector.__init__`: `pass`.
- [tests/test_gesture_runtime.py:142](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:142) — `Detector.reset`: `pass`.
- [tests/test_gesture_runtime.py:150](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:150) — `Detector.close`: `pass`.
- [tests/test_gesture_runtime.py:157](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:157) — `Executor.close`: `pass`.
- [tests/test_minimal_voice.py:123](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:123) — `Stream.abort`: `pass`.
- [tests/test_minimal_voice.py:124](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:124) — `Stream.close`: `pass`.
- [tests/test_minimal_voice.py:130](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:130) — `VAD.reset`: `pass`.
- [tests/test_modernization_streaming.py:18](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_streaming.py:18) — `Recognizer.__init__`: `pass`.
- [tests/test_modernization_streaming.py:26](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_streaming.py:26) — `Recorder.configure`: `pass`.
- [tests/test_modernization_streaming.py:60](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_streaming.py:60) — `Recognizer.__init__`: `pass`.
- [tests/test_ollama_transport.py:37](C:/Users/Элдос/Desktop/Eidos/tests/test_ollama_transport.py:37) — `Handler.log_message`: `pass`.
- [tests/test_pcm_voice.py:25](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:25) — `Communicate.__init__`: `pass`.
- [tests/test_pcm_voice.py:57](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:57) — `VAD.reset`: `pass`.
- [tests/test_pcm_voice.py:70](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:70) — `Stream.abort`: `pass`.
- [tests/test_pcm_voice.py:71](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:71) — `Stream.close`: `pass`.
- [tests/test_pcm_voice.py:84](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:84) — `VAD.reset`: `pass`.
- [tests/test_pcm_voice.py:95](C:/Users/Элдос/Desktop/Eidos/tests/test_pcm_voice.py:95) — `Stream.abort`: `pass`.
- [tests/test_persistent_audio_stream.py:33](C:/Users/Элдос/Desktop/Eidos/tests/test_persistent_audio_stream.py:33) — `VAD.reset`: `pass`.
- [tests/test_voice_indicator.py:30](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:30) — `Stream.abort`: `pass`.
- [tests/test_voice_indicator.py:31](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:31) — `Stream.close`: `pass`.
- [tests/test_voice_upgrade.py:28](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:28) — `Sink.deleteLater`: `pass`.
- [tests/test_voice_upgrade.py:211](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:211) — `Stream.abort`: `pass`.
- [tests/test_voice_upgrade.py:212](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:212) — `Stream.close`: `pass`.
- [tests/test_voice_upgrade.py:217](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:217) — `VAD.reset`: `pass`.
- [tests/test_voice_upgrade.py:330](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:330) — `Stream.start`: `pass`.

Внешний календарь также намеренно недоступен:

- [eidos/modules/calendar/interface.py:12](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:12) — `ExternalCalendarUnavailable.list`: RuntimeError, внешний календарь не реализован.
- [eidos/modules/calendar/interface.py:15](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:15) — `ExternalCalendarUnavailable.change`: RuntimeError, синхронизация не подключена.

DisconnectedOCR / DisconnectedVision — явные заглушки без найденных обращений к классам. GestureEmergencyHotkey._focus_changed / _application_state — намеренные no-op переопределения: сохраняют аварийную клавишу при смене фокуса. Удалять их нельзя. Пустые методы базовых классов плагинов JARVIS могут быть точками расширения.

## TODO / FIXME

- [JARVIS-main/actions/dev_agent.py:240](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/dev_agent.py:240) — `- Write COMPLETE, RUNNABLE code — no placeholders, no "# TODO", no "pass" stubs.`

Найденное упоминание TODO в промпте dev_agent — запрет генерации заглушек, а не оставленная задача разработчика.

## Стили: кандидаты QSS-селекторов по objectName

Выбраны селекторы #objectName, для которых нет точного строкового литерала имени в Python-коде проекта. Возможны динамические имена, Qt-наследование и переопределение стилей; требуется визуальная проверка перед удалением. Общие правила QWidget/QLabel и каскадные частичные переопределения не объявляются неиспользуемыми.

- [eidos/ui/theme.py:58](C:/Users/Элдос/Desktop/Eidos/eidos/ui/theme.py:58) — `QLabel#heroTitle`.
- [eidos/ui/theme.py:67](C:/Users/Элдос/Desktop/Eidos/eidos/ui/theme.py:67) — `QFrame#hero`.
- [eidos/ui/theme.py:86](C:/Users/Элдос/Desktop/Eidos/eidos/ui/theme.py:86) — `QPushButton#chip`.
- [eidos/ui/theme.py:87](C:/Users/Элдос/Desktop/Eidos/eidos/ui/theme.py:87) — `QPushButton#chip:hover`.
- [eidos/ui/theme.py:88](C:/Users/Элдос/Desktop/Eidos/eidos/ui/theme.py:88) — `QPushButton#details`.

В JARVIS login.html классы и id используются разметкой и JavaScript (включая shake через classList); неиспользуемость не подтверждена. app.html пустой.

## Дополнительные кандидаты Vulture

Это необработанные эвристики, НЕ список безопасного удаления. Здесь есть известные ложные срабатывания: Qt virtual methods, HTMLParser callbacks, ctypes-поля, sqlite row_factory, поля конфигурации и динамические плагины. Проценты — оценка инструмента, не гарантия. Vulture проверил все Python-файлы с той же нормализацией except в памяти, что и AST.

- [eidos/agent/controller.py:20](C:/Users/Элдос/Desktop/Eidos/eidos/agent/controller.py:20) — unused variable 'ACTING' (60% confidence).
- [eidos/agent/controller.py:21](C:/Users/Элдос/Desktop/Eidos/eidos/agent/controller.py:21) — unused variable 'CHECKING' (60% confidence).
- [eidos/agent/controller.py:22](C:/Users/Элдос/Desktop/Eidos/eidos/agent/controller.py:22) — unused variable 'CONFIRMING' (60% confidence).
- [eidos/agent/memory.py:86](C:/Users/Элдос/Desktop/Eidos/eidos/agent/memory.py:86) — unused attribute 'row_factory' (60% confidence).
- [eidos/agent/settings.py:34](C:/Users/Элдос/Desktop/Eidos/eidos/agent/settings.py:34) — unused variable 'telegram_users' (60% confidence).
- [eidos/agent/settings.py:35](C:/Users/Элдос/Desktop/Eidos/eidos/agent/settings.py:35) — unused variable 'telegram_channels' (60% confidence).
- [eidos/agent/settings.py:36](C:/Users/Элдос/Desktop/Eidos/eidos/agent/settings.py:36) — unused variable 'discord_users' (60% confidence).
- [eidos/agent/tools.py:188](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:188) — unused method 'handle_starttag' (60% confidence).
- [eidos/agent/tools.py:188](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:188) — unused variable 'attrs' (100% confidence).
- [eidos/agent/tools.py:192](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:192) — unused method 'handle_endtag' (60% confidence).
- [eidos/agent/tools.py:196](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:196) — unused method 'handle_data' (60% confidence).
- [eidos/agent/tools.py:206](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:206) — unused attribute 'sock' (60% confidence).
- [eidos/agent/tools.py:210](C:/Users/Элдос/Desktop/Eidos/eidos/agent/tools.py:210) — unused attribute 'sock' (60% confidence).
- [eidos/core/config.py:76](C:/Users/Элдос/Desktop/Eidos/eidos/core/config.py:76) — unused variable 'gesture_sensitivity' (60% confidence).
- [eidos/core/config.py:80](C:/Users/Элдос/Desktop/Eidos/eidos/core/config.py:80) — unused variable 'gesture_volume_dead' (60% confidence).
- [eidos/core/config.py:81](C:/Users/Элдос/Desktop/Eidos/eidos/core/config.py:81) — unused variable 'gesture_volume_interval' (60% confidence).
- [eidos/core/config.py:82](C:/Users/Элдос/Desktop/Eidos/eidos/core/config.py:82) — unused variable 'gesture_hold' (60% confidence).
- [eidos/core/config.py:83](C:/Users/Элдос/Desktop/Eidos/eidos/core/config.py:83) — unused variable 'gesture_cooldown' (60% confidence).
- [eidos/core/shortcuts.py:70](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:70) — unused attribute 'argtypes' (60% confidence).
- [eidos/core/shortcuts.py:70](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:70) — unused attribute 'restype' (60% confidence).
- [eidos/core/shortcuts.py:76](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:76) — unused attribute 'argtypes' (60% confidence).
- [eidos/core/shortcuts.py:77](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:77) — unused attribute 'restype' (60% confidence).
- [eidos/core/shortcuts.py:81](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:81) — unused attribute 'argtypes' (60% confidence).
- [eidos/core/shortcuts.py:82](C:/Users/Элдос/Desktop/Eidos/eidos/core/shortcuts.py:82) — unused attribute 'restype' (60% confidence).
- [eidos/desktop/windows.py:13](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:13) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:14](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:14) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:15](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:15) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:16](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:16) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:17](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:17) — unused attribute 'restype' (60% confidence).
- [eidos/desktop/windows.py:18](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:18) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:19](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:19) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:23](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:23) — unused variable 'unused' (100% confidence).
- [eidos/desktop/windows.py:51](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:51) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:59](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:59) — unused attribute 'argtypes' (60% confidence).
- [eidos/desktop/windows.py:60](C:/Users/Элдос/Desktop/Eidos/eidos/desktop/windows.py:60) — unused attribute 'argtypes' (60% confidence).
- [eidos/modules/calendar/interface.py:5](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:5) — unused class 'CalendarProvider' (60% confidence).
- [eidos/modules/calendar/interface.py:11](C:/Users/Элдос/Desktop/Eidos/eidos/modules/calendar/interface.py:11) — unused class 'ExternalCalendarUnavailable' (60% confidence).
- [eidos/modules/ocr/interface.py:13](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:13) — unused class 'ScreenTranslator' (60% confidence).
- [eidos/modules/ocr/interface.py:15](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:15) — unused variable 'target_language' (100% confidence).
- [eidos/modules/ocr/interface.py:18](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:18) — unused class 'DisconnectedOCR' (60% confidence).
- [eidos/modules/ocr/interface.py:24](C:/Users/Элдос/Desktop/Eidos/eidos/modules/ocr/interface.py:24) — unused variable 'target_language' (100% confidence).
- [eidos/modules/vision/actions.py:69](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:69) — unused attribute 'dmSize' (60% confidence).
- [eidos/modules/vision/actions.py:88](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:88) — unused attribute 'argtypes' (60% confidence).
- [eidos/modules/vision/actions.py:89](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:89) — unused attribute 'restype' (60% confidence).
- [eidos/modules/vision/actions.py:146](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:146) — unused attribute 'vk' (60% confidence).
- [eidos/modules/vision/actions.py:148](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:148) — unused attribute 'argtypes' (60% confidence).
- [eidos/modules/vision/actions.py:153](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/actions.py:153) — unused attribute 'restype' (60% confidence).
- [eidos/modules/vision/interface.py:4](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:4) — unused class 'GestureProvider' (60% confidence).
- [eidos/modules/vision/interface.py:7](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:7) — unused method 'poll_gesture' (60% confidence).
- [eidos/modules/vision/interface.py:10](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:10) — unused class 'DisconnectedVision' (60% confidence).
- [eidos/modules/vision/interface.py:19](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/interface.py:19) — unused method 'poll_gesture' (60% confidence).
- [eidos/modules/vision/service.py:351](C:/Users/Элдос/Desktop/Eidos/eidos/modules/vision/service.py:351) — unused method 'poll_gesture' (60% confidence).
- [eidos/modules/voice/recorder.py:42](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/recorder.py:42) — unused variable 'SPEECH_THRESHOLD' (60% confidence).
- [eidos/modules/voice/recorder.py:43](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/recorder.py:43) — unused variable 'PRE_ROLL_SECONDS' (60% confidence).
- [eidos/modules/voice/recorder.py:113](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/recorder.py:113) — unused variable 'time_info' (100% confidence).
- [eidos/modules/voice/stt.py:20](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/stt.py:20) — unused attribute 'argtypes' (60% confidence).
- [eidos/modules/voice/stt.py:21](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/stt.py:21) — unused attribute 'restype' (60% confidence).
- [eidos/modules/voice/tts.py:115](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/tts.py:115) — unused attribute 'AudioOutputStream' (60% confidence).
- [eidos/modules/voice/vad.py:6](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/vad.py:6) — unused variable 'FRAME_SAMPLES' (60% confidence).
- [eidos/modules/voice/vad.py:11](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/vad.py:11) — unused attribute 'inter_op_num_threads' (60% confidence).
- [eidos/modules/voice/vad.py:11](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/vad.py:11) — unused attribute 'intra_op_num_threads' (60% confidence).
- [eidos/modules/voice/wake.py:200](C:/Users/Элдос/Desktop/Eidos/eidos/modules/voice/wake.py:200) — unused method 'finish_command' (60% confidence).
- [eidos/ui/assistant_bindings.py:296](C:/Users/Элдос/Desktop/Eidos/eidos/ui/assistant_bindings.py:296) — unused method '_restore_history' (60% confidence).
- [eidos/ui/background.py:20](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:20) — unused attribute '_capture_visible' (60% confidence).
- [eidos/ui/background.py:464](C:/Users/Элдос/Desktop/Eidos/eidos/ui/background.py:464) — unused attribute '_capture_visible' (60% confidence).
- [eidos/ui/components.py:99](C:/Users/Элдос/Desktop/Eidos/eidos/ui/components.py:99) — unused method 'minimumSizeHint' (60% confidence).
- [eidos/ui/floating.py:58](C:/Users/Элдос/Desktop/Eidos/eidos/ui/floating.py:58) — unused attribute 'open_button' (60% confidence).
- [eidos/ui/hotkeys.py:19](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:19) — unused attribute 'argtypes' (60% confidence).
- [eidos/ui/hotkeys.py:20](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:20) — unused attribute 'restype' (60% confidence).
- [eidos/ui/hotkeys.py:21](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:21) — unused attribute 'argtypes' (60% confidence).
- [eidos/ui/hotkeys.py:22](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:22) — unused attribute 'restype' (60% confidence).
- [eidos/ui/hotkeys.py:57](C:/Users/Элдос/Desktop/Eidos/eidos/ui/hotkeys.py:57) — unused method 'nativeEventFilter' (60% confidence).
- [eidos/ui/localized.py:12](C:/Users/Элдос/Desktop/Eidos/eidos/ui/localized.py:12) — unused variable 'disambiguation' (100% confidence).
- [eidos/ui/localized.py:64](C:/Users/Элдос/Desktop/Eidos/eidos/ui/localized.py:64) — unused method 'setTitle' (60% confidence).
- [eidos/ui/main_window.py:611](C:/Users/Элдос/Desktop/Eidos/eidos/ui/main_window.py:611) — unused variable 'waking' (60% confidence).
- [eidos/ui/pages/activation.py:5](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/activation.py:5) — unused class 'ActivationPage' (60% confidence).
- [eidos/ui/pages/gestures_layout.py:91](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/gestures_layout.py:91) — unused attribute 'gesture_badge' (60% confidence).
- [eidos/ui/pages/gestures_layout.py:91](C:/Users/Элдос/Desktop/Eidos/eidos/ui/pages/gestures_layout.py:91) — unused attribute 'metrics_badge' (60% confidence).
- [JARVIS-main/actions/browser_control.py:42](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/browser_control.py:42) — unused function '_user_agent' (60% confidence).
- [JARVIS-main/actions/browser_control.py:930](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/browser_control.py:930) — unused method 'close_browser' (60% confidence).
- [JARVIS-main/actions/code_helper.py:518](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/code_helper.py:518) — unused variable 'image_base64' (60% confidence).
- [JARVIS-main/actions/computer_control.py:21](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_control.py:21) — unused attribute 'FAILSAFE' (60% confidence).
- [JARVIS-main/actions/computer_control.py:22](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_control.py:22) — unused attribute 'PAUSE' (60% confidence).
- [JARVIS-main/actions/computer_settings.py:13](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_settings.py:13) — unused attribute 'FAILSAFE' (60% confidence).
- [JARVIS-main/actions/computer_settings.py:14](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_settings.py:14) — unused attribute 'PAUSE' (60% confidence).
- [JARVIS-main/actions/computer_settings.py:226](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/computer_settings.py:226) — unused attribute 'volume_percent' (60% confidence).
- [JARVIS-main/actions/desktop.py:136](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/desktop.py:136) — unused import '_genai' (90% confidence).
- [JARVIS-main/actions/flight_finder.py:165](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/flight_finder.py:165) — unused import '_genai' (90% confidence).
- [JARVIS-main/actions/open_app.py:163](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/open_app.py:163) — unused attribute 'PAUSE' (60% confidence).
- [JARVIS-main/actions/send_message.py:10](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/send_message.py:10) — unused attribute 'FAILSAFE' (60% confidence).
- [JARVIS-main/actions/send_message.py:11](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/send_message.py:11) — unused attribute 'PAUSE' (60% confidence).
- [JARVIS-main/actions/web_search.py:216](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/actions/web_search.py:216) — unused function '_gemini_headlines' (60% confidence).
- [JARVIS-main/core/audio_devices.py:35](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/audio_devices.py:35) — unused variable 'DEFAULT_VALUE' (60% confidence).
- [JARVIS-main/core/avatar.py:204](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/avatar.py:204) — unused attribute '_v_wide' (60% confidence).
- [JARVIS-main/core/echo.py:129](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/echo.py:129) — unused attribute '_last_expected' (60% confidence).
- [JARVIS-main/core/echo.py:137](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/echo.py:137) — unused property 'gain' (60% confidence).
- [JARVIS-main/core/echo.py:141](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/echo.py:141) — unused property 'calibrated' (60% confidence).
- [JARVIS-main/core/echo.py:166](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/echo.py:166) — unused property 'required_blocks' (60% confidence).
- [JARVIS-main/core/echo.py:171](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/echo.py:171) — unused property 'last_similarity' (60% confidence).
- [JARVIS-main/core/hotkey.py:140](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/hotkey.py:140) — unused method 'set_held' (60% confidence).
- [JARVIS-main/core/installer.py:95](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/installer.py:95) — unused function 'install_for_config' (60% confidence).
- [JARVIS-main/core/llm_client.py:133](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:133) — unused function 'warmup_model' (60% confidence).
- [JARVIS-main/core/llm_client.py:197](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:197) — unused function 'check_model_available' (60% confidence).
- [JARVIS-main/core/llm_client.py:239](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:239) — unused function 'call_llm' (60% confidence).
- [JARVIS-main/core/llm_client.py:341](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:341) — unused function 'call_llm_text' (60% confidence).
- [JARVIS-main/core/llm_client.py:518](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/llm_client.py:518) — unused function 'call_llm_stream' (60% confidence).
- [JARVIS-main/core/stt.py:108](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/stt.py:108) — unused method 'process_chunk' (60% confidence).
- [JARVIS-main/core/tts.py:422](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/tts.py:422) — unused property 'is_playing' (60% confidence).
- [JARVIS-main/core/tts.py:458](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/tts.py:458) — unused function 'create_tts_player' (60% confidence).
- [JARVIS-main/core/undo.py:79](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/undo.py:79) — unused function 'can_undo' (60% confidence).
- [JARVIS-main/core/wake_word.py:33](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/core/wake_word.py:33) — unused variable 'SAMPLE_RATE' (60% confidence).
- [JARVIS-main/dashboard/server.py:64](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:64) — unused function '_get_gemini_key' (60% confidence).
- [JARVIS-main/dashboard/server.py:592](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:592) — unused method 'set_wake_callback' (60% confidence).
- [JARVIS-main/dashboard/server.py:622](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:622) — unused function 'serve_crypto' (60% confidence).
- [JARVIS-main/dashboard/server.py:632](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:632) — unused function 'login_page' (60% confidence).
- [JARVIS-main/dashboard/server.py:670](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:670) — unused function 'auto_login' (60% confidence).
- [JARVIS-main/dashboard/server.py:726](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:726) — unused function 'device_login_ep' (60% confidence).
- [JARVIS-main/dashboard/server.py:750](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:750) — unused function 'revoke_devices' (60% confidence).
- [JARVIS-main/dashboard/server.py:778](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:778) — unused function 'wake_ep' (60% confidence).
- [JARVIS-main/dashboard/server.py:788](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:788) — unused function 'phone_audio_ws' (60% confidence).
- [JARVIS-main/dashboard/server.py:823](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:823) — unused function 'upload_file' (60% confidence).
- [JARVIS-main/dashboard/server.py:876](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:876) — unused function 'upload_unavailable' (60% confidence).
- [JARVIS-main/dashboard/server.py:899](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:899) — unused function 'download_file' (60% confidence).
- [JARVIS-main/dashboard/server.py:911](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/dashboard/server.py:911) — unused function 'ws_ep' (60% confidence).
- [JARVIS-main/main.py:724](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:724) — unused attribute 'on_wake_install' (60% confidence).
- [JARVIS-main/main.py:1174](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:1174) — unused attribute 'end_of_speech_sensitivity' (60% confidence).
- [JARVIS-main/main.py:1178](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:1178) — unused attribute 'end_of_speech_sensitivity' (60% confidence).
- [JARVIS-main/main.py:1182](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:1182) — unused attribute 'start_of_speech_sensitivity' (60% confidence).
- [JARVIS-main/main.py:1186](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:1186) — unused attribute 'start_of_speech_sensitivity' (60% confidence).
- [JARVIS-main/main.py:1442](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/main.py:1442) — unused variable 'time_info' (100% confidence).
- [JARVIS-main/memory/config_manager.py:21](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:21) — unused function 'config_exists' (60% confidence).
- [JARVIS-main/memory/config_manager.py:25](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:25) — unused function 'save_api_keys' (60% confidence).
- [JARVIS-main/memory/config_manager.py:54](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:54) — unused function 'is_configured' (60% confidence).
- [JARVIS-main/memory/config_manager.py:64](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:64) — unused function 'get_user_name' (60% confidence).
- [JARVIS-main/memory/config_manager.py:69](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:69) — unused function 'save_assistant_config' (60% confidence).
- [JARVIS-main/memory/config_manager.py:174](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:174) — unused function 'save_thinking_enabled' (60% confidence).
- [JARVIS-main/memory/config_manager.py:212](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:212) — unused function 'save_turn_tuning' (60% confidence).
- [JARVIS-main/memory/config_manager.py:240](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:240) — unused function 'save_proactive_audio_enabled' (60% confidence).
- [JARVIS-main/memory/config_manager.py:256](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/config_manager.py:256) — unused function 'save_media_resolution' (60% confidence).
- [JARVIS-main/memory/memory_manager.py:463](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/memory/memory_manager.py:463) — unused variable 'forget_memory' (60% confidence).
- [JARVIS-main/plugins/_live_panels_core.py:2113](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:2113) — unused function 'show_system' (60% confidence).
- [JARVIS-main/plugins/_live_panels_core.py:2118](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:2118) — unused function 'system_status' (60% confidence).
- [JARVIS-main/plugins/_live_panels_core.py:2124](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:2124) — unused function 'close_system' (60% confidence).
- [JARVIS-main/plugins/_live_panels_core.py:2130](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/_live_panels_core.py:2130) — unused function 'show_weather' (60% confidence).
- [JARVIS-main/plugins/excel_writer.py:128](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/excel_writer.py:128) — unused attribute 'alignment' (60% confidence).
- [JARVIS-main/plugins/game_updater.py:535](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/game_updater.py:535) — unused variable 'SF_UNINSTALLED' (60% confidence).
- [JARVIS-main/plugins/game_updater.py:539](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/plugins/game_updater.py:539) — unused variable 'SF_RUNNING' (60% confidence).
- [JARVIS-main/ui.py:202](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:202) — unused variable 'BORDER_A' (60% confidence).
- [JARVIS-main/ui.py:217](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:217) — unused variable 'BAR_BG' (60% confidence).
- [JARVIS-main/ui.py:451](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:451) — unused attribute '_ss_src' (60% confidence).
- [JARVIS-main/ui.py:497](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:497) — unused attribute '_ss_src' (60% confidence).
- [JARVIS-main/ui.py:2038](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2038) — unused method 'hasHeightForWidth' (60% confidence).
- [JARVIS-main/ui.py:2041](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2041) — unused method 'heightForWidth' (60% confidence).
- [JARVIS-main/ui.py:2270](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2270) — unused class 'MetricBar' (60% confidence).
- [JARVIS-main/ui.py:2655](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2655) — unused method 'dragEnterEvent' (60% confidence).
- [JARVIS-main/ui.py:2661](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2661) — unused method 'dragLeaveEvent' (60% confidence).
- [JARVIS-main/ui.py:2665](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:2665) — unused method 'dropEvent' (60% confidence).
- [JARVIS-main/ui.py:4497](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:4497) — unused attribute '_auto_login_url' (60% confidence).
- [JARVIS-main/ui.py:4703](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:4703) — unused attribute '_auto_login_url' (60% confidence).
- [JARVIS-main/ui.py:5277](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:5277) — unused attribute '_face_path' (60% confidence).
- [JARVIS-main/ui.py:6944](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:6944) — unused attribute 'Arguments' (60% confidence).
- [JARVIS-main/ui.py:6945](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:6945) — unused attribute 'WorkingDirectory' (60% confidence).
- [JARVIS-main/ui.py:6946](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:6946) — unused attribute 'Description' (60% confidence).
- [JARVIS-main/ui.py:6947](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:6947) — unused attribute 'IconLocation' (60% confidence).
- [JARVIS-main/ui.py:7561](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:7561) — unused attribute '_bar_tmp' (60% confidence).
- [JARVIS-main/ui.py:7816](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:7816) — unused attribute '_BTN_DIM' (60% confidence).
- [JARVIS-main/ui.py:7816](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:7816) — unused attribute '_BTN_PRI' (60% confidence).
- [JARVIS-main/ui.py:8037](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:8037) — unused attribute '_settings_autostart_switch' (60% confidence).
- [JARVIS-main/ui.py:8044](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:8044) — unused attribute '_settings_brief_switch' (60% confidence).
- [JARVIS-main/ui.py:8171](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:8171) — unused method '_place_drawer' (60% confidence).
- [JARVIS-main/ui.py:9315](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9315) — unused method '_set_theme' (60% confidence).
- [JARVIS-main/ui.py:9319](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9319) — unused method '_cycle_theme' (60% confidence).
- [JARVIS-main/ui.py:9394](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9394) — unused attribute '_audio_overlay' (60% confidence).
- [JARVIS-main/ui.py:9406](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9406) — unused attribute '_memory_overlay' (60% confidence).
- [JARVIS-main/ui.py:9456](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9456) — unused attribute '_plugin_manager_overlay' (60% confidence).
- [JARVIS-main/ui.py:9472](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9472) — unused attribute '_plugin_settings_overlay' (60% confidence).
- [JARVIS-main/ui.py:9644](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9644) — unused method 'protocol' (60% confidence).
- [JARVIS-main/ui.py:9854](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9854) — unused method 'show_camera_frame' (60% confidence).
- [JARVIS-main/ui.py:9904](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9904) — unused method 'add_task' (60% confidence).
- [JARVIS-main/ui.py:9909](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9909) — unused method 'get_tasks' (60% confidence).
- [JARVIS-main/ui.py:9929](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9929) — unused method 'start_speaking' (60% confidence).
- [JARVIS-main/ui.py:9932](C:/Users/Элдос/Desktop/Eidos/JARVIS-main/ui.py:9932) — unused method 'stop_speaking' (60% confidence).
- [scripts/benchmark_local_response.py:43](C:/Users/Элдос/Desktop/Eidos/scripts/benchmark_local_response.py:43) — unused import 'providers' (90% confidence).
- [scripts/check_hotkeys_native.py:27](C:/Users/Элдос/Desktop/Eidos/scripts/check_hotkeys_native.py:27) — unused attribute 'argtypes' (60% confidence).
- [scripts/check_hotkeys_native.py:28](C:/Users/Элдос/Desktop/Eidos/scripts/check_hotkeys_native.py:28) — unused attribute 'restype' (60% confidence).
- [scripts/check_translation_native.py:10](C:/Users/Элдос/Desktop/Eidos/scripts/check_translation_native.py:10) — unused attribute 'excepthook' (60% confidence).
- [scripts/verify_voice_native.py:14](C:/Users/Элдос/Desktop/Eidos/scripts/verify_voice_native.py:14) — unused import 'QCoreApplication' (90% confidence).
- [tests/conftest.py:5](C:/Users/Элдос/Desktop/Eidos/tests/conftest.py:5) — unused function 'no_live_desktop_operations' (60% confidence).
- [tests/conftest.py:15](C:/Users/Элдос/Desktop/Eidos/tests/conftest.py:15) — unused function 'no_native_credentials' (60% confidence).
- [tests/conftest.py:20](C:/Users/Элдос/Desktop/Eidos/tests/conftest.py:20) — unused function 'no_live_tts' (60% confidence).
- [tests/test_desktop_adapters.py:39](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_adapters.py:39) — unused variable 'unused' (100% confidence).
- [tests/test_desktop_adapters.py:41](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_adapters.py:41) — unused variable 'unused' (100% confidence).
- [tests/test_ollama_transport.py:21](C:/Users/Элдос/Desktop/Eidos/tests/test_ollama_transport.py:21) — unused method 'do_POST' (60% confidence).
- [tests/test_ollama_transport.py:37](C:/Users/Элдос/Desktop/Eidos/tests/test_ollama_transport.py:37) — unused method 'log_message' (60% confidence).
- [tests/test_voice_upgrade.py:14](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:14) — unused function 'isolated_credentials' (60% confidence).

## Фикстуры pytest: предупреждения, которые не надо автоматически исправлять

Импортированные фикстуры app/window/и другие регистрируются pytest и запрашиваются параметрами тестов. F401/F811 здесь сами по себе не означают лишний код.

- [tests/test_agent_ui.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:10) — F401: `test_ui.app` imported but unused.
- [tests/test_agent_ui.py:13](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:13) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_agent_ui.py:33](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:33) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_agent_ui.py:51](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:51) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_agent_ui.py:69](C:/Users/Элдос/Desktop/Eidos/tests/test_agent_ui.py:69) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_background_integration.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:5) — F401: `test_ui.app` imported but unused.
- [tests/test_background_integration.py:18](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:18) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:35](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:35) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:67](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:67) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:97](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:97) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:112](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:112) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:125](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:125) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_background_integration.py:145](C:/Users/Элдос/Desktop/Eidos/tests/test_background_integration.py:145) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_continuous_voice.py:1](C:/Users/Элдос/Desktop/Eidos/tests/test_continuous_voice.py:1) — F401: `test_ui.app` imported but unused.
- [tests/test_continuous_voice.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_continuous_voice.py:5) — F811: Redefinition of unused `app` from line 1: `app` redefined here.
- [tests/test_desktop_ui.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_ui.py:7) — F401: `test_ui.app` imported but unused.
- [tests/test_desktop_ui.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_ui.py:10) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_desktop_ui.py:32](C:/Users/Элдос/Desktop/Eidos/tests/test_desktop_ui.py:32) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_gemini_ui.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_gemini_ui.py:5) — F401: `test_ui.app` imported but unused.
- [tests/test_gemini_ui.py:8](C:/Users/Элдос/Desktop/Eidos/tests/test_gemini_ui.py:8) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_gemini_ui.py:37](C:/Users/Элдос/Desktop/Eidos/tests/test_gemini_ui.py:37) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_gesture_runtime.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:5) — F401: `test_ui.app` imported but unused.
- [tests/test_gesture_runtime.py:88](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:88) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_gesture_runtime.py:126](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_runtime.py:126) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_gesture_ui.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:7) — F401: `test_ui.app` imported but unused.
- [tests/test_gesture_ui.py:11](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:11) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_gesture_ui.py:34](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:34) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_gesture_ui.py:59](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:59) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_gesture_ui.py:85](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:85) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_gesture_ui.py:96](C:/Users/Элдос/Desktop/Eidos/tests/test_gesture_ui.py:96) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_home_refresh.py:11](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:11) — F401: `test_ui.app` imported but unused.
- [tests/test_home_refresh.py:15](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:15) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:26](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:26) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:43](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:43) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:79](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:79) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:90](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:90) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:124](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:124) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_home_refresh.py:160](C:/Users/Элдос/Desktop/Eidos/tests/test_home_refresh.py:160) — F811: Redefinition of unused `app` from line 11: `app` redefined here.
- [tests/test_hotkeys.py:12](C:/Users/Элдос/Desktop/Eidos/tests/test_hotkeys.py:12) — F401: `test_ui.app` imported but unused.
- [tests/test_hotkeys.py:58](C:/Users/Элдос/Desktop/Eidos/tests/test_hotkeys.py:58) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_hotkeys.py:77](C:/Users/Элдос/Desktop/Eidos/tests/test_hotkeys.py:77) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_hotkeys.py:99](C:/Users/Элдос/Desktop/Eidos/tests/test_hotkeys.py:99) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_hotkeys.py:127](C:/Users/Элдос/Desktop/Eidos/tests/test_hotkeys.py:127) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_jonsnow_integration.py:13](C:/Users/Элдос/Desktop/Eidos/tests/test_jonsnow_integration.py:13) — F401: `test_ui.app` imported but unused.
- [tests/test_jonsnow_integration.py:16](C:/Users/Элдос/Desktop/Eidos/tests/test_jonsnow_integration.py:16) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_jonsnow_integration.py:85](C:/Users/Элдос/Desktop/Eidos/tests/test_jonsnow_integration.py:85) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_latched_voice.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_latched_voice.py:10) — F401: `test_ui.app` imported but unused.
- [tests/test_latched_voice.py:19](C:/Users/Элдос/Desktop/Eidos/tests/test_latched_voice.py:19) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_latched_voice.py:28](C:/Users/Элдос/Desktop/Eidos/tests/test_latched_voice.py:28) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_latched_voice.py:59](C:/Users/Элдос/Desktop/Eidos/tests/test_latched_voice.py:59) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_minimal_camera_ui.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_camera_ui.py:7) — F401: `test_ui.app` imported but unused.
- [tests/test_minimal_camera_ui.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_camera_ui.py:10) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_minimal_camera_ui.py:26](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_camera_ui.py:26) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_minimal_camera_ui.py:42](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_camera_ui.py:42) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_minimal_screen_capture.py:12](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:12) — F401: `test_ui.app` imported but unused.
- [tests/test_minimal_screen_capture.py:15](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:15) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_minimal_screen_capture.py:31](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:31) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_minimal_screen_capture.py:48](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:48) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_minimal_screen_capture.py:68](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:68) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_minimal_screen_capture.py:95](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_screen_capture.py:95) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_minimal_voice.py:6](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:6) — F401: `test_ui.app` imported but unused.
- [tests/test_minimal_voice.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:7) — F401: `test_home_refresh.window` imported but unused.
- [tests/test_minimal_voice.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:10) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:10) — F811: Redefinition of unused `app` from line 6: `app` redefined here.
- [tests/test_minimal_voice.py:27](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:27) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:27](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:27) — F811: Redefinition of unused `app` from line 6: `app` redefined here.
- [tests/test_minimal_voice.py:49](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:49) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:73](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:73) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:81](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:81) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:81](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:81) — F811: Redefinition of unused `app` from line 6: `app` redefined here.
- [tests/test_minimal_voice.py:97](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:97) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_minimal_voice.py:140](C:/Users/Элдос/Desktop/Eidos/tests/test_minimal_voice.py:140) — F811: Redefinition of unused `window` from line 7: `window` redefined here.
- [tests/test_modernization_i18n.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_i18n.py:7) — F401: `test_ui.app` imported but unused.
- [tests/test_modernization_i18n.py:29](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_i18n.py:29) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_modernization_i18n.py:56](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_i18n.py:56) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_modernization_startup.py:14](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_startup.py:14) — F811: Redefinition of unused `app` from line 35: `app` redefined here.
- [tests/test_modernization_startup.py:35](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_startup.py:35) — F401: `test_ui.app` imported but unused.
- [tests/test_modernization_streaming.py:11](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_streaming.py:11) — F811: Redefinition of unused `app` from line 50: `app` redefined here.
- [tests/test_modernization_streaming.py:50](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_streaming.py:50) — F401: `test_ui.app` imported but unused.
- [tests/test_modernization_ui.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_ui.py:5) — F401: `test_ui.app` imported but unused.
- [tests/test_modernization_ui.py:8](C:/Users/Элдос/Desktop/Eidos/tests/test_modernization_ui.py:8) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_persistent_audio_stream.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_persistent_audio_stream.py:10) — F401: `test_ui.app` imported but unused.
- [tests/test_persistent_audio_stream.py:66](C:/Users/Элдос/Desktop/Eidos/tests/test_persistent_audio_stream.py:66) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:10) — F401: `test_ui.app` imported but unused.
- [tests/test_redesign.py:13](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:13) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:28](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:28) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:48](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:48) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:81](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:81) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:106](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:106) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_redesign.py:126](C:/Users/Элдос/Desktop/Eidos/tests/test_redesign.py:126) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_settings_layout.py:4](C:/Users/Элдос/Desktop/Eidos/tests/test_settings_layout.py:4) — F401: `test_ui.app` imported but unused.
- [tests/test_settings_layout.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_settings_layout.py:7) — F811: Redefinition of unused `app` from line 4: `app` redefined here.
- [tests/test_translation.py:10](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:10) — F401: `test_ui.app` imported but unused.
- [tests/test_translation.py:13](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:13) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:34](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:34) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:53](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:53) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:81](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:81) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:107](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:107) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:125](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:125) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:140](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:140) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:157](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:157) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:170](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:170) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:200](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:200) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:230](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:230) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:240](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:240) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation.py:253](C:/Users/Элдос/Desktop/Eidos/tests/test_translation.py:253) — F811: Redefinition of unused `app` from line 10: `app` redefined here.
- [tests/test_translation_features.py:13](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:13) — F401: `test_ui.app` imported but unused.
- [tests/test_translation_features.py:22](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:22) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_translation_features.py:41](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:41) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_translation_features.py:54](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:54) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_translation_features.py:78](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:78) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_translation_features.py:91](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:91) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_translation_features.py:114](C:/Users/Элдос/Desktop/Eidos/tests/test_translation_features.py:114) — F811: Redefinition of unused `app` from line 13: `app` redefined here.
- [tests/test_voice_harness.py:6](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_harness.py:6) — F401: `test_ui.app` imported but unused.
- [tests/test_voice_harness.py:9](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_harness.py:9) — F811: Redefinition of unused `app` from line 6: `app` redefined here.
- [tests/test_voice_indicator.py:12](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:12) — F401: `test_ui.app` imported but unused.
- [tests/test_voice_indicator.py:49](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:49) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:63](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:63) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:86](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:86) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:106](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:106) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:123](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:123) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:147](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:147) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_indicator.py:172](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_indicator.py:172) — F811: Redefinition of unused `app` from line 12: `app` redefined here.
- [tests/test_voice_settings_regressions.py:6](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_settings_regressions.py:6) — F401: `test_ui.app` imported but unused.
- [tests/test_voice_settings_regressions.py:18](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_settings_regressions.py:18) — F811: Redefinition of unused `app` from line 6: `app` redefined here.
- [tests/test_voice_upgrade.py:9](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:9) — F401: `test_ui.app` imported but unused.
- [tests/test_voice_upgrade.py:20](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:20) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:106](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:106) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:123](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:123) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:142](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:142) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:157](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:157) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:225](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:225) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:247](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:247) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:271](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:271) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:292](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:292) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:315](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:315) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:357](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:357) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:375](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:375) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:391](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:391) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:414](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:414) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_voice_upgrade.py:433](C:/Users/Элдос/Desktop/Eidos/tests/test_voice_upgrade.py:433) — F811: Redefinition of unused `app` from line 9: `app` redefined here.
- [tests/test_wave_hover.py:5](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:5) — F401: `test_ui.app` imported but unused.
- [tests/test_wave_hover.py:6](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:6) — F401: `test_home_refresh.window` imported but unused.
- [tests/test_wave_hover.py:9](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:9) — F811: Redefinition of unused `window` from line 6: `window` redefined here.
- [tests/test_wave_hover.py:9](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:9) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_wave_hover.py:36](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:36) — F811: Redefinition of unused `window` from line 6: `window` redefined here.
- [tests/test_wave_hover.py:36](C:/Users/Элдос/Desktop/Eidos/tests/test_wave_hover.py:36) — F811: Redefinition of unused `app` from line 5: `app` redefined here.
- [tests/test_workspace.py:7](C:/Users/Элдос/Desktop/Eidos/tests/test_workspace.py:7) — F401: `test_ui.app` imported but unused.
- [tests/test_workspace.py:11](C:/Users/Элдос/Desktop/Eidos/tests/test_workspace.py:11) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_workspace.py:85](C:/Users/Элдос/Desktop/Eidos/tests/test_workspace.py:85) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_workspace.py:101](C:/Users/Элдос/Desktop/Eidos/tests/test_workspace.py:101) — F811: Redefinition of unused `app` from line 7: `app` redefined here.
- [tests/test_workspace.py:145](C:/Users/Элдос/Desktop/Eidos/tests/test_workspace.py:145) — F811: Redefinition of unused `app` from line 7: `app` redefined here.

## Что можно очистить после подтверждения

- Высокая уверенность: обычные неиспользуемые импорты без побочных эффектов; локальные имена window в background.voice_action и muted/recording/waking в main_window; неиспользуемые константы SPEECH_THRESHOLD, PRE_ROLL_SECONDS, FRAME_SAMPLES.
- Хорошие кандидаты после проверки внешних пользователей: ui/pages/activation.py, modules/calendar/interface.py, modules/vision/interface.py; классы ScreenTranslator и DisconnectedOCR в используемом modules/ocr/interface.py; метод AssistantBindings._restore_history и запись _capture_visible.
- resampler в local_input._capture и переменные с вычисляемой правой частью требуют сохранения значимых вызовов; не удалять функцию LinearResampler только на основании одного предупреждения.
- Стили — только после проверки экранов во всех темах и состояниях; callbacks, фикстуры, Protocol, no-op переопределения и плагины автоматически не удалять.
- TODO/FIXME как незавершённых задач не найдено; единственное совпадение находится в промпте.

Полнота ограничена статическим анализом. Недостижимость при всех возможных запусках Python/Qt/плагинов автоматически доказать нельзя.
