"""Escritura de muestras y resultados completos en CSV/JSON (evidencia inspeccionable)."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path


def carpeta_salida() -> Path:
    p = Path(os.environ.get("DES_SALIDA_DIR", "evidencias/simulaciones"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def guardar_simulacion(res: dict, huella: str, directorio: Path | None = None) -> dict:
    d = (directorio or carpeta_salida())
    d.mkdir(parents=True, exist_ok=True)
    ruta_res = d / f"resultados_{huella}.csv"
    with open(ruta_res, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["capacidad", "replica", "espera_promedio", "salida_ultima"])
        for cap, filas in res["por_replica"].items():
            for r in filas:
                w.writerow([cap, r["replica"], repr(r["espera_promedio"]), repr(r["salida_ultima"])])
    ruta_mu = d / f"muestras_{huella}.csv"
    with open(ruta_mu, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["replica", "persona", "semilla_llegadas", "semilla_servicios", "intervalo", "llegada", "servicio"])
        for m in res["muestras"]:
            for i, (ll, sv) in enumerate(zip(m["llegadas"], m["servicios"])):
                inter = "" if i == 0 else repr(m["intervalos"][i - 1])
                w.writerow([m["replica"], i, m["semilla_llegadas"], m["semilla_servicios"], inter, repr(ll), repr(sv)])
    ruta_json = d / f"resumen_{huella}.json"
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump({"configuracion": res["configuracion"], "agregados": res["agregados"]}, f, indent=2, ensure_ascii=False)
    return {"resultados_csv": str(ruta_res), "muestras_csv": str(ruta_mu), "resumen_json": str(ruta_json)}
