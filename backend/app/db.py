import os
from sqlalchemy import URL, create_engine

def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ.get("DB_HOST", "database"),
        database=os.environ["DB_NAME"],
    )

def make_engine():
    return create_engine(database_url(), pool_pre_ping=True)
