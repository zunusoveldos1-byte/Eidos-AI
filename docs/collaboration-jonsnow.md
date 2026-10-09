# Совместная работа с JonSnow

Общий репозиторий: https://github.com/zunusoveldos1-byte/Eidos-AI
JonSnow: https://github.com/doniadishov901-arch

## 1. Принять приглашение

Войди на GitHub под `doniadishov901-arch` и прими приглашение в collaborators
через уведомления GitHub или письмо. Для загрузки веток нужны права Write.
Если приглашения ещё нет, попроси владельца добавить этот аккаунт в
Settings → Collaborators → Add people.

## 2. Получить общую основу

Установи Git и Python 3.11 (64-bit). В PowerShell выполни:

```powershell
git clone https://github.com/zunusoveldos1-byte/Eidos-AI.git Eidos-shared
Set-Location Eidos-shared
git switch -c codex/jonsnow-import
```

Работай в новой папке `Eidos-shared`. Сохрани исходный проект у себя отдельно.
Не копируй из него `.git`, `.venv`, кеши, модели, токены и личные настройки.

## 3. Загрузить свой проект для объединения

Если это отдельное приложение или стек пока отличается, перенеси его исходники
в `contributions/jonsnow/` внутри `Eidos-shared`. Вместе с ними добавь README:
как запустить, какие зависимости нужны, что уже работает, какие модули
нужно объединить с Eidos и какие файлы являются точками входа. Исключи из Git
сборки, зависимости, секреты и большие веса моделей своего проекта.

Если это уже совместимый модуль Eidos, перенеси его в подходящую папку
`eidos/modules/` и добавь проверки в `tests/`. Перед замещением существующих
файлов сравни изменения; не заменяй весь проект целиком.

```powershell
git status --short
git add contributions/jonsnow
git diff --cached --stat
git commit -m "Add JonSnow project for integration"
git push -u origin codex/jonsnow-import
```

Команда `git add contributions/jonsnow` относится к варианту с отдельным
проектом. Для совместимого модуля укажи вместо неё конкретные изменённые
папки и файлы. Перед commit проверь, что в загрузку не попали секреты.
При первом push Git может открыть вход в GitHub через браузер.

## 4. Открыть Pull Request

Открой https://github.com/zunusoveldos1-byte/Eidos-AI/pulls и нажми New pull
request: base — `main`, compare — `codex/jonsnow-import`.
В описании укажи назначение проекта, запуск, проверки и предлагаемый способ
интеграции. Назначь `zunusoveldos1-byte` reviewer.
После этого можно сравнить проекты и согласовать объединение модулей.
Загрузка отдельного проекта сама по себе ещё не делает его частью приложения.

## 5. Проверить Eidos и продолжать работу

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m eidos
```

Для локального AI отдельно установи Ollama и модель из основного README.
Секреты и настройки создай на своём компьютере; используй `agent.example.json`
и `config.example.json` как образцы.

После слияния PR получай новую основу и создавай ветку для следующего изменения:

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/jonsnow-next-module
```

Если твой проект уже находится в другом GitHub-репозитории, приложи ссылку
к PR. Исходную историю сохрани там; для первого объединения используй копию
исходников в ветке общей основы. Не используй force push и не загружай свою
независимую историю поверх `main`.
