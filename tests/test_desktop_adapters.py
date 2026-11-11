import os
import sys
from types import SimpleNamespace
import pytest
from eidos.agent.harness import TaskContext
from eidos.desktop.windows import WindowsBackend
from eidos.desktop.sound import change

NATIVE_DESKTOP = WindowsBackend.desktop
NATIVE_POWER = WindowsBackend.power


def test_show_desktop_uses_minimize_all_twice_not_toggle(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, 'comtypes', SimpleNamespace(CoInitialize=lambda: calls.append('init'), CoUninitialize=lambda: calls.append('release')))
    monkeypatch.setitem(sys.modules, 'comtypes.client', SimpleNamespace(CreateObject=lambda *args, **kw: SimpleNamespace(MinimizeAll=lambda: calls.append('minimize'))))
    NATIVE_DESKTOP(WindowsBackend())
    NATIVE_DESKTOP(WindowsBackend())
    assert calls == ['init', 'minimize', 'release'] * 2


@pytest.mark.skipif(os.name != 'nt', reason='Windows command flags')
def test_native_power_has_zero_timeout_and_never_force(monkeypatch):
    import eidos.desktop.windows as module
    calls = []
    monkeypatch.setattr(module.subprocess, 'run', lambda args, **kw: calls.append(args) or SimpleNamespace(returncode=0))
    NATIVE_POWER(WindowsBackend(), 'shutdown')
    NATIVE_POWER(WindowsBackend(), 'restart')
    assert calls[0][1:] == ['/s', '/t', '0']
    assert calls[1][1:] == ['/r', '/t', '0']
    with pytest.raises(ValueError): NATIVE_POWER(WindowsBackend(), 'arbitrary-command')
    assert len(calls) == 2


def test_core_audio_clamps_and_requeries_current_device_and_unmute_keeps_level(monkeypatch):
    class Endpoint:
        def __init__(self, level): self.level, self.muted = level, False
        def GetMasterVolumeLevelScalar(self): return self.level
        def SetMasterVolumeLevelScalar(self, level, unused): self.level = level
        def GetMute(self): return self.muted
        def SetMute(self, muted, unused): self.muted = bool(muted)
    first, second = Endpoint(.95), Endpoint(.2)
    current = [first]
    released = []
    monkeypatch.setitem(sys.modules, 'comtypes', SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: released.append(True)))
    monkeypatch.setitem(sys.modules, 'pycaw.pycaw', SimpleNamespace(AudioUtilities=SimpleNamespace(GetSpeakers=lambda: SimpleNamespace(EndpointVolume=current[0]))))
    change({'mode': 'up', 'value': 10}, TaskContext())
    assert first.level == 1
    current[0] = second
    change({'mode': 'down', 'value': 30}, TaskContext())
    assert second.level == 0
    second.level, second.muted = .4, True
    change({'enabled': False}, TaskContext(), mute=True)
    assert second.level == .4 and not second.muted
    assert len(released) == 3
