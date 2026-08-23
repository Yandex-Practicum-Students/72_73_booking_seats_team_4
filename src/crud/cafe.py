import uuid
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.base import CRUDBase
from models.cafe import Cafe
from schemas.cafe import CafeCreate, CafeUpdate

from models.user import User, UserRole


class CafeCRUD(CRUDBase[Cafe, CafeCreate, CafeUpdate]):
    """CRUD-операции для кафе и связанных менеджеров."""

    def __init__(self) -> None:
        """Настраивает модель кафе и соответствие поля менеджеров."""
        super().__init__(Cafe, rel_map={'managers_id': 'managers'})

    '''
    async def get(self, obj_id: uuid.UUID, session: AsyncSession) -> Cafe | None:
        """Возвращает кафе вместе со списком менеджеров."""
        logger.info('Получение кафе по ID: {}', obj_id)
        cafe = await super().get(
            obj_id,
            session,
            options=[selectinload(Cafe.managers)],
        )
        if cafe is None:
            logger.warning('Кафе не найдено: cafe_id={}', obj_id)
        else:
            # Гарантируем, что managers - это список
            if cafe.managers is None:
                cafe.managers = []
            logger.info('Кафе найдено: cafe_id={}, name={}', obj_id, cafe.name)
        return cafe
'''

    async def get(self, obj_id: uuid.UUID, session: AsyncSession) -> Cafe | None:
        """Возвращает кафе вместе со списком менеджеров."""
        logger.info('Получение кафе по ID: {}', obj_id)
        cafe = await super().get(obj_id, session)  # ✅ Без options
        if cafe is None:
            logger.warning('Кафе не найдено: cafe_id={}', obj_id)
        else:
            logger.info('Кафе найдено: cafe_id={}, name={}', obj_id, cafe.name)
        return cafe

    async def get_all(
        self,
        session: AsyncSession,
        show_active: Optional[bool] = None,
    ) -> list[Cafe]:
        """Возвращает все кафе вместе со списками менеджеров с фильтрацией по активности."""
        try:
            # Строим базовый запрос
            query = select(Cafe)

            # Добавляем фильтр по активности
            if show_active is not None:
                logger.debug('Применён фильтр по активности: show_active={}', show_active)
                query = query.where(Cafe.is_active == show_active)

            query = query.order_by(Cafe.created_at)

            # ВАЖНО: Добавляем selectinload для менеджеров
            # Если менеджеров нет, вернётся пустой список
            query = query.options(selectinload(Cafe.managers))

            result = await session.execute(query)
            cafes = list(result.scalars().all())

            logger.debug(f'Получено {len(cafes)} кафе из БД')

            # Гарантируем, что у каждого кафе managers - это список
            for idx, cafe in enumerate(cafes):
                logger.debug(
                    f'Кафе {idx}: id={cafe.id}, name={cafe.name}, is_active={cafe.is_active}, managers_type={type(cafe.managers)}')
                if cafe.managers is None:
                    cafe.managers = []
                    logger.debug(f'  managers был None, установлен в пустой список')
                elif not isinstance(cafe.managers, list):
                    cafe.managers = list(cafe.managers)
                    logger.debug(f'  managers преобразован в список, длина={len(cafe.managers)}')
                else:
                    logger.debug(f'  managers уже список, длина={len(cafe.managers)}')

            logger.info('Найдено {} кафе', len(cafes))
            return cafes

        except Exception as e:
            logger.error(f'Ошибка в get_all: {e}', exc_info=True)
            raise

    async def create(self, obj_in: CafeCreate, session: AsyncSession) -> Cafe:
        """Создаёт новое кафе."""
        logger.info('Создание нового кафе: name={}, address={}', obj_in.name, obj_in.address)
        logger.debug('Количество менеджеров: {}', len(obj_in.managers_id) if obj_in.managers_id else 0)

        cafe = await super().create(obj_in, session)

        logger.success('Кафе успешно создано: cafe_id={}, name={}', cafe.id, cafe.name)
        return cafe

    async def update(self, db_obj: Cafe, obj_in: CafeUpdate, session: AsyncSession) -> Cafe:
        logger.info('Обновление кафе: cafe_id={}, name={}', db_obj.id, db_obj.name)

        update_data = obj_in.model_dump(exclude_unset=True)
        logger.debug('Обновляемые поля: {}', list(update_data.keys()))

        # ===== ОБНОВЛЕНИЕ МЕНЕДЖЕРОВ =====
        if 'managers_id' in update_data:
            new_manager_ids = update_data['managers_id'] or []

            # 1. Получаем текущих менеджеров кафе
            current_managers = db_obj.managers or []
            current_ids = {str(m.id) for m in current_managers}
            new_ids = {str(id) for id in new_manager_ids}

            # 2. Определяем, кого добавляем и удаляем
            to_add = new_ids - current_ids
            to_remove = current_ids - new_ids

            # 3. Убираем cafe_id у менеджеров, которых удаляем
            if to_remove:
                result = await session.execute(
                    select(User).where(User.id.in_(list(to_remove)))  # ← ИСПРАВЛЕНО
                )
                removed_managers = result.scalars().all()
                for manager in removed_managers:
                    logger.info(f'Убираем менеджера {manager.username} из кафе {db_obj.id}')
                    manager.cafe_id = None
                    session.add(manager)

            # 4. Добавляем новых менеджеров
            if to_add:
                result = await session.execute(
                    select(User).where(User.id.in_(list(to_add)))  # ← ИСПРАВЛЕНО
                )
                new_managers = result.scalars().all()
                for manager in new_managers:
                    # Проверяем, что пользователь может быть менеджером
                    if manager.role != UserRole.MANAGER:
                        raise ValueError(f'Пользователь {manager.username} не является менеджером. '
                                         f'Сначала назначьте ему роль MANAGER.')
                    manager.cafe_id = db_obj.id
                    session.add(manager)

                # Проверяем, что все ID найдены
                found_ids = {str(u.id) for u in new_managers}
                missing_ids = to_add - found_ids
                if missing_ids:
                    logger.error(f'Пользователи не найдены: {missing_ids}')
                    raise ValueError(f'Пользователи не найдены: {missing_ids}')

                # Переназначаем менеджеров
                for manager in new_managers:
                    if manager.cafe_id is not None and manager.cafe_id != db_obj.id:
                        logger.info(f'Переназначаем менеджера {manager.username} в новое кафе {db_obj.id}')
                    manager.cafe_id = db_obj.id
                    session.add(manager)

            # 5. Обновляем список менеджеров в объекте кафе
            if new_manager_ids:
                result = await session.execute(
                    select(User).where(User.id.in_(new_manager_ids))  # ← ИСПРАВЛЕНО
                )
                setattr(db_obj, 'managers', list(result.scalars().all()))
            else:
                setattr(db_obj, 'managers', [])

        # Обновляем остальные поля (name, address, phone и т.д.)
        for field, value in update_data.items():
            if field != 'managers_id' and hasattr(db_obj, field):
                setattr(db_obj, field, value)

        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)

        # Подгружаем менеджеров для ответа
        result = await session.execute(
            select(Cafe).where(Cafe.id == db_obj.id).options(selectinload(Cafe.managers))
        )
        cafe = result.scalar_one()

        logger.success('✅ Кафе успешно обновлено: cafe_id={}, name={}', cafe.id, cafe.name)
        return cafe


cafe_crud = CafeCRUD()
