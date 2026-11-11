import json
from pathlib import Path
import re
import pytest
from eidos.core import i18n
from eidos.ui.localized import QLabel, QLineEdit
from test_ui import app


def test_all_catalogues_have_identical_keys_and_preserve_placeholders():
    catalogs = {code: json.loads((i18n.DIRECTORY / f'{code}.json').read_text(encoding='utf-8'))
                for code in i18n.LANGUAGES}
    for code, catalog in catalogs.items():
        assert catalog.keys() == catalogs['ru'].keys(), code
        for ident, source in catalogs['ru'].items():
            assert sorted(re.findall(r'\{\d+\}', catalog[ident])) == sorted(re.findall(r'\{\d+\}', source)), (code, ident)
            assert 'ZXPH' not in catalog[ident] and 'ZXNL' not in catalog[ident], (code, ident)


@pytest.mark.parametrize('language', ['en', 'ky', 'uz', 'kk'])
def test_dynamic_command_limit_is_retained_in_each_language(language):
    try:
        i18n.set_language(language)
        assert '37' in i18n.tr('Eidos готов. Активация включается отдельно. Лимит команды — 37 секунд.')
    finally:
        i18n.set_language('ru')


def test_existing_widget_retranslates_without_touching_user_text(app):
    label = QLabel('Настройки')
    user = QLineEdit()
    user.setText('Главная')
    try:
        i18n.set_language('en')
        assert label.text() == 'Settings'
        assert user.text() == 'Главная'
        i18n.set_language('ru')
        assert label.text() == 'Настройки'
    finally:
        i18n.set_language('ru')


def test_missing_key_falls_back_to_russian(monkeypatch):
    i18n.load()
    ident = i18n.key('Настройки')
    catalog = dict(i18n._catalogs['en'])
    catalog.pop(ident)
    monkeypatch.setitem(i18n._catalogs, 'en', catalog)
    try:
        i18n.set_language('en')
        assert i18n.t(ident) == 'Настройки'
    finally:
        i18n.set_language('ru')


def test_navigation_spacing_and_composite_chrome_translate(app):
    from eidos.ui.localized import QComboBox
    device = QComboBox()
    device.addRawItem('Набор микрофонов (Realtek)', 2)
    try:
        i18n.set_language('en')
        assert i18n.tr('  Настройки') == '  Settings'
        assert i18n.tr('Микрофон выключен · Перетащите персонажа / меню правой кнопкой') == (
            'Microphone off · Drag the character / right-click menu')
        assert device.currentText() == 'Набор микрофонов (Realtek)'
    finally:
        i18n.set_language('ru')
