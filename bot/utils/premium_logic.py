from typing import Dict, Set

from bot.utils.ai.providers import get_all_models


def get_free_models() -> Set[str]:
    """
    Возвращает список моделей доступных для свободных пользователей.
    """
    models = get_all_models()
    return {mid for mid, mdata in models.items() if not mdata.get("is_premium", False)}


def get_premium_models() -> Set[str]:
    """
    Возвращает список моделей доступных только для премиум пользователей.
    """
    models = get_all_models()
    return {mid for mid, mdata in models.items() if mdata.get("is_premium", False)}


def get_all_available_models() -> Set[str]:
    """
    Возвращает все доступные модели (свободные + премиум).
    """
    return set(get_all_models().keys())


def is_model_free(model_id: str) -> bool:
    """
    Проверяет, является ли модель свободной.
    """
    return model_id in get_free_models()


def is_model_premium(model_id: str) -> bool:
    """
    Проверяет, является ли модель премиум моделью.
    """
    return model_id in get_premium_models()


def is_model_available_for_user(model_id: str, user_tier: int) -> bool:
    """
    Проверяет, доступна ли конкретная модель для пользователя.
    """
    models = get_all_models()

    # Если модели нет в нашем конфиге, она недоступна
    if model_id not in models:
        return False

    model_data = models[model_id]

    # Если модель премиальная, проверяем тариф пользователя
    if model_data.get("is_premium", False):
        return user_tier > 0

    # Свободные модели доступны всем
    return True


def get_user_available_models(user_tier: int) -> Dict[str, str]:
    """
    Возвращает словарь доступных моделей для пользователя с их типом доступа.
    """
    result = {}
    models = get_all_models()

    for model_id, model_data in models.items():
        if model_data.get("is_premium", False):
            if user_tier > 0:
                result[model_id] = "premium"
            else:
                result[model_id] = "unavailable"
        else:
            result[model_id] = "free"

    return result


def filter_models_by_availability(models_dict: Dict, user_tier: int) -> Dict:
    """
    Фильтрует модели в зависимости от доступности для пользователя.
    """
    filtered_models = {}
    available_for_user = get_user_available_models(user_tier)

    for model_id, model_data in models_dict.items():
        access_type = available_for_user.get(model_id, "unavailable")

        if access_type == "unavailable":
            continue

        filtered_models[model_id] = {
            **model_data,
            "access_type": access_type,
            "is_premium": access_type == "premium",
        }

    return filtered_models
