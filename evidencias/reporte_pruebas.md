# Reporte de pruebas

Generado por `python scripts/generar_evidencias.py` (los valores de «obtenido» se calculan en esa ejecución).

## Origen de las evidencias
- **ENSAYO**: conversaciones `evidencias/conversaciones/ensayo_*.json` — modelo de ensayo (guion fijo, sin red) + **servidor MCP real** + agente/HITL reales. Validan orquestación, estado, contexto y revisión humana; **no** demuestran la interpretación de lenguaje natural.
- **REAL**: real_1_registro_aprobado.json, real_2_cambio_parametro.json

## Resultado de `pytest`
`74 passed, 2 warnings in 18.11s` — salida completa en `evidencias/pytest_salida.txt`.

## Tabla de verificación P1–P14

| ID | Entrada / configuración | Esperado | Obtenido | Evidencia |
|---|---|---|---|---|
| P1 | 20 personas, exp(2), tri(1,3,5), 30 réplicas, semilla 2026, meta 1 | 30 réplicas x 3 capacidades; recomendación según la regla | réplicas=[30, 30, 30]; 1p=11.881±4.546, 2p=1.376±1.377, 3p=0.251±0.357; recomendación=3 | evidencias\simulaciones\resultados_ea3a8572363e.csv |
| P2 | mismo hilo, meta 1→2 desde el contexto; regla aislada 7,5/2/0,5 con metas 2 y 8 | simulaciones conservadas; recomendación recalculada; control: 2 y 1 | simulaciones idénticas=True; recomendación 3→2; control meta 2→2, meta 8→1 | evidencias/conversaciones/ensayo_P1_P2_P4.json; tests/test_decisiones.py |
| P4 | hilo de P1: servicio uniforme 1-3 | conserva personas/llegadas/réplicas/semilla; mismas llegadas, nuevos servicios; recalcula | conservados=True; llegadas idénticas (réplica 0)=True; servicios distintos=True; 1p=3.983±2.897, 2p=0.371±0.444, 3p=0.064±0.115; recomendación=2 | evidencias\simulaciones\muestras_8fc0bf82f1e1.csv |
| P3 | regla aislada 7,5/2/0,5 con meta 0,25; y escenario estocástico con meta 0,0001 (registro) | None; registro bloqueado | regla aislada=None; estocástico recomendación=None; interrupción=False; decisión=None | evidencias\conversaciones\ensayo_P3.json |
| P5 | otro hilo: «Conserva los datos y compara» | no hereda el escenario; pide datos | hilo A escenario=True; hilo B escenario=None; herramienta: FALTAN DATOS: este hilo no tiene escenario. Pide al usuario: cantidad de personas, media d... | evidencias/trazas/ensayo-P5-B.jsonl (la pregunta de aclaración del modelo es de ENSAYO; ver conversaciones reales) |
| P6 | 0 y 101 personas, media<=0, moda fuera, uniforme invertida, 29 réplicas, semilla<0, meta<0 | rechazo explícito en cada caso | 0 personas: rechazado; 101 personas: rechazado; media exp. no positiva: rechazado; moda fuera del intervalo: rechazado; uniforme invertida: rechazado; 29 réplicas: rechazado; semilla negativa: rechazado; meta negativa: rechazada | tests/test_validaciones.py, tests/test_mcp.py |
| P7 | servidor MCP no disponible (puerto sin servidor), evaluación nueva | error comprensible; sin evaluación ni decisión | mensaje herramienta: ERROR MCP: no se pudo completar la evaluación (Servidor MCP no disponible o con fallo en http://127.0.0.1:9/mc...; resultados=None; decisión=None | evidencias\conversaciones\ensayo_P7.json |
| P8 | operador pide registro; aprobar | decisión vacía antes; después coincide con propuesta y configuración | antes=None; después capacidad=3, meta=1.0, nota='Recomendación por simulación.', config==escenario:True | evidencias\conversaciones\ensayo_P8_aprobar.json |
| P9 | otro hilo: editar la nota | registro con nota corregida y capacidad válida | capacidad=3, nota='Nota corregida por la persona revisora' | evidencias\conversaciones\ensayo_P9_editar.json |
| P10 | otro hilo: rechazar | resultados conservados; decisión vacía | resultados conservados=True; decisión=None | evidencias\conversaciones\ensayo_P10_rechazar.json |
| P11 | observador pide registro; validación directa | rechazado en ambas rutas | ruta agente: interrupción=False, decisión=None, herramienta: REGISTRO RECHAZADO: El rol 'observador' no puede registrar decisiones: se requiere rol 'op...; validación directa: El rol 'observador' no puede registrar decisiones: se requiere rol 'operador'. | evidencias\conversaciones\ensayo_P11_observador.json |
| P12 | Opción B: administración del historial (max 8 mensajes), 5 turnos | historial antes/después; escenario y resultados conservados; pares íntegros | recortes=3; último: 9→5 mensajes; pares íntegros=True; escenario conservado=True; resultados conservados=True | evidencias\conversaciones\ensayo_P12_historial.json; evidencias/trazas/ensayo-P12-historial.jsonl (evento historial_recortado) |
| P13 | 6 personas, llegadas c/1 min, servicio 4 min | 1p: 0,3,6,9,12,15 / 7,5 / 24; 2p: 0,0,2,2,4,4 / 2 / 13; 3p: 0,0,0,1,1,1 / 0,5 / 10 | 1p: [0, 3, 6, 9, 12, 15] prom=7.5 salida=24; 2p: [0, 0, 2, 2, 4, 4] prom=2.0 salida=13; 3p: [0, 0, 0, 1, 1, 1] prom=0.5 salida=10 | tests/test_simulador.py::test_p13_regresion_determinista |
| P14 | repetir P1 (semilla 2026) y con semilla 2027 | misma semilla: igual; réplicas distintas entre sí; otra semilla: otras muestras | 2026 repetido idéntico=True; réplica0≠réplica1 servicios=True; semilla 2027 muestras distintas=True; recomendaciones 2026/2027=3/3 | tests/test_simulador.py::test_p14_*; evidencias/muestras.csv |

## Fallos encontrados durante el desarrollo
- `tests/test_human_review.py::test_p5_...` falló en la primera ejecución con `KeyError: 'escenario'`: en un hilo nuevo el estado no incluye las claves aún no asignadas. Causa: defecto de la PRUEBA (no del agente); se corrigió usando `estado.get(...)`. Tras la corrección: 74 passed, 2 warnings in 18.11s.
- Al fijar versiones, `langgraph-prebuilt` más reciente era incompatible con `langgraph==1.0.3` (`ImportError: ExecutionInfo`); se fijó `langgraph-prebuilt==1.0.5` (ver `requirements.txt`).

## Limitaciones
- Las conversaciones REAL se ejecutaron vía OpenRouter (modelo openrouter/free) y dependen de una clave de proveedor.
- La memoria (checkpointer en proceso) se pierde al reiniciar el agente.
- Los resultados de P1/P4 son estimaciones por simulación con semilla 2026.
