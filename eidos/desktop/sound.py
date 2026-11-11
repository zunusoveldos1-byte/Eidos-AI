"""A fresh Core Audio endpoint for every command; no stale device cache."""
from eidos.agent.harness import ToolResult


def change(args, context, mute=False, status=False):
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        if mute:
            endpoint.SetMute(int(args['enabled']), None)
            actual = bool(endpoint.GetMute())
            return ToolResult('Звук ' + ('выключен.' if actual else 'включён.'), actual == args['enabled'])
        current = float(endpoint.GetMasterVolumeLevelScalar()) * 100
        if status:
            return ToolResult(f'Громкость {round(current)} процентов' + ('; звук выключен' if endpoint.GetMute() else ''))
        requested = args['value'] if args['mode'] == 'set' else current + args['value'] * (1 if args['mode'] == 'up' else -1)
        requested = min(100, max(0, requested))
        endpoint.SetMasterVolumeLevelScalar(requested / 100, None)
        actual = float(endpoint.GetMasterVolumeLevelScalar()) * 100
        return ToolResult(f'Громкость {round(actual)} процентов', abs(actual - requested) < 1)
    except Exception:
        raise RuntimeError('Аудиоустройство недоступно. Проверьте устройство вывода Windows и зависимости Core Audio.') from None
    finally: comtypes.CoUninitialize()
