# Асинхронный голос: Vosk, Gemini, Edge

Обновление 14 октября: аудио переведено в память. Текущий голосовой контур
описан в [pcm-voice-report.md](pcm-voice-report.md); анализ ниже отражает исходное состояние.

## Что установлено по коду Eidos

Гипотеза «весь проект синхронно блокирует GUI» не подтверждается:
VoiceWorker, AgentWorker и _SynthesisWorker работают в отдельных QThread;
QtMultimedia.play запускает асинхронное воспроизведение. asyncio.run в TTS
вызывается в synthesis worker, а не в главном Qt-потоке.

Найдены потенциальные причины пауз: SpeechQueue._start_next запрещает синтез
следующего предложения, пока _playing=True. Следующее сетевое TTS начинается
после окончания звука, поэтому каждый сетевой round trip становится слышимой
паузой. GUI callback AudioPlayback._audio_buffer вычисляет numpy RMS; при
декодировании, большом числе сигналов и анимаций это требует профилирования.
Загрузка/импорты QtMultimedia при первом play тоже выполняются из GUI.
Это анализ кода, а не измеренная причина каждого пользовательского фриза.
Новый пример не объявляется исправлением всего существующего playback.

Длительный requests.post, time.sleep, recognizer.AcceptWaveform или runAndWait
в GUI останавливает обработку событий, перерисовку, клики и таймеры.
Обычный blocking вызов внутри async def блокирует asyncio тоже: await не
превращает синхронную библиотеку в асинхронную. QThread/to_thread снимают такую
блокировку с GUI, но не убирают сетевую задержку и конкуренцию за CPU/GIL.

## Схема для PyQt6

GUI: QApplication.exec, widgets и QAudioSink в основном потоке.
STT: один worker/QThread, ограниченная очередь PCM, один Vosk Model.
Сеть: один долгоживущий asyncio loop в отдельном потоке, один client.aio.
Речь: очередь максимум несколько предложений, один playback, один synthesis;
prefetch максимум одного следующего PCM-буфера во время текущего воспроизведения.
Готовый текст/PCM/ошибки возвращаются в GUI через queued Qt signals.
Для запуска coroutine из GUI использовать asyncio.run_coroutine_threadsafe;
не вызывать future.result, thread.join или asyncio.run в обработчике кнопки.
Остановка: отменить asyncio tasks, выставить threading.Event для STT,
остановить playback, дождаться worker.finished асинхронно, затем закрыть окно.
Отмена coroutine не останавливает нативный to_thread-вызов сама по себе.

Для CustomTkinter аналогичное разделение; изменять UI только через root.after.
Не создавайте новое аудиоустройство/модель на каждый callback.
Для прерывания речи пользователем нужен отдельный barge-in/VAD и подавление
эхо. Пример сознательно использует half-duplex: слушает только между ответами.

## Рабочий каркас

Файл: `examples/async_voice_gemini.py`. Это самостоятельный консольный процесс,
его asyncio.run нельзя вставлять в основной Qt event loop. Внутри:

1. Model загружается один раз через to_thread, без скачивания.
2. RawInputStream и AcceptWaveform выполняются в executor, PCM16/16k/20ms.
   Если устройство не поддерживает 16k, требуется выбрать другое или добавить
   преобразование частоты в worker. Переполнение отвергает запись.
3. Внешний запрос через client.aio с timeout25s, max_output_tokens180,
   thinking_budget0; ответ нормализуется и ограничивается двумя предложениями.
4. Edge Communicate.stream — await, timeout45s. Сетевые байты декодируются
   miniaudio в памяти; нативный PCM-проигрыватель закрывается при отмене.
5. Микрофон закрыт на время запроса/озвучки. Одновременно только один запрос;
   очереди старых записей нет. Ctrl+C выставляет Event, закрывает HTTP-клиент,
   останавливает проигрыватель. Нативная загрузка модели не прерывается мгновенно.

Gemini и Edge получают текст после общего фильтра секретов. Транскрипт,
ответ, API key и vendor exception body не логируются. В Gemini не отправляется
личная SQLite-память. Ключ читается программой только при явном запуске примера.
Пример не выполняет инструменты/команды Windows и не меняет провайдер основного Eidos.

## Подготовка и запуск

Python 3.11/3.12, существующая .venv:

```powershell
.\.venv\Scripts\python.exe -m pip install -r examples\requirements-gemini.txt
```

FFmpeg и ffplay больше не требуются; miniaudio указан в зависимостях примера.
Для Gemini требуется отдельно подготовить SDK и доступ к API. Ключ задайте только в локальном окружении запуска; не
вставляйте его в исходники/чат/коммиты. После задания GEMINI_API_KEY:

```powershell
.\.venv\Scripts\python.exe examples\async_voice_gemini.py --vosk-model .cache\voice-models\vosk-model-small-ru-0.22
```

Не запускайте пример параллельно с голосовым режимом Eidos: он тоже использует
микрофон. `--device N` выбирает input device, `--model ID` задаёт модель.

gemini-2.5-flash указан по запросу. По текущей странице Google доступ к 2.5
ограничен ранее использовавшими их пользователями; новый проект может получить
ошибку доступа. Модель можно явно заменить параметром --model; silent fallback
и скрытые повторные платные запросы не предусмотрены. ThinkingConfig для другой
модели следует проверить в её документации.

Edge — удобный онлайн вариант, но задержка сети не гарантирована. Windows SAPI
работает локально; существующий SapiTTS уже создаёт COM-объекты в своём worker.
pyttsx3.runAndWait также нужно держать в одном выделенном потоке; Silero требует
локальной модели и отдельного worker, его скорость надо измерить на вашей системе.
Пример сначала получает короткий ответ целиком в RAM, а затем начинает звук; настоящий
streaming TTS требует потокового декодера, sample-rate handling и backpressure.

## Проверка и источники

Модульные проверки не обращаются в сеть/микрофон: async запрос уступает event loop,
секрет не попадает в SDK, отмена TTS закрывает сетевой поток, отмена playback
освобождает нативное устройство. Живой Gemini не проверен; проверка Edge-TTS
14 октября получила HTTP 403. Подробности в отчёте PCM.
Статические проверки выполнены compileall; отдельные тесты в
`tests/test_async_voice_gemini_example.py`.

Context7: resolve /googleapis/python-genai, затем query для async generate_content,
HttpOptions и aclose. Первичный общий resolve не нашёл Python SDK; повтор по точному
имени репозитория нашёл его.

Официальные источники:
- https://github.com/googleapis/python-genai
- https://ai.google.dev/gemini-api/docs/deprecations
- https://github.com/rany2/edge-tts/blob/master/examples/async_audio_gen_with_predefined_voice.py
- https://alphacephei.com/vosk/

Измерять отдельно: GUI timer drift, время первой загрузки, конец фразы→STT,
LLM first-token/complete, TTS first-audio/complete и start playback. Последовательные
измерения нужны для анализа; p50/p95 не складываются как математическая гарантия
сквозного p95. Само наличие async не обещает мгновенный ответ.
