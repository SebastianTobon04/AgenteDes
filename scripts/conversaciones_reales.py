"""Ejecuta las DOS conversaciones con un modelo REAL (requiere clave en .env y el servidor MCP en marcha).

  1) evaluación con registro aprobado          -> evidencias/conversaciones/real_1_registro_aprobado.json
  2) evaluación + cambio de parámetro después  -> evidencias/conversaciones/real_2_cambio_parametro.json

La respuesta humana (aprobar) la da este script de forma explícita y queda registrada en 'turnos'.
Consulta una API de pago. Uso:  python scripts/conversaciones_reales.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from src import cliente_mcp  # noqa: E402
from src.agente import crear_agente, crear_modelo_real  # noqa: E402
from src.aplicacion import Sesion  # noqa: E402
from src.evidencias import guardar_conversacion  # noqa: E402

CARPETA = Path("evidencias/conversaciones")
PETICION = ("Necesito evaluar una oficina con 20 personas, llegadas exponenciales con media de 2 minutos, servicios triangulares "
            "entre 1 y 5 minutos con moda de 3, 30 réplicas y una meta de espera de 1 minuto. Recomiéndame cuántos puestos necesitamos")


def main() -> int:
    try:
        cliente_mcp.descubrir_herramientas()
    except cliente_mcp.ErrorMCP as e:
        print(f"Inicia primero el servidor MCP (python servidor_mcp.py): {e}"); return 2
    modelo_id = f"{os.environ.get('DES_PROVIDER', 'anthropic')}:{os.environ.get('DES_MODEL', 'claude-sonnet-4-5')}"
    # Conversación 1
    s1 = Sesion(crear_agente(crear_modelo_real()), "real-1-aprobado", "operador", 1.0)
    t = []
    for u in (PETICION, "Registra la decisión con la capacidad recomendada y una nota breve."):
        r = s1.enviar(u); t.append({"usuario": u, "respuesta": r["respuesta"], "interrupcion": r["interrupcion"]})
        print("\n>>", u, "\n", r["respuesta"])
    if s1.interrupcion_pendiente():
        r = s1.reanudar("approve"); t.append({"humano": "approve", "respuesta": r["respuesta"]}); print("\n[APROBADO]", r["respuesta"])
    print("->", guardar_conversacion(CARPETA / "real_1_registro_aprobado.json", s1, modelo_id, "REAL", t))
    # Conversación 2
    s2 = Sesion(crear_agente(crear_modelo_real()), "real-2-cambio", "operador", 1.0)
    t = []
    for u in (PETICION, "Ahora usa un servicio uniforme entre 1 y 3 minutos; conserva los demás datos"):
        r = s2.enviar(u); t.append({"usuario": u, "respuesta": r["respuesta"]}); print("\n>>", u, "\n", r["respuesta"])
    print("->", guardar_conversacion(CARPETA / "real_2_cambio_parametro.json", s2, modelo_id, "REAL", t))
    return 0


if __name__ == "__main__":
    sys.exit(main())
