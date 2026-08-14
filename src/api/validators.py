from fastapi import HTTPException, status

from models.user import User


def ensure_contact_remains(
    user: User,
    update_data: dict[str, object],
) -> None:
    """Не позволяет удалить оба доступных идентификатора для входа."""
    email = update_data.get('email', user.email)
    phone = update_data.get('phone', user.phone)
    if not email and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Необходимо указать email или телефон.',
        )


def reject_null_required_fields(update_data: dict[str, object]) -> None:
    """Не позволяет обнулить обязательные поля через PATCH."""
    null_fields = {
        field_name
        for field_name in ('username', 'role', 'is_active')
        if field_name in update_data and update_data[field_name] is None
    }
    if null_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Поля {", ".join(sorted(null_fields))} не могут быть null.',
        )
