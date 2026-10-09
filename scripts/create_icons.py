"""Rebuild local SVG resources, using our shared 24-unit stroke grid."""
from pathlib import Path

PATHS = {
    'home': '<path d="M3 10 12 3l9 7v11H3Z"/><path d="M9 21v-7h6v7"/>',
    'mic': '<rect x="8" y="2" width="8" height="13" rx="4"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',
    'hand': '<path d="M8 13V5a1.5 1.5 0 0 1 3 0v6-8a1.5 1.5 0 0 1 3 0v8-6a1.5 1.5 0 0 1 3 0v7-4a1.5 1.5 0 0 1 3 0v7c0 4-3 7-6 7-3 0-5-2-7-5l-3-5c-1-2 1-3 2-2Z"/>',
    'languages': '<path d="M2 5h12M8 2v3m-4 3c2 4 5 6 9 8M12 5c-1 5-5 10-10 13M14 21l4-11 4 11m-7-3h6"/>',
    'settings': '<path d="m9 3 1-2h4l1 2 3 2 3 1-1 4v4l1 4-3 1-3 2-1 2h-4l-1-2-3-2-3-1 1-4v-4l-1-4 3-1Z"/><circle cx="12" cy="12" r="3.5"/>',
    'copy': '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 5V3H3v13h2"/>',
    'refresh': '<path d="M20 4v6h-6M4 20v-6h6M20 10a8 8 0 0 0-14-5M4 14a8 8 0 0 0 14 5"/>',
    'camera': '<path d="M3 6h4l2-3h6l2 3h4v15H3Z"/><circle cx="12" cy="13" r="4"/>',
    'scan': '<path d="M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6"/>',
    'monitor': '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M12 17v4m-5 0h10"/>',
    'user': '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3Z"/>',
    'chevron': '<path d="m6 9 6 6 6-6"/>',
    'arrow': '<path d="M3 12h18m-6-6 6 6-6 6"/>',
    'wave': '<path d="M3 9v6m4-10v14M12 2v20m5-16v12m4-9v6"/>',
    'list': '<path d="M8 5h13M8 12h13M8 19h13M3 5h.1M3 12h.1M3 19h.1"/>',
    'message': '<path d="M21 3H3v14h4v5l6-5h8Z"/><path d="M7 8h10M7 12h7"/>',
    'file': '<path d="M4 2h11l5 5v15H4Zm11 0v6h5M8 12h8M8 16h6"/>',
    'pinch': '<path d="m3 21 4-12 5-5 5-1c3 0 3 3 0 3l-4 1-2 3 4-2c4-2 6 2 3 4l-4 4-4 5M19 2l2-1m0 5h2"/>',
    'finger': '<path d="M9 12V3c0-3 4-3 4 0v8c3-1 7 1 7 4v2c0 4-3 6-6 6-4 0-5-2-7-5l-3-5c-1-3 2-4 5-1Z"/>',
}

if __name__ == '__main__':
    folder = Path(__file__).resolve().parents[1] / 'eidos/assets/icons'
    folder.mkdir(parents=True, exist_ok=True)
    for name, paths in PATHS.items():
        color = '#A8B7AE' if name == 'chevron' else 'currentColor'
        (folder / f'{name}.svg').write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>', encoding='utf-8')
