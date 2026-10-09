"""Fast system OCR, with local Tesseract language models for other scripts."""
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage

from eidos.core.config import data_dir
from .engine import TextLine, WindowsOCR

# The Windows wheel installs Python signal handlers on import: initialize it on
# the GUI/main thread, before recognition workers start.
os.environ.setdefault('OMP_THREAD_LIMIT', '1')
try:
    import tesserocr
except ImportError:
    tesserocr = None


# Google language code, Tesseract model, visible language name.
LANGUAGES = [
    ('ru', 'rus', 'Русский'), ('en', 'eng', 'Английский'), ('ky', 'kir', 'Кыргызский'),
    ('kk', 'kaz', 'Казахский'), ('uz', 'uzb', 'Узбекский'), ('de', 'deu', 'Немецкий'),
    ('fr', 'fra', 'Французский'), ('es', 'spa', 'Испанский'), ('it', 'ita', 'Итальянский'),
    ('pt', 'por', 'Португальский'), ('tr', 'tur', 'Турецкий'), ('uk', 'ukr', 'Украинский'),
    ('be', 'bel', 'Белорусский'), ('pl', 'pol', 'Польский'), ('cs', 'ces', 'Чешский'),
    ('sk', 'slk', 'Словацкий'), ('bg', 'bul', 'Болгарский'), ('sr', 'srp', 'Сербский'),
    ('hr', 'hrv', 'Хорватский'), ('sl', 'slv', 'Словенский'), ('ro', 'ron', 'Румынский'),
    ('hu', 'hun', 'Венгерский'), ('el', 'ell', 'Греческий'), ('nl', 'nld', 'Нидерландский'),
    ('sv', 'swe', 'Шведский'), ('no', 'nor', 'Норвежский'), ('da', 'dan', 'Датский'),
    ('fi', 'fin', 'Финский'), ('et', 'est', 'Эстонский'), ('lv', 'lav', 'Латышский'),
    ('lt', 'lit', 'Литовский'), ('zh-CN', 'chi_sim', 'Китайский (упрощённый)'),
    ('zh-TW', 'chi_tra', 'Китайский (традиционный)'), ('ja', 'jpn', 'Японский'),
    ('ko', 'kor', 'Корейский'), ('ar', 'ara', 'Арабский'), ('fa', 'fas', 'Персидский'),
    ('he', 'heb', 'Иврит'), ('hi', 'hin', 'Хинди'), ('bn', 'ben', 'Бенгальский'),
    ('ur', 'urd', 'Урду'), ('ta', 'tam', 'Тамильский'), ('te', 'tel', 'Телугу'),
    ('mr', 'mar', 'Маратхи'), ('ne', 'nep', 'Непальский'), ('gu', 'guj', 'Гуджарати'),
    ('th', 'tha', 'Тайский'), ('vi', 'vie', 'Вьетнамский'), ('id', 'ind', 'Индонезийский'),
    ('ms', 'msa', 'Малайский'), ('tl', 'fil', 'Филиппинский'), ('hy', 'hye', 'Армянский'),
    ('ka', 'kat', 'Грузинский'), ('az', 'aze', 'Азербайджанский'), ('mn', 'mon', 'Монгольский'),
    ('af', 'afr', 'Африкаанс'), ('sq', 'sqi', 'Албанский'), ('eu', 'eus', 'Баскский'),
    ('ca', 'cat', 'Каталанский'), ('is', 'isl', 'Исландский'), ('ga', 'gle', 'Ирландский'),
    ('cy', 'cym', 'Валлийский'), ('sw', 'swa', 'Суахили'), ('km', 'khm', 'Кхмерский'),
    ('lo', 'lao', 'Лаосский'), ('my', 'mya', 'Бирманский'), ('si', 'sin', 'Сингальский'),
]
MODELS = {code: model for code, model, _ in LANGUAGES}
SCRIPTS = {'Latin': 'Latin', 'Cyrillic': 'Cyrillic', 'Arabic': 'Arabic', 'Han': 'HanS',
           'Japanese': 'Japanese', 'Hangul': 'Hangul', 'Devanagari': 'Devanagari',
           'Bengali': 'Bengali', 'Tamil': 'Tamil', 'Telugu': 'Telugu', 'Thai': 'Thai',
           'Hebrew': 'Hebrew', 'Greek': 'Greek', 'Armenian': 'Armenian', 'Georgian': 'Georgian',
           'Khmer': 'Khmer', 'Lao': 'Lao', 'Myanmar': 'Myanmar', 'Sinhala': 'Sinhala'}


