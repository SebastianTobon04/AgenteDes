"""Interfaz de terminal del agente DES.  Ejemplo:  python main.py --rol operador --meta 1 --hilo demo"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from src.agente import crear_agente
from src.aplicacion import Sesion
from src.validaciones import ErrorValidacion

AYUDA = """Comandos: /rol observador|operador   /meta <minutos>   /hilo <id>   /estado   /ayuda   /salir
Cualquier otro texto se envía al agente. Cuando aparezca una revisión humana responde: a (aprobar), e (editar nota), r (rechazar)."""


def mostrar_revision(pend: dict) -> None:
    print("\n" + "=" * 70)
    for ar in pend["action_requests"]:
        print(ar["description"])
        print(f"Acción: {ar['name']}  Argumentos: {ar['args']}")
    print("Opciones: [a]probar  [e]ditar nota  [r]echazar")
    print("=" * 70)


def resolver_revision(sesion: Sesion, res: dict) -> dict:
    while res.get("interrupcion"):
        mostrar_revision(res["interrupcion"])
        op = input("Decisión > ").strip().lower()
        try:
            if op in ("a", "aprobar"):
                res = sesion.reanudar("approve")
            elif op in ("e", "editar"):
                res = sesion.reanudar("edit", nota=input("Nueva nota > ").strip())
            elif op in ("r", "rechazar"):
                res = sesion.reanudar("reject", mensaje=input("Motivo (opcional) > ").strip() or None)
            else:
                print("Elige explícitamente a, e o r.")
        except (ValueError, RuntimeError) as e:
            print(f"[!] {e}")
    return res


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Agente DES: recomendación de puestos de atención")
    ap.add_argument("--rol", default=os.environ.get("DES_ROL", "observador"), choices=["observador", "operador"])
    ap.add_argument("--meta", type=float, default=float(os.environ.get("DES_META", "1")))
    ap.add_argument("--hilo", default="hilo-1")
    ap.add_argument("--limite-personas", type=int, default=100)
    a = ap.parse_args()
    try:
        agente = crear_agente()
        sesion = Sesion(agente, a.hilo, a.rol, a.meta, a.limite_personas)
    except ErrorValidacion as e:
        print(f"Configuración inválida: {e}"); return 2
    except Exception as e:
        print(f"No se pudo crear el modelo ({type(e).__name__}: {e}). Revisa .env (ver README)."); return 2
    print(f"Agente DES | hilo={a.hilo} rol={a.rol} meta={a.meta}\n{AYUDA}")
    while True:
        try:
            linea = input(f"[{sesion.thread_id}|{sesion.contexto.rol}|meta={sesion.contexto.meta}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return 0
        if not linea:
            continue
        try:
            if linea == "/salir": return 0
            if linea == "/ayuda": print(AYUDA); continue
            if linea.startswith("/rol "): sesion.fijar_rol(linea.split(None, 1)[1]); print("rol =", sesion.contexto.rol); continue
            if linea.startswith("/meta "): sesion.fijar_meta(float(linea.split(None, 1)[1])); print("meta =", sesion.contexto.meta); continue
            if linea.startswith("/hilo "): sesion.thread_id = linea.split(None, 1)[1]; print("hilo =", sesion.thread_id); continue
            if linea == "/estado":
                e = sesion.estado()
                print({k: e.get(k) for k in ("escenario", "recomendacion", "decision")}); continue
            res = resolver_revision(sesion, sesion.enviar(linea))
            print("\n" + (res["respuesta"] or "(sin texto)") + "\n")
        except (ErrorValidacion, ValueError, RuntimeError) as e:
            print(f"[!] {e}")


if __name__ == "__main__":
    sys.exit(main())
