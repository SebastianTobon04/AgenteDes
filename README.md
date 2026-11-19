# Agente inteligente para dimensionar una oficina de atención estudiantil (DES estocástica + MCP)

**Institución:** Institución Universitaria Pascual Bravo · **Integrantes:** Juan Sebastián Tobón Restrepo, Juan Camilo Muñoz

Un agente (LangChain/LangGraph) interpreta peticiones en lenguaje natural, ejecuta una simulación de eventos discretos
estocástica (SimPy) **a través de un servidor MCP real**, compara 1, 2 y 3 puestos, recomienda la cantidad mínima que cumple la meta
de espera y **se detiene para que una persona apruebe, edite o rechace** el registro de la decisión.

> **Estado de la entrega.** Código, servidor MCP, revisión humana, 74 pruebas (sin clave) y evidencias P1–P14 ejecutados (`evidencias/reporte_pruebas.md`).
> Las **dos conversaciones con modelo real** (R6) se ejecutaron vía OpenRouter y están en `evidencias/conversaciones/real_*.json` con sus trazas en `evidencias/trazas/real-*.jsonl`.
> Las conversaciones de `ensayo_*` usan un modelo de ensayo (guion fijo) y se identifican como tal.

## 1. Integrantes y contribuciones
Ambos integrantes revisaron la integración y pueden explicar todo el código.

| Integrante | Contribución |
|---|---|
| Juan Sebastián Tobón Restrepo | Simulador SimPy, distribuciones, estadísticas y regla de decisión, validaciones Pydantic, servidor MCP y pruebas del simulador (P1–P6, P13, P14). |
| Juan Camilo Muñoz | Cliente MCP, agente LangChain/LangGraph, estado/contexto/`Command`, revisión humana, ampliación B, terminal, pruebas de agente/HITL (P7–P12), ejecución de las conversaciones reales y evidencias. |

## 2. Arquitectura
```
main.py (terminal) ─► src/aplicacion.py (Sesion: hilo, contexto, interrupciones)
                          │
                          ▼
              src/agente.py  create_agent + checkpointer (InMemorySaver) + middleware
                │  SincronizarMeta · RecorteHistorial (ampliación B) · InyectarEstado · ModelCallLimit · RevisionHumana (HITL)
                ▼
        src/herramientas.py ──(cliente MCP, streamable-http)──► servidor_mcp.py ──► src/simulador.py (SimPy)
        configurar_escenario · simular_capacidades · consultar_supuestos · recomendar_capacidad_actual · registrar_decision
```
| Archivo | Rol |
|---|---|
| `src/distribuciones.py` | Muestreo exponencial / triangular / uniforme con `random.Random` local y validación de parámetros |
| `src/simulador.py` | Corrida SimPy (fila FIFO), generación de muestras por réplica, réplicas × capacidades con muestras compartidas |
| `src/estadisticas.py` | Promedios, desviación muestral (R−1) y **regla de decisión** |
| `src/validaciones.py` | Modelos Pydantic del escenario, validación de meta/rol y `validar_registro` (validación interna del registro) |
| `servidor_mcp.py` | Servidor MCP: herramienta `simular_estocastico` y recurso `des://supuestos` |
| `src/cliente_mcp.py` | Cliente MCP: descubre herramientas, lee el recurso, llama a la herramienta, errores claros |
| `src/estado.py` | `EstadoDES` (escenario, resultados, recomendacion, decision + historial) y `ContextoDES` (rol, meta, límite) |
| `src/herramientas.py` | Herramientas tipadas que actualizan el estado con `Command` y `ToolMessage` ligado a su llamada |
| `src/revision_humana.py` | `HumanInTheLoopMiddleware` extendido: interrupción real antes de `registrar_decision` |
| `src/politicas.py` | Middleware: sincronizar meta, **recorte de historial**, inyección del estado en el prompt |
| `src/aplicacion.py`, `main.py` | Sesión programática y terminal interactiva |
| `src/modelo_ensayo.py` | Modelo de ensayo determinista (solo pruebas) |
| `src/trazas.py`, `src/evidencias.py`, `src/archivos.py` | Bitácora JSONL, conversaciones JSON, CSV de muestras/resultados |
| `tests/` | 74 pruebas automáticas · `scripts/` generación de evidencias y conversaciones reales · `notebooks/` exploración |

## 3. Distribuciones y parámetros (minutos)
| Componente | Distribución | Parámetros / validación |
|---|---|---|
| Entre llegadas | Exponencial | media > 0 y finita (tasa = 1/media). La primera llegada es en el minuto 0; se generan los n−1 intervalos restantes |
| Servicio inicial | Triangular | 0 < mínimo < moda < máximo (inicial 1, 3, 5) |
| Servicio alternativo | Uniforme continua | 0 < mínimo < máximo (ejemplo 1, 3) |

