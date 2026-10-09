import threading
import time
from dataclasses import replace

from eidos.agent.controller import AgentController
from eidos.agent.controller import TaskState
from eidos.agent.service import AgentService
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_agent_close_cancels_blocking_work_and_repeated_start(app, tmp_path):
    service = AgentService(tmp_path)
    started = threading.Event()
    def respond(text, context):
        started.set()
        while not context.cancel.wait(.01):
            context.check()
        context.check()
    service.respond = respond
    controller = AgentController(service)
    assert controller.start('chat','test')
    assert controller.state == TaskState.THINKING
    assert not controller.start('chat','duplicate')
    wait_until(app, started.is_set)
    controller.shutdown()
    wait_until(app, lambda:not controller.thread.isRunning())
    assert controller.closing
    app.processEvents()


def test_confirmation_and_window_close(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path/'config.json'))
    window.show()
    try:
        wait_until(app, lambda: not window.controller.discovering)
        args = dict(mode='create',id=0,title='No accidental event',start='2030-01-01T12:00:00',timezone='Asia/Bishkek',reminder_minutes=10)
        assert window._start_agent_task('tool', ('calendar_change',args))
        wait_until(app, lambda:bool(window._approval_boxes))
        assert not window.agent_service.calendar.list()
        window.close()
        wait_until(app, lambda:not window.agent_controller.thread.isRunning() and not window.controller.thread.isRunning())
        assert not window.agent_service.calendar.list()
    finally:
        window.close()
        wait_until(app, lambda:not window.agent_controller.thread.isRunning() and not window.controller.thread.isRunning())
        app.processEvents()


def test_memory_disable_does_not_silently_remain_on_after_disk_error(app, tmp_path, monkeypatch):
    window = MainWindow(ConfigStore(tmp_path/'config.json'))
    try:
        wait_until(app, lambda:not window.controller.discovering)
        window.assistant.memory_enabled.setChecked(True)
        assert window.agent_service.settings.memory_enabled
        def fail(settings):
            raise OSError('read only')
        monkeypatch.setattr(window.agent_service.store,'save',fail)
        window.assistant.memory_enabled.setChecked(False)
        assert not window.agent_service.settings.memory_enabled
        assert 'текущем запуске' in window.assistant.feedback.text()
    finally:
        window.close()
        wait_until(app, lambda:not window.agent_controller.thread.isRunning() and not window.controller.thread.isRunning())
        app.processEvents()


def test_chat_memory_tabs_and_profile_opt_in(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path/'config.json'))
    window.show()
    try:
        wait_until(app, lambda:not window.controller.discovering)
        ui = window.assistant
        assert ui.tabs.count()==7
        assert not ui.memory_enabled.isChecked()
        assert not any(c.isChecked() for c in ui.remote_checks.values())
        ui.input.setPlainText('Привет')
        ui.send.click()
        wait_until(app, lambda:not window.agent_controller.active)
        assert 'Привет! Я Eidos' in ui.history.toPlainText()
        assert not window.agent_service.memory.items()
        ui.memory_enabled.setChecked(True)
        ui.memory_edit.setPlainText('Проект на Python')
        ui.memory_save.click()
        wait_until(app, lambda:not window.agent_controller.active)
        assert window.agent_service.memory.search('Python')
        ui.incognito.setChecked(True)
        ui.input.setPlainText('Который час?')
        ui.send.click()
        wait_until(app, lambda:not window.agent_controller.active)
        assert not window.agent_service.memory.items('dialogue')
    finally:
        window.close()
        wait_until(app, lambda:not window.agent_controller.thread.isRunning() and not window.controller.thread.isRunning())
        app.processEvents()
