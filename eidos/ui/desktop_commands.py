"""Qt/STA-only desktop actions, queued from the existing agent workers."""
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Event
from time import monotonic
from uuid import uuid4
import os
from PyQt6.QtCore import QObject, QTimer, QRect, Qt, QStandardPaths, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox


@dataclass
class Request:
    action: str
    args: dict
    cancel: Event
    done: Event = field(default_factory=Event)
    answer: str = ''
    error: str = ''


class DesktopUI(QObject):
    requested = pyqtSignal(object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.requested.connect(self.execute)
        self.power_box = None
        self.region_request = None

    def request(self, action, args, cancel):
        req = Request(action, args, cancel)
        self.requested.emit(req)
        deadline = monotonic() + (65 if action == 'screenshot' and args.get('mode') == 'region' else 120)
        while not req.done.wait(.05):
            if cancel.is_set(): raise InterruptedError('Действие отменено')
            if monotonic() > deadline:
                cancel.set()
                raise TimeoutError('Действие интерфейса не завершено')
        if cancel.is_set(): raise InterruptedError('Действие отменено')
        if req.error: raise RuntimeError(req.error)
        return req.answer

    def capture(self, mode):
        screens = QApplication.screens()
        if not screens: raise RuntimeError('Монитор не найден')
        if mode != 'all':
            image = QApplication.primaryScreen().grabWindow(0).toImage()
        else:
            bounds = QRect()
            for screen in screens: bounds = bounds.united(screen.geometry())
            ratio = max(screen.devicePixelRatio() for screen in screens)
            image = QImage(round(bounds.width() * ratio), round(bounds.height() * ratio), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.black)
            painter = QPainter(image)
            try:
                for screen in screens:
                    geom = screen.geometry().translated(-bounds.topLeft())
                    target = QRect(round(geom.x() * ratio), round(geom.y() * ratio),
                                   round(geom.width() * ratio), round(geom.height() * ratio))
                    shot = screen.grabWindow(0)
                    if shot.isNull(): raise RuntimeError('Не удалось захватить один из мониторов')
                    painter.drawPixmap(target, shot)
            finally: painter.end()
        if image.isNull(): raise RuntimeError('Не удалось захватить экран')
        return image

    def execute(self, req):
        pending = False
        try:
            if req.cancel.is_set() or self.window._closing: raise InterruptedError('Действие отменено')
            if req.action == 'screenshot':
                mode = req.args['mode']
                if mode == 'region':
                    self._region(req)
                    pending = True
                    return
                image = self.capture(mode)
                if mode == 'save':
                    directory = Path(req.args['folder'] or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation))
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory / ('Eidos-' + uuid4().hex + '.png')
                    if not image.save(str(path), 'PNG'): raise RuntimeError('Не удалось сохранить скриншот')
                    req.answer = 'Скриншот сохранён: ' + str(path)
                else:
                    QApplication.clipboard().setImage(image)
                    if QApplication.clipboard().image().isNull(): raise RuntimeError('Буфер обмена не принял изображение')
                    req.answer = 'Скриншот в буфере обмена'
            elif req.action == 'power_prompt':
                self.hide_power()
                box = QMessageBox(self.window)
                self.power_box = box
                box.setWindowTitle('Подтверждение питания')
                box.setText('Выключить компьютер?' if req.args['action'] == 'shutdown' else 'Перезагрузить компьютер?')
                box.setInformativeText('Подтверждение действует 15 секунд. Несохранённые данные не закрываются принудительно.')
                box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
                box.setDefaultButton(QMessageBox.StandardButton.Cancel)
                token = self.window.agent_service.desktop.pending
                def chosen(button):
                    current = self.window.agent_service.desktop.pending
                    if current is not token: return
                    text = ('Подтверждаю выключение' if req.args['action'] == 'shutdown' else 'Подтверждаю перезагрузку') if box.standardButton(button) == QMessageBox.StandardButton.Yes else 'Отмена'
                    self.window._start_agent_task('chat', text)
                box.buttonClicked.connect(chosen)
                def rejected(result):
                    if result != int(QMessageBox.StandardButton.Yes) and self.window.agent_service.desktop.pending is token:
                        self.window.agent_service.desktop.cancel_pending()
                box.finished.connect(rejected)
                QTimer.singleShot(15000, box.close)
                box.show()
                req.answer = ''
            elif req.action == 'power_hide':
                self.hide_power()
            elif req.action == 'application_path':
                path, _ = QFileDialog.getOpenFileName(self.window, 'Укажите путь: ' + req.args['name'], '', 'Приложения (*.exe)')
                req.answer = path
            else: raise ValueError('Неизвестное действие интерфейса')
        except Exception as exc:
            req.error = str(exc)
        finally:
            if not pending: req.done.set()

    def hide_power(self):
        if self.power_box:
            self.power_box.close()
            self.power_box.deleteLater()
            self.power_box = None

    def _region(self, req):
        if self.region_request: raise RuntimeError('Выделение уже выполняется')
        clipboard = QApplication.clipboard()
        initial = clipboard.image().cacheKey()
        self.region_request = req
        started = monotonic()
        timer = QTimer(self)
        def finish(error=''):
            timer.stop()
            timer.deleteLater()
            req.error = error
            req.answer = '' if error else 'Скриншот в буфере обмена'
            self.region_request = None
            req.done.set()
        def poll():
            if req.cancel.is_set() or self.window._closing: return finish('Выделение отменено')
            image = clipboard.image()
            if not image.isNull() and image.cacheKey() != initial: return finish()
            if monotonic() - started > 60: finish('Выделение отменено или изображение не поступило в буфер')
        timer.timeout.connect(poll)
        try:
            os.startfile('ms-screenclip:')
        except Exception:
            self.region_request = None
            timer.deleteLater()
            raise
        timer.start(100)
