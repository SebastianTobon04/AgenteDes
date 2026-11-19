"""P12 — ampliación elegida: opción B (administración del historial)."""
from src.modelo_ensayo import llamada, texto
from src.politicas import pares_integros, recortar_por_turnos
from src.trazas import leer_eventos
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from tests.conftest import ESC_INICIAL


def _turno(i):
    return [HumanMessage(content=f"h{i}"), AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": f"c{i}", "type": "tool_call"}]),
            ToolMessage(content="r", tool_call_id=f"c{i}"), AIMessage(content=f"a{i}")]


def test_recorte_por_turnos_conserva_pares():
    msgs = [m for i in range(6) for m in _turno(i)]
    quedan = recortar_por_turnos(msgs, 10)
    assert len(quedan) == 8 and isinstance(quedan[0], HumanMessage) and pares_integros(quedan)
    assert recortar_por_turnos(msgs[:5], 10) == msgs[:5]


def test_p12_recorte_dentro_del_ciclo_conserva_estado(servidor_mcp, nueva_sesion):
    guion = [llamada("configurar_escenario", "a1", **ESC_INICIAL), llamada("simular_capacidades", "a2"), texto("Evaluado.")]
    for i in range(4):
        guion += [llamada("recomendar_capacidad_actual", f"r{i}"), texto(f"Turno {i}")]
    s, modelo = nueva_sesion(guion, "hist", "observador", 1.0, max_mensajes_historial=8)
    s.enviar("evalúa")
    for i in range(4):
        s.enviar(f"consulta {i}")
    est = s.estado()
    ev = [e for e in leer_eventos("hist") if e["tipo"] == "historial_recortado"]
    assert ev, "debió recortarse el historial"
    e = ev[-1]["datos"]
    assert len(e["despues"]) < len(e["antes"]) and e["pares_integros_despues"]
    assert e["campos_conservados"]["escenario"] and e["campos_conservados"]["resultados"]
    assert len(est["messages"]) <= 8 + 4   # recortado respecto al total acumulado
    assert est["escenario"]["n_personas"] == 20 and est["resultados"] is not None and est["recomendacion"]["capacidad"] == 3
    assert pares_integros(est["messages"])
    # lo enviado al modelo en la última llamada también está acotado y con pares íntegros
    ultimo = modelo.llamadas[-1]
    assert pares_integros([m for m in ultimo if m.type in ("ai", "tool")])