Límites: 1–100 personas, 30–100 réplicas, semilla base entera ≥ 0, capacidades {1, 2, 3}, meta finita ≥ 0. Datos inválidos se **rechazan** (nunca se sustituyen).
Inicial: 20 personas, exponencial(2), triangular(1,3,5), 30 réplicas, semilla 2026, meta 1. Solo si el usuario no indica réplicas/semilla en un escenario *nuevo* se usan 30 y 2026 (y la herramienta lo informa).

**Semillas:** réplica `r` (desde 0): llegadas `semilla_base + 2r`, servicios `semilla_base + 2r + 1`, en generadores separados. Las muestras se pregeneran y se **reutilizan para 1, 2 y 3 puestos**; entre réplicas son nuevas.

## 4. Regla de decisión
Menor número de puestos cuyo **promedio de las esperas promedio de las réplicas** sea ≤ meta (igualdad aceptada, tolerancia 1e−9); si ninguno, `None` y el agente explica que las capacidades evaluadas son insuficientes. Se calcula en Python (`src/estadisticas.py`). Es una estimación por simulación, no garantiza que cada persona o réplica cumpla la meta. Una sola corrida es insuficiente porque su espera promedio es una variable aleatoria: la desviación muestral entre réplicas (ej. ≈4,5 min con 1 puesto) muestra que una corrida aislada puede quedar lejos de la media.

## 5. Ampliación presentada para calificación: **Opción B — administración del historial**
`RecorteHistorial` (`src/politicas.py`) actúa en `before_model`, dentro del ciclo del agente: cuando el historial supera `max_mensajes` conserva los **últimos turnos completos** (un turno empieza en un mensaje del usuario), de modo que ninguna llamada queda separada de su `ToolMessage`. Escenario, resultados, recomendación y decisión viven en campos del estado, y `InyectarEstado` los reinyecta en el prompt. Cada recorte registra en la traza el historial antes/después, la integridad de los pares y los campos conservados. Evidencia: P12 en `evidencias/reporte_pruebas.md`, `evidencias/trazas/ensayo-P12-historial.jsonl`, `tests/test_historial.py`.

## 6. Requisitos previos e instalación
Python **3.12** (versión de referencia, probada con 3.12.3; las pruebas P1–P14 y 74 tests se ejecutaron ahí). Las conversaciones reales se ejecutaron en Windows con Python 3.14. Todas las dependencias están fijadas en `requirements.txt` (incluye `mcp` para el servidor y los clientes de Anthropic/OpenAI).
```bash
python3.12 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
```

## 7. Configuración del `.env`
Completa solo la clave del proveedor elegido (`ANTHROPIC_API_KEY` u `OPENAI_API_KEY`), `DES_PROVIDER` y `DES_MODEL` (un modelo con llamadas a herramientas). Para **OpenRouter** con las versiones fijadas de `requirements.txt` usa `DES_PROVIDER=openai`, `DES_BASE_URL=https://openrouter.ai/api/v1` y la clave en `OPENAI_API_KEY` (o `DES_API_KEY`). Las conversaciones reales entregadas se ejecutaron con `DES_PROVIDER=openrouter` y `DES_MODEL=openrouter/free` (enrutador gratuito de OpenRouter; el modelo concreto lo elige OpenRouter en cada llamada), disponible en la versión más reciente de LangChain instalada en el entorno de ejecución. Las demás variables
(`DES_MCP_URL`, `DES_MCP_HOST/PORT`, `DES_ROL`, `DES_META`, `DES_SALIDA_DIR`, `DES_TRAZAS_DIR`) tienen valores de ejemplo funcionales. **Consultan una API de pago:** el agente interactivo (`main.py`) y `scripts/conversaciones_reales.py`. El simulador, el servidor MCP y las pruebas **no** requieren clave.

## 8. Cómo iniciar (dos terminales, en este orden)
```bash
# Terminal 1 — servidor MCP (Ctrl+C para detener)
python servidor_mcp.py                     # escucha en http://127.0.0.1:8765/mcp
# Terminal 2 — agente (escribe /salir o Ctrl+C para detener)
python main.py --rol operador --meta 1 --hilo demo
```
Comandos de la terminal: `/rol observador|operador`, `/meta <min>`, `/hilo <id>`, `/estado`, `/ayuda`, `/salir`. El rol y la meta **se configuran aquí (o con `--rol/--meta`/`DES_ROL/DES_META`), no en el chat**.

