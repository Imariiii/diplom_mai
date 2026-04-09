"""
Утилиты для работы в Docker-контейнере.

Обеспечивает прозрачную замену localhost/127.0.0.1 на host.docker.internal
при работе бэкенда внутри контейнера, чтобы подключения к БД на хост-машине
работали корректно.
"""
import os
from functools import lru_cache

_LOCALHOST_ALIASES = {"localhost", "127.0.0.1"}
_DOCKER_HOST = "host.docker.internal"


@lru_cache(maxsize=1)
def is_running_in_docker() -> bool:
    """Определить, запущен ли процесс внутри Docker-контейнера."""
    return os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")


def resolve_host(host: str) -> str:
    """
    Заменить localhost / 127.0.0.1 на host.docker.internal,
    если бэкенд запущен внутри Docker-контейнера.

    Вне Docker возвращает хост без изменений.
    """
    if is_running_in_docker() and host in _LOCALHOST_ALIASES:
        return _DOCKER_HOST
    return host
