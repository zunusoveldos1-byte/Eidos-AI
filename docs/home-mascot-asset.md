# Ресурс для главной страницы

Выход: `eidos/assets/eidos-home.png`, прозрачный PNG RGBA. Использован встроенный ImageGen в режиме редактирования `background-extraction`, без CLI. Вход — приложенный пользователем утверждённый макет. Исходное изображение сохранено без изменения.

Задание генератору:

> Extract ONLY the exact large mascot located on the right of the screenshot into a high-resolution transparent RGBA asset for the desktop application. Preserve the mascot's identity and proportions faithfully: smooth white rounded pear-like body, black/dark emerald oval face screen, precisely two luminous mint vertical oval eyes, two small rounded feet, long curved green stem and single green leaf tilted right. Same front view and same materials, gently mint-lit edges. Remove all UI, background, particles, ground rings and cast shadow; transparent background everywhere outside mascot. Center the whole character including the entire leaf and both feet with a small 5% safe margin; no cropping, no text, no new features. Do not redesign the character. Return one isolated mascot.

Результат визуально проверен на сохранение корпуса, лица, двух глаз, двух ножек, стебля и листа. Qt подтвердил наличие alpha-канала и alpha=0 в углу. Это подготовленный по референсу растровый ресурс; генеративная обработка не гарантирует буквальное совпадение каждого исходного пикселя.
