from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import AdminUser, CurrentUser, StaffUser
from core.db import get_session

DBSession = Annotated[AsyncSession, Depends(get_session)]
