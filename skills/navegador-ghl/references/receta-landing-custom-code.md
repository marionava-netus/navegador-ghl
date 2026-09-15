# Receta: Landing completa en GHL vía Custom Code (Playwright)

**Validada en producción (2026-07)** construyendo la landing de un taller con registro. Publica una página HTML completa en un funnel de GHL **sin pelear con el builder drag-and-drop**: un solo elemento *Custom HTML/Javascript* contiene toda la landing.

## Cuándo usarla
Landing/página **one-off** con diseño propio (HTML+CSS self-contained) que debe vivir en un funnel de GHL con su dominio.

> ⚠️ **Esta NO es la vía por defecto.** Una página hecha con custom code deja de ser editable en el builder: para cualquier landing normal usa la skill **`landings-ghl`**, que arma la página con los **elementos nativos** de GHL (secciones, columnas, textos, imágenes, botones y formularios) y queda editable a mano. Esta receta es para el caso excepcional: un diseño propio que nadie va a tocar después.

## Piezas
1. **HTML self-contained** — un solo `<div id="...">` + `<style>` con scope por id (el CSS de GHL no interfiere). Imágenes hosteadas en el Media Storage de la cuenta (Sites → Media). Form nativo de GHL embebido: `<iframe src="https://api.leadconnectorhq.com/widget/form/<FORM_ID>">` + `<script src="https://link.msgsndr.com/js/form_embed.js">`.
2. **Form**: crear en Sites → Forms (Create form → Start from Scratch → **Create**; el default trae First/Last/Phone/Email). Limpiar los 2 checkboxes de consentimiento EN y el footer example.com (click elemento → "Remove field"). Labels a español: click input → "Open settings" → Label/Placeholder. Botón: click → settings → fill del paragraph. Settings tab → On Submit → **Redirect to URL** (página gracias). Save.
3. **Funnel step**: abrir funnel existente (hereda dominio) → "Add new step or import" → Name + Path → "Create funnel step" → "Create from blank".

## Trampas clave (aprendidas a golpes)
- El builder vive en un **iframe cross-origin** (`page-builder.leadconnectorhq.com`) → `eval` del DOM NO llega. **`run-code` sí**: `page.frames().find(fr => fr.url().includes('page-builder.leadconnectorhq'))` y locators de Playwright atraviesan el frame.
- El **canvas NO aparece en `snapshot`** (a11y) → navegar por **screenshots + clicks por coordenadas** (`page.mouse.click(x,y)`): el "+" de la sección/columna abre el panel Quick Add.
- Secuencia canvas: sección **Full Width** (panel Sections) → click "+" del canvas → **1 Column** → click "+" de la columna → buscar "code" → **Code** → click "Custom HTML/Javascript" en canvas → **Open Code Editor**.
- **Pegar el HTML**: click dentro del editor (coordenadas ~640,300) → `Meta+KeyA` → `Delete` → **`page.keyboard.insertText(html)`** (instantáneo, aguanta ~10KB sin problema). El HTML se embebe en el script vía `JSON.stringify` en un archivo para `run-code --filename`.
- Guardar: botón **Save del modal** → **icono disco** (~1144,25) → **Publish**.
- El slug de la página se crea como `<path>-page`, pero **la URL buena es la del step path** (`/<tu-path>`); ambas responden 200.
- El form embebido **carga lazy** — en QA esperar ~6s o hacer scroll antes del screenshot; un iframe "en blanco" no es bug.
- Al crear el form, "Start from Scratch" ya viene seleccionado (radio) → el botón es **Create** (no clickear la tarjeta).

## Píxel de Meta — NO va en este HTML
El píxel se instala una sola vez en **Settings → Head Tracking Code** del funnel (aplica a todas las páginas), y los eventos de conversión (`Lead`, `CompleteRegistration`) los manda GHL **por servidor** con el token de la API de conversiones.

Consecuencia para el QA: al hacer `curl` a la página solo vas a ver `fbq('init')` + `PageView`. **Eso es lo normal** — no significa que falte configurar el evento. Verifícalo en el Administrador de Eventos de Meta, no en el HTML.



## QA mínimo
`curl -s -o /dev/null -w "%{http_code}"` a landing y gracias (200) + abrir con Playwright, scroll al form, screenshot y verificar campos visibles.
