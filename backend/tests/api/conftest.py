from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from src.config.settings import get_settings
from src.db.base import Base
from src.db.session import get_db_session
from src.main import create_app
from tests.database import make_test_engine, reset_database


@pytest.fixture
def api_session(tmp_path):
    engine = make_test_engine()
    reset_database(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    settings = get_settings()
    old_upload_dir = settings.upload_dir
    old_derived_dir = settings.derived_dir
    settings.upload_dir = tmp_path / "uploads"
    settings.derived_dir = tmp_path / "derived"
    try:
        yield session
    finally:
        session.close()
        reset_database(engine)
        engine.dispose()
        settings.upload_dir = old_upload_dir
        settings.derived_dir = old_derived_dir


@pytest.fixture
async def api_client(api_session):
    app = create_app()

    def override_session():
        yield api_session

    app.dependency_overrides[get_db_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
