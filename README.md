# Бронирование мест в кафе

Backend API для выбора кафе, просмотра меню и акций, бронирования столов и управления заведениями. Проект разработан командой студентов Яндекс Практикума.

## Возможности

- регистрация и авторизация пользователей по JWT;
- роли `ADMIN`, `MANAGER` и `USER` с разграничением прав;
- управление кафе, столами, временными слотами, блюдами и акциями;
- создание, просмотр и изменение бронирований;
- загрузка изображений JPG и PNG размером до 5 МБ с сохранением в JPG;
- email уведомления персоналу и напоминания клиентам;
- фоновые задачи и повторная отправка уведомлений через Celery и RabbitMQ;
- кэширование и хранение активных JWT сессий в Redis;
- интерактивная документация OpenAPI.

Все прикладные маршруты опубликованы с префиксом `/api/v1`.

## Запущенный проект

- [API](https://bookingseatsteam4.myddns.me/)
- [Swagger UI](https://bookingseatsteam4.myddns.me/docs)
- [ReDoc](https://bookingseatsteam4.myddns.me/redoc)
- [Статическая документация](https://yandex-practicum-students.github.io/72_73_booking_seats_team_4/)

## Быстрый запуск через Docker Compose

Понадобятся Git и Docker с поддержкой Compose.

```bash
git clone https://github.com/Yandex-Practicum-Students/72_73_booking_seats_team_4.git
cd 72_73_booking_seats_team_4
cp infra/.env.example infra/.env
```

Заполните значения в `infra/.env`. Для `JWT_SECRET` используйте случайную строку длиной не менее 32 символов. Файл `.env` нельзя добавлять в Git.

```bash
cd infra
docker compose up --build
```

После запуска доступны:

- API и Swagger UI на `http://localhost:8000` и `http://localhost:8000/docs`;
- Flower на `http://localhost:5555`;
- интерфейс RabbitMQ на `http://localhost:15672`.

Compose поднимает приложение, PostgreSQL, Redis, RabbitMQ, Celery worker, Celery beat и Flower. Миграции Alembic применяются автоматически при старте контейнера приложения.

Для остановки:

```bash
docker compose down
```

Добавьте `-v`, только если вместе с контейнерами нужно удалить локальные тома с данными.

## Запуск для разработки

Проект использует Python 3.12 и [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cd src
uv run alembic upgrade head
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Для локального запуска должны быть доступны PostgreSQL, Redis и RabbitMQ, а их параметры должны быть указаны в `infra/.env`.

Также репозиторий содержит готовую конфигурацию Dev Containers. В VS Code можно выполнить команду `Dev Containers: Reopen in Container`, после чего зависимости установятся автоматически.

## Проверки

Из корня репозитория:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -t .
```

## Фоновые задачи

Celery worker обрабатывает очередь `booking_notifications`. Celery beat запускает периодическую проверку напоминаний, RabbitMQ используется как брокер, Redis участвует в кэшировании и хранении JWT сессий, а Flower позволяет наблюдать за задачами.

Параметры RabbitMQ, Redis, SMTP и Flower задаются в `infra/.env`. Для проверки worker предусмотрена задача `booking_seats.system.healthcheck`.

## Стек

- Python 3.12, FastAPI, Pydantic;
- SQLAlchemy, Alembic, PostgreSQL;
- Redis;
- Celery, RabbitMQ, Flower;
- Pillow;
- Docker и Docker Compose;
- uv, Ruff, unittest;
- GitHub Actions, Nginx, Loguru.

## Команда

- [Andrei Mezer](https://github.com/AnMezer), Team Lead, Backend Developer
- [Curiosity](https://github.com/BondarenkoMaximSergeevich), Backend Developer
- [NataEditor](https://github.com/NataEditor), Backend Developer
- [veronikaTatar](https://github.com/veronikaTatar), Backend Developer
- [Roman Papenov](https://github.com/roman82direct), Backend Developer
- [KvazyModa00](https://github.com/KvazyModa00), Backend Developer
- [GalinaLody](https://github.com/GalinaLody), Backend Developer
- [Alexei](https://github.com/Alek20s), Backend Developer
