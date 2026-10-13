from dataclasses import replace
from types import SimpleNamespace
from PyQt6.QtGui import QKeySequence, QImage
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.hotkeys import GestureEmergencyHotkey
from test_ui import app, wait_until
from test_hotkeys import Registry


def test_gesture_preferences_save_and_permission_is_not_persisted(app, tmp_path):
    w = MainWindow(ConfigStore(tmp_path / "config.json"))
    try:
        p = w.gestures
        p.hand.setCurrentIndex(1)
        p.smoothing.setValue(0.45)
        p.emergency_key.setKeySequence(QKeySequence("Ctrl+Shift+F9"))
        p.save_preferences()
        saved = w.store.load()
        assert saved.gesture_hand == "Left" and saved.gesture_smoothing == 0.45
        assert saved.gesture_emergency_hotkey == "Ctrl+Shift+F9"
        assert not p.control.isChecked()
        assert not any(
            "enabled" in k
            for k in saved.__dataclass_fields__
            if k.startswith("gesture_")
        )
        assert p.service.gate.snapshot()[1] is False
    finally:
        w.request_exit()
        wait_until(app, lambda: not w.controller.thread.isRunning())


def test_emergency_key_is_global_and_not_suspended_while_editing(app):
    from PyQt6.QtWidgets import QWidget, QKeySequenceEdit

    owner = QWidget()
    backend = Registry()
    backend.native = True
    manager = GestureEmergencyHotkey(owner, backend)
    try:
        assert manager.configure(AppConfig()) and manager.available
        manager._focus_changed(None, QKeySequenceEdit(owner))
        assert manager.available and len(backend.active) == 1
        called = []
        manager.activated.connect(called.append)
        assert manager.trigger(next(iter(manager.actions)))
        wait_until(app, lambda: called == ["gesture_stop"])
        backend.blocked.add("Ctrl+Shift+F9")
        assert not manager.configure(
            replace(AppConfig(), gesture_emergency_hotkey="Ctrl+Shift+F9")
        )
        assert len(backend.active) == 1
    finally:
        manager.shutdown()
        owner.close()


def test_ui_control_requires_detection_and_emergency_key(app, tmp_path):
    w = MainWindow(ConfigStore(tmp_path / "config.json"))
    try:
        p = w.gestures
        p._active = True
        p.service.recognition_ready = True
        # Offscreen uses local shortcuts and must never grant system control.
        p._refresh_control()
        assert not p.control.isEnabled()
        p.control.setChecked(True)
        assert not p.control.isChecked() and not p.service.gate.snapshot()[1]
        p.hotkey = SimpleNamespace(available=True)
        p._refresh_control()
        assert p.control.isEnabled()
        p.control.setChecked(True)
        assert p.service.gate.snapshot()[1]
        p.emergency_stop()
        assert not p.service.gate.snapshot()[1]
        p.control.setChecked(True)
        p.mode.setCurrentIndex(1)
        assert not p.control.isChecked() and not p.service.gate.snapshot()[1]
    finally:
        w.request_exit()
        wait_until(app, lambda: not w.controller.thread.isRunning())


def test_queued_discovery_cannot_restart_after_application_close(app, tmp_path):
    from PyQt6.QtCore import QTimer

    w = MainWindow(ConfigStore(tmp_path / "config.json"))
    QTimer.singleShot(0, w.gestures.refresh_devices)
    w.request_exit()
    wait_until(app, lambda: w._allow_close, timeout=5)
    assert not w.gestures.is_running


def test_calibration_stays_pending_when_preferences_cannot_be_saved(
    app, tmp_path, monkeypatch
):
    import time
    from test_gestures import hand

    w = MainWindow(ConfigStore(tmp_path / "config.json"))
    try:
        p = w.gestures
        p._calibration_step = 3
        p._calibration_values = {"gesture_pinch_min": 0.2, "gesture_pinch_max": 1.1}
        p.latest = SimpleNamespace(hand=hand("cursor"), timestamp=time.perf_counter())

        def fail(*a):
            raise OSError("denied")

        monkeypatch.setattr(w.store, "save", fail)
        p.calibration_next()
        assert p._calibration_step == 3
        assert "завершена" not in p.calibration_text.text()
        assert w.config.gesture_pinch_min == 0.15
    finally:
        w.request_exit()
        wait_until(app, lambda: not w.controller.thread.isRunning())