def ensure_model(name, progress=None):
    allowed = set(MODELS.values()) | set(SCRIPTS.values()) | {'osd'}
    if name not in allowed:
        raise ValueError('Неизвестная OCR-модель')
    directory = data_dir() / 'ocr-models'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (name + '.traineddata')
    if target.exists():
        return directory
    if progress:
        progress('Загрузка OCR: ' + name)
    path = 'script/' + name if name in set(SCRIPTS.values()) else name
    url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{path}.traineddata'
    temporary = None
    try:
        with urlopen(url, timeout=20) as response, tempfile.NamedTemporaryFile(
                dir=directory, prefix=name + '-', suffix='.partial', delete=False) as output:
            temporary = Path(output.name)
            while chunk := response.read(128 * 1024):
                output.write(chunk)
        temporary.replace(target)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return directory


def pillow_image(image):
    from PIL import Image
    rgb = image.convertToFormat(QImage.Format.Format_RGB888)
    return Image.frombytes('RGB', (rgb.width(), rgb.height()),
        rgb.constBits().asstring(rgb.sizeInBytes()), 'raw', 'RGB', rgb.bytesPerLine(), 1)


class ScreenOCR:
    def __init__(self):
        self.system = WindowsOCR()
        self.script = None
        self.progress = None

    def recognize(self, image, source='auto'):
        if source != 'auto':
            try:
                return self.system.recognize(image, source)
            except (ImportError, RuntimeError):
                return self._tesseract(image, MODELS.get(source, 'eng'))
        self.script = self._detect_script(image)
        if self.script is None:
            try:
                return self.system.recognize(image, 'auto')
            except (ImportError, RuntimeError):
                pass
        return self._tesseract(image, SCRIPTS.get(self.script, 'Latin'), script=True)

    def _detect_script(self, image):
        try:
            if tesserocr is None:
                return None
            picture = pillow_image(image)
            picture.thumbnail((1800, 1800))
            directory = ensure_model('osd', self.progress)
            with tesserocr.PyTessBaseAPI(path=str(directory), lang='osd', psm=tesserocr.PSM.OSD_ONLY) as api:
                api.SetImage(picture)
                api.SetSourceResolution(70)
                result = api.DetectOrientationScript()
                if result and result.get('script_name') in SCRIPTS:
                    return result.get('script_name')
        except (ImportError, RuntimeError, OSError):
            return None
        return None

    def _tesseract(self, image, model, script=False):
        if tesserocr is None:
            raise RuntimeError('Не установлен многоязычный OCR. Установите зависимости проекта.')
        directory = ensure_model(model, self.progress)
        ensure_model('eng', self.progress)
        # Script models retain Latin UI alongside the selected non-Latin script.
        with tesserocr.PyTessBaseAPI(path=str(directory), lang=model + ('+eng' if model != 'eng' else ''),
                                    psm=tesserocr.PSM.SPARSE_TEXT) as api:
            api.SetImage(pillow_image(image))
            # Screen images carry no print DPI. An explicit low source resolution
            # keeps sparse UI labels from being split into individual CJK glyphs.
            api.SetSourceResolution(70)
            api.Recognize()
            # The page API applies Unicode/BiDi ordering. The low-level iterator
            # returns visual-order Arabic and inserts spaces between CJK glyphs.
            text_lines = [text.strip() for text in api.GetUTF8Text().splitlines() if text.strip()]
            iterator = api.GetIterator()
            lines = []
            if iterator is None:
                return lines
            index = 0
            while True:
                text = text_lines[index] if index < len(text_lines) else ''
                box = iterator.BoundingBox(tesserocr.RIL.TEXTLINE)
                if text and box and iterator.Confidence(tesserocr.RIL.TEXTLINE) >= 35:
                    x1, y1, x2, y2 = box
                    lines.append(TextLine(text, QRectF(x1, y1, x2 - x1, y2 - y1)))
                if not iterator.Next(tesserocr.RIL.TEXTLINE):
                    break
                index += 1
            return lines
