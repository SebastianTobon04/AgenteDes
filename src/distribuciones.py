"""Funciones de muestreo de las tres distribuciones requeridas.

Todas usan un generador LOCAL ``random.Random`` (nunca el estado global).
Unidad de tiempo: minutos.

* Exponencial(media):    tasa = 1 / media  (media > 0, finita).
* Triangular(min, moda, max): 0 < min < moda < max, finitos.
* Uniforme continua(min, max): 0 < min < max, finitos.
"""
from __future__ import annotations

import math
import random
from typing import List


def _finito_positivo(valor: float, nombre: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{nombre} debe ser un número, recibido {valor!r}")
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nombre} debe ser finito y mayor que 0, recibido {valor!r}")


def validar_exponencial(media: float) -> None:
    _finito_positivo(media, "La media de llegadas")


def validar_triangular(minimo: float, moda: float, maximo: float) -> None:
    for v, n in ((minimo, "mínimo"), (moda, "moda"), (maximo, "máximo")):
        _finito_positivo(v, f"El {n} de la triangular")
    if not (0 < minimo < moda < maximo):
        raise ValueError(
            "Triangular requiere 0 < mínimo < moda < máximo; "
            f"recibido ({minimo}, {moda}, {maximo})"
        )


def validar_uniforme(minimo: float, maximo: float) -> None:
    for v, n in ((minimo, "mínimo"), (maximo, "máximo")):
        _finito_positivo(v, f"El {n} de la uniforme")
    if not (0 < minimo < maximo):
        raise ValueError(f"Uniforme requiere 0 < mínimo < máximo; recibido ({minimo}, {maximo})")


def muestrear_exponencial(rng: random.Random, media: float, n: int) -> List[float]:
    """n muestras exponenciales con la media dada (tasa = 1/media)."""
    validar_exponencial(media)
    tasa = 1.0 / media
    return [rng.expovariate(tasa) for _ in range(n)]


def muestrear_triangular(rng: random.Random, minimo: float, moda: float, maximo: float, n: int) -> List[float]:
    """n muestras triangulares. Nota: random.triangular(low, high, mode)."""
    validar_triangular(minimo, moda, maximo)
    return [rng.triangular(minimo, maximo, moda) for _ in range(n)]


def muestrear_uniforme(rng: random.Random, minimo: float, maximo: float, n: int) -> List[float]:
    validar_uniforme(minimo, maximo)
    return [rng.uniform(minimo, maximo) for _ in range(n)]
