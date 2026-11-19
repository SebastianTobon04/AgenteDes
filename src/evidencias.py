"""Serialización de conversaciones como evidencia (con etiqueta del tipo de modelo)."""
from __future__ import annotations

import json
from pathlib import Path


def serializar_mensajes(msgs) -> list[dict]:
    out = []
    for m in msgs:
        d = {"tipo": m.type, "contenido": m.content if isinstance(m.content, str) else str(m.content)}
        if getattr(m, "tool_calls", None):
            d["llamadas_herramienta"] = [{"id": t["id"], "nombre": t["name"], "args": t["args"]} for t in m.tool_calls]
        if m.type == "tool":
            d["responde_a"] = m.tool_call_id
            d["estado"] = getattr(m, "status", None)
        out.append(d)
    return out


def guardar_conversacion(ruta: Path, sesion, modelo: str, tipo_modelo: str, turnos: list[dict]) -> Path:
    """tipo_modelo: 'REAL' o 'ENSAYO'. turnos: eventos de la interacción (usuario, revisión humana, etc.)."""
    est = sesion.estado()
    res = est.get("resultados")
    doc = {
        "tipo_modelo": tipo_modelo, "modelo": modelo, "hilo": sesion.thread_id,
        "contexto": {"rol": sesion.contexto.rol, "meta": sesion.contexto.meta, "limite_personas": sesion.contexto.limite_personas},
        "turnos": turnos,
        "mensajes": serializar_mensajes(est.get("messages", [])),
        "estado_final": {"escenario": est.get("escenario"), "recomendacion": est.get("recomendacion"), "decision": est.get("decision"),
                         "resultados_agregados": res["agregados"] if res else None, "archivos": res["archivos"] if res else None},
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return ruta
