from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)

    with engine.begin() as connection:
        columns = connection.exec_driver_sql(
            "PRAGMA table_info(receipt_item)"
        ).fetchall()
        column_names = {column[1] for column in columns}
        if "is_manual_assignment" not in column_names:
            connection.exec_driver_sql(
                "ALTER TABLE receipt_item ADD COLUMN is_manual_assignment BOOLEAN NOT NULL DEFAULT 0"
            )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
