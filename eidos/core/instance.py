"""Atomic per-data-directory process lock plus local activation signal."""
import hashlib
from PyQt6.QtCore import QObject, QLockFile, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


class SingleInstance(QObject):
    activated = pyqtSignal()

    def __init__(self, root, parent=None):
        super().__init__(parent)
        root.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(root / 'eidos.lock'))
        self._name = 'Eidos-' + hashlib.sha256(str(root.resolve()).casefold().encode()).hexdigest()[:24]
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._connected)

    def acquire(self):
        if not self._lock.tryLock(0):
            socket = QLocalSocket(self)
            socket.connectToServer(self._name)
            if socket.waitForConnected(100):
                socket.write(b'activate')
                socket.waitForBytesWritten(100)
            socket.abort()
            socket.deleteLater()
            return False
        QLocalServer.removeServer(self._name)
        if not self._server.listen(self._name):
            # Some Windows sandboxes disallow named pipes. The lock still
            # prevents a second microphone/camera owner; activation is optional.
            self.activation_available = False
        else:
            self.activation_available = True
        return True

    def _connected(self):
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.close()
            socket.deleteLater()
        self.activated.emit()

    def close(self):
        self._server.close()
        self._lock.unlock()
