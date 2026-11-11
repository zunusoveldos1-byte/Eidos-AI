"""Small reviewed Qt standard-button catalogue (no translated user content)."""
STRINGS = {
    'ru': {'Yes': 'Да', 'No': 'Нет', 'Cancel': 'Отмена', 'OK': 'ОК', 'Save': 'Сохранить',
           'Open': 'Открыть', 'Close': 'Закрыть', 'Apply': 'Применить', 'Reset': 'Сбросить',
           'Help': 'Справка', 'Discard': 'Не сохранять', 'All Files (*)': 'Все файлы (*)'},
    'en': {},
    'ky': {'Yes': 'Ооба', 'No': 'Жок', 'Cancel': 'Жокко чыгаруу', 'OK': 'Макул', 'Save': 'Сактоо',
           'Open': 'Ачуу', 'Close': 'Жабуу', 'Apply': 'Колдонуу', 'Reset': 'Калыбына келтирүү',
           'Help': 'Жардам', 'Discard': 'Сактабоо', 'All Files (*)': 'Бардык файлдар (*)'},
    'uz': {'Yes': 'Ha', 'No': 'Yo‘q', 'Cancel': 'Bekor qilish', 'OK': 'OK', 'Save': 'Saqlash',
           'Open': 'Ochish', 'Close': 'Yopish', 'Apply': 'Qo‘llash', 'Reset': 'Tiklash',
           'Help': 'Yordam', 'Discard': 'Saqlamaslik', 'All Files (*)': 'Barcha fayllar (*)'},
    'kk': {'Yes': 'Иә', 'No': 'Жоқ', 'Cancel': 'Болдырмау', 'OK': 'Жарайды', 'Save': 'Сақтау',
           'Open': 'Ашу', 'Close': 'Жабу', 'Apply': 'Қолдану', 'Reset': 'Қалпына келтіру',
           'Help': 'Көмек', 'Discard': 'Сақтамау', 'All Files (*)': 'Барлық файлдар (*)'},
}

# Qt file/text menus use these stable source keys even with a native locale.
_MENU = {
    'ru': ('Имя', 'Размер', 'Тип', 'Дата изменения', 'Имя файла:', 'Тип файлов:', 'Папка:', 'Папка:',
           'Назад', 'Вперёд', 'На уровень выше', 'Создать папку', 'Список', 'Подробности', 'Показать скрытые файлы',
           'Компьютер', 'Домашняя папка', 'Новая папка', 'Выбрать', 'Папка', 'Вырезать', 'Копировать', 'Вставить',
           'Удалить', 'Переименовать', 'Выделить всё', 'Отменить', 'Повторить', 'Сегодня', 'Предыдущий месяц', 'Следующий месяц'),
    'ky': ('Аты', 'Көлөмү', 'Түрү', 'Өзгөртүлгөн күнү', 'Файлдын аты:', 'Файлдын түрлөрү:', 'Папка:', 'Папка:',
           'Артка', 'Алга', 'Жогорку папка', 'Папка түзүү', 'Тизме', 'Толук маалымат', 'Жашыруун файлдарды көрсөтүү',
           'Компьютер', 'Үй папкасы', 'Жаңы папка', 'Тандоо', 'Папка', 'Кесүү', 'Көчүрүү', 'Коюу',
           'Өчүрүү', 'Атын өзгөртүү', 'Баарын тандоо', 'Артка кайтаруу', 'Кайталоо', 'Бүгүн', 'Мурунку ай', 'Кийинки ай'),
    'uz': ('Nomi', 'Hajmi', 'Turi', 'O‘zgartirilgan sana', 'Fayl nomi:', 'Fayl turlari:', 'Jild:', 'Jild:',
           'Orqaga', 'Oldinga', 'Yuqori jild', 'Jild yaratish', 'Ro‘yxat', 'Tafsilotlar', 'Yashirin fayllarni ko‘rsatish',
           'Kompyuter', 'Uy jildi', 'Yangi jild', 'Tanlash', 'Jild', 'Kesish', 'Nusxalash', 'Joylashtirish',
           'O‘chirish', 'Nomini o‘zgartirish', 'Barchasini tanlash', 'Bekor qilish', 'Takrorlash', 'Bugun', 'Oldingi oy', 'Keyingi oy'),
    'kk': ('Атауы', 'Өлшемі', 'Түрі', 'Өзгертілген күні', 'Файл атауы:', 'Файл түрлері:', 'Қалта:', 'Қалта:',
           'Артқа', 'Алға', 'Жоғарғы қалта', 'Қалта жасау', 'Тізім', 'Толық мәлімет', 'Жасырын файлдарды көрсету',
           'Компьютер', 'Үй қалтасы', 'Жаңа қалта', 'Таңдау', 'Қалта', 'Қиып алу', 'Көшіру', 'Қою',
           'Жою', 'Атауын өзгерту', 'Барлығын таңдау', 'Болдырмау', 'Қайталау', 'Бүгін', 'Алдыңғы ай', 'Келесі ай'),
}
_KEYS = ('Name', 'Size', 'Type', 'Date Modified', 'File name:', 'Files of type:', 'Look in:', 'Directory:',
         'Back', 'Forward', 'Parent Directory', 'Create New Folder', 'List View', 'Detail View', 'Show hidden files',
         'Computer', 'Home', 'New Folder', 'Choose', 'Folder', 'Cut', 'Copy', 'Paste', 'Delete', 'Rename',
         'Select All', 'Undo', 'Redo', 'Today', 'Go back one month', 'Go forward one month')
for _language, _values in _MENU.items():
    STRINGS[_language].update(zip(_KEYS, _values))
