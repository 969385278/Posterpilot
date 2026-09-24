"""Exclusive local API ownership before reconciling abandoned SQLite tasks."""

from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout
from sqlalchemy.engine import make_url


@contextmanager
def runtime_ownership(database_url: str):
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        yield False
        return
    if url.query.get("uri") == "true":
        # URI databases need an explicitly coordinated deployment strategy.
        yield False
        return
    path = Path(url.database).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".runtime.lock", timeout=0)
    try:
        lock.acquire()
    except Timeout as error:
        raise RuntimeError(
            "该任务数据库已有运行中的 API 实例；请使用单 worker，或为另一实例指定独立数据目录。"
        ) from error
    try:
        yield True
    finally:
        lock.release()
