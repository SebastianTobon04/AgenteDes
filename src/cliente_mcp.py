"""Cliente MCP real (streamable-http): descubre herramientas, lee recursos y las invoca."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL_POR_DEFECTO = "http://127.0.0.1:8765/mcp"
TIMEOUT_S = 60


class ErrorMCP(RuntimeError):
    """El servidor MCP no está disponible o devolvió un error."""


def url_mcp() -> str:
    return os.environ.get("DES_MCP_URL", URL_POR_DEFECTO)


def _aplanar(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_aplanar(e) for e in exc.exceptions)
    return f"{type(exc).__name__}: {exc}"


@asynccontextmanager
async def _sesion(url: str):
    async with streamablehttp_client(url) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


async def _ejecutar(url: str, operacion):
    try:
        async with asyncio.timeout(TIMEOUT_S):
            async with _sesion(url) as s:
                return await operacion(s)
    except ErrorMCP:
        raise
    except BaseException as e:  # incluye ExceptionGroup de anyio
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        raise ErrorMCP(f"Servidor MCP no disponible o con fallo en {url}: {_aplanar(e)}") from None


def _correr(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # ya hay un bucle (p. ej. Jupyter): ejecutar en otro hilo
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()


def descubrir_herramientas(url: str | None = None) -> list[dict]:
    async def op(s):
        r = await s.list_tools()
        return [{"nombre": t.name, "descripcion": t.description, "esquema": t.inputSchema} for t in r.tools]
    return _correr(_ejecutar(url or url_mcp(), op))


def leer_recurso(uri: str = "des://supuestos", url: str | None = None) -> str:
    async def op(s):
        r = await s.read_resource(uri)
        return "".join(getattr(c, "text", "") for c in r.contents)
    return _correr(_ejecutar(url or url_mcp(), op))


def llamar_herramienta(nombre: str, argumentos: dict[str, Any], url: str | None = None) -> dict:
    async def op(s):
        r = await s.call_tool(nombre, argumentos)
        if r.isError:
            texto = " ".join(getattr(c, "text", "") for c in r.content)
            raise ErrorMCP(f"La herramienta MCP '{nombre}' devolvió un error: {texto}")
        if getattr(r, "structuredContent", None):
            sc = r.structuredContent
            return sc.get("result", sc) if set(sc) == {"result"} else sc
        return json.loads("".join(getattr(c, "text", "") for c in r.content))
    return _correr(_ejecutar(url or url_mcp(), op))