## 9. Ejemplo completo
1. Petición inicial (hilo `demo`):
   `Necesito evaluar una oficina con 20 personas, llegadas exponenciales con media de 2 minutos, servicios triangulares entre 1 y 5 minutos con moda de 3, 30 réplicas y una meta de espera de 1 minuto. Recomiéndame cuántos puestos necesitamos`
   → el agente descubre la herramienta MCP, simula 1/2/3 puestos y presenta la tabla (con semilla 2026 salen ≈ 11,88 / 1,38 / 0,25 min de espera promedio; recomendación 3).
2. Continuación en el mismo hilo: `Ahora usa un servicio uniforme entre 1 y 3 minutos; conserva los demás datos` (conserva personas, llegadas, réplicas y semilla; mismas llegadas, nuevos servicios; recalcula).
3. Cambiar la meta sin re-simular: `/meta 2` y luego `Revisa la recomendación con la nueva meta`.
4. Registro (requiere `/rol operador`): `Registra la decisión con una nota breve`. Aparece la **revisión humana** con capacidad, comparación, resultados, meta, configuración y nota. Responde `a` (aprobar), `e` (editar la nota; se pedirá la nueva) o `r` (rechazar: se conservan los resultados y la decisión queda vacía). No se puede continuar el hilo sin elegir explícitamente.
5. Ambigüedad: `cambia el servicio a 1 minuto` → el agente pregunta si es tiempo fijo o cambio de distribución/parámetros. En un hilo nuevo, `Conserva los datos y compara` → pide los datos.
6. Reproducir un escenario: pide los mismos datos con la misma semilla (p. ej. «semilla 2026») o cambia `réplicas`/`semilla` en la petición.

## 10. Pruebas sin clave del modelo
```bash
python -m pytest -q                         # 74 pruebas; levantan un servidor MCP real en un puerto libre
python scripts/generar_evidencias.py        # regenera evidencias/ y reporte_pruebas.md (ensayo + MCP real)
```
El **modo de ensayo** (`src/modelo_ensayo.py`) reemplaza solo al LLM por un guion fijo de llamadas a herramientas: valida orquestación, estado, contexto, invalidaciones, HITL, límites y manejo de fallos, pero **no** la comprensión del lenguaje natural. El simulador, el servidor MCP, el agente, las herramientas y la revisión humana son los reales. Las pruebas verifican la regla con promedios controlados (7,5/2/0,5), la regresión determinista, límites de las distribuciones y reproducibilidad, sin exigir que una media muestral iguale la teórica (tolerancias explícitas).

## 11. Conversaciones con modelo real (consultan una API; ya ejecutadas)
```bash
# Terminal 1: python servidor_mcp.py      (con .env completo)
python scripts/conversaciones_reales.py   # genera real_1_registro_aprobado.json y real_2_cambio_parametro.json
python scripts/generar_evidencias.py      # actualiza el reporte (conserva los real_*; regenera solo los de ensayo)
```
- `real_1_registro_aprobado.json`: petición inicial → recomendación 3 puestos → registro → revisión humana **aprobada** → decisión en el estado.
- `real_2_cambio_parametro.json`: petición inicial → «servicio uniforme entre 1 y 3» → nuevos resultados y recomendación 2 puestos.
- Ambas usan MCP (`mcp_llamada_herramienta`/`mcp_resultado` en las trazas). La aprobación de la conversación 1 la emite el script (`reanudar("approve")`) y queda como `respuesta_humana` en la traza. Las trazas `real-*.jsonl` pueden contener más de una corrida; los JSON de conversación corresponden a la última.

## 12. Evidencias y resultados
`evidencias/resultados.csv` (30 réplicas × 3 capacidades), `evidencias/muestras.csv` (muestras de todas las réplicas del escenario P1: semillas, intervalos, llegadas, servicios), `evidencias/simulaciones/` (CSV/JSON por escenario, incl. P4 uniforme), `evidencias/conversaciones/` (ensayo; real cuando se ejecuten), `evidencias/trazas/*.jsonl` (mensajes del usuario, llamadas a herramientas, recurso MCP leído, descubrimiento y llamada MCP con parámetros y semillas, interrupciones y respuestas humanas, decisiones, recortes de historial), `evidencias/reporte_pruebas.md` (tabla P1–P14 con esperado/obtenido/ruta) y `evidencias/pytest_salida.txt`.

**Límites del agente:** máx. 10 llamadas al modelo por solicitud (`ModelCallLimitMiddleware`) y `recursion_limit=40`. **Fallos del proveedor:** el cliente reintenta 3 veces con timeout de 60 s; si falla, `Sesion` informa el error, lo registra y el estado del hilo (checkpoint) queda intacto. **MCP caído:** la herramienta devuelve un error comprensible, descarta resultados y no permite registrar.

