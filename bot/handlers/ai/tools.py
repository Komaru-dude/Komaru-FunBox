import inspect
import json
import random
from typing import Any, Dict

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from pydantic import BaseModel

from bot import logger
from bot.utils.ai_api import simple_text_api
from bot.utils.global_storage import active_chats, active_chats_lock


class ChatStopTool(BaseModel):
    """Останавливает текущую активную сессию чата, сбрасывая состояние пользователя."""

    pass


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "chat_stop",
            "description": "Останавливает текущую активную сессию чата.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_search",
            "description": "ОБЯЗАТЕЛЬНО используй для поиска актуальной/меняющейся информации.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос"},
                    "level": {
                        "type": "string",
                        "enum": ["lite", "standard", "max"],
                        "description": "Уровень глубины поиска",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


AVAILABLE_TOOLS: Dict[str, Any] = {}

SEARCH_MODELS = {
    "lite": ["sonar"],
    "standard": ["sonar-pro"],
    "max": ["sonar-reasoning-pro"],
}


async def execute_chat_stop(message: Message, state: FSMContext) -> str:
    """Выполняет логику команды /chat_stop и возвращает результат для LLM."""
    chat_id = message.chat.id
    current_state = await state.get_state()

    if current_state is not None:
        await state.clear()

    async with active_chats_lock:
        if chat_id in active_chats:
            active_chats.remove(chat_id)
            return "Чат успешно остановлен, и состояние сброшено. Пользователь может начать новый разговор."
        else:
            return "Чат уже был остановлен. Никаких дополнительных действий не требовалось."


AVAILABLE_TOOLS["chat_stop"] = execute_chat_stop


async def execute_search(query: str, level: str = "standard") -> str:
    """ИИ поиск для моделей."""
    available_pool = SEARCH_MODELS.get(level, SEARCH_MODELS["standard"]).copy()

    max_retries = 3
    attempted_models = []

    for attempt in range(max_retries):
        if not available_pool:
            break

        current_model = random.choice(available_pool)
        available_pool.remove(current_model)
        attempted_models.append(current_model)

        try:
            answer = await simple_text_api(
                current_model, [{"role": "user", "content": query}]
            )

            if not answer:
                raise ValueError("Empty response")

            return f"{answer}"

        except Exception as e:
            logger.error(
                f"Search failed for model {current_model} (Attempt {attempt + 1}): {e}"
            )

            if attempt == max_retries - 1:
                return f"Ошибка поиска после {max_retries} попыток. Использовались: {', '.join(attempted_models)}"

            continue

    return "Поиск недоступен: нет подходящих моделей."


AVAILABLE_TOOLS["execute_search"] = execute_search


async def handle_tool_call(tool_call, message: Message, state: FSMContext) -> dict:
    try:
        function_name = tool_call.function.name
    except Exception:
        return {
            "tool_call_id": getattr(tool_call, "id", None),
            "output": "Ошибка: неверный формат tool_call.",
        }

    function_to_call = AVAILABLE_TOOLS.get(function_name)
    if function_to_call is None:
        return {
            "tool_call_id": getattr(tool_call, "id", None),
            "output": f"Ошибка: Функция {function_name} не найдена в списке доступных инструментов.",
        }

    parsed_args = {}
    try:
        raw_args = getattr(tool_call.function, "arguments", None)
        if raw_args:
            if isinstance(raw_args, str):
                parsed_args = json.loads(raw_args)
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
    except Exception as e:
        logger.error(f"Failed to parse tool_call arguments: {e}")
        return {
            "tool_call_id": tool_call.id,
            "output": f"Ошибка при разборе аргументов: {e}",
        }

    try:
        sig = inspect.signature(function_to_call)
        call_kwargs = {}
        for param in sig.parameters.values():
            pname = param.name
            if pname in parsed_args:
                call_kwargs[pname] = parsed_args[pname]
            elif pname == "message":
                call_kwargs["message"] = message
            elif pname == "state":
                call_kwargs["state"] = state

        if inspect.iscoroutinefunction(function_to_call):
            result = await function_to_call(**call_kwargs)
        else:
            result = function_to_call(**call_kwargs)

        return {"tool_call_id": tool_call.id, "output": result}

    except Exception as e:
        logger.error(f"Tool {function_name} execution error: {e}")
        return {
            "tool_call_id": tool_call.id,
            "output": f"Ошибка при выполнении функции {function_name}: {e}",
        }
