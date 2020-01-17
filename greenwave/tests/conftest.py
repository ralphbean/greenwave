import pytest

from greenwave.app_factory import create_app


@pytest.fixture
def app():
    app = create_app(config_obj='greenwave.config.TestingConfig')
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    yield app.test_client()