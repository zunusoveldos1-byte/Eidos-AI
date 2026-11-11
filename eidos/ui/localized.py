"""Qt widget adapters. Translate UI chrome, never editable user content."""
from PyQt6 import QtWidgets as QtW
from PyQt6 import QtGui
from PyQt6.QtCore import QSignalBlocker, QTranslator
from eidos.core.i18n import register, tr


class NativeTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        from eidos.core.i18n import language
        from eidos.core.native_strings import STRINGS
        plain = sourceText.replace('&', '')
        result = STRINGS.get(language(), {}).get(plain)
        return result if result is not None else sourceText


def install_native_translator():
    app = QtW.QApplication.instance()
    if not hasattr(app, '_eidos_native_translator'):
        app._eidos_native_translator = NativeTranslator(app)
        app.installTranslator(app._eidos_native_translator)


class Localized:
    def __init__(self, *args, **kwargs):
        self._ui_sources = {}
        self._ui_items = {}
        self._ui_tabs = {}
        if args and isinstance(args[0], str):
            method = 'setTitle' if isinstance(self, (QtW.QGroupBox, QtW.QMenu)) else 'setText'
            self._ui_sources[method] = args[0]
            args = (tr(args[0]), *args[1:])
        super().__init__(*args, **kwargs)
        register(self)

    def _set(self, method, value):
        self._ui_sources[method] = value
        getattr(super(), method)(tr(value))

    def setText(self, value):
        self._set('setText', value)

    def setToolTip(self, value):
        self._set('setToolTip', value)

    def setAccessibleName(self, value):
        self._set('setAccessibleName', value)

    def setAccessibleDescription(self, value):
        self._set('setAccessibleDescription', value)

    def setSuffix(self, value):
        self._set('setSuffix', value)

    def setWindowTitle(self, value):
        self._set('setWindowTitle', value)

    def setPlaceholderText(self, value):
        self._set('setPlaceholderText', value)

    def setTitle(self, value):
        self._set('setTitle', value)

    def source_text(self):
        return self._ui_sources.get('setText', self.text() if hasattr(self, 'text') else '')

    def retranslate(self):
        blocker = QSignalBlocker(self)
        for method, source in self._ui_sources.items():
            getattr(super(), method)(tr(source))
        for index, source in self._ui_items.items():
            super().setItemText(index, tr(source))
        for index, source in self._ui_tabs.items():
            super().setTabText(index, tr(source))
        del blocker
        self.update() if hasattr(self, 'update') else None


class QComboBox(Localized, QtW.QComboBox):
    def addRawItem(self, text, data=None):
        """Device/model/user names retain their original spelling."""
        super().addItem(text, data)

    def addItem(self, *args):
        text_index = 0 if isinstance(args[0], str) else 1
        source = args[text_index]
        args = list(args)
        args[text_index] = tr(source)
        index = self.count()
        super().addItem(*args)
        self._ui_items[index] = source

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def clear(self):
        self._ui_items.clear()
        super().clear()

    def setItemText(self, index, text):
        self._ui_items[index] = text
        super().setItemText(index, tr(text))


class QTabWidget(Localized, QtW.QTabWidget):
    def addTab(self, widget, text):
        index = super().addTab(widget, tr(text))
        self._ui_tabs[index] = text
        return index

    def insertTab(self, index, widget, text):
        self._ui_tabs = {i + 1 if i >= index else i: s for i, s in self._ui_tabs.items()}
        result = super().insertTab(index, widget, tr(text))
        self._ui_tabs[result] = text
        return result

    def removeTab(self, index):
        self._ui_tabs = {i - 1 if i > index else i: s for i, s in self._ui_tabs.items() if i != index}
        super().removeTab(index)


class QMenu(Localized, QtW.QMenu):
    def addAction(self, *args):
        if args and isinstance(args[0], str):
            action = QAction(args[0], self)
            if len(args) > 1:
                action.triggered.connect(args[1])
            super().addAction(action)
            return action
        return super().addAction(*args)


class QMessageBox(Localized, QtW.QMessageBox):
    def __init__(self, *args, **kwargs):
        if args and not isinstance(args[0], (str, QtW.QWidget)) and len(args) >= 3:
            args = (args[0], tr(args[1]), tr(args[2]), *args[3:])
        super().__init__(*args, **kwargs)

    @staticmethod
    def question(parent, title, text, *args):
        return QtW.QMessageBox.question(parent, tr(title), tr(text), *args)

    @staticmethod
    def warning(parent, title, text, *args):
        return QtW.QMessageBox.warning(parent, tr(title), tr(text), *args)

    @staticmethod
    def information(parent, title, text, *args):
        return QtW.QMessageBox.information(parent, tr(title), tr(text), *args)


class QAction(Localized, QtGui.QAction):
    pass


class QLineEdit(Localized, QtW.QLineEdit):
    def setText(self, value):
        QtW.QLineEdit.setText(self, value)


class QFileDialog:
    @staticmethod
    def getOpenFileNames(parent, title, directory='', filter=''):
        return QtW.QFileDialog.getOpenFileNames(parent, tr(title), directory, tr(filter),
            options=QtW.QFileDialog.Option.DontUseNativeDialog)

    @staticmethod
    def getOpenFileName(parent, title, directory='', filter=''):
        return QtW.QFileDialog.getOpenFileName(parent, tr(title), directory, tr(filter),
            options=QtW.QFileDialog.Option.DontUseNativeDialog)

    @staticmethod
    def getSaveFileName(parent, title, directory='', filter=''):
        return QtW.QFileDialog.getSaveFileName(parent, tr(title), directory, tr(filter),
            options=QtW.QFileDialog.Option.DontUseNativeDialog)

    @staticmethod
    def getExistingDirectory(parent, title, directory=''):
        return QtW.QFileDialog.getExistingDirectory(parent, tr(title), directory,
            options=QtW.QFileDialog.Option.DontUseNativeDialog)


class QInputDialog:
    @staticmethod
    def getItem(parent, title, label, *args):
        return QtW.QInputDialog.getItem(parent, tr(title), tr(label), *args)

    @staticmethod
    def getText(parent, title, label, *args, **kwargs):
        return QtW.QInputDialog.getText(parent, tr(title), tr(label), *args, **kwargs)

    @staticmethod
    def getMultiLineText(parent, title, label, *args):
        return QtW.QInputDialog.getMultiLineText(parent, tr(title), tr(label), *args)


for _name in ('QAbstractButton', 'QLabel', 'QPushButton', 'QCheckBox', 'QPlainTextEdit',
              'QGroupBox', 'QDialog', 'QMainWindow', 'QWidget', 'QSpinBox', 'QDoubleSpinBox'):
    globals()[_name] = type(_name, (Localized, getattr(QtW, _name)), {})
