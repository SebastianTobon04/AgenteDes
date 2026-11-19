"""Simulador de eventos discretos con SimPy.

* ``simular_capacidad``: una corrida con muestras dadas (fila FIFO, c servidores idénticos).
* ``generar_muestras_replica``: muestras pregeneradas, generadores locales separados.
* ``ejecutar_simulacion``: R réplicas x capacidades con MUESTRAS COMPARTIDAS entre capacidades.
"""
from __future__ import annotations

import random
from typing import Dict, List, Sequence

import simpy

from .distribuciones import (
    muestrear_exponencial,
    muestrear_triangular,
    muestrear_uniforme,
)
from .estadisticas import agregar_capacidad
from .validaciones import Escenario


def simular_capacidad(llegadas: Sequence[float], servicios: Sequence[float], capacidad: int) -> dict:
    """Simula una corrida. ``llegadas`` = instantes de llegada (orden no decreciente).

    Devuelve esperas individuales (solo fila, sin servicio), salidas y la salida final.
    """
    if len(llegadas) != len(servicios):
        raise ValueError("llegadas y servicios deben tener la misma longitud")
    if capacidad < 1:
        raise ValueError("La capacidad debe ser >= 1")
    n = len(llegadas)
    env = simpy.Environment()
    puestos = simpy.Resource(env, capacity=capacidad)  # cola FIFO
    esperas: List[float] = [0.0] * n
    salidas: List[float] = [0.0] * n

    def persona(i: int):
        yield env.timeout(llegadas[i])
        t_llegada = env.now
        with puestos.request() as req:
            yield req
            esperas[i] = env.now - t_llegada
            yield env.timeout(servicios[i])
        salidas[i] = env.now

    for i in range(n):
        env.process(persona(i))
    env.run()
    return {
        "esperas": esperas,
        "salidas": salidas,
        "espera_promedio": sum(esperas) / n,
        "salida_ultima": max(salidas),
    }


def generar_muestras_replica(esc: Escenario, r: int) -> dict:
    """Muestras de la réplica r (desde 0): semilla llegadas = base+2r, servicios = base+2r+1."""
    sem_ll = esc.semilla_base + 2 * r
    sem_sv = esc.semilla_base + 2 * r + 1
    rng_ll = random.Random(sem_ll)
    rng_sv = random.Random(sem_sv)
    n = esc.n_personas
    # la primera llegada es 0; se generan los n-1 intervalos restantes
    intervalos = muestrear_exponencial(rng_ll, esc.llegadas.media, n - 1)
    llegadas = [0.0]
    for x in intervalos:
        llegadas.append(llegadas[-1] + x)
    s = esc.servicio
    if s.distribucion == "triangular":
        servicios = muestrear_triangular(rng_sv, s.minimo, s.moda, s.maximo, n)
    else:
        servicios = muestrear_uniforme(rng_sv, s.minimo, s.maximo, n)
    return {
        "replica": r,
        "semilla_llegadas": sem_ll,
        "semilla_servicios": sem_sv,
        "intervalos": intervalos,
        "llegadas": llegadas,
        "servicios": servicios,
    }


def ejecutar_simulacion(esc: Escenario, guardar_muestras: bool = True) -> dict:
    """Ejecuta todas las réplicas y capacidades. Mismas muestras para todas las capacidades."""
    por_replica: Dict[int, List[dict]] = {c: [] for c in esc.capacidades}
    muestras: List[dict] = []
    for r in range(esc.replicas):
        m = generar_muestras_replica(esc, r)
        muestras.append(m)
        for c in esc.capacidades:
            res = simular_capacidad(m["llegadas"], m["servicios"], c)
            por_replica[c].append(
                {"replica": r, "espera_promedio": res["espera_promedio"], "salida_ultima": res["salida_ultima"]}
            )
    agregados = {c: agregar_capacidad(por_replica[c]) for c in esc.capacidades}
    return {
        "configuracion": esc.como_dict(),
        "por_replica": {str(c): v for c, v in por_replica.items()},
        "agregados": {str(c): v for c, v in agregados.items()},
        "muestras": muestras if guardar_muestras else None,
    }
