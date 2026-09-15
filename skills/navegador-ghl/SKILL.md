---
name: navegador-ghl
description: Controla el navegador con la Playwright CLI para operar GHL/HighLevel y cualquier app web que no tenga API (o cuya API no alcance). Úsala SIEMPRE que se diga "entra a GHL y haz X", "controla el navegador", "automatiza [sitio]", "haz QA de mi landing/funnel", "revisa que mi página funcione", "sácame los datos de esta página", "clona este sitio/tablero a la otra cuenta", "entra al portal de [proveedor]", o cuando una tarea requiera operar dentro de una aplicación web con login.
allowed-tools: Bash(npx playwright-cli:*) Bash(playwright-cli:*) Bash(npx:*)
---

# Navegador web para GHL (Playwright CLI)

El "cable" para operar lo que no tiene API: el panel de **GHL / HighLevel** (y sus instancias white-label), portales de proveedores, QA de landings y extracción de datos de una página. Tú escribes y ejecutas los comandos de la **Playwright CLI oficial** (`@playwright/cli`), iteras leyendo el snapshot, y guardas como receta lo que funcione.

> **Por qué la CLI y no el MCP de Playwright:** la CLI es ~4× más eficiente en tokens (~27k vs ~114k por tarea) porque no vuelca todo el estado del navegador en cada paso — guarda los snapshots en disco y tú lees solo lo que necesitas. **No uses el MCP de Playwright** para esto.

## Instalación y arranque
```bash
npm install --save-dev @playwright/cli      # una sola vez, en la carpeta del asistente
npx --no-install playwright-cli --version   # verificar
npx playwright-cli install-browser chromium # si falta el navegador
```
**Referencia COMPLETA de comandos** (open/goto/click/fill/snapshot/eval/run-code/state-save/…): [references/playwright-cli-comandos.md](references/playwright-cli-comandos.md). Consúltala para la sintaxis exacta.

## El flujo
1. **Entiende la tarea** y planea los pasos si son muchos.
2. **Abre** la sesión (ver Sesiones) y **navega** (`goto`).
3. **`snapshot`** para obtener los *refs* (`e3`, `e15`…) y actúa con ellos (`click e15`, `fill e5 "..."`). Refs > selectores; usa CSS/locators solo si el ref no basta.
4. **Itera**: si algo falla, lee el snapshot / `console` / `requests`, ajusta y reintenta. Pregunta si hay ambigüedad.
5. **Resultados a archivo, no al contexto**: usa `--raw` y vuelca a CSV/JSON en `downloads/` (gitignored). Ej.: `npx playwright-cli --raw eval "JSON.stringify(...)" > downloads/datos.json`.
6. **Cierra** (`close`) al terminar.
7. **Si el flujo se va a repetir**, guárdalo como **receta** en `references/`.

## Sesiones y perfil dedicado (login persistido)
- **Sesiones con nombre** para no pisar flujos: `npx playwright-cli -s=ghl <cmd>`. Lista/limpia con `list` / `close-all` / `kill-all`.
- Para sitios **con login** (GHL, portales, correo) usa un **perfil persistente** en `.auth/pw-ghl/` (gitignored — nunca se commitea):
  ```bash
  npx playwright-cli -s=ghl open <url-de-tu-panel> --persistent --profile=.auth/pw-ghl
  ```
- **Login asistido (una sola vez):**
  ```bash
  bash .claude/skills/navegador-ghl/scripts/login.sh "https://<tu-panel>" ghl
  ```
  Abre el navegador **headed** para que inicies sesión con tus propias credenciales; la sesión queda guardada en el perfil y las tareas siguientes la reutilizan sin volver a pedir login.
- **Login con credenciales del `.env`** (sin teclear, sin exponer la contraseña): ver [references/receta-login-credenciales.md](references/receta-login-credenciales.md).
- Alternativa puntual: `state-save .auth/<sitio>.json` / `state-load`, cuando no quieras un perfil completo.

> ⚠️ **Un perfil = un navegador a la vez.** Si otra sesión lo tiene tomado (revisa `npx playwright-cli list`), reutilízala con `-s=<nombre>` en vez de cerrarla.

