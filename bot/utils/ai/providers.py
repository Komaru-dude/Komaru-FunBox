from __future__ import annotations

import fnmatch
import json
import os
from typing import Any, Optional

import litellm

from bot import AI_PROVIDERS_CONFIG_PATH, logger

_DEFAULT_CONFIG: dict[str, Any] = {
    "default_provider": "onlysq",
    "providers": {
        "onlysq": {
            "api_base_env": "OPENAI_SDK_API_URL",
            "api_key_env": "ONLYSQ_API_KEY",
            "litellm_prefix": "openai/",
            "default": True,
            "models": {},
        }
    },
    "fallbacks": {
        "free": {"max_chain": 2},
        "premium": {"max_chain": 3},
    },
    "healthchecks": {
        "poll_interval": 300,
        "success_cooldown": 43200,
        "failure_cooldown": 900,
        "models": {},
    },
}

_config_cache: Optional[dict[str, Any]] = None
_flat_models_cache: Optional[dict[str, dict[str, Any]]] = None


def load_ai_providers() -> dict[str, Any]:
    """Прочитать (и закэшировать) сырой конфиг провайдеров."""
    global _config_cache, _flat_models_cache
    if _config_cache is not None:
        return _config_cache

    try:
        raw = AI_PROVIDERS_CONFIG_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            raise ValueError("empty ai_providers.json")
        data = json.loads(raw)
        if not isinstance(data, dict) or "providers" not in data:
            raise ValueError("missing 'providers' key")

        data.setdefault("default_provider", next(iter(data["providers"])))
        data.setdefault("fallbacks", _DEFAULT_CONFIG["fallbacks"])

        healthchecks = data.setdefault("healthchecks", {})
        for key, value in _DEFAULT_CONFIG["healthchecks"].items():
            healthchecks.setdefault(key, value)

        _config_cache = data
        _flat_models_cache = None  # Сбрасываем кэш плоского списка

        provider_count = len(data["providers"])
        model_count = sum(len(p.get("models", {})) for p in data["providers"].values())
        logger.info(
            f"✅ ai_providers.json: {provider_count} провайдеров, {model_count} моделей"
        )

    except Exception as e:
        logger.warning(f"⚠️ ai_providers.json невалиден ({e}) — использую дефолт")
        _config_cache = _DEFAULT_CONFIG
        _flat_models_cache = None

    return _config_cache


def get_all_models() -> dict[str, dict[str, Any]]:
    """
    Собирает плоский словарь всех моделей из всех провайдеров.
    Формат: {"internal_model_id": { ...данные модели + ключи провайдера... }}
    """
    global _flat_models_cache
    if _flat_models_cache is not None:
        return _flat_models_cache

    cfg = load_ai_providers()
    models_flat: dict[str, dict[str, Any]] = {}

    for prov_name, prov_data in cfg.get("providers", {}).items():
        for model_id, model_data in prov_data.get("models", {}).items():
            # Обогащаем данные модели информацией от её родительского провайдера
            enriched_model = dict(model_data)
            enriched_model["provider_name"] = prov_name
            enriched_model["api_base_env"] = prov_data.get("api_base_env")
            enriched_model["api_key_env"] = prov_data.get("api_key_env")
            enriched_model["litellm_prefix"] = prov_data.get("litellm_prefix", "")

            models_flat[model_id] = enriched_model

    _flat_models_cache = models_flat
    _register_litellm_models(models_flat)
    return _flat_models_cache


def _cost_per_token(m_data: dict[str, Any], kind: str) -> Optional[float]:
    """Цена за токен из конфига: либо {kind}_cost_per_token, либо {kind}_cost_per_1m."""
    try:
        direct = m_data.get(f"{kind}_cost_per_token")
        if direct is not None:
            return float(direct)
        per_million = m_data.get(f"{kind}_cost_per_1m")
        if per_million is not None:
            return float(per_million) / 1_000_000
    except (TypeError, ValueError):
        pass
    return None


def _register_litellm_models(models_flat: dict[str, dict[str, Any]]) -> None:
    """Регистрирует модели из ai_providers.json в cost map litellm.

    Без этого litellm не знает контекст и цены кастомных моделей и сыпет
    'is not mapped in model cost map' в дебаг-лог. Модели, уже известные
    litellm, не трогаем, если в конфиге нет явных переопределений.
    """
    mapping: dict[str, dict[str, Any]] = {}
    for model_id, m_data in models_flat.items():
        prefix = m_data.get("litellm_prefix", "")
        bare_id = m_data.get("litellm_model", model_id)
        full_id = f"{prefix}{bare_id}"

        overrides = {
            "max_tokens": m_data.get("max_output_tokens"),
            "max_input_tokens": m_data.get("context_window"),
            "input_cost_per_token": _cost_per_token(m_data, "input"),
            "output_cost_per_token": _cost_per_token(m_data, "output"),
        }
        has_overrides = any(v is not None for v in overrides.values())
        # litellm хранит известные модели без префикса — проверяем оба варианта,
        # иначе нулевые цены перекроют реальные данные litellm
        already_known = full_id in litellm.model_cost or bare_id in litellm.model_cost
        if already_known and not has_overrides:
            continue

        entry: dict[str, Any] = {
            "max_tokens": 8192,
            "max_input_tokens": 32768,
            "input_cost_per_token": 0.0,
            "output_cost_per_token": 0.0,
            "litellm_provider": prefix.rstrip("/") or "openai",
            "mode": "chat",
        }
        entry.update({k: v for k, v in overrides.items() if v is not None})
        mapping[full_id] = entry

    if not mapping:
        return
    try:
        litellm.register_model(mapping)
        logger.info(f"✅ litellm: зарегистрировано моделей в cost map: {len(mapping)}")
    except Exception as e:
        logger.warning(f"⚠️ litellm.register_model не удался: {e}")


