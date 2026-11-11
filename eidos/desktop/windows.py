"""Windows adapters: fixed commands, no recognized text enters a shell."""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess


class WindowsBackend:
    def windows(self):
        if os.name != 'nt': return []
        user, kernel = ctypes.WinDLL('user32'), ctypes.WinDLL('kernel32')
        user.IsWindowVisible.argtypes = [W.HWND]
        user.GetWindowTextLengthW.argtypes = [W.HWND]
        user.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
        kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
        kernel.OpenProcess.restype = W.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
        kernel.CloseHandle.argtypes = [W.HANDLE]
        result = []
        callback_type = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
        @callback_type
        def collect(hwnd, unused):
            if not user.IsWindowVisible(hwnd) or not user.GetWindowTextLengthW(hwnd): return True
            pid = W.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == os.getpid(): return True
            handle = kernel.OpenProcess(0x1000, False, pid.value)
            if not handle: return True
            try:
                buf, size = ctypes.create_unicode_buffer(32768), W.DWORD(32768)
                if kernel.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    path = Path(buf.value)
                    excluded = {'explorer.exe', 'applicationframehost.exe', 'shellexperiencehost.exe',
                        'searchhost.exe', 'startmenuexperiencehost.exe', 'textinputhost.exe', 'dwm.exe',
                        'taskmgr.exe', 'setup.exe', 'msiexec.exe', 'conhost.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe'}
                    installer = any(part in path.stem.lower() for part in ('installer', 'setup', 'unins'))
                    if not installer and path.name.lower() not in excluded and path.suffix.lower() == '.exe' and path.is_file():
                        launch = path
                        if path.name.casefold() == 'steamwebhelper.exe':
                            for parent in list(path.parents)[:8]:
                                if (parent / 'steam.exe').is_file():
                                    launch = parent / 'steam.exe'
                                    break
                        result.append({'name': launch.stem, 'path': str(path), 'launch_path': str(launch), 'hwnd': int(hwnd)})
            except (OSError, ValueError):
                pass
            finally:
                kernel.CloseHandle(handle)
            return True
        user.EnumWindows.argtypes = [callback_type, W.LPARAM]
        user.EnumWindows(collect, 0)
        return result

    def activate(self, path):
        matches = [row for row in self.windows() if os.path.normcase(row.get('launch_path', row['path'])) == os.path.normcase(str(path))]
        if not matches: return False
        user = ctypes.WinDLL('user32')
        user.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
        user.SetForegroundWindow.argtypes = [W.HWND]
        hwnd = matches[0]['hwnd']
        user.ShowWindow(hwnd, 9)
        return bool(user.SetForegroundWindow(hwnd))

    def launch(self, value):
        os.startfile(value)

    def desktop(self):
        import comtypes
        from comtypes.client import CreateObject
        comtypes.CoInitialize()
        shell = None
        try:
            shell = CreateObject('Shell.Application', dynamic=True)
            shell.MinimizeAll()  # Idempotent, unlike a Win+D toggle.
            shell = None
        except Exception:
            raise RuntimeError('Не удалось показать рабочий стол') from None
        finally:
            shell = None
            comtypes.CoUninitialize()

    def lock(self):
        if not ctypes.WinDLL('user32').LockWorkStation(): raise RuntimeError('Не удалось заблокировать экран')

    def power(self, action):
        if action not in ('shutdown', 'restart'): raise ValueError('Неизвестное действие питания')
        path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/shutdown.exe'
        # /t > 0 implies force; use /t 0 and never /f.
        result = subprocess.run([str(path), '/s' if action == 'shutdown' else '/r', '/t', '0'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise RuntimeError('Windows отклонил запрос питания')
