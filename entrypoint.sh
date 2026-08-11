#!/bin/bash

while ! nc -z $POSTGRES_SERVER $POSTGRES_PORT; do
  echo "Waiting for postgres to start..."
  sleep 3
done
echo 'Postgres started'

alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000
