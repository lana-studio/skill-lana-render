# Instalar la skill lana-reel

Funciona en **Claude Code**, en macOS 13+ o Linux. Tiempo estimado: 5-10 minutos la primera vez.

Necesitas una cuenta de **Lana Studio** ([lanastudio.pe](https://lanastudio.pe)).

## 1. Instalar Remotion

Abre Claude Code y pídele:

> Instala las skills de Remotion con `npx skills add remotion-dev/skills` y verifica que tenga
> node 20 o más, python3 y ffmpeg. Si falta alguno, instálalo.

Claude Code revisa lo que tienes e instala lo que falte. No necesitas GPU ni instalar modelos:
el trabajo pesado se hace en Lana.

## 2. Copiar la skill

Copia la carpeta **`lana-reel/`** entera (no su contenido suelto):

```bash
mkdir -p ~/.claude/skills && cp -R lana-reel ~/.claude/skills/
```

**Si ya tenías una versión anterior**, bórrala antes de copiar la nueva:
`rm -rf ~/.claude/skills/lana-reel`. Si instalaste la versión 1.5.0, que venía en dos skills
separadas (`reel` y `lana-mcp-render`), bórralas también: esta carpeta las reemplaza a las dos.

## 3. Conectar Lana

En la terminal:

```bash
claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp
```

Abre Claude Code, escribe `/mcp`, elige **lana** y luego **Authenticate**. Se abre el navegador
para que entres con tu cuenta de Lana Studio. Si al principio aparece un error 401, es normal:
es lo que inicia el inicio de sesión.

Reinicia Claude Code para que detecte la skill.

## 4. Probar que todo funciona

En Claude Code, pídele:

> Corre el hello render de Lana.

Tarda unos dos minutos y renderiza dos segundos de video. Con eso confirmas que la conexión,
los permisos, la cuota y la descarga funcionan.

## 5. Tu primer reel

1. **Graba 30-45 segundos con el celular, en vertical, hablándole a la cámara.**
2. Crea una carpeta para el reel y pon el video adentro.
3. Abre Claude Code **en esa carpeta**.
4. Copia la plantilla de `lana-reel/prompt-reel.md`, complétala y pégala. Si no quieres llenarla,
   basta con:
   > Hazme un reel con take.MOV

Claude mira el video, te hace las preguntas que no puede resolver solo (¿está en espejo?,
¿guion completo o recortado?, ¿qué estilo?), hace un render de prueba y después el final.
Un reel completo usa entre 6 y 12 trabajos de Lana.

La primera vez que crea un proyecto en tu máquina instala la plantilla de Remotion (tarda un
minuto). Después ya no.

## Problemas comunes

- **La skill no aparece** → verifica que la ruta sea `~/.claude/skills/lana-reel/SKILL.md` (sin
  una carpeta de más en el medio) y reinicia Claude Code.
- **`FORBIDDEN_SCOPE`** → vuelve a `/mcp` → lana → Authenticate y acepta el permiso que nombra
  el mensaje.
- **`ffmpeg/ffprobe not found`** → en Mac: `brew install ffmpeg`. En Linux: `sudo apt install
  ffmpeg` (o el equivalente de tu distribución).
- **`npm not found`** → instala Node.js 20 o más nuevo y vuelve a intentar.
- **Windows** → todavía no está soportado.
