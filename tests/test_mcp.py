import json

import pytest

from src import cliente_mcp
from src.simulador import ejecutar_simulacion
from src.validaciones import validar_escenario

ARGS = dict(n_personas=20, media_llegadas=2, distribucion_servicio="triangular", minimo_servicio=1,
            moda_servicio=3, maximo_servicio=5, replicas=30, semilla_base=2026)


def test_descubre_herramienta_y_lee_recurso(servidor_mcp):
    nombres = [t["nombre"] for t in cliente_mcp.descubrir_herramientas()]
    assert "simular_estocastico" in nombres
    sup = json.loads(cliente_mcp.leer_recurso("des://supuestos"))
    assert sup["parametros_iniciales"]["semilla_base"] == 2026 and "triangular" in json.dumps(sup)


def test_resultado_mcp_coincide_con_el_simulador_directo(servidor_mcp):
    r = cliente_mcp.llamar_herramienta("simular_estocastico", ARGS)
    esc = validar_escenario({"n_personas": 20, "llegadas": {"distribucion": "exponencial", "media": 2},
                             "servicio": {"distribucion": "triangular", "minimo": 1, "moda": 3, "maximo": 5}})
    d = ejecutar_simulacion(esc)
    for c in ("1", "2", "3"):
        assert r["agregados"][c]["espera_promedio_media"] == pytest.approx(d["agregados"][c]["espera_promedio_media"], abs=1e-9)
        assert len(r["por_replica"][c]) == 30
    assert r["archivos"]["muestras_csv"].endswith(".csv")


def test_mcp_rechaza_parametros_invalidos(servidor_mcp):
    for mal in (dict(ARGS, n_personas=0), dict(ARGS, n_personas=101), dict(ARGS, replicas=29),
                dict(ARGS, semilla_base=-1), dict(ARGS, media_llegadas=0), dict(ARGS, moda_servicio=6)):
        with pytest.raises(cliente_mcp.ErrorMCP):
            cliente_mcp.llamar_herramienta("simular_estocastico", mal)


def test_p7_servidor_no_disponible():
    with pytest.raises(cliente_mcp.ErrorMCP) as e:
        cliente_mcp.descubrir_herramientas("http://127.0.0.1:9/mcp")
    assert "no disponible" in str(e.value)
