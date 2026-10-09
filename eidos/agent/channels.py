"""Official bot REST adapters; allowlists are mandatory, attachments disabled."""
from dataclasses import dataclass
from .providers import request_json
from .harness import Tool, ToolResult
from .memory import has_secret


@dataclass(frozen=True)
class Incoming:
    channel: str
    user: str
    target: str
    ident: str
    text: str


class BotAdapter:
    def __init__(self, kind, settings, secrets):
        if kind not in ('telegram', 'discord'):
            raise ValueError('Неизвестный канал')
        self.kind, self.settings, self.secrets = kind, settings, secrets
        self.offset = 0
        self.after = {}

    def api(self, path, *, body=None, context=None):
        token = self.secrets.get(self.kind)
        if not token:
            raise ValueError('Токен бота не задан')
        if self.kind == 'telegram':
            result = request_json('POST', 'https://api.telegram.org/bot' + token + '/' + path, body=body or {}, context=context)
            if not result.get('ok'):
                raise RuntimeError('Telegram отклонил запрос')
            return result['result']
        return request_json('POST' if body is not None else 'GET', 'https://discord.com/api/v10/' + path,
                            headers={'Authorization': 'Bot ' + token}, body=body, context=context)

    def test(self, context):
        result = self.api('getMe' if self.kind == 'telegram' else 'users/@me', context=context)
        if not result.get('is_bot', result.get('bot', False)):
            raise ValueError('Поддерживаются только официальные bot tokens')
        return self.kind + ': bot API ответил успешно.'

    def allowed(self, user, channel):
        users = getattr(self.settings, self.kind + '_users')
        channels = getattr(self.settings, self.kind + '_channels')
        return str(user) in users and str(channel) in channels

    def poll(self, context):
        result = []
        if not getattr(self.settings, self.kind + '_enabled'):
            return result
        if self.kind == 'telegram':
            updates = self.api('getUpdates', body={'offset': self.offset, 'timeout': 0, 'limit': 20, 'allowed_updates': ['message']}, context=context)
            for update in updates:
                self.offset = max(self.offset, int(update['update_id']) + 1)
                msg = update.get('message', {})
                user, channel = str(msg.get('from', {}).get('id', '')), str(msg.get('chat', {}).get('id', ''))
                text = msg.get('text', '')
                if self.allowed(user, channel) and 0 < len(text) <= 2000 and not has_secret(text) and not msg.get('from', {}).get('is_bot'):
                    result.append(Incoming(self.kind, user, channel, str(update['update_id']), text))
        else:
            for channel in self.settings.discord_channels:
                context.check()
                last = self.after.get(channel)
                path = f'channels/{channel}/messages?limit=20' + ('&after=' + last if last else '')
                messages = self.api(path, context=context)
                if not isinstance(messages, list):
                    raise ValueError('Неверный ответ Discord')
                if not messages:
                    continue
                self.after[channel] = max((msg['id'] for msg in messages), key=int)
                if last is None:
                    continue  # Baseline: don't replay old channel history on enable.
                for msg in sorted(messages, key=lambda m: int(m['id'])):
                    user = str(msg.get('author', {}).get('id', ''))
                    text = msg.get('content', '')
                    if self.allowed(user, channel) and not msg.get('author', {}).get('bot') and not msg.get('attachments') and 0 < len(text) <= 2000 and not has_secret(text):
                        result.append(Incoming(self.kind, user, channel, str(msg['id']), text))
        return result

    def send(self, target, text, context):
        if not 0 < len(text) <= 2000 or has_secret(text, context.secret_values):
            raise ValueError('Ответ содержит секрет или превышает 2000 символов')
        if target not in getattr(self.settings, self.kind + '_channels'):
            raise PermissionError('Получатель отсутствует в разрешённых каналах')
        if self.kind == 'telegram':
            response = self.api('sendMessage', body={'chat_id': target, 'text': text}, context=context)
            verified = 'message_id' in response
        else:
            response = self.api(f'channels/{target}/messages', body={'content': text, 'allowed_mentions': {'parse': []}}, context=context)
            verified = bool(response.get('id'))
        return ToolResult('Bot API подтвердил отправку.' if verified else 'Отправка не подтверждена.', verified)


def reply_tool(adapter, incoming, memory):
    def send(args, context):
        ident = f'{incoming.channel}:{incoming.target}:{incoming.ident}'
        if not memory.reserve_delivery(ident):
            raise PermissionError('Повтор отправки заблокирован: эта доставка уже начиналась')
        try:
            result = adapter.send(incoming.target, args['text'], context)
            memory.delivery_status(ident, 'sent' if result.verified else 'unknown')
            return result
        except Exception:
            memory.delivery_status(ident, 'unknown')
            raise
    return Tool('channel_reply', f'Отправить ответ в {incoming.channel}, канал {incoming.target}, пользователь {incoming.user}',
                {'text': {'type': 'string', 'maxLength': 2000}}, send, 'channel.reply', confirmation=True)
