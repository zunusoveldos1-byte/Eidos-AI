"""Only Eidos' own per-user Run value; no elevation or shell execution."""
from pathlib import Path
import subprocess
import sys


def startup_command(executable=None, launcher=None):
    executable = Path(executable or sys.executable).resolve()
    if executable.name.lower() == 'python.exe' and executable.with_name('pythonw.exe').is_file():
        executable = executable.with_name('pythonw.exe')
    parts = [str(executable)]
    if not getattr(sys, 'frozen', False):
        parts.append(str(Path(launcher or Path(__file__).parents[1] / 'startup_launcher.py').resolve()))
    command = subprocess.list2cmdline(parts)
    if len(command) > 260:
        raise ValueError('Путь автозапуска слишком длинный для Windows Run (260 символов).')
    return command


class WindowsStartup:
    KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
    NAME = 'Eidos'

    def enabled(self):
        if sys.platform != 'win32':
            return False
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY) as key:
                value, kind = winreg.QueryValueEx(key, self.NAME)
                return kind == winreg.REG_SZ and value == startup_command()
        except FileNotFoundError:
            return False

    def configure(self, enabled):
        if sys.platform != 'win32':
            if enabled:
                raise ValueError('Автозапуск доступен только в Windows.')
            return
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.KEY, access=winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, self.NAME, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, self.NAME)
                except FileNotFoundError:
                    pass
        if self.enabled() != enabled:
            raise OSError('Не удалось подтвердить состояние автозапуска Windows.')
