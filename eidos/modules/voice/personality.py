"""Conversational wording; only evidence may say an action succeeded."""
import random

STYLE_INSTRUCTIONS = {
    'neutral': 'Характер ответа: нейтральный, краткий и спокойный.',
    'friendly': 'Характер ответа: дружелюбный и тёплый; короткие естественные реплики, без преувеличений.',
    'energetic': 'Характер ответа: энергичный и бодрый; короткие реплики, без выдуманного успеха действий.',
}


def verified_reply(text, style):
    choices = {'neutral': ('',), 'friendly': ('Хорошо. ', 'Пожалуйста. ', ''),
               'energetic': ('Так точно, капитан. ', 'Есть! ', '')}
    return random.choice(choices.get(style, ('',))) + text


def listening_reply(style, name='', *, use_name=False):
    if name and use_name:
        return 'Слушаю вас, ' + name
    return random.choice({'neutral': ('Слушаю',), 'friendly': ('Слушаю вас', 'Я на связи'),
                          'energetic': ('Слушаю, капитан', 'Готов к команде')}.get(style, ('Слушаю',)))


def speech_rate(config):
    offset = {'neutral': 0, 'friendly': -3, 'energetic': 6}.get(getattr(config, 'communication_style', 'neutral'), 0)
    return max(-50, min(100, getattr(config, 'tts_rate', 0) + offset))
