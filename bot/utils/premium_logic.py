import os
from typing import Dict, Set


def get_free_models() -> Set[str]:
    """
    Возвращает список моделей доступных для свободных пользователей.

    Returns:
        Set[str]: Множество ID моделей для свободного тарифа
    """
    free_models_str = os.getenv("ONLYSQ_ALLOWED_FREE_MODELS", "")
    return {m.strip() for m in free_models_str.split(",") if m.strip()}


def get_premium_models() -> Set[str]:
    """
    Возвращает список моделей доступных только для премиум пользователей.

    Returns:
        Set[str]: Множество ID моделей для премиум тарифа
    """
    premium_models_str = os.getenv("ONLYSQ_ALLOWED_PREMIUM_MODELS", "")
    return {m.strip() for m in premium_models_str.split(",") if m.strip()}


def get_all_available_models() -> Set[str]:
    """
    Возвращает все доступные модели (свободные + премиум).

    Returns:
        Set[str]: Множество всех доступных ID моделей
    """
    return get_free_models() | get_premium_models()


def is_model_free(model_id: str) -> bool:
    """
    Проверяет, является ли модель свободной.

    Args:
        model_id: ID модели для проверки

    Returns:
        bool: True если модель в списке свободных, иначе False
    """
    return model_id in get_free_models()


def is_model_premium(model_id: str) -> bool:
    """
    Проверяет, является ли модель премиум моделью.

    Args:
        model_id: ID модели для проверки

    Returns:
        bool: True если модель в списке премиум, иначе False
    """
    return model_id in get_premium_models()


def is_model_available_for_user(model_id: str, user_tier: int) -> bool:
    """
    Проверяет, доступна ли конкретная модель для пользователя.

    Args:
        model_id: ID модели для проверки
        user_tier: Тариф пользователя (0 = свободный, 1+ = премиум)

    Returns:
        bool: True если модель доступна пользователю, иначе False
    """
    # Свободные модели доступны всем
    if is_model_free(model_id):
        return True

    # Премиум модели доступны только премиум пользователям
    if user_tier > 0 and is_model_premium(model_id):
        return True

    return False


def get_user_available_models(user_tier: int) -> Dict[str, str]:
    """
    Возвращает словарь доступных моделей для пользователя с их типом доступа.

    Args:
        user_tier: Тариф пользователя (0 = свободный, 1+ = премиум)

    Returns:
        Dict[str, str]: Словарь вида {model_id: access_type}
                       где access_type = 'free', 'premium', или 'unavailable'
    """
    result = {}
    free_models = get_free_models()
    premium_models = get_premium_models()

    for model_id in free_models | premium_models:
        if is_model_available_for_user(model_id, user_tier):
            if model_id in free_models:
                result[model_id] = "free"
            else:
                result[model_id] = "premium"
        else:
            result[model_id] = "unavailable"

    return result


def filter_models_by_availability(
    models: Dict, user_tier: int
) -> Dict:
    """
    Фильтрует модели в зависимости от доступности для пользователя.

    Args:
        models: Словарь моделей из onlysq_models["models"]
        user_tier: Тариф пользователя (0 = свободный, 1+ = премиум)

    Returns:
        Dict: Отфильтрованный словарь моделей с добавленной информацией о типе доступа
    """
    filtered_models = {}
    available_for_user = get_user_available_models(user_tier)

    for model_id, model_data in models.items():
        # Проверяем доступность для пользователя
        if model_id not in available_for_user:
            continue

        access_type = available_for_user[model_id]
        if access_type == "unavailable":
            continue

        # Добавляем информацию о типе доступа
        filtered_models[model_id] = {
            **model_data,
            "access_type": access_type,  # 'free' или 'premium'
            "is_premium": access_type == "premium",
        }

    return filtered_models
