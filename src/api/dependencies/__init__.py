from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import AdminUser as AdminUser
from api.dependencies.permissions import CurrentUser as CurrentUser
from api.dependencies.permissions import StaffUser as StaffUser

from core.db import get_session

DBSession = Annotated[AsyncSession, Depends(get_session)]