## 13. Limitaciones conocidas
- El modelo real usado (`openrouter/free`) es un enrutador: la respuesta puede variar entre ejecuciones; las cifras provienen siempre de las herramientas.
- La memoria (`InMemorySaver`) vive en el proceso: al reiniciar `main.py` se pierden hilos, escenarios y revisiones pendientes. El servidor MCP no guarda estado (solo CSV).
- El rol viene de la aplicación (argumento/variable). Para asociarlo a usuarios autenticados haría falta autenticación (p. ej. tokens en una API) y derivar el rol del usuario verificado, nunca de datos enviados por el cliente.
- Los resultados son estimaciones (30 réplicas, un lote de 20 personas); no se estima régimen estacionario.

## 14. Explicación técnica (≤ 600 palabras)
**Estado, contexto e historial.** El *estado* (`EstadoDES`) pertenece a cada hilo y lo persiste el checkpointer: escenario, resultados, recomendación y decisión en campos explícitos. El *contexto* (`ContextoDES`: rol, meta y límite de personas) lo suministra la aplicación en cada invocación y no está en los mensajes, de modo que el usuario no puede cambiarlo escribiendo «soy operador». El *historial* es la lista de mensajes; es lo único que se recorta (opción B), y por eso la verdad del escenario está en el estado, que además se reinyecta en el prompt.

**Qué calcula Python y qué decide el modelo.** Python genera las muestras, simula con SimPy, agrega (media y desviación con R−1), aplica la regla de decisión, valida parámetros y decide si un registro es admisible. El modelo solo interpreta el lenguaje natural, elige la herramienta y sus argumentos, pregunta cuando faltan datos o hay ambigüedad y redacta la explicación con las cifras devueltas. La recomendación nunca depende de su texto.

**MCP.** `servidor_mcp.py` expone la herramienta `simular_estocastico` y el recurso `des://supuestos`. El cliente abre una sesión, descubre las herramientas, lee el recurso y llama a la herramienta con distribuciones, parámetros, personas, réplicas y semilla. El agente no llama directamente al simulador; si el servidor no responde, no se crean resultados ni se registra nada.

**Semillas y variabilidad.** En la réplica r las llegadas usan la semilla base+2r y los servicios base+2r+1, en generadores locales separados. Las muestras de cada réplica se comparten entre 1, 2 y 3 puestos (misma demanda), y cambian entre réplicas. La desviación entre réplicas describe la variabilidad de la espera promedio de una corrida, no la dispersión entre personas; por eso una sola corrida no basta. Cambiar solo el servicio conserva las llegadas porque sus semillas no cambian.

**Validaciones.** Pydantic rechaza personas fuera de 1–100, réplicas fuera de 30–100, semillas negativas o no enteras, medias no positivas, modas fuera del intervalo, límites invertidos, valores no finitos y metas negativas. Cambiar un parámetro de simulación invalida resultados, recomendación y decisión; cambiar la meta recalcula la recomendación sin re-simular e invalida la decisión previa.

**Revisión humana.** Antes de ejecutar `registrar_decision`, el middleware lanza una interrupción real de LangGraph que muestra capacidad, comparación, resultados, meta, configuración y nota. La persona aprueba, edita la nota o rechaza; la reanudación usa el mismo `thread_id`. La herramienta vuelve a validar (rol operador, resultados completos de las tres capacidades, correspondencia con el escenario y con la recomendación de Python), incluso tras editar. Si el registro ya es inadmisible (observador, sin resultados, ninguna capacidad cumple) no se interrumpe y se rechaza.

**Duración de la memoria y rol.** La memoria dura lo que el proceso. El rol procede de `--rol`/`DES_ROL`/`/rol`, es decir, de la aplicación.

## 15. Archivos del curso, fuentes y uso de asistentes de IA
- **Archivos del curso reutilizados:** ninguno copiado. Los notebooks de referencia (`intro_langchain_des*.ipynb`, `Laboratorio_Guiado_MCP_DES.ipynb`) y `simulacion_des.py`/`servidor_mcp_des.py` no estaban disponibles al construir esta entrega; el código se escribió desde cero siguiendo los conceptos del enunciado. **Si la pareja adapta algún archivo del curso, debe listarlo aquí con los cambios.**
- **Fuentes:** enunciado de la evaluación; documentación de LangChain/LangGraph, MCP y SimPy.
- **Asistentes de IA:** se usó **Claude (Anthropic)** para generar el código, las pruebas, las evidencias y este README a partir del enunciado, y **ChatGPT** como guía para ejecutar y depurar en el equipo de los integrantes. El código fue ejecutado y verificado con las pruebas descritas; ambos integrantes lo revisaron y pueden explicarlo.
