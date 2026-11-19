"""Bitácora JSONL por hilo: evidencia de mensajes, herramientas, MCP, interrupciones y decisiones."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def carpeta_trazas() -> Path:
    p = Path(os.environ.get("DES_TRAZAS_DIR", "evidencias/trazas"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def registrar_evento(thread_id: str, tipo: str, datos: dict | None = None) -> None:
    ev = {"t": round(time.time(), 3), "hilo": thread_id, "tipo": tipo, "datos": datos or {}}
    with open(carpeta_trazas() / f"{thread_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")


def leer_eventos(thread_id: str) -> list[dict]:
    ruta = carpeta_trazas() / f"{thread_id}.jsonl"
    if not ruta.exists():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
