"""Bounded mailboxes and authorization checked at the point of execution."""

import threading


class Latest:
    def __init__(self):
        self._lock = threading.Lock()
        self._value = None

    def put(self, value):
        with self._lock:
            self._value = value

    def take(self):
        with self._lock:
            value, self._value = self._value, None
            return value

    def peek(self):
        with self._lock:
            return self._value


class ControlGate:
    def __init__(self):
        self.lock = threading.RLock()
        self.settings = None
        self.enabled = False
        self.generation = 0

    def configure(self, settings, enabled=False):
        with self.lock:
            self.settings = settings
            self.enabled = enabled
            self.generation += 1

    def snapshot(self):
        with self.lock:
            return self.settings, self.enabled, self.generation

    def execute(self, generation, action, executor, fresh=True):
        with self.lock:
            if not self.enabled or generation != self.generation or not fresh:
                return None
            return executor.execute(action)
