from sqlalchemy.engine import make_url

from src.config.settings import get_settings
from tests.database import TEST_DATABASE_URL


def test_pytest_uses_database_separate_from_development_database():
    assert make_url(TEST_DATABASE_URL).database != make_url(get_settings().database_url).database

