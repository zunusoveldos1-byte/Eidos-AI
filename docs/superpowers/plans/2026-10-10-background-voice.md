# Background voice implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or executing-plans, task by task.

**Goal:** Implement the approved background voice, speech queue, mascot and translation integration.
**Architecture:** Existing QThreads and harness remain; one speech queue and explicit application lifetime coordinate independent UI surfaces. Optional wake detector owns microphone only while voice and speech are idle.
**Tech Stack:** Python 3.11, PyQt6, sounddevice, Edge TTS, optional Porcupine, Windows SAPI.
**Spec:** ../specs/2026-10-10-background-voice-design.md

## Global constraints
- Preserve existing agent, memory, calendar, translation and voice functions.
- No secret in JSON/repository; no model download or microphone use on default startup.
- Native RegisterHotKey; Ctrl+Alt+V default voice shortcut.
- Hidden visual animations stop; no fabricated microphone level or lip sync.
- Close-to-tray opt-in; explicit exit waits for all workers.

## Review focus
- Exit with pending synthesis must discard late audio and free threads.
- Hotkey conflict must preserve previous registrations across voice and translation.
- Removed monitor must not leave floating widget inaccessible.
- Paused/failed wake engine must not resume after user pause.
- Capture cancellation must restore prior floating-widget visibility.

### 1. Speech and optional listening engines
Files: voice/speech.py, speech_text.py, wake.py, recorder.py, tts.py; tests/test_background_voice.py.
Interfaces: SpeechQueue(parent, playback), enqueue(text, config), stop(), shutdown(), active/is_running, state_changed(str,str), closed; Recorder.level_callback and optional end-of-speech. WakeController activated(), level(float), status(str), stopped(); configure(config), pause(bool), set_busy(bool), shutdown().
- [x] Add failing tests for speech cleaning, queue cancellation and missing wake prerequisites.
- [x] Implement one synthesis worker, bounded sentence queue, shared playback, Edge settings and SAPI provider.
- [x] Implement local Porcupine detection, exclusive microphone handoff, silence end and RMS.
- [x] Run targeted tests.

### 2. Mascot and floating surface
Files: ui/mascot.py, ui/floating.py; tests/test_floating.py.
Interfaces: Mascot.set_state/state, set_level(float), set_animations(bool); FloatingMascot signals start_requested, stop_requested, pause_requested, open_requested, position_changed; set_status(state,message), set_level(value), restore_position(x,y), position config.
- [x] Test added states, hidden animations and monitor bounds.
- [x] Implement seven visible states and draggable widget with explicit voice/stop/pause/open controls.
- [x] Run targeted tests.

### 3. Application integration and settings
Files: core/config.py, shortcuts.py, ui/hotkeys.py, background.py, main_window.py, pages/settings.py, assistant_bindings.py, __main__.py.
- [x] Test tray close versus exit, speech exclusivity, settings migration, voice shortcut conflicts.
- [x] Integrate queue, tray, optional detector, widget and real levels into current controllers.
- [x] Expose all settings with validation and external secret storage; ensure shutdown waits.
- [x] Run old and new UI/lifecycle tests.

### 4. Translation adapter and verification
Files: modules/ocr/interface.py, ui/screen_translation.py, pages/translation.py; tests/test_translation_adapter.py; docs/background-voice.md.
- [x] Test real adapter delegation, cancel, provider choice, reset and overlay visibility.
- [x] Delegate to JonSnow OCR/translation, expose provider and speak-result; hide floating overlay during capture.
- [x] Run full tests, native smoke, compileall, pip check and controlled screenshots.
- [x] Independent final review; document actual hardware/credential limitations.

User explicitly authorized stage execution without repeated technical approvals. Preserve all local user data; no automatic publish is requested in this task.
