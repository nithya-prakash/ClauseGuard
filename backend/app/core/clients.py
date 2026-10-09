from functools import lru_cache

import redis
from qdrant_client import QdrantClient

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url)


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


@lru_cache
def get_neo4j_driver():  # noqa: ANN201 - neo4j imported lazily; it's optional at runtime
    from neo4j import GraphDatabase

    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
