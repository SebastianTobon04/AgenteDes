"""Modelo de ENSAYO (determinista, sin red ni clave). Reproduce una secuencia de respuestas escrita a mano.
Sirve para probar la orquestación, el estado y HITL; NO es un modelo real ni interpreta lenguaje natural."""
from __future__ import annotations

from typing import Any, Callable, List, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

Paso = Union[AIMessage, Callable[[List[BaseMessage]], AIMessage]]


class ModeloEnsayo(BaseChatModel):
    guion: List[Any]
    posicion: int = 0
    llamadas: List[Any] = []

    @property
    def _llm_type(self) -> str:
        return "modelo-ensayo"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.llamadas.append(list(messages))
        if self.posicion >= len(self.guion):
            msg = AIMessage(content="(modelo de ensayo: guion agotado)")
        else:
            paso = self.guion[self.posicion]
            self.posicion += 1
            msg = paso(messages) if callable(paso) else paso
        return ChatResult(generations=[ChatGeneration(message=msg)])


def llamada(nombre: str, id_: str, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": nombre, "args": args, "id": id_, "type": "tool_call"}])


def texto(t: str) -> AIMessage:
    return AIMessage(content=t)
