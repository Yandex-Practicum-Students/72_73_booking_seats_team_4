FROM redis:8.8.2-alpine3.23

ENV REDIS_PASSWORD="change_me_in_prod" \
    REDIS_PORT=6379

CMD ["sh", "-c", "redis-server --requirepass \"$REDIS_PASSWORD\" --maxmemory 268435456 --maxmemory-policy volatile-lru --save '' --loglevel debug --port \"$REDIS_PORT\""]
