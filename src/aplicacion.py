"""Capa de aplicación: envía mensajes, detecta interrupciones y reanuda con la decisión humana.
El rol, la meta y el límite los fija la aplicación (ContextoDES), nunca el mensaje del usuario."""
from __future__ import annotations

from typing import Any, Optional

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from .agente import RECURSION_LIMIT
from .estado import ContextoDES
from .trazas import registrar_evento
from .validaciones import validar_meta, validar_rol


def _texto(msg) -> str:
    c = msg.content
    if isinstance(c, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    return c or ""


class Sesion:
    def __init__(self, agente, thread_id: str, rol: str = "observador", meta: float = 1.0, limite_personas: int = 100):
        self.agente, self.thread_id = agente, thread_id
        self.contexto = ContextoDES(rol=validar_rol(rol), meta=validar_meta(meta), limite_personas=limite_personas)

    @property
    def config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}, "recursion_limit": RECURSION_LIMIT}

    def fijar_rol(self, rol: str) -> None:
        self.contexto.rol = validar_rol(rol)
        registrar_evento(self.thread_id, "contexto", {"rol": rol})

    def fijar_meta(self, meta: float) -> None:
        self.contexto.meta = validar_meta(meta)
        registrar_evento(self.thread_id, "contexto", {"meta": meta})

    def estado(self) -> dict:
        return dict(self.agente.get_state(self.config).values or {})

    def interrupcion_pendiente(self) -> Optional[dict]:
        for t in self.agente.get_state(self.config).tasks:
            for i in getattr(t, "interrupts", ()):
                return i.value
        return None

    def _procesar(self, entrada) -> dict:
        try:
            salida = self.agente.invoke(entrada, self.config, context=self.contexto)
        except Exception as e:  # fallo del proveedor/modelo: el estado persistido queda coherente
            registrar_evento(self.thread_id, "error_proveedor", {"error": f"{type(e).__name__}: {e}"})
            return {"respuesta": f"ERROR del modelo/proveedor ({type(e).__name__}): {e}. El estado del hilo se conserva; reintenta.",
                    "interrupcion": None, "error": True}
        pend = self.interrupcion_pendiente()
        if pend is not None:
            registrar_evento(self.thread_id, "interrupcion_humana", pend)
        msgs = salida.get("messages", [])
        resp = _texto(msgs[-1]) if msgs and msgs[-1].type == "ai" else ""
        if resp:
            registrar_evento(self.thread_id, "respuesta_agente", {"texto": resp})
        return {"respuesta": resp, "interrupcion": pend, "error": False}

    def enviar(self, texto: str) -> dict:
        if self.interrupcion_pendiente() is not None:
            raise RuntimeError("Hay una revisión humana pendiente en este hilo: responde aprobar/editar/rechazar antes de continuar.")
        registrar_evento(self.thread_id, "mensaje_usuario", {"texto": texto, "rol": self.contexto.rol, "meta": self.contexto.meta})
        return self._procesar({"messages": [HumanMessage(content=texto)]})

    def reanudar(self, tipo: str, nota: Optional[str] = None, mensaje: Optional[str] = None) -> dict:
        """tipo: 'approve' | 'edit' | 'reject'. En 'edit' se corrige la nota (la capacidad sigue validándose)."""
        pend = self.interrupcion_pendiente()
        if pend is None:
            raise RuntimeError("No hay revisión humana pendiente en este hilo.")
        accion = pend["action_requests"][0]
        if tipo == "approve":
            d: dict[str, Any] = {"type": "approve"}
        elif tipo == "edit":
            if not nota:
                raise ValueError("Para editar se requiere la nota corregida.")
            d = {"type": "edit", "edited_action": {"name": accion["name"], "args": {**accion["args"], "nota": nota}}}
        elif tipo == "reject":
            d = {"type": "reject", "message": mensaje or "La persona revisora rechazó la propuesta."}
        else:
            raise ValueError("Decisión no válida: use approve, edit o reject.")
        registrar_evento(self.thread_id, "respuesta_humana", {"decision": d})
        return self._procesar(Command(resume={"decisions": [d]}))
