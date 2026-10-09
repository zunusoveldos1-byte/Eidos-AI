"""Local Windows OCR and bounded online translation requests."""
import asyncio
from dataclasses import dataclass
import json
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PyQt6.QtCore import QBuffer, QIODevice, QRectF, Qt


@dataclass
class TextLine:
    text: str
    rect: QRectF
    translation: str = ''


class WindowsOCR:
    @staticmethod
    def available() -> bool:
        if sys.platform != 'win32':
            return False
        try:
            from winrt.windows.media.ocr import OcrEngine
            return bool(OcrEngine.available_recognizer_languages)
        except ImportError:
            return False

    def recognize(self, image, source='auto') -> list[TextLine]:
        from winrt.runtime import ApartmentType, init_apartment, uninit_apartment
        init_apartment(ApartmentType.MULTI_THREADED)
        try:
            return asyncio.run(asyncio.wait_for(self._recognize(image, source), timeout=20))
        finally:
            uninit_apartment()

    async def _recognize(self, image, source):
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, BitmapAlphaMode
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import InMemoryRandomAccessStream, DataWriter

        engine = (OcrEngine.try_create_from_user_profile_languages() if source == 'auto'
                  else OcrEngine.try_create_from_language(Language(source)))
        if engine is None:
            raise RuntimeError('Установите OCR для исходного языка в настройках языков Windows.')
        original_width = image.width()
        maximum = OcrEngine.max_image_dimension
        if max(image.width(), image.height()) > maximum:
            image = image.scaled(maximum, maximum, Qt.AspectRatioMode.KeepAspectRatio)
        scale = original_width / image.width()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(bytes(buffer.data()))
        await writer.store_async()
        writer.detach_stream()
        writer.close()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_converted_async(BitmapPixelFormat.BGRA8, BitmapAlphaMode.PREMULTIPLIED)
        try:
            result = await engine.recognize_async(bitmap)
            lines = []
            for line in result.lines:
                rect = QRectF()
                for word in line.words:
                    box = word.bounding_rect
                    rect = rect.united(QRectF(box.x, box.y, box.width, box.height))
                if line.text.strip() and not rect.isEmpty():
                    lines.append(TextLine(line.text, QRectF(rect.x() * scale, rect.y() * scale,
                                                          rect.width() * scale, rect.height() * scale)))
            return lines
        finally:
            bitmap.close()
            stream.close()


class OnlineTranslator:
    """Google's public translation endpoint; no API key, timeout on every request."""
    def translate(self, text: str, source: str, target: str, cancel=None, progress=None) -> str:
        source = {'zh-Hans': 'zh-CN'}.get(source, source)
        if source == target:
            return text
        # OCR lines are short; bound oversized lines instead of sending truncated text.
        chunks = [text[i:i + 1500] for i in range(0, len(text), 1500)]
        output = []
        for index, chunk in enumerate(chunks, 1):
            if cancel is not None and cancel.is_set():
                raise InterruptedError('Перевод отменён')
            if progress:
                progress(f'Перевод текста: часть {index} из {len(chunks)}')
            query = urlencode({'client': 'gtx', 'sl': source, 'tl': target, 'dt': 't', 'q': chunk})
            request = Request('https://translate.googleapis.com/translate_a/single?' + query,
                              headers={'User-Agent': 'Eidos/0.1'})
            with urlopen(request, timeout=15) as response:
                data = json.load(response)
            translated = ''.join(part[0] for part in data[0] if part and part[0])
            if not translated:
                raise RuntimeError('Сервис перевода вернул пустой ответ.')
            output.append(translated)
        return ''.join(output)
