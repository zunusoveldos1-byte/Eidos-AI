from dataclasses import replace
import numpy as np
from eidos.agent.harness import Registry, Tool, ToolResult
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_real_ui_voice_signals_dispatch_windows_tool_without_llm(app, tmp_path, monkeypatch):
    seen = []
    registry = Registry()
    registry.add(Tool('volume','Громкость',{'mode':{'type':'string','enum':['set']},
                      'value':{'type':'integer','minimum':0,'maximum':100}},
                      lambda args, ctx:seen.append(args) or ToolResult('Громкость: 30%.'),'windows.audio'))
    monkeypatch.setattr('eidos.agent.service.build_registry',lambda *args:registry)
    class NoModel:
        def chat(self,*args):
            raise AssertionError('Windows command must not invoke LLM')
    monkeypatch.setattr('eidos.agent.service.provider_for',lambda *args:NoModel())
    class Recorder:
        def record(self,device,stop,cancel,started):
            started()
            return np.ones(8000,dtype=np.float32)
    class STT:
        def transcribe(self,audio,config,cache,progress,cancel):
            progress('transcribing','Распознавание тестовой команды')
            return 'Сделай громкость 30 процентов'
    window=MainWindow(ConfigStore(tmp_path/'config.json'))
    window.show()
    try:
        wait_until(app,lambda:not window.controller.discovering)
        window.controller.worker.recorder=Recorder()
        window.controller.worker.stt=STT()
        window._persist(replace(window.config,speak=False))
        window.controller.start(window.config)
        wait_until(app,lambda:not window.controller.active)
        assert seen==[{'mode':'set','value':30}]
        assert window.voice.answer.text.toPlainText()=='Громкость: 30%.'
        assert not window.agent_service.memory.items()
    finally:
        window.close()
        wait_until(app,lambda:not window.agent_controller.thread.isRunning() and not window.controller.thread.isRunning())
        app.processEvents()
