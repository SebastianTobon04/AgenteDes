"""Middleware propio: sincronización de meta, administración del historial (ampliación B) e inyección de estado."""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.config import get_config
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from .estado import EstadoDES
from .herramientas import construir_recomendacion
from .trazas import registrar_evento
from .validaciones import ErrorValidacion, validar_escenario, validar_meta


def _hilo() -> str:
    try:
        return get_config().get("configurable", {}).get("thread_id", "sin_hilo")
    except Exception:
        return "sin_hilo"


def resumen_mensajes(msgs) -> list[dict]:
    out = []
    for m in msgs:
        d = {"tipo": m.type, "id": getattr(m, "id", None)}
        if isinstance(m, AIMessage) and m.tool_calls:
            d["llamadas"] = [tc["id"] for tc in m.tool_calls]
        if isinstance(m, ToolMessage):
            d["responde_a"] = m.tool_call_id
        out.append(d)
    return out


def pares_integros(msgs) -> bool:
    """Toda llamada a herramienta tiene su ToolMessage y ningún ToolMessage queda huérfano."""
    llamadas = {tc["id"] for m in msgs if isinstance(m, AIMessage) for tc in m.tool_calls}
    respuestas = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
    return respuestas <= llamadas and llamadas <= respuestas


def recortar_por_turnos(msgs: list, max_mensajes: int) -> list:
    """Conserva los últimos turnos completos (un turno empieza en un HumanMessage) con <= max_mensajes.
    Siempre conserva al menos el turno actual. Nunca separa una llamada de su ToolMessage."""
    if len(msgs) <= max_mensajes:
        return list(msgs)
    inicios = [i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)]
    for ini in inicios:
        if len(msgs) - ini <= max_mensajes:
            return list(msgs[ini:])
    return list(msgs[inicios[-1]:]) if inicios else list(msgs[-max_mensajes:])


class SincronizarMeta(AgentMiddleware):
    """Si la meta del contexto cambió, recalcula la recomendación (sin re-simular) e invalida la decisión
    asociada a la meta anterior. Si cambió el escenario sin resultados vigentes, los descarta."""

    state_schema = EstadoDES

    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        meta = validar_meta(runtime.context.meta)
        res, rec, dec, esc_d = state.get("resultados"), state.get("recomendacion"), state.get("decision"), state.get("escenario")
        upd: dict[str, Any] = {}
        if res and esc_d:
            try:
                esc = validar_escenario(esc_d, limite_personas=runtime.context.limite_personas)
            except ErrorValidacion:
                return None
            if res.get("huella") != esc.huella():
                upd.update(resultados=None, recomendacion=None, decision=None)
            elif not rec or rec.get("meta") != meta:
                nueva = construir_recomendacion(res, esc, meta)
                upd["recomendacion"] = nueva
                registrar_evento(_hilo(), "meta_cambiada_recomendacion_recalculada",
                                 {"meta_anterior": rec.get("meta") if rec else None, "meta_nueva": meta, "recomendacion": nueva["capacidad"]})
                if dec is not None and dec.get("meta") != meta:
                    upd["decision"] = None
        return upd or None


class RecorteHistorial(AgentMiddleware):
    """Ampliación B — administración del historial dentro del ciclo del agente.
    Antes de cada llamada al modelo recorta por turnos completos; el escenario, los resultados, la
    recomendación y la decisión viven en campos del estado y no se ven afectados."""

    state_schema = EstadoDES

    def __init__(self, max_mensajes: int = 12):
        super().__init__()
        self.max_mensajes = max_mensajes

    def before_model(self, state, runtime) -> dict[str, Any] | None:
        msgs = state["messages"]
        if len(msgs) <= self.max_mensajes:
            return None
        quedan = recortar_por_turnos(msgs, self.max_mensajes)
        if len(quedan) == len(msgs):
            return None
        registrar_evento(_hilo(), "historial_recortado", {
            "antes": resumen_mensajes(msgs), "despues": resumen_mensajes(quedan),
            "pares_integros_despues": pares_integros(quedan),
            "campos_conservados": {k: state.get(k) is not None for k in ("escenario", "resultados", "recomendacion", "decision")}})
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *quedan]}


class InyectarEstado(AgentMiddleware):
    """Añade al prompt del sistema un resumen del estado vigente (para que el recorte del historial no
    haga perder el escenario) y el contexto de ejecución (rol, meta, límite)."""

    state_schema = EstadoDES

    def wrap_model_call(self, request, handler):
        s, c = request.state, request.runtime.context
        partes = ["", "ESTADO VIGENTE DEL HILO (fuente de verdad):",
                  f"- Contexto de la aplicación: rol={c.rol}, meta de espera={c.meta} min, límite de personas={c.limite_personas}",
                  f"- Escenario: {s.get('escenario') or 'NO DEFINIDO'}"]
        res, rec, dec = s.get("resultados"), s.get("recomendacion"), s.get("decision")
        if res:
            partes.append("- Resultados (agregados): " + str({k: round(v['espera_promedio_media'], 4) for k, v in res['agregados'].items()}) + " min de espera promedio")
        else:
            partes.append("- Resultados: ninguno vigente")
        partes.append(f"- Recomendación: {('capacidad=' + str(rec['capacidad']) + ' con meta ' + str(rec['meta'])) if rec else 'ninguna'}")
        partes.append(f"- Decisión registrada: {dec['capacidad'] if dec else 'vacía'}")
        return handler(request.override(system_prompt=(request.system_prompt or "") + "\n".join(partes)))
