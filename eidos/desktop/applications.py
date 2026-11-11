import os
from pathlib import Path
import time

ALIASES = {'стим': 'steam', 'steam': 'steam', 'спотифай': 'spotify', 'spotify': 'spotify',
    'блокнот': 'notepad', 'notepad': 'notepad'}
PROTOCOLS = {'steam': 'steam://open/main', 'spotify': 'spotify:'}
SCRIPT_HOSTS = {'cmd.exe', 'powershell.exe', 'pwsh.exe', 'mshta.exe', 'wscript.exe', 'cscript.exe'}


def checked_executable(value):
    path = Path(os.path.expandvars(str(value))).expanduser().resolve()
    if path.suffix.lower() != '.exe' or path.name.lower() in SCRIPT_HOSTS or not path.is_file():
        raise ValueError('Нужен существующий EXE приложения, не командная оболочка')
    return str(path)


class ApplicationCatalog:
    def __init__(self, settings, backend):
        self.settings, self.backend = settings, backend
        self._entries, self._expires = {}, 0

    def refresh(self):
        if time.monotonic() < self._expires: return
        entries = {}
        if os.name == 'nt':
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(root, r'Software\Microsoft\Windows\CurrentVersion\App Paths', 0, winreg.KEY_READ | view) as key:
                            for i in range(min(512, winreg.QueryInfoKey(key)[0])):
                                name = winreg.EnumKey(key, i)
                                try:
                                    with winreg.OpenKey(key, name) as child:
                                        value = winreg.QueryValueEx(child, '')[0].strip('"')
                                    entries[Path(name).stem.casefold()] = checked_executable(value)
                                except (OSError, ValueError): pass
                    except OSError: pass
            # Only Start Menu shortcuts, never a whole-disk scan.
            try:
                import comtypes
                from comtypes.client import CreateObject
                comtypes.CoInitialize()
                try:
                    shell = CreateObject('WScript.Shell', dynamic=True)
                    roots = [Path(os.environ.get(key, '')) / 'Microsoft/Windows/Start Menu/Programs'
                             for key in ('APPDATA', 'PROGRAMDATA')]
                    for root in roots:
                        if not root.is_dir(): continue
                        for index, shortcut in enumerate(root.rglob('*.lnk')):
                            if index >= 512: break
                            try:
                                target = checked_executable(shell.CreateShortcut(str(shortcut)).TargetPath)
                                entries.setdefault(shortcut.stem.casefold(), target)
                            except Exception: continue
                    shell = None
                finally: comtypes.CoUninitialize()
            except Exception: pass
        self._entries, self._expires = entries, time.monotonic() + 300

    def resolve(self, name):
        original = name.casefold().strip()
        name = ALIASES.get(original, original)
        for title, path in self.settings.approved_apps.items():
            if title.casefold() in (original, name): return checked_executable(path)
        self.refresh()
        if name in self._entries: return self._entries[name]
        if os.name == 'nt' and name in PROTOCOLS:
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, name) as key:
                    winreg.QueryValueEx(key, 'URL Protocol')
                return PROTOCOLS[name]
            except OSError: pass
        if name == 'notepad':
            return checked_executable(Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/notepad.exe')
        return None

    def open(self, name):
        target = self.resolve(name)
        if not target: return None
        if '://' not in target and not target.endswith(':'):
            if any(os.path.normcase(row.get('launch_path', row['path'])) == os.path.normcase(target) for row in self.backend.windows()):
                self.backend.activate(target)
                return 'Приложение уже открыто: ' + name
        if '://' not in target and not target.endswith(':') and self.backend.activate(target):
            return 'Активирую ' + name
        self.backend.launch(target)
        return 'Запускаю ' + name
