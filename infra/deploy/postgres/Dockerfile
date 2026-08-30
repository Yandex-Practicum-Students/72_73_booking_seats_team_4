FROM postgres:17-alpine

CMD ["postgres", "-c", "max_connections=100", "-c", "shared_buffers=256MB", "-c", "effective_cache_size=768MB", "-c", "maintenance_work_mem=64MB", "-c", "checkpoint_completion_target=0.7", "-c", "wal_buffers=16MB", "-c", "default_statistics_target=100", "-c", "logging_collector=on", "-c", "log_directory=/logs", "-c", "log_filename=postgresql.log"]
