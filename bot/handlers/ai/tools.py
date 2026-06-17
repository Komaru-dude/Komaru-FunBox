import inspect
import json
from typing import Any, Dict

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from pydantic import BaseModel

from bot import logger
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
    }
]


AVAILABLE_TOOLS: Dict[str, Any] = {}


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
