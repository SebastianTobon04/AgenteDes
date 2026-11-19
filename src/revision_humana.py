"""Revisión humana obligatoria antes de registrar la decisión (interrupción real de LangGraph)."""
from __future__ import annotations

from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig

from .herramientas import texto_comparacion
from .validaciones import validar_registro


def describir_revision(tool_call, state, runtime) -> str:
    """Texto mostrado a la persona: capacidad, comparación, resultados, meta, configuración y nota."""
    args = tool_call["args"]
    res, rec, esc = state.get("resultados"), state.get("recomendacion"), state.get("escenario")
    meta = runtime.context.meta
    partes = [
        "REVISIÓN HUMANA — registro de decisión",
        f"Capacidad propuesta: {args.get('capacidad')} puesto(s)  |  Recomendación calculada en Python: {rec['capacidad'] if rec else 'n/d'}",
        f"Meta de espera: {meta} min  |  Rol de la sesión: {runtime.context.rol}",
        f"Configuración evaluada: {esc}",
    ]
    if res and rec:
        partes += ["Comparación de alternativas:", texto_comparacion(res, rec),
                   f"Réplicas por capacidad: {res['agregados']['1']['replicas']}  |  Archivos: {res.get('archivos')}"]
    partes.append(f"Nota justificativa: {args.get('nota')}")
    return "\n".join(partes)


class RevisionHumana(HumanInTheLoopMiddleware):
    """HITL sobre ``registrar_decision``. Solo interrumpe si el registro superaría la validación previa
    (rol operador, resultados completos, recomendación vigente). Si no, la herramienta lo rechaza sin molestar
    a la persona. La validación interna de la herramienta se mantiene siempre (defensa en profundidad)."""

    def __init__(self):
        super().__init__(interrupt_on={"registrar_decision": InterruptOnConfig(
            allowed_decisions=["approve", "edit", "reject"], description=describir_revision)})

    def after_model(self, state, runtime):
        msgs = state["messages"]
        ultimo = next((m for m in reversed(msgs) if getattr(m, "type", "") == "ai"), None)
        if ultimo is None or not getattr(ultimo, "tool_calls", None):
            return None
        for tc in ultimo.tool_calls:
            if tc["name"] == "registrar_decision":
                est = {k: state.get(k) for k in ("escenario", "resultados", "recomendacion")}
                errores = validar_registro(est, runtime.context.rol, runtime.context.meta,
                                           tc["args"].get("capacidad"), tc["args"].get("nota"))
                if errores:
                    return None  # sin interrupción: la herramienta devolverá REGISTRO RECHAZADO
        return super().after_model(state, runtime)
