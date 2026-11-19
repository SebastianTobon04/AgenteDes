"""Estadísticos y regla de decisión (todo en Python, nunca delegado al modelo)."""
from __future__ import annotations

import math
import statistics
from typing import Dict, Iterable, Optional

TOL = 1e-9  # tolerancia explícita para comparar contra la meta (igualdad aceptada)


def promedio(valores: Iterable[float]) -> float:
    v = list(valores)
    if not v:
        raise ValueError("No hay valores para promediar")
    return math.fsum(v) / len(v)


def desviacion_muestral(valores: Iterable[float]) -> float:
    """Desviación estándar muestral (denominador R-1)."""
    v = list(valores)
    if len(v) < 2:
        raise ValueError("Se requieren al menos 2 réplicas para la desviación muestral")
    return statistics.stdev(v)


def agregar_capacidad(por_replica: list[dict]) -> dict:
    esperas = [r["espera_promedio"] for r in por_replica]
    salidas = [r["salida_ultima"] for r in por_replica]
    return {
        "replicas": len(por_replica),
        "espera_promedio_media": promedio(esperas),
        "salida_ultima_media": promedio(salidas),
        "espera_desviacion_muestral": desviacion_muestral(esperas),
    }


def recomendar_capacidad(promedios: Dict[int, float], meta: float) -> Optional[int]:
    """Menor capacidad cuyo promedio de esperas promedio <= meta; None si ninguna."""
    if isinstance(meta, bool) or not isinstance(meta, (int, float)) or not math.isfinite(meta) or meta < 0:
        raise ValueError(f"La meta debe ser un número finito >= 0, recibido {meta!r}")
    for cap in sorted(promedios):
        if promedios[cap] <= meta + TOL:
            return cap
    return None