def reload_ai_providers() -> dict[str, Any]:
    """Сбросить кэши и перечитать конфиг с диска."""
    global _config_cache, _flat_models_cache
    _config_cache = None
    _flat_models_cache = None
    return load_ai_providers()


def resolve_model(internal_id: str) -> tuple[str, dict[str, Any]]:
    """
    Возвращает (litellm_model_string, provider_cfg).
    """
    models = get_all_models()

    if internal_id not in models:
        # Fallback на случай, если модель не найдена (например, хардкод default_model)
        logger.warning(f"⚠️ Модель {internal_id} не найдена в конфиге.")
        return internal_id, {}

    m_data = models[internal_id]
    prefix = m_data.get("litellm_prefix", "")
    litellm_model = m_data.get("litellm_model", internal_id)

    full_model_string = f"{prefix}{litellm_model}"

    provider_cfg = {
        "api_base_env": m_data.get("api_base_env"),
        "api_key_env": m_data.get("api_key_env"),
    }

    return full_model_string, provider_cfg


def provider_credentials(provider_cfg: dict[str, Any]) -> dict[str, Any]:
    """Собрать kwargs для litellm.acompletion из env-переменных провайдера."""
    kwargs: dict[str, Any] = {}
    api_base_env = provider_cfg.get("api_base_env")
    api_key_env = provider_cfg.get("api_key_env")

    if api_base_env:
        val = os.getenv(api_base_env)
        if val:
            kwargs["api_base"] = val

    if api_key_env:
        val = os.getenv(api_key_env)
        if val:
            kwargs["api_key"] = val

    return kwargs


def fallback_max_chain(user_tier: int) -> int:
    cfg = load_ai_providers()
    key = "premium" if user_tier > 0 else "free"
    return int(cfg.get("fallbacks", {}).get(key, {}).get("max_chain", 2))


def healthcheck_settings(model_id: str) -> dict[str, Any]:
    """Итоговые настройки healthcheck: глобальные -> provider -> model pattern."""
    cfg = load_ai_providers()
    models = get_all_models()

    settings: dict[str, Any] = dict(_DEFAULT_CONFIG["healthchecks"])

    # 1. Глобальные настройки
    global_settings = cfg.get("healthchecks") or {}
    settings.update({k: v for k, v in global_settings.items() if k != "models"})

    # 2. Настройки конкретного провайдера (если модель найдена)
    if model_id in models:
        prov_name = models[model_id].get("provider_name")
        provider_data = cfg.get("providers", {}).get(prov_name, {})
        settings.update(provider_data.get("healthcheck") or {})

    # 3. Переопределения по паттерну имени модели (из глобального healthchecks.models)
    for pattern, override in (global_settings.get("models") or {}).items():
        if fnmatch.fnmatchcase(model_id, pattern) and isinstance(override, dict):
            settings.update(override)

    return settings


def healthcheck_cooldowns(model_id: str) -> tuple[float, float]:
    settings = healthcheck_settings(model_id)
    try:
        success = max(0.0, float(settings.get("success_cooldown", 43200)))
    except (TypeError, ValueError):
        success = 43200.0
    try:
        failure = max(0.0, float(settings.get("failure_cooldown", 900)))
    except (TypeError, ValueError):
        failure = 900.0
    return success, failure


def healthcheck_enabled(model_id: str) -> bool:
    return bool(healthcheck_settings(model_id).get("enabled", True))


def healthcheck_poll_interval() -> float:
    cfg = load_ai_providers()
    try:
        return max(
            30.0, float((cfg.get("healthchecks") or {}).get("poll_interval", 300))
        )
    except (TypeError, ValueError):
        return 300.0


def format_model_line(actual: str | None, requested: str, name_lookup=None) -> str:
    """Рендер строки '🧠 Модель: <actual> (запрошена: <requested>)'."""

    def _pretty(mid: str) -> str:
        if name_lookup is None:
            return mid
        try:
            return name_lookup(mid) or mid
        except Exception:
            return mid

    if not actual or actual == requested:
        return f"🧠 Модель: {_pretty(requested)}"
    return f"🧠 Модель: {_pretty(actual)} (запрошена: {_pretty(requested)})"