## Las dos APIs de GHL (esto explica el 80% de los errores)
- **API pública** (`services.leadconnectorhq.com`) — con un **Private Integration Token** de la sub-cuenta. Documentada y estable, pero **no cubre todo**: los dashboards, el builder de páginas y los workflows no están ahí.
- **API interna** (`backend.leadconnectorhq.com`) — la que usa la propia UI, con el `token-id` de tu **sesión del navegador**. Es la que te deja clonar sitios y tableros. No está documentada, cambia sin avisar y **es por-empresa**: el token de una agencia no sirve en otra.

Cuando algo "no se puede por API", casi siempre se puede por la interna con esta skill. Cuando algo deja de funcionar de un día para otro, sospecha primero de la interna.

## Seguridad (OBLIGATORIO)
- **Human-in-the-loop:** NUNCA publiques, envíes, pagues, borres ni escribas hacia afuera (mensajes, formularios reales, publicaciones, cambios en una cuenta viva) sin **aprobación explícita** primero. Leer y extraer, libre; actuar hacia afuera, se confirma.
- **Datos de clientes.** Lo que sale del CRM o del portal de un proveedor son datos personales: no los pegues de más en el chat, no los subas a ningún lado y respeta la ley de protección de datos aplicable (en México, la LFPDPPP).
- **Nunca** commitees `.auth/` ni credenciales. Las llaves viven en `.env` (gitignored). Este repo trae `.gitignore` y `.env.ejemplo` listos.
- **Clonar entre cuentas solo con permiso.** Llevarte un sitio tuyo o de tu cliente a otra cuenta es una cosa; copiar el trabajo de un tercero sin autorización es otra.
- Respeta los Términos de Servicio de cada sitio. Automatizar tu propio panel es una cosa; raspar un sitio ajeno a volumen es otra.

## Eficiencia de tokens
- **`--raw`** para piping y para no arrastrar el estado completo al contexto.
- **`snapshot --depth=N`** o `snapshot <ref>` para snapshots parciales.
- Lee los snapshots **desde el archivo** que la CLI deja en `.playwright-cli/` en vez de imprimirlos completos.
- `console` / `requests` solo cuando estés depurando.

## Lecciones aprendidas (no volver a tropezar)
- **Verifica el estado EN VIVO después de un submit** (`eval location.href`), no con un snapshot previo: la navegación tarda y un snapshot viejo te hace concluir que "no entró" cuando sí entró.
- El **Chromium alpha** de la CLI puede arrojar errores de `pattern`/CORS/500 **cosméticos** que no impiden nada. Si de verdad estorban, reabre con Chrome estable: `--browser=chrome`.
- Un badge "protected by reCAPTCHA" **no** es un reto real. Intenta el login directo antes de asumir bloqueo.
- Mantén el navegador **headed** cuando haya riesgo de 2FA o captcha: tú resuelves, la automatización sigue.
- El **builder de páginas y el de workflows no renderizan** en el Chromium de la CLI (canvas vacío). No es un bug tuyo: verifica por API o abre con `--browser=chrome`.

## Recetas incluidas
| Receta | Para qué |
|---|---|
| [receta-login-credenciales.md](references/receta-login-credenciales.md) | Entrar a un portal con usuario/contraseña del `.env` sin exponer la contraseña. Incluye el caso de portales que exigen geolocalización. |
| [receta-qa-funnel.md](references/receta-qa-funnel.md) | Verificar que una landing/funnel cargue, que el formulario funcione y reportar errores de consola y red. |
| [receta-landing-custom-code.md](references/receta-landing-custom-code.md) | Publicar una landing HTML self-contained dentro de un funnel de GHL, sin pelear con el builder. |
| [receta-modal-pdf-footer.md](references/receta-modal-pdf-footer.md) | Convertir los PDFs sueltos del footer (aviso de privacidad, condiciones) en un modal branded con visor y descarga. |
| [receta-clonar-sitio-entre-cuentas.md](references/receta-clonar-sitio-entre-cuentas.md) | Clonar sitios, funnels, blogs y workflows **entre cuentas de GHL distintas**, dejándolos editables en el builder. |
| [receta-clonar-tablero-entre-cuentas.md](references/receta-clonar-tablero-entre-cuentas.md) | Clonar un dashboard de reportes completo (widgets, layout, permisos) entre cuentas. |

Cuando un flujo nuevo quede afinado, escríbelo como receta paso a paso en `references/` — comandos exactos y selectores estables — para reejecutarlo sin re-descubrirlo. Ahí está el valor que se acumula.
