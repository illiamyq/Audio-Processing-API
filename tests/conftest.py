import asyncio
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.user import User
from app.setup.database import Base, get_db
from app.setup.security import create_access_token, hash_password

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture  
# issue: sess scoped engine powoduje data to leak between tests, ( triggering !UNIQUE! constraint failures on user creation.)
# temp fix: lower fixture scope (blank slate on each test, tables dropping and recreating tables for every single test)
# TODO perm fix: separate test db, worker adjustments?
async def engine():
    eng = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db) -> AsyncClient:
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user(db) -> User:
    u = User(email="test@example.com", hashed_password=hash_password("password123"))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
def auth_headers(user) -> dict:
    token = create_access_token(user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_storage():
    with patch("app.services.storage.get_s3_client") as mock_client, \
         patch("app.services.storage.ensure_bucket"), \
         patch("app.api.routes.audio.process_audio") as mock_task:

        s3 = MagicMock()
        mock_client.return_value = s3
        s3.put_object.return_value = {}
        s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fake-audio")}
        s3.delete_object.return_value = {}
        s3.generate_presigned_url.return_value = "http://minio/fake-url"
        mock_task.delay.return_value = MagicMock(id="fake-task-id")

        yield {"s3": s3, "task": mock_task}