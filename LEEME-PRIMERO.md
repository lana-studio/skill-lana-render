# lana-reel — léeme primero

Una skill para **Claude Code** que convierte un video tuyo hablando a cámara, grabado con el
celular, en un **reel vertical terminado**: silencios cortados, subtítulos alineados a lo que
dijiste, titulares, tarjetas, transiciones y efectos de sonido. El render se hace en la GPU de
**Lana Studio**, así que tu computadora no necesita ser potente.

**Qué hay en esta carpeta**
- `lana-reel/` → la skill (esto es lo que se instala).
- `INSTALAR.md` → instalación paso a paso.
- `DETALLES.md` → tus datos, cuotas, licencias y qué no hace todavía.

**Los 4 pasos**
1. **Instala Remotion** con una línea en Claude Code (y de paso verifica node, python y ffmpeg).
2. **Copia** la carpeta `lana-reel/` a `~/.claude/skills/`.
3. **Conecta Lana**: `claude mcp add --transport http lana https://mcp.lanastudio.pe/mcp` y
   autentícate en `/mcp`.
4. **Pídele el reel** con la plantilla de `lana-reel/prompt-reel.md`, como si le hablaras a tu
   editor.

El detalle de cada paso está en `INSTALAR.md`.
