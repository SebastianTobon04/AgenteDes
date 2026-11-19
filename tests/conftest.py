import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor_mcp(tmp_path_factory):
    """Servidor MCP REAL en un subproceso (no se simula)."""
    puerto = _puerto_libre()
    salida = tmp_path_factory.mktemp("sim")
    env = {**os.environ, "DES_SALIDA_DIR": str(salida)}
    p = subprocess.Popen([sys.executable, "-W", "ignore", str(RAIZ / "servidor_mcp.py"), "--port", str(puerto)],
                         cwd=RAIZ, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        p.terminate()
        pytest.fail("El servidor MCP no arrancó")
    url = f"http://127.0.0.1:{puerto}/mcp"
    previo = os.environ.get("DES_MCP_URL")
    os.environ["DES_MCP_URL"] = url
    yield {"url": url, "salida": salida}
    p.terminate()
    p.wait(timeout=10)
    if previo is None:
        os.environ.pop("DES_MCP_URL", None)
    else:
        os.environ["DES_MCP_URL"] = previo


@pytest.fixture(autouse=True)
def trazas_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("DES_TRAZAS_DIR", str(tmp_path / "trazas"))
    return tmp_path / "trazas"


@pytest.fixture
def nueva_sesion():
    from src.agente import crear_agente
    from src.aplicacion import Sesion
    from src.modelo_ensayo import ModeloEnsayo

    def f(guion, hilo="t", rol="operador", meta=1.0, **kw):
        modelo = ModeloEnsayo(guion=guion)
        return Sesion(crear_agente(modelo, **kw), hilo, rol, meta), modelo
    return f


ESC_INICIAL = dict(n_personas=20, media_llegadas=2, distribucion_servicio="triangular",
                   minimo_servicio=1, moda_servicio=3, maximo_servicio=5)
