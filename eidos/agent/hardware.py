"""Local measurements; excludes serials, UUIDs and network identifiers."""
import json
from pathlib import Path
import shutil
import subprocess


def ollama_rss_mib():
    """Sum working sets of the daemon and its real backend descendants."""
    import psutil
    processes = {}
    for process in psutil.process_iter(['name']):
        try:
            if 'ollama' in (process.info['name'] or '').lower():
                processes[process.pid] = process
                for child in process.children(recursive=True):
                    processes[child.pid] = child
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    rss = 0
    for process in processes.values():
        try:
            rss += process.memory_info().rss
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            pass
    return round(rss/2**20,2)


def diagnose():
    import psutil
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage(Path.cwd().anchor)
    result = {'ram_total_gib': round(ram.total / 2**30, 2), 'ram_available_gib': round(ram.available / 2**30, 2),
              'disk_free_gib': round(disk.free / 2**30, 2), 'cpu_threads': psutil.cpu_count(), 'gpu': []}
    flags = subprocess.CREATE_NO_WINDOW
    command = ('Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json')
    try:
        output = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, timeout=15, creationflags=flags)
        result['cpu'] = json.loads(output.stdout.decode('utf-8-sig'))
    except Exception:
        result['cpu'] = 'CIM недоступен'
    try:
        output = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv,noheader,nounits'], capture_output=True, timeout=10, creationflags=flags)
        for line in output.stdout.decode().splitlines():
            name, total, free, driver = [v.strip() for v in line.split(',')]
            result['gpu'].append({'name': name, 'vram_total_mib': int(total), 'vram_free_mib': int(free), 'driver': driver})
        result['gpu_acceleration'] = bool(result['gpu'])
    except Exception:
        result['gpu_acceleration'] = False
    try:
        cmd = 'Get-CimInstance Win32_VideoController | Select-Object Name | ConvertTo-Json'
        output = subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, timeout=15, creationflags=flags)
        result['display_adapters'] = json.loads(output.stdout.decode('utf-8-sig'))
    except Exception:
        result['display_adapters'] = 'CIM недоступен'
    return result
