"""Herramientas del agente (argumentos tipados, descripciones claras, Command + ToolMessage)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from . import cliente_mcp
from .estadisticas import agregar_capacidad, recomendar_capacidad, TOL
from .trazas import registrar_evento
from .validaciones import (
    ErrorValidacion, validar_escenario, validar_meta, validar_registro, promedios_desde_resultados,
)


def _hilo(runtime: ToolRuntime) -> str:
    try:
        return runtime.config.get("configurable", {}).get("thread_id", "sin_hilo")
    except Exception:
        return "sin_hilo"


def _resp(runtime: ToolRuntime, texto: str, **estado) -> Command:
    """Command que actualiza el estado y responde la llamada con su ToolMessage."""
    return Command(update={**estado, "messages": [ToolMessage(content=texto, tool_call_id=runtime.tool_call_id)]})


def construir_recomendacion(resultados: dict, esc, meta: float) -> dict:
    promedios = promedios_desde_resultados(resultados)
    cap = recomendar_capacidad(promedios, meta)
    return {"capacidad": cap, "meta": meta, "huella": esc.huella(),
            "promedios": {str(k): v for k, v in promedios.items()},
            "regla": "menor capacidad con promedio de esperas promedio <= meta"}


def texto_comparacion(resultados: dict, rec: dict) -> str:
    lineas = ["| Puestos | Espera prom. (min) | Desv. muestral | Salida última prom. (min) | ¿Cumple meta? |", "|---|---|---|---|---|"]
    for c in sorted(resultados["agregados"], key=int):
        a = resultados["agregados"][c]
        cumple = "sí" if a["espera_promedio_media"] <= rec["meta"] + TOL else "no"
        lineas.append(f"| {c} | {a['espera_promedio_media']:.4f} | {a['espera_desviacion_muestral']:.4f} | {a['salida_ultima_media']:.2f} | {cumple} |")
    return "\n".join(lineas)


def _resumen_resultados(resultados: dict, rec: dict) -> str:
    cap = rec["capacidad"]
    r = resultados["agregados"]["1"]["replicas"]
    cab = (f"Réplicas por capacidad: {r}. Meta: {rec['meta']} min.\n{texto_comparacion(resultados, rec)}\n"
           f"Recomendación calculada en Python: {cap if cap is not None else 'None (las capacidades evaluadas son insuficientes)'}.\n"
           f"Archivos: {resultados['archivos']}\n"
           "Nota: es una estimación por simulación; no garantiza que cada persona o réplica cumpla la meta.")
    return cab


@tool
def consultar_supuestos(runtime: ToolRuntime) -> Command:
    """Lee el recurso MCP 'des://supuestos' (supuestos del modelo, distribuciones y parámetros válidos)."""
    h = _hilo(runtime)
    try:
        texto = cliente_mcp.leer_recurso("des://supuestos")
    except cliente_mcp.ErrorMCP as e:
        registrar_evento(h, "mcp_recurso_error", {"uri": "des://supuestos", "error": str(e)})
        return _resp(runtime, f"ERROR: no se pudo leer el recurso MCP. {e}")
    registrar_evento(h, "mcp_recurso_leido", {"uri": "des://supuestos", "caracteres": len(texto)})
    return _resp(runtime, texto)


@tool
def configurar_escenario(
    runtime: ToolRuntime,
    n_personas: Optional[int] = None,
    media_llegadas: Optional[float] = None,
    distribucion_servicio: Optional[Literal["triangular", "uniforme"]] = None,
    minimo_servicio: Optional[float] = None,
    moda_servicio: Optional[float] = None,
    maximo_servicio: Optional[float] = None,
    replicas: Optional[int] = None,
    semilla_base: Optional[int] = None,
) -> Command:
    """Crea o modifica el escenario del hilo. Pasa SOLO los datos que el usuario pidió fijar o cambiar;
    lo omitido se conserva del escenario actual. En un hilo sin escenario son obligatorios: n_personas,
    media_llegadas, distribucion_servicio y sus parámetros (triangular: mínimo, moda, máximo; uniforme:
    mínimo y máximo). Si no se indican réplicas ni semilla en un escenario nuevo se usan 30 y 2026.
    Al cambiar la distribución del servicio hay que indicar sus parámetros. NO uses esta herramienta si la
    petición es ambigua (p. ej. «cambia el servicio a 1 minuto»): primero pregunta al usuario.
    Si cambia algo que afecta la simulación se invalidan resultados, recomendación y decisión."""
    h = _hilo(runtime)
    actual = (runtime.state.get("escenario") or None)
    limite = runtime.context.limite_personas
    pedido = {k: v for k, v in dict(n_personas=n_personas, media_llegadas=media_llegadas,
              distribucion_servicio=distribucion_servicio, minimo_servicio=minimo_servicio,
              moda_servicio=moda_servicio, maximo_servicio=maximo_servicio, replicas=replicas,
              semilla_base=semilla_base).items() if v is not None}
    registrar_evento(h, "herramienta_configurar_escenario", {"argumentos": pedido})
    avisos = []
    if actual is None:
        faltan = []
        if n_personas is None: faltan.append("cantidad de personas")
        if media_llegadas is None: faltan.append("media de llegadas")
        if distribucion_servicio is None: faltan.append("distribución del servicio")
        else:
            if minimo_servicio is None: faltan.append("mínimo del servicio")
            if maximo_servicio is None: faltan.append("máximo del servicio")
            if distribucion_servicio == "triangular" and moda_servicio is None: faltan.append("moda del servicio")
        if faltan:
            return _resp(runtime, "FALTAN DATOS: este hilo no tiene escenario. Pide al usuario: " + ", ".join(faltan) + ". No simules todavía.")
        d = {"n_personas": n_personas, "llegadas": {"distribucion": "exponencial", "media": media_llegadas},
             "servicio": {"distribucion": distribucion_servicio, "minimo": minimo_servicio,
                          "moda": moda_servicio if distribucion_servicio == "triangular" else None, "maximo": maximo_servicio}}
        if replicas is None: d["replicas"] = 30; avisos.append("réplicas=30 (valor documentado por defecto)")
        else: d["replicas"] = replicas
        if semilla_base is None: d["semilla_base"] = 2026; avisos.append("semilla_base=2026 (valor documentado por defecto)")
        else: d["semilla_base"] = semilla_base
    else:
        d = {**actual, "llegadas": dict(actual["llegadas"]), "servicio": dict(actual["servicio"])}
        if n_personas is not None: d["n_personas"] = n_personas
        if media_llegadas is not None: d["llegadas"]["media"] = media_llegadas
        if replicas is not None: d["replicas"] = replicas
        if semilla_base is not None: d["semilla_base"] = semilla_base
        s = d["servicio"]
        if distribucion_servicio is not None and distribucion_servicio != s["distribucion"]:
            if minimo_servicio is None or maximo_servicio is None or (distribucion_servicio == "triangular" and moda_servicio is None):
                return _resp(runtime, "FALTAN DATOS: al cambiar la distribución del servicio hay que indicar todos sus parámetros "
                                      "(triangular: mínimo, moda y máximo; uniforme: mínimo y máximo). Pregunta al usuario.")
            s.update(distribucion=distribucion_servicio, minimo=minimo_servicio, maximo=maximo_servicio,
                     moda=moda_servicio if distribucion_servicio == "triangular" else None)
        else:
            if minimo_servicio is not None: s["minimo"] = minimo_servicio
            if maximo_servicio is not None: s["maximo"] = maximo_servicio
            if moda_servicio is not None: s["moda"] = moda_servicio
    try:
        nuevo = validar_escenario(d, limite_personas=limite)
    except ErrorValidacion as e:
        registrar_evento(h, "validacion_rechazada", {"error": str(e)})
        return _resp(runtime, f"DATOS INVÁLIDOS (rechazados, el escenario no cambió): {e}")
    nuevo_d = nuevo.como_dict()
    if actual is not None and nuevo_d == actual:
        return _resp(runtime, "El escenario ya tenía esos valores; no hay cambios ni invalidaciones.")
    registrar_evento(h, "escenario_actualizado", {"escenario": nuevo_d, "huella": nuevo.huella()})
    aviso = (" Valores por defecto aplicados: " + "; ".join(avisos) + ".") if avisos else ""
    return _resp(runtime, f"Escenario fijado: {nuevo_d}. Resultados, recomendación y decisión anteriores quedaron invalidados; falta simular.{aviso}",
                 escenario=nuevo_d, resultados=None, recomendacion=None, decision=None)


@tool
def simular_capacidades(runtime: ToolRuntime) -> Command:
    """Evalúa 1, 2 y 3 puestos para el escenario vigente llamando al servidor MCP (descubre la herramienta
    'simular_estocastico', la invoca y guarda los resultados completos en el estado). Calcula la
    recomendación en Python con la meta del contexto. Requiere un escenario ya configurado."""
    h = _hilo(runtime)
    d = runtime.state.get("escenario")
    if not d:
        return _resp(runtime, "FALTAN DATOS: no hay escenario en este hilo. Pide los datos al usuario antes de simular.")
    meta = validar_meta(runtime.context.meta)
    esc = validar_escenario(d, limite_personas=runtime.context.limite_personas)
    s, ll = esc.servicio, esc.llegadas
    args = {"n_personas": esc.n_personas, "media_llegadas": ll.media, "distribucion_servicio": s.distribucion,
            "minimo_servicio": s.minimo, "maximo_servicio": s.maximo, "replicas": esc.replicas,
            "semilla_base": esc.semilla_base, "capacidades": list(esc.capacidades)}
    if s.moda is not None:
        args["moda_servicio"] = s.moda
    try:
        herramientas = cliente_mcp.descubrir_herramientas()
        nombres = [t["nombre"] for t in herramientas]
        registrar_evento(h, "mcp_herramientas_descubiertas", {"herramientas": nombres})
        if "simular_estocastico" not in nombres:
            raise cliente_mcp.ErrorMCP(f"El servidor no expone 'simular_estocastico' (expone {nombres})")
        registrar_evento(h, "mcp_llamada_herramienta", {"herramienta": "simular_estocastico", "argumentos": args})
        r = cliente_mcp.llamar_herramienta("simular_estocastico", args)
    except cliente_mcp.ErrorMCP as e:
        registrar_evento(h, "mcp_error", {"error": str(e)})
        # estado coherente: sin resultados nuevos; se invalidan los anteriores para no mezclar escenarios
        return _resp(runtime, f"ERROR MCP: no se pudo completar la evaluación ({e}). No hay resultados nuevos ni se puede registrar una decisión. "
                              "Informa el fallo al usuario y sugiere iniciar el servidor MCP (python servidor_mcp.py).",
                     resultados=None, recomendacion=None, decision=None)
    # verificación cruzada: recomputar agregados desde las réplicas
    for c, filas in r["por_replica"].items():
        ag = agregar_capacidad(filas)
        if abs(ag["espera_promedio_media"] - r["agregados"][c]["espera_promedio_media"]) > 1e-9:
            registrar_evento(h, "mcp_inconsistente", {"capacidad": c})
            return _resp(runtime, "ERROR: los agregados del servidor no coinciden con sus réplicas; resultado descartado.",
                         resultados=None, recomendacion=None, decision=None)
    resultados = {"huella": esc.huella(), "configuracion": r["configuracion"], "por_replica": r["por_replica"],
                  "agregados": {c: agregar_capacidad(f) for c, f in r["por_replica"].items()}, "archivos": r["archivos"]}
    rec = construir_recomendacion(resultados, esc, meta)
    registrar_evento(h, "mcp_resultado", {"huella": esc.huella(), "agregados": resultados["agregados"], "archivos": r["archivos"],
                                          "muestras_primera_replica": {k: r["muestras_primera_replica"][k] for k in ("semilla_llegadas", "semilla_servicios")}})
    registrar_evento(h, "recomendacion", rec)
    return _resp(runtime, _resumen_resultados(resultados, rec), resultados=resultados, recomendacion=rec, decision=None)


@tool
def recomendar_capacidad_actual(runtime: ToolRuntime) -> Command:
    """Recalcula en Python la recomendación con la meta vigente del contexto usando los resultados ya
    simulados (sin volver a simular). Úsala cuando solo cambió la meta o para releer la comparación."""
    h = _hilo(runtime)
    res, d = runtime.state.get("resultados"), runtime.state.get("escenario")
    if not res or not d:
        return _resp(runtime, "No hay resultados simulados; primero configura el escenario y simula.")
    esc = validar_escenario(d, limite_personas=runtime.context.limite_personas)
    try:
        rec = construir_recomendacion(res, esc, validar_meta(runtime.context.meta))
    except ErrorValidacion as e:
        return _resp(runtime, f"Meta inválida: {e}")
    decision_previa = runtime.state.get("decision")
    registrar_evento(h, "recomendacion", rec)
    cambio = decision_previa is not None and decision_previa.get("meta") != rec["meta"]
    return _resp(runtime, _resumen_resultados(res, rec), recomendacion=rec, **({"decision": None} if cambio else {}))


@tool
def registrar_decision(capacidad: int, nota: str, runtime: ToolRuntime) -> Command:
    """Registra en el estado la decisión sobre la cantidad de puestos. Requiere rol operador, resultados
    completos de las tres capacidades del escenario vigente y que 'capacidad' coincida con la recomendación
    calculada en Python. Antes de ejecutarse, una persona debe aprobar, editar la nota o rechazar."""
    h = _hilo(runtime)
    est = {"escenario": runtime.state.get("escenario"), "resultados": runtime.state.get("resultados"),
           "recomendacion": runtime.state.get("recomendacion")}
    errores = validar_registro(est, runtime.context.rol, runtime.context.meta, capacidad, nota)
    if errores:
        registrar_evento(h, "registro_rechazado_validacion", {"errores": errores, "capacidad": capacidad})
        return _resp(runtime, "REGISTRO RECHAZADO: " + " | ".join(errores))
    rec = est["recomendacion"]
    decision = {"capacidad": capacidad, "meta": rec["meta"], "configuracion": est["escenario"],
                "promedios": rec["promedios"], "nota": nota.strip(), "rol": runtime.context.rol,
                "huella": est["resultados"]["huella"], "registrado_en": datetime.now(timezone.utc).isoformat()}
    registrar_evento(h, "decision_registrada", decision)
    return _resp(runtime, f"Decisión registrada: {capacidad} puesto(s), meta {rec['meta']} min. Nota: {decision['nota']}", decision=decision)


HERRAMIENTAS = [consultar_supuestos, configurar_escenario, simular_capacidades, recomendar_capacidad_actual, registrar_decision]
