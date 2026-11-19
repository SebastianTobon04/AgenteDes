import random
import statistics

import pytest

from src import distribuciones as d


def test_servicios_triangulares_respetan_limites():
    xs = d.muestrear_triangular(random.Random(1), 1, 3, 5, 5000)
    assert min(xs) >= 1 and max(xs) <= 5
    assert statistics.mean(xs) == pytest.approx(3.0, abs=0.15)  # tolerancia amplia, no igualdad exacta


def test_servicios_uniformes_respetan_limites():
    xs = d.muestrear_uniforme(random.Random(1), 1, 3, 5000)
    assert min(xs) >= 1 and max(xs) <= 3


def test_intervalos_exponenciales_no_son_constantes_y_positivos():
    xs = d.muestrear_exponencial(random.Random(7), 2.0, 200)
    assert len(set(xs)) > 150 and min(xs) > 0
    assert statistics.mean(xs) == pytest.approx(2.0, rel=0.25)


def test_generador_local_no_toca_el_estado_global():
    random.seed(123)
    esperado = random.random()
    random.seed(123)
    d.muestrear_exponencial(random.Random(5), 2.0, 10)
    assert random.random() == esperado


def test_misma_semilla_mismas_muestras():
    a = d.muestrear_triangular(random.Random(9), 1, 3, 5, 20)
    b = d.muestrear_triangular(random.Random(9), 1, 3, 5, 20)
    assert a == b


@pytest.mark.parametrize("f,args", [
    (d.validar_exponencial, (0,)), (d.validar_exponencial, (-1,)), (d.validar_exponencial, (float("inf"),)),
    (d.validar_triangular, (1, 6, 5)), (d.validar_triangular, (1, 1, 5)), (d.validar_triangular, (0, 3, 5)),
    (d.validar_uniforme, (3, 1)), (d.validar_uniforme, (1, 1)), (d.validar_uniforme, (float("nan"), 3)),
])
def test_parametros_invalidos(f, args):
    with pytest.raises(ValueError):
        f(*args)
