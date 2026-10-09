"""Global Windows shortcuts without polling or low-level keyboard hooks."""
import ctypes
from itertools import count
import sys

from PyQt6.QtCore import QObject, QAbstractNativeEventFilter, Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QKeySequenceEdit

from eidos.core.shortcuts import configured_shortcuts, ACTIONS


class WindowsBackend:
    native = True

    def __init__(self):
        from ctypes import wintypes
        self.user = ctypes.windll.user32
        self.user.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        self.user.RegisterHotKey.restype = wintypes.BOOL
        self.user.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.UnregisterHotKey.restype = wintypes.BOOL

    def register(self, identifier, shortcut):
        return bool(self.user.RegisterHotKey(None, identifier, shortcut.modifiers | 0x4000, shortcut.key))

    def unregister(self, identifier):
        self.user.UnregisterHotKey(None, identifier)


class LocalBackend:
    native = False

    def __init__(self, owner, callback):
        self.owner, self.callback, self.shortcuts = owner, callback, {}

    def register(self, identifier, shortcut):
        control = QShortcut(QKeySequence(shortcut.text), self.owner)
        control.setContext(Qt.ShortcutContext.ApplicationShortcut)
        control.setAutoRepeat(False)
        control.activated.connect(lambda: self.callback(identifier))
        self.shortcuts[identifier] = control
        return True

    def unregister(self, identifier):
        control = self.shortcuts.pop(identifier, None)
        if control:
            control.setEnabled(False)
            control.deleteLater()


class NativeFilter(QAbstractNativeEventFilter):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            from ctypes import wintypes
            event = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
            if event.message == 0x0312 and self.manager.trigger(event.wParam):
                return True, 0
        return False, 0


class TranslationHotkeys(QObject):
    activated = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    _identifiers = count(0x2000)

    def __init__(self, parent, backend=None):
        super().__init__(parent)
        app = QApplication.instance()
        self.backend = backend or (WindowsBackend() if sys.platform == 'win32' and app.platformName() != 'offscreen'
                                  else LocalBackend(parent, self.trigger))
        self.filter = NativeFilter(self) if self.backend.native else None
        if self.filter:
            app.installNativeEventFilter(self.filter)
        self.bindings = {}
        self.actions = {}
        self.config = None
        self.suspended = self.closed = False
        self.message = ''
        app.focusChanged.connect(self._focus_changed)
        app.applicationStateChanged.connect(self._application_state)

    def configure(self, config):
        configured = configured_shortcuts(config)
        wanted = {action: shortcut for action, shortcut in configured.items()
                  if not self.suspended and (config.voice_hotkey_enabled if action == 'voice'
                                             else config.translation_hotkeys_enabled)}
        new_bindings, new_actions, acquired = {}, {}, []
        for action, shortcut in wanted.items():
            if shortcut is None:
                continue
            identity = (shortcut.modifiers, shortcut.key)
            identifier = self.bindings.get(identity)
            if identifier is None:
                identifier = next(self._identifiers)
                if not self.backend.register(identifier, shortcut):
                    for pending in acquired:
                        self.backend.unregister(pending)
                    self.message = f'{shortcut.text} уже занята Windows или другой программой. Выберите другую комбинацию.'
                    if self.actions:
                        self.message += ' Прежние сочетания продолжают работать.'
                    self.status_changed.emit(self.message)
                    return False
                acquired.append(identifier)
            new_bindings[identity] = identifier
            new_actions[identifier] = action
        for identity, identifier in self.bindings.items():
            if identity not in new_bindings:
                self.backend.unregister(identifier)
        self.bindings, self.actions, self.config = new_bindings, new_actions, config
        if not config.translation_hotkeys_enabled and not config.voice_hotkey_enabled:
            self.message = 'Горячие клавиши выключены.'
        elif self.suspended:
            self.message = 'Введите комбинацию, затем нажмите «Сохранить».'
        elif not self.actions:
            self.message = 'Комбинации клавиш не назначены.'
        elif self.backend.native:
            self.message = 'Горячие клавиши работают во всех приложениях, пока Eidos запущен.'
        else:
            self.message = 'Горячие клавиши работают внутри Eidos.'
        self.status_changed.emit(self.message)
        return True

    def trigger(self, identifier):
        action = self.actions.get(int(identifier))
        if action is None or self.suspended or self.closed:
            return False
        QTimer.singleShot(0, lambda: self.activated.emit(action)
            if not self.closed and not self.suspended and self.actions.get(int(identifier)) == action else None)
        return True

    def _focus_changed(self, previous, current):
        editing = False
        widget = current
        while widget:
            if isinstance(widget, QKeySequenceEdit):
                editing = True
                break
            widget = widget.parentWidget()
        if self.backend.native and QApplication.instance().applicationState() != Qt.ApplicationState.ApplicationActive:
            editing = False
        if editing != self.suspended and not self.closed:
            self.suspended = editing
            if self.config is not None:
                self.configure(self.config)

    def _application_state(self, state):
        if self.closed:
            return
        if state == Qt.ApplicationState.ApplicationActive:
            self._focus_changed(None, QApplication.instance().focusWidget())
        elif self.suspended:
            self.suspended = False
            if self.config is not None:
                self.configure(self.config)

    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        for identifier in self.bindings.values():
            self.backend.unregister(identifier)
        self.bindings.clear()
        self.actions.clear()
        app = QApplication.instance()
        app.focusChanged.disconnect(self._focus_changed)
        app.applicationStateChanged.disconnect(self._application_state)
        if self.filter:
            app.removeNativeEventFilter(self.filter)
