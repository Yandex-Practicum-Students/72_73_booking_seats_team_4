from uuid import UUID

from fastapi import APIRouter
from loguru import logger

from api.dependencies.permissions import AdminUser, MeUser, StaffUser
from models.user import User, UserRole

TEST_ADMIN = User(
    id=UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
    username='test_admin',
    email='admin@example.com',
    phone=None,
    hashed_password='test_admin_hashed_password',
    role=UserRole.ADMIN,
    tg_id='100000001',
)


TEST_MANAGER = User(
    id=UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
    username='test_manager',
    email='manager@example.com',
    phone=None,
    hashed_password='test_manager_hashed_password',
    role=UserRole.MANAGER,
    tg_id='100000002',
)


TEST_USER = User(
    id=UUID('cccccccc-cccc-cccc-cccc-cccccccccccc'),
    username='test_user',
    email='user@example.com',
    phone=None,
    hashed_password='test_user_hashed_password',
    role=UserRole.USER,
    tg_id='100000003',
)

test_router = APIRouter()


@test_router.get('/test/me')
async def test_me(user: MeUser) -> dict[str, str]:
    """Ручка тестирования Me."""
    logger.info(
        'USER LOG: id={} username={}',
        user.id,
        user.username,
    )

    return {
        'user_id': str(user.id),
        'username': user.username,
    }


@test_router.get('/test/staff')
async def test_staff(user: StaffUser) -> dict[str, str]:
    """Ручка тестирования Staff."""
    logger.info('Лог внутри staff endpoint')

    return {
        'user_id': str(user.id),
        'username': user.username,
    }


@test_router.get('/test/admin')
async def test_admin(user: AdminUser) -> dict[str, str]:
    """Ручка тестирования Admin."""
    logger.info('Лог внутри admin endpoint')

    return {
        'user_id': str(user.id),
        'username': user.username,
    }
