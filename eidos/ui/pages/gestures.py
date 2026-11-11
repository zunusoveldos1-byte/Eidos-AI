"""Local camera/gesture workspace with transient control permission."""

from dataclasses import replace
from PyQt6.QtCore import Qt, pyqtSignal, QSignalBlocker, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QImage, QKeySequence, QColor
from PyQt6.QtWidgets import QFormLayout, QKeySequenceEdit
from eidos.ui.localized import QWidget, QCheckBox, QDoubleSpinBox, QSpinBox, QGroupBox
from ..components import Card, Page, ResponsiveRow, Toggle, button, combo, label
from eidos.core.config import AppConfig, data_dir
from eidos.core.i18n import tr
from eidos.modules.vision.logic import GestureSettings, pinch_ratio
from eidos.modules.vision.actions import monitors
from eidos.modules.vision.service import CameraGestureService


class CameraPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.setMinimumHeight(240)
        self.setMaximumHeight(420)
        self.setAccessibleName("Локальное видео камеры с точками руки")

    def set_image(self, image):
        self.image = image
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.setClipPath(clip)
        painter.fillRect(self.rect(), QColor('#0F1714'))
        if not self.image.isNull():
            size = self.image.size()
            size.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            from PyQt6.QtCore import QRect

            target = QRect(
                (self.width() - size.width()) // 2,
                (self.height() - size.height()) // 2,
                size.width(),
                size.height(),
            )
            painter.drawImage(target, self.image)
        else:
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, tr("Камера выключена")
            )

    def position_badges(self):
        for attribute in ('gesture_badge', 'metrics_badge'):
            badge = getattr(self, attribute, None)
            if badge:
                badge.adjustSize()
                badge.move(12 if attribute == 'gesture_badge' else max(12, self.width() - badge.width() - 12), 12)

    def resizeEvent(self, event):
        self.position_badges()
        if hasattr(self, 'toolbar'):
            self.toolbar.reflow(self.width())
            self.toolbar.adjustSize()
            self.toolbar.move(max(8, (self.width() - self.toolbar.width()) // 2),
                              max(8, self.height() - self.toolbar.height() - 20))
        super().resizeEvent(event)


def decimal(value, low, high, step=0.05):
    control = QDoubleSpinBox()
    control.setRange(low, high)
    control.setSingleStep(step)
    control.setValue(value)
    return control


class GesturesPage(Page):
    notice = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    preferences_changed = pyqtSignal(dict)
    stopped = pyqtSignal()

    def __init__(self, model_dir=None, service_factory=CameraGestureService):
        super().__init__(
            "Камера и жесты",
            "Локальное распознавание руки · управление компьютером включается отдельно",
        )
        self.config = AppConfig()
        self.hotkey = None
        self._devices = []
        self._active = False
        self._inventory_ready = False
        self._inventory_requested = False
        self._calibration_step = None
        self._calibration_min = None
        self._calibration_values = {}
        self.latest = None
        self.service = service_factory(
            model_dir or data_dir() / "models" / "vision", self
        )
        card = Card()
        card.heading("Камера и распознавание", "camera")
        self.camera_status = label("Камера выключена", "secondary")
        self.recognition_status = label(
            "Включите камеру. При первом запуске загрузится модель руки (~8 МБ).",
            "muted",
        )
        card.body.addWidget(self.camera_status)
        card.body.addWidget(self.recognition_status)
        self.preview = CameraPreview()
        card.body.addWidget(self.preview)
        self.camera = combo()
        self.camera.setAccessibleName("Камера OpenCV")
        self.camera_button = button("Включить камеру", "camera", True)
        self.refresh_button = button("Обновить устройства", "refresh")
        card.body.addWidget(
            ResponsiveRow(
                [self.camera, self.camera_button, self.refresh_button], threshold=650
            )
        )
        self.hand_status = label(
            "Покажите руку целиком · при плохом свете добавьте освещение", "secondary"
        )
        self.gesture_status = label("Жест: —", "secondary")
        self.metrics = label("FPS и задержка появятся после обработки кадров", "muted")
        for w in (self.hand_status, self.gesture_status, self.metrics):
            card.body.addWidget(w)
        self.body.addWidget(card)
        actions = Card()
        actions.heading("Управление", "settings")
        self.control = Toggle("Разрешить управление компьютером")
        self.control.setEnabled(False)
        self.mode = combo()
        for title, value in [
            ("Авто", "auto"),
            ("Громкость", "volume"),
            ("Медиа", "media"),
            ("Курсор", "cursor"),
        ]:
            self.mode.addItem(title, value)
        actions.body.addWidget(ResponsiveRow([self.control, self.mode]))
        self.action_status = label("Управление выключено", "secondary")
        self.volume_status = label("Системная громкость: —", "muted")
        self.hotkey_status = label("Проверяю аварийную клавишу…", "muted")
        self.emergency_button = button("Отключить управление", "stop")
        for w in (
            self.action_status,
            self.volume_status,
            self.hotkey_status,
            self.emergency_button,
        ):
            actions.body.addWidget(w)
        actions.body.addWidget(
            label(
                "Громкость: большой и указательный пальцы выпрямлены, остальные согнуты. Медиа: открытая ладонь. Курсор: только указательный палец выпрямлен. Клики не выполняются.",
                "muted",
            )
        )
        self.body.addWidget(actions)
        self.details_button = button('Параметры и калибровка', 'settings')
        self.details_button.setCheckable(True)
        self.body.addWidget(self.details_button)
        calibration = Card()
        calibration.heading("Калибровка", "settings")
        self.calibration_text = label(
            "Можно начать с заводских параметров. Калибровка проходит без системных действий.",
            "muted",
        )
        self.calibrate_button = button("Начать / повторить")
        self.calibrate_next = button("Подтвердить шаг")
        self.calibrate_next.setEnabled(False)
        self.calibrate_skip = button("Пропустить")
        self.calibrate_reset = button("Сбросить")
        calibration.body.addWidget(self.calibration_text)
        calibration.body.addWidget(
            ResponsiveRow(
                [
                    self.calibrate_button,
                    self.calibrate_next,
                    self.calibrate_skip,
                    self.calibrate_reset,
                ]
            )
        )
        self.body.addWidget(calibration)
        self.parameters = QGroupBox("Параметры камеры и жестов")
        form = QFormLayout(self.parameters)
        self.hand = combo()
        self.hand.addItem("Правая", "Right")
        self.hand.addItem("Левая", "Left")
        self.mirror = QCheckBox("Зеркальный предпросмотр и направление курсора")
        self.mirror.setChecked(True)
        self.overlay = QCheckBox("Показывать точки и соединения")
        self.overlay.setChecked(True)
        self.fps = QSpinBox()
        self.fps.setRange(5, 30)
        self.fps.setValue(15)
        self.resolution = combo()
        for title, size in [
            ("640 × 480", (640, 480)),
            ("320 × 240", (320, 240)),
            ("1280 × 720", (1280, 720)),
        ]:
            self.resolution.addItem(title, size)
        self.sensitivity = decimal(1, 0.5, 2)
        self.smoothing = decimal(0.3, 0.05, 1)
        self.pinch_min = decimal(0.15, 0.01, 2)
        self.pinch_max = decimal(1.5, 0.1, 4)
        self.volume_dead = decimal(2, 0.1, 10, 0.5)
        self.volume_interval = decimal(0.1, 0.05, 1)
        self.hold = decimal(0.5, 0.2, 2)
        self.cooldown = decimal(1.2, 0.5, 3)
        self.monitor = combo()
        self._monitors = []
        self.refresh_monitors()
        self.emergency_key = QKeySequenceEdit(QKeySequence("Ctrl+Alt+G"))
        for title, control in [
            ("Ведущая рука", self.hand),
            ("Отображение", self.mirror),
            ("Разметка", self.overlay),
            ("Анализ, кадров/с", self.fps),
            ("Разрешение", self.resolution),
            ("Чувствительность курсора", self.sensitivity),
            ("Сглаживание (больше — быстрее)", self.smoothing),
            ("Минимум расстояния / ладонь", self.pinch_min),
            ("Максимум расстояния / ладонь", self.pinch_max),
            ("Мёртвая зона громкости, %", self.volume_dead),
            ("Интервал громкости, с", self.volume_interval),
            ("Удержание ладони, с", self.hold),
            ("Защита повтора, с", self.cooldown),
            ("Монитор курсора (физические пиксели)", self.monitor),
            ("Аварийное отключение", self.emergency_key),
        ]:
            control.setAccessibleName(title)
            form.addRow(title, control)
        self.body.addWidget(self.parameters)
        calibration.hide()
        self.parameters.hide()
        self.details_button.toggled.connect(calibration.setVisible)
        self.details_button.toggled.connect(self.parameters.setVisible)
        self.save_button = button("Сохранить параметры", None, True)
        self.body.addWidget(self.save_button)
        from .assistant import FeedbackLabel
        self.feedback = FeedbackLabel()
        self.feedback.notification.connect(self.notice.emit)
        self.body.addWidget(self.feedback)
        self.body.addWidget(
            label(
                "Видео обрабатывается локально и не сохраняется. Параметры сохраняются по кнопке; разрешение управления после перезапуска всегда выключено. Для изменения параметров остановите камеру.",
                "muted",
            )
        )
        self.body.addStretch()
        self.camera_button.clicked.connect(self.toggle_camera)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.emergency_button.clicked.connect(self.emergency_stop)
        self.control.toggled.connect(self._control_changed)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.calibrate_button.clicked.connect(self.start_calibration)
        self.calibrate_next.clicked.connect(self.calibration_next)
        self.calibrate_skip.clicked.connect(self.skip_calibration)
        self.calibrate_reset.clicked.connect(self.reset_calibration)
        self.save_button.clicked.connect(self.save_preferences)
        self.service.status_changed.connect(self._camera_status)
        self.service.recognition_status.connect(self.recognition_status.setText)
        self.service.frame_ready.connect(self.preview.set_image)
        self.service.result_ready.connect(self._result)
        self.service.ready.connect(self._refresh_control)
        self.service.control_failed.connect(self._control_failed)
        self.service.stopped.connect(self._stopped)
        self.service.cameras_ready.connect(self._devices_ready)
        from .gestures_layout import rebuild
        rebuild(self)
        self.refresh_devices(initial=True)

    @property
    def is_running(self):
        return self.service.is_running

    def refresh_devices(self, checked=False, initial=False):
        if self.service.closed or self.service.is_running:
            return
        if not initial:
            self._inventory_requested = True
            self.camera_button.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.camera_status.setText("Проверяю устройства OpenCV…")
            self.service.discover()
            return
        self.camera.clear()
        self._devices = []
        try:
            from PyQt6.QtMultimedia import QMediaDevices

            self._devices = QMediaDevices.videoInputs()
            for index, device in enumerate(self._devices):
                self.camera.addItem(device.description(), bytes(device.id()).hex())
            if not self._devices:
                self.camera.addItem("Камера не найдена")
                self.camera_status.setText(
                    "Камера не найдена. Подключите устройство и обновите список."
                )
        except Exception as exc:
            self.camera_status.setText("Не удалось перечислить камеры: " + str(exc))
        self.camera_button.setEnabled(bool(self._devices))
        index = self.camera.findData(self.config.gesture_camera)
        if index >= 0:
            self.camera.setCurrentIndex(index)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._inventory_requested:
            QTimer.singleShot(0, self.refresh_devices)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_resize_preview'):
            self._resize_preview(self.details_button.isChecked())

    def _devices_ready(self, devices):
        self._devices = devices
        self._inventory_ready = True
        self.camera.clear()
        for device in devices:
            self.camera.addItem(
                f"{device.index}: {device.name}",
                device.path or f"MSMF:{device.index}:{device.name}",
            )
        if not devices:
            self.camera.addItem("Камера не найдена")
            self.camera_status.setText(
                "Камера не найдена. Подключите устройство и обновите список."
            )
        else:
            self.camera_status.setText("Камера выключена")
        self.camera_button.setEnabled(bool(devices))
        self.refresh_button.setEnabled(True)
        self.status_changed.emit(self.camera_status.source_text())
        index = self.camera.findData(self.config.gesture_camera)
        if index >= 0:
            self.camera.setCurrentIndex(index)

    def refresh_monitors(self):
        self.monitor.clear()
        try:
            self._monitors = monitors()
        except Exception:
            self._monitors = []
        for m in self._monitors:
            self.monitor.addItem(
                f"{m.name} · {m.width}×{m.height} · ({m.x}, {m.y})", m.name
            )
        if not self._monitors:
            self.monitor.addItem("Системный монитор недоступен")

    def bind_hotkey(self, hotkey):
        self.hotkey = hotkey
        hotkey.activated.connect(lambda action: self.emergency_stop())
        hotkey.status_changed.connect(self._hotkey_changed)
        self._hotkey_changed(hotkey.message)

    def _hotkey_changed(self, message):
        self.hotkey_status.setText(message)
        if not self.hotkey or not self.hotkey.available:
            self.emergency_stop()
        self._refresh_control()

    def load(self, config):
        self.config = config
        for control, value in [
            (self.hand, config.gesture_hand),
            (self.mode, config.gesture_mode),
            (self.camera, config.gesture_camera),
            (self.monitor, config.gesture_monitor),
            (self.resolution, (config.gesture_width, config.gesture_height)),
        ]:
            blocker = QSignalBlocker(control)
            index = control.findData(value)
            if index >= 0:
                control.setCurrentIndex(index)
            del blocker
        self.mirror.setChecked(config.gesture_mirror)
        self.overlay.setChecked(config.gesture_overlay)
        self.fps.setValue(config.gesture_fps)
        for name in (
            "sensitivity",
            "smoothing",
            "pinch_min",
            "pinch_max",
            "volume_dead",
            "volume_interval",
            "hold",
            "cooldown",
        ):
            getattr(self, name).setValue(getattr(config, "gesture_" + name))
        self.emergency_key.setKeySequence(QKeySequence(config.gesture_emergency_hotkey))

    def settings(self):
        selected = next(
            (m for m in self._monitors if m.name == self.monitor.currentData()), None
        )
        kwargs = dict(
            mode=self.mode.currentData(),
            hand=self.hand.currentData(),
            mirror=self.mirror.isChecked(),
            **{
                n: getattr(self, n).value()
                for n in (
                    "sensitivity",
                    "smoothing",
                    "pinch_min",
                    "pinch_max",
                    "volume_dead",
                    "volume_interval",
                    "hold",
                    "cooldown",
                )
            },
        )
        if selected:
            kwargs["monitor"] = selected
        return GestureSettings(**kwargs)

    def preference_values(self):
        width, height = self.resolution.currentData()
        values = dict(
            gesture_camera=self.camera.currentData() or "",
            gesture_hand=self.hand.currentData(),
            gesture_mode=self.mode.currentData(),
            gesture_mirror=self.mirror.isChecked(),
            gesture_overlay=self.overlay.isChecked(),
            gesture_width=width,
            gesture_height=height,
            gesture_fps=self.fps.value(),
            gesture_monitor=self.monitor.currentData() or "",
            gesture_emergency_hotkey=self.emergency_key.keySequence().toString(
                QKeySequence.SequenceFormat.PortableText
            ),
        )
        values.update(
            {
                "gesture_" + n: getattr(self, n).value()
                for n in (
                    "sensitivity",
                    "smoothing",
                    "pinch_min",
                    "pinch_max",
                    "volume_dead",
                    "volume_interval",
                    "hold",
                    "cooldown",
                )
            }
        )
        return values

    def save_preferences(self):
        try:
            replace(self.config, **self.preference_values()).validate()
        except ValueError as exc:
            self.feedback.setText(str(exc))
            return
        self.preferences_changed.emit(self.preference_values())

    def preferences_saved(self, success, message):
        self.feedback.setText(message)
        if success and self._calibration_step == 3:
            self.skip_calibration()
            self.calibration_text.setText(
                "Калибровка завершена. Управление можно включить отдельно."
            )

    def toggle_camera(self):
        if self._active or self.service.is_running:
            self.shutdown()
            return
        if not self._devices:
            return
        if not self._inventory_ready:
            self.refresh_devices()
            return
        try:
            replace(self.config, **self.preference_values()).validate()
        except ValueError as exc:
            self.feedback.setText(str(exc))
            return
        self.emergency_stop()
        self.latest = None
        self._active = True
        self.camera.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.parameters.setEnabled(False)
        self.save_button.setEnabled(False)
        self._camera_button_state(True)
        width, height = self.resolution.currentData()
        device = self._devices[self.camera.currentIndex()]
        self.service.start(
            device.index,
            width,
            height,
            self.fps.value(),
            self.settings(),
            self.overlay.isChecked(),
        )

    def _camera_status(self, text):
        self.camera_status.setText(text)
        self.preview.setToolTip(text)
        self.notice.emit(text)
        self.status_changed.emit(text)
        if "недоступен" in text and not self._active:
            self.refresh_button.setEnabled(True)
            self.camera_button.setEnabled(False)

    def _camera_button_state(self, active):
        from ..icons import icon
        self.camera_button.setText('')
        title = "Выключить камеру" if active else "Включить камеру"
        self.camera_button.setToolTip(title)
        self.camera_button.setAccessibleName(title)
        self.camera_button.setIcon(icon('stop' if active else 'camera', '#E2E8F0'))
        self.camera_button.setProperty('active', active)
        self.camera_button.style().unpolish(self.camera_button)
        self.camera_button.style().polish(self.camera_button)

    def _refresh_control(self):
        allowed = (
            self._active
            and self.service.recognition_ready
            and self.hotkey is not None
            and self.hotkey.available
        )
        self.control.setEnabled(allowed and self._calibration_step is None)

    def _control_changed(self, enabled):
        allowed = (
            enabled
            and self.hotkey is not None
            and self.hotkey.available
            and self._calibration_step is None
        )
        actual = self.service.configure(self.settings(), bool(allowed))
        if actual != enabled:
            blocker = QSignalBlocker(self.control)
            self.control.setChecked(actual)
            del blocker
        self.gesture_status.setText("Жест: —")
        self.action_status.setText(
            "Управление включено · ожидаю устойчивый жест"
            if actual
            else "Управление выключено"
        )

    def emergency_stop(self):
        blocker = QSignalBlocker(self.control)
        self.control.setChecked(False)
        del blocker
        self.service.configure(self.settings(), False)
        self.gesture_status.setText("Жест: —")
        self.action_status.setText("Управление выключено")

    def _mode_changed(self):
        self.emergency_stop()

    def _control_failed(self, message):
        self.emergency_stop()
        self.action_status.setText(message)
        self.notice.emit(message)
        self._refresh_control()

    def _result(self, result):
        self.latest = result
        names = {"volume": "Громкость", "media": "Открытая ладонь", "cursor": "Курсор"}
        side = "правая" if self.hand.currentData() == "Right" else "левая"
        self.hand_status.setText(
            f"Рука обнаружена · {side}"
            if result.hand
            else "Покажите ведущую руку целиком · добавьте свет, если рука не видна"
        )
        self.gesture_status.setText(
            "Жест: " + names.get(result.gesture, "неопределённый")
        )
        self.metrics.setText(f"{result.fps:.0f} FPS | {result.latency_ms:.0f} мс")
        self.preview.position_badges()
        self.volume_status.setText(
            f"Системная громкость: {result.volume:.0f}%"
            if result.volume is not None
            else "Системная громкость недоступна: проверьте аудиоустройство"
        )
        self.action_status.setText(
            result.action if self.control.isChecked() else "Управление выключено"
        )

    def start_calibration(self):
        self.emergency_stop()
        if not self._active or not self.service.recognition_ready:
            self.calibration_text.setText(
                "Сначала включите камеру и дождитесь распознавания руки."
            )
            return
        self._calibration_step = 0
        self._calibration_values = {}
        self._calibration_min = None
        self.calibrate_next.setEnabled(True)
        self._refresh_control()
        self._calibration_hint()

    def _calibration_hint(self):
        messages = [
            "1/4 · Покажите открытую ладонь выбранной руки и подтвердите.",
            "2/4 · Сведите большой и указательный пальцы. Остальные согните. Подтвердите удобный минимум.",
            "3/4 · Разведите большой и указательный пальцы. Подтвердите удобный максимум.",
            "4/4 · Подвигайте указательным пальцем: точки должны идти в ожидаемом направлении. Если направление неверное, выключите камеру и измените зеркальность. Подтвердите для сохранения.",
        ]
        self.calibration_text.setText(messages[self._calibration_step])

    def calibration_next(self):
        from time import perf_counter
        from eidos.modules.vision.logic import classify

        if self._calibration_step is None:
            return
        h = (
            self.latest.hand
            if self.latest and perf_counter() - self.latest.timestamp < 0.3
            else None
        )
        if h is None:
            self.calibration_text.setText(
                "Рука не обнаружена. Покажите ведущую руку целиком и повторите шаг."
            )
            return
        step = self._calibration_step
        if step == 0 and classify(h) != "media":
            self.calibration_text.setText("Для первого шага нужна открытая ладонь.")
            return
        if step in (1, 2) and classify(h) != "volume":
            self.calibration_text.setText(
                "Для этого шага используйте большой и указательный пальцы; остальные согните."
            )
            return
        if step == 3 and classify(h) != "cursor":
            self.calibration_text.setText(
                "Для проверки направления оставьте выпрямленным только указательный палец."
            )
            return
        if step == 1:
            self._calibration_min = max(0.01, min(2.0, pinch_ratio(h)))
        if step == 2:
            maximum = min(4.0, pinch_ratio(h))
            if maximum - self._calibration_min < 0.1:
                self.calibration_text.setText(
                    "Диапазон слишком мал: разведите пальцы сильнее и повторите."
                )
                return
            self._calibration_values = {
                "gesture_pinch_min": self._calibration_min,
                "gesture_pinch_max": maximum,
            }
        if step == 3:
            values = self.preference_values()
            values.update(self._calibration_values)
            self.preferences_changed.emit(values)
            return
        self._calibration_step += 1
        self._calibration_hint()

    def skip_calibration(self):
        self._calibration_step = None
        self._calibration_values = {}
        self.calibrate_next.setEnabled(False)
        self.calibration_text.setText(
            "Калибровка пропущена. Используются сохранённые параметры."
        )
        self._refresh_control()

    def reset_calibration(self):
        self.emergency_stop()
        self.skip_calibration()
        self.pinch_min.setValue(0.15)
        self.pinch_max.setValue(1.5)
        self.preferences_changed.emit(
            {"gesture_pinch_min": 0.15, "gesture_pinch_max": 1.5}
        )
        self.calibration_text.setText(
            "Диапазон громкости сброшен: 0,15–1,50 размера ладони."
        )

    def shutdown(self, final=False):
        self.emergency_stop()
        self.skip_calibration()
        self._active = False
        self.camera_button.setEnabled(False)
        if final:
            self.service.shutdown()
        else:
            self.service.stop()

    def _stopped(self):
        self._active = False
        self.latest = None
        self.camera.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.parameters.setEnabled(True)
        self.save_button.setEnabled(True)
        self._camera_button_state(False)
        self.camera_button.setEnabled(bool(self._devices))
        self.control.setEnabled(False)
        self.preview.set_image(QImage())
        self.hand_status.setText("Покажите руку")
        self.metrics.setText('— FPS | — мс')
        self.preview.position_badges()
        self.stopped.emit()
