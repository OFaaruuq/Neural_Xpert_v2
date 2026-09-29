import pytest

from app import create_app
from app.extensions import db
from app.seed import seed


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        seed()
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
