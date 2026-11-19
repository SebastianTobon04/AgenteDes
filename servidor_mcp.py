"""Servidor MCP del simulador DES (transporte streamable-http).

Expone:
  * herramienta  ``simular_estocastico``  -> simulación completa (1, 2, 3 puestos) con muestras compartidas
  * recurso      ``des://supuestos``      -> supuestos, distribuciones y parámetros

Uso:  python servidor_mcp.py [--host 127.0.0.1] [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from src.archivos import guardar_simulacion
from src.simulador import ejecutar_simulacion
from src.validaciones import ErrorValidacion, validar_escenario

SUPUESTOS = {
    "modelo": "Lote finito de personas; fila única FIFO; puestos idénticos; sistema inicialmente vacío.",
    "unidad_tiempo": "minutos",
    "primera_llegada": "minuto 0; se generan aleatoriamente los n-1 intervalos restantes",
    "fin_simulacion": "sale la última persona",
    "espera": "solo tiempo en fila, sin servicio",
    "distribuciones": {
        "llegadas": {"tipo": "exponencial", "parametro": "media > 0 (tasa = 1/media)", "inicial": {"media": 2}},
        "servicio_inicial": {"tipo": "triangular", "parametros": "0 < minimo < moda < maximo", "inicial": {"minimo": 1, "moda": 3, "maximo": 5}},
        "servicio_alternativo": {"tipo": "uniforme", "parametros": "0 < minimo < maximo", "ejemplo": {"minimo": 1, "maximo": 3}},
    },
    "limites": {"personas": "1..100", "replicas": "30..100", "semilla_base": "entero >= 0", "capacidades": [1, 2, 3]},
    "semillas": "replica r (desde 0): llegadas = base + 2r ; servicios = base + 2r + 1 (generadores random.Random locales y separados)",
    "muestras_compartidas": "dentro de cada réplica las 3 capacidades usan las mismas muestras; entre réplicas son nuevas",
    "parametros_iniciales": {"personas": 20, "replicas": 30, "semilla_base": 2026, "meta_espera": 1},
    "regla_decision": "menor capacidad cuyo promedio de las esperas promedio de las réplicas <= meta; None si ninguna",
    "advertencia": "Estimación por simulación; no garantiza que cada persona o réplica cumpla la meta.",
}


def crear_servidor(host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    mcp = FastMCP("simulador-des-oficina", host=host, port=port)

    @mcp.resource("des://supuestos", mime_type="application/json")
    def supuestos() -> str:
        """Supuestos del modelo, distribuciones y parámetros."""
        return json.dumps(SUPUESTOS, ensure_ascii=False, indent=2)

    @mcp.tool()
    def simular_estocastico(
        n_personas: int,
        media_llegadas: float,
        distribucion_servicio: str,
        minimo_servicio: float,
        maximo_servicio: float,
        replicas: int = 30,
        semilla_base: int = 2026,
        moda_servicio: Optional[float] = None,
        capacidades: Optional[List[int]] = None,
        guardar_archivos: bool = True,
    ) -> dict:
        """Simula la oficina con 1, 2 y 3 puestos (muestras compartidas dentro de cada réplica).

        Llegadas exponenciales (media en minutos); servicio 'triangular' (requiere moda_servicio)
        o 'uniforme'. Devuelve esperas promedio y salida de la última persona por réplica,
        agregados (media y desviación muestral R-1) y rutas de los archivos CSV.
        """
        datos = {
            "n_personas": n_personas,
            "llegadas": {"distribucion": "exponencial", "media": media_llegadas},
            "servicio": {"distribucion": distribucion_servicio, "minimo": minimo_servicio,
                         "moda": moda_servicio, "maximo": maximo_servicio},
            "replicas": replicas,
            "semilla_base": semilla_base,
            "capacidades": tuple(capacidades) if capacidades else (1, 2, 3),
        }
        try:
            esc = validar_escenario(datos)
        except ErrorValidacion as e:
            raise ValueError(f"Parámetros inválidos: {e}")
        res = ejecutar_simulacion(esc)
        archivos = guardar_simulacion(res, esc.huella()) if guardar_archivos else {}
        return {
            "huella": esc.huella(),
            "configuracion": res["configuracion"],
            "por_replica": res["por_replica"],
            "agregados": res["agregados"],
            "archivos": archivos,
            "muestras_primera_replica": {k: res["muestras"][0][k] for k in
                                         ("replica", "semilla_llegadas", "semilla_servicios", "intervalos", "llegadas", "servicios")},
        }

    return mcp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("DES_MCP_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("DES_MCP_PORT", "8765")))
    a = ap.parse_args()
    print(f"Servidor MCP DES en http://{a.host}:{a.port}/mcp  (Ctrl+C para detener)", flush=True)
    crear_servidor(a.host, a.port).run(transport="streamable-http")
