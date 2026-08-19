from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.permissions import AdminUser as AdminUser
from api.dependencies.permissions import CurrentUser as CurrentUser
from api.dependencies.permissions import StaffUser as StaffUser
from api.dependencies.tables import get_cafe_or_404 as get_cafe_or_404
from api.dependencies.tables import get_table_in_cafe as get_table_in_cafe
from api.dependencies.tables import get_table_or_404 as get_table_or_404
from api.dependencies.tables import require_manager_cafe_access as require_manager_cafe_access
from core.db import get_session

DBSession = Annotated[AsyncSession, Depends(get_session)]
