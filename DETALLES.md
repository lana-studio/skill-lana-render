# lana-reel — detalles

## Qué corre dónde

| En tu computadora | En Lana |
|---|---|
| Mirar frames del video (`ffmpeg`) | Ingesta: proxy h264 + audio a 16 kHz |
| Escribir el plan y el React | Transcripción (palabra por palabra) |
| Chequear tipos y empaquetar | Medición de silencios |
| Verificar el archivo terminado | Segmentación de la persona |
| | El render (GPU) |

## Tus datos

- **Tu material no se usa para entrenar modelos.** Este es un compromiso de Lana Studio sobre
  cómo opera el servicio: a diferencia de todo lo que sigue, no es algo que el código de este
  repositorio pueda mostrarte.

Lo demás lo puedes verificar aquí, porque es cómo está construido el sistema:

- **Lo que subes se procesa en las máquinas de Lana Studio**: la ingesta, la transcripción y el
  render. No pasa por una API de medios de terceros.
- **Las transferencias son directas y firmadas.** Una herramienta te da una URL firmada y tu
  máquina sube o baja los bytes; los archivos no pasan por el servidor MCP. Las URLs de subida
  vencen en 15 minutos; las de descarga, en 1 hora.
- **Nada en este repositorio toca una credencial.** Ningún script lee un token, ninguno habla con
  el gateway y ninguna URL firmada se escribe en disco. La única llamada de red que hace un
  script es mover bytes hacia o desde una URL que una herramienta acaba de devolver.
- **Los registros de trabajos se guardan 7 días** después de terminar; luego `lana_get_job`
  responde `JOB_NOT_FOUND`. **El archivo renderizado no se borra con el registro**: queda en tu
  almacenamiento de Lana Studio y sigue disponible con `lana_get_asset`.
- **Tu material lo borras desde tu cuenta de Lana Studio.** Borrar un original borra también todo
  lo derivado (proxy, audio extraído). En esta versión no hay herramienta de borrado por MCP.

Los términos formales y la política de privacidad se enlazarán aquí cuando se publiquen.

## Biblioteca compartida y licencias

Lana ofrece una biblioteca de recursos (fuentes, overlays con alfa, texturas, B-roll, audio) que
puedes usar en un render **sin subir nada**. La skill te muestra cada recurso con su campo
`license` **tal como viene**.

**Algunos recursos dicen `license: unknown`.** Se muestran igual, con ese valor visible; la skill
nunca oculta ni filtra recursos por licencia. **Revisar la licencia antes de publicar
comercialmente es decisión tuya**, no de la skill. Los recursos también traen
`attribution_required`.

## Cuotas

| | |
|---|---|
| Trabajos por día | 50 |
| Trabajos en curso a la vez | 3 |
| Renders simultáneos | 1 |
| Segundos de GPU por mes | 36 000 |

Todo tipo de trabajo cuenta como "en curso": ingesta, transcripción, silencios, segmentación y
render. Un reel completo usa entre 6 y 12. La GPU es compartida: si varias personas renderizan a
la vez, la cola se alarga.

## Qué no hace todavía

- **Otros clientes además de Claude Code** (Codex CLI incluido).
- **Windows.**
- Quitar las miradas al teleprompter, seguimiento de manos, titulares detrás de la persona, eco
  de voz.
- Música de fondo.
- Render local: es a propósito, el render es para lo que existe el servidor MCP.

Los cuatro primeros necesitan capacidades que todavía no existen como herramientas del MCP.

## Soporte

[GitHub Issues](https://github.com/lana-studio/skill-lana-render/issues), **sin SLA ni tiempo de
respuesta garantizado.** No hay correo de soporte ni canal privado.

**Nunca pegues un token ni una URL firmada en un issue.**

## Licencia

El código es [Apache-2.0](LICENSE). Los recursos incluidos tienen su propia licencia, listada en
[NOTICE](NOTICE): las cinco fuentes de `lana-reel/assets/fonts/` están bajo SIL Open Font
License 1.1 y los dos efectos de sonido de `lana-reel/assets/sfx/` son CC0 1.0.

## Versiones

Esta skill se versiona **junto con el servicio `lana-mcp-render`**: la versión de
`lana-reel/VERSION` necesita esa versión del servicio o una más nueva. La skill lo compara sola
al empezar cada reel. La plantilla de Remotion está fijada a la versión exacta que usa el
renderizador (4.0.484).
