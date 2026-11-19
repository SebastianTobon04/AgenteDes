"""Validación de escenario, meta y registro de decisiones (reglas en Python)."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from . import distribuciones as dist
from .estadisticas import recomendar_capacidad

CAPACIDADES_PERMITIDAS: Tuple[int, ...] = (1, 2, 3)
LIMITE_PERSONAS = 100
MIN_REPLICAS, MAX_REPLICAS = 30, 100
ROLES = ("observador", "operador")


class ErrorValidacion(ValueError):
    """Dato inválido: se rechaza explícitamente, sin sustituirlo por un valor por defecto."""


def _num(v: Any, nombre: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{nombre} debe ser numérico (recibido {v!r})")
    if not math.isfinite(v):
        raise ValueError(f"{nombre} debe ser finito (recibido {v!r})")
    return float(v)


def _entero(v: Any, nombre: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        raise ValueError(f"{nombre} debe ser un entero (recibido {v!r})")
    return v


class Llegadas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribucion: Literal["exponencial"] = "exponencial"
    media: float

    @field_validator("media", mode="before")
    @classmethod
    def _media(cls, v):
        v = _num(v, "media de llegadas")
        dist.validar_exponencial(v)
        return v


class Servicio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribucion: Literal["triangular", "uniforme"]
    minimo: float
    moda: Optional[float] = None
    maximo: float

    @field_validator("minimo", "maximo", mode="before")
    @classmethod
    def _n(cls, v, info):
        return _num(v, f"{info.field_name} del servicio")

    @field_validator("moda", mode="before")
    @classmethod
    def _m(cls, v):
        return None if v is None else _num(v, "moda del servicio")

    @model_validator(mode="after")
    def _coherencia(self):
        if self.distribucion == "triangular":
            if self.moda is None:
                raise ValueError("La triangular requiere moda")
            dist.validar_triangular(self.minimo, self.moda, self.maximo)
        else:
            if self.moda is not None:
                raise ValueError("La uniforme no usa moda")
            dist.validar_uniforme(self.minimo, self.maximo)
        return self


class Escenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_personas: int
    llegadas: Llegadas
    servicio: Servicio
    replicas: int = 30
    semilla_base: int = 2026
    capacidades: Tuple[int, ...] = CAPACIDADES_PERMITIDAS
    limite_personas: int = LIMITE_PERSONAS  # lo fija la aplicación (contexto)

    @field_validator("n_personas", "replicas", "semilla_base", mode="before")
    @classmethod
    def _enteros(cls, v, info):
        return _entero(v, info.field_name)

    @model_validator(mode="after")
    def _rangos(self):
        if not (1 <= self.n_personas <= min(self.limite_personas, LIMITE_PERSONAS)):
            raise ValueError(f"n_personas debe estar entre 1 y {min(self.limite_personas, LIMITE_PERSONAS)} (recibido {self.n_personas})")
        if not (MIN_REPLICAS <= self.replicas <= MAX_REPLICAS):
            raise ValueError(f"replicas debe estar entre {MIN_REPLICAS} y {MAX_REPLICAS} (recibido {self.replicas})")
        if self.semilla_base < 0:
            raise ValueError(f"semilla_base debe ser un entero no negativo (recibido {self.semilla_base})")
        if not self.capacidades or any(c not in CAPACIDADES_PERMITIDAS for c in self.capacidades) or len(set(self.capacidades)) != len(self.capacidades):
            raise ValueError(f"capacidades debe ser un subconjunto sin repetidos de {CAPACIDADES_PERMITIDAS}")
        return self

    def como_dict(self) -> dict:
        d = self.model_dump()
        d["capacidades"] = list(self.capacidades)
        d.pop("limite_personas", None)
        return d

    def huella(self) -> str:
        """Hash estable de los parámetros que afectan la simulación."""
        return hashlib.sha1(json.dumps(self.como_dict(), sort_keys=True).encode()).hexdigest()[:12]


def validar_escenario(datos: dict, limite_personas: int = LIMITE_PERSONAS) -> Escenario:
    """Valida un diccionario de escenario; lanza ErrorValidacion con el mensaje de cada fallo."""
    from pydantic import ValidationError

    d = dict(datos)
    d.pop("limite_personas", None)
    try:
        return Escenario(**d, limite_personas=limite_personas)
    except ValidationError as e:
        msgs = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msgs.append(f"{loc}: {err['msg'].removeprefix('Value error, ')}")
        raise ErrorValidacion("; ".join(msgs)) from None


def validar_meta(meta: Any) -> float:
    if isinstance(meta, bool) or not isinstance(meta, (int, float)) or not math.isfinite(meta) or meta < 0:
        raise ErrorValidacion(f"La meta de espera debe ser un número finito >= 0 (recibido {meta!r})")
    return float(meta)


def validar_rol(rol: Any) -> str:
    if rol not in ROLES:
        raise ErrorValidacion(f"Rol inválido {rol!r}; permitidos: {ROLES}")
    return rol


def promedios_desde_resultados(resultados: dict) -> dict[int, float]:
    return {int(c): a["espera_promedio_media"] for c, a in resultados["agregados"].items()}


def validar_registro(estado: dict, rol: str, meta: float, capacidad: Any, nota: Optional[str] = None) -> list[str]:
    """Devuelve la lista de errores (vacía = el registro es válido).

    Es la validación interna usada por la herramienta ``registrar_decision`` y por el
    middleware antes de interrumpir. No depende del texto del usuario ni del modelo.
    """
    errores: list[str] = []
    if rol != "operador":
        errores.append(f"El rol '{rol}' no puede registrar decisiones: se requiere rol 'operador'.")
    esc_d = estado.get("escenario")
    res = estado.get("resultados")
    rec = estado.get("recomendacion")
    if not esc_d:
        errores.append("No hay escenario vigente.")
        return errores
    try:
        esc = validar_escenario(esc_d)
    except ErrorValidacion as e:
        errores.append(f"Escenario inválido: {e}")
        return errores
    if tuple(sorted(esc.capacidades)) != CAPACIDADES_PERMITIDAS:
        errores.append("Deben estar evaluadas las tres capacidades (1, 2 y 3).")
    if not res:
        errores.append("No hay resultados de simulación para el escenario vigente.")
        return errores
    if res.get("huella") != esc.huella():
        errores.append("Los resultados no corresponden al escenario vigente (deben recalcularse).")
        return errores
    for c in CAPACIDADES_PERMITIDAS:
        filas = res.get("por_replica", {}).get(str(c))
        if not filas or len(filas) != esc.replicas:
            errores.append(f"Resultados incompletos para {c} puesto(s): se esperaban {esc.replicas} réplicas.")
            continue
        for f in filas:
            if not all(isinstance(f.get(k), (int, float)) and math.isfinite(f[k]) for k in ("espera_promedio", "salida_ultima")):
                errores.append(f"Resultados no finitos para {c} puesto(s).")
                break
    if errores:
        return errores
    try:
        meta_v = validar_meta(meta)
        promedios = promedios_desde_resultados(res)
        correcta = recomendar_capacidad(promedios, meta_v)
    except (ErrorValidacion, ValueError, KeyError) as e:
        return [f"No se pudo aplicar la regla de decisión: {e}"]
    if correcta is None:
        errores.append("Ninguna capacidad evaluada cumple la meta: no hay recomendación y el registro está bloqueado.")
        return errores
    if not rec or rec.get("meta") != meta_v or rec.get("huella") != esc.huella() or rec.get("capacidad") != correcta:
        errores.append("La recomendación almacenada no corresponde a la meta/configuración vigentes (debe recalcularse).")
    if isinstance(capacidad, bool) or capacidad != correcta:
        errores.append(f"La capacidad {capacidad!r} no coincide con la recomendación calculada en Python ({correcta}).")
    if nota is not None and (not isinstance(nota, str) or not nota.strip() or len(nota) > 2000):
        errores.append("La nota debe ser un texto no vacío de hasta 2000 caracteres.")
    return errores
