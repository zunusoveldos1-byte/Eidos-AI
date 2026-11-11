from dataclasses import replace
from PyQt6.QtWidgets import QLineEdit
from eidos.core.config import AppConfig,ConfigStore
from eidos.ui.main_window import MainWindow
from test_ui import app,wait_until


def test_dynamic_gemini_fields_key_vault_and_settings(app,tmp_path,monkeypatch):
    store=ConfigStore(tmp_path/'config.json')
    store.save(replace(AppConfig(),voice_hotkey_enabled=False,translation_hotkeys_enabled=False))
    window=MainWindow(store)
    keys={}
    monkeypatch.setattr(window.agent_service.secrets,'set',lambda name,value:keys.update({name:value}))
    monkeypatch.setattr(window.agent_service.secrets,'get',lambda name:keys.get(name))
    try:
        window.navigate(4); window.show(); window.settings.tabs.setCurrentIndex(1)
        ui=window.assistant
        ui.provider.setCurrentIndex(ui.provider.findData('gemini'))
        assert ui.gemini_key.isVisibleTo(window) and ui.gemini_model.isVisibleTo(window)
        assert ui.gemini_key.echoMode()==QLineEdit.EchoMode.Password
        assert not ui.cloud_model.isVisibleTo(window) and not ui.server_start.isVisibleTo(window)
        assert not ui.model_pull.isVisibleTo(window) and not ui.model_name.isVisibleTo(window)
        assert ui.model_refresh.text()=='Проверить ключ'
        ui.gemini_key.setText('unit-gemini-key')
        ui.gemini_model.setText('gemini-2.5-flash')
        assert window._save_model()
        assert keys=={'gemini':'unit-gemini-key'} and not ui.gemini_key.text()
        assert window.agent_service.settings.provider=='gemini'
        assert 'unit-gemini-key' not in window.agent_service.store.path.read_text(encoding='utf-8')
        assert window._save_model() and keys['gemini']=='unit-gemini-key'
        ui.provider.setCurrentIndex(ui.provider.findData('ollama'))
        assert not ui.gemini_key.isVisibleTo(window) and ui.server_start.isVisibleTo(window)
    finally:
        window.request_exit(); wait_until(app,lambda:window._allow_close)


def test_cloud_connection_check_is_in_worker_and_gui_keeps_ticking(app,tmp_path,monkeypatch):
    from threading import Event
    from PyQt6.QtCore import QThread,QTimer
    from eidos.agent.gemini import GeminiProvider
    entered,release=Event(),Event()
    def check(self,context):
        assert QThread.currentThread() is not app.thread()
        entered.set()
        release.wait(2)
        return 'Gemini · ключ принят'
    monkeypatch.setattr(GeminiProvider,'check_connection',check)
    window=MainWindow(ConfigStore(tmp_path/'config.json'))
    timer=QTimer()
    ticks=[]
    timer.timeout.connect(lambda:ticks.append(True))
    timer.start(5)
    try:
        wait_until(app,lambda:not window.controller.discovering)
        window.assistant.provider.setCurrentIndex(window.assistant.provider.findData('gemini'))
        window.assistant.model_refresh.click()
        wait_until(app,entered.is_set)
        baseline=len(ticks)
        wait_until(app,lambda:len(ticks)>baseline+3)
        assert window.agent_controller.active
        release.set()
        wait_until(app,lambda:not window.agent_controller.active)
        assert 'ключ принят' in window.assistant.model_status.text()
    finally:
        release.set(); timer.stop()
        window.request_exit(); wait_until(app,lambda:window._allow_close)
