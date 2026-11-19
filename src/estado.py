"""Estado (persistido por hilo) y contexto de ejecución (lo fija la aplicación)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from langchain.agents import AgentState


class EstadoDES(AgentState):
    """Campos explícitos además del historial (``messages``).

    escenario:      distribuciones, parámetros, personas, réplicas, semilla (dict) o None
    resultados:     resultados completos de la simulación MCP del escenario vigente o None
    recomendacion:  {capacidad|None, meta, huella, promedios, ...} o None
    decision:       decisión registrada tras la revisión humana o None
    """

    escenario: Optional[dict]
    resultados: Optional[dict]
    recomendacion: Optional[dict]
    decision: Optional[dict]


@dataclass
class ContextoDES:
    """Contexto de ejecución inmutable por invocación: NO viene del mensaje del usuario."""

    rol: str = "observador"          # "observador" | "operador"
    meta: float = 1.0                # espera promedio máxima en fila (minutos)
    limite_personas: int = 100
