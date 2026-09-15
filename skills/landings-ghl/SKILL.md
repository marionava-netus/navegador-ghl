---
name: landings-ghl
description: Crea las landing pages y páginas de funnel del agente como páginas NATIVAS y EDITABLES del builder de GHL — secciones, textos, imágenes, botones y formularios reales — autorando el pageData e inyectándolo por la API interna. Incluye cómo crear y clonar los FORMULARIOS que capturan los leads. Úsala SIEMPRE que el agente diga "hazme una landing", "arma la página de registro/gracias", "una página para captar prospectos de [producto]", "crea el formulario de contacto", "quiero una landing que pueda editar yo después", o cuando tras diseñar una campaña haya que materializar sus páginas. NO es para una landing de código que nadie va a editar visualmente (para eso, la receta receta-landing-custom-code de navegador-ghl).
---

# Landing pages nativas en GHL

Convierte un diseño (HTML o un brief) en **páginas nativas del builder**: cada texto, imagen, botón y formulario es un elemento real que el agente ajusta después arrastrando, sin tocar código. Se autora el `pageData` con un motor de factories y se inyecta por la API interna.

## Por qué así
- El objetivo es **editabilidad**. Un bloque *Custom HTML* se ve idéntico pero el agente no puede cambiarle una palabra sin llamarte.
- No existe un conversor HTML → builder. La vía que funciona: **autorar el `pageData` nativo** reusando plantillas de elementos reales del builder.
- El motor vive en `scripts/builder.py` (factories `heading/para/button/image/form`, contenedores `Sec.col/row`, `card_col`, `section`) + plantillas limpias en `assets/el-*.json`.

## Antes de empezar
- `context/ghl.json` con `panel_base` y `location_id` (ver [../../CONFIGURACION-GHL.md](../../CONFIGURACION-GHL.md)).
- Sesión iniciada en el panel, en el perfil `.auth/pw-profile` de la skill `navegador-ghl`. Si expiró, corre su login asistido.

## Modelo de datos (imprescindible)
- **pageData** = `{sections, settings, general, pageStyles, trackingCode, fontsForPreview, popups, popupsList}`. **Reusa `settings/general/pageStyles/fonts` del blob ACTUAL de la página** — así heredas el tema y las tipografías del sitio del agente; solo reemplazas `sections`.
- Una **sección** = `{id, metaData:{type:section, child:[rowIds], styles,...}, elements:[TODOS los nodos planos], sequence,...}`. `elements[]` es una lista PLANA de rows + cols + hojas; el árbol se arma por `child` (ids): section.child=[rowIds] → row.child=[colIds] → col.child=[elementIds]. El motor lo hace por ti.
- **Endpoints** (`backend.leadconnectorhq.com` salvo formularios):
  - `GET /funnels/funnel/fetch/{funnelId}` → `steps[]` con `{name, pages:[pageId], url}` (mapea las páginas).
  - `GET /funnels/page/{pageId}` → el registro; el contenido real está en `pageDataDownloadUrl` (blob público con token) → bájalo con curl.
  - `POST /funnels/builder/autosave/{pageId}` → **guarda**. Body `{funnelId, pageData, pageVersion:<actual+1>, pageType:'draft', manualSave:true, integrations:{...}}`. Responde **201**.
  - Formularios: `GET backend…/forms/{id}` y `POST services…/forms/{id}` — ver [references/formularios.md](references/formularios.md).
- **Auth**: header `token-id` (JWT de sesión) + `source:WEB_USER, channel:APP, version:2021-07-28`. Se captura navegando in-script al builder (ver `make_inject_js`).

## Flujo de trabajo
1. **Confirma con el agente el alcance**: una página o el funnel completo, y qué tan fiel al diseño. Enséñale la estructura antes de construir.
2. **Consigue el diseño**: HTML propio, un brief o una referencia. Extrae contenido, paleta, imágenes y el `formId`.
3. **Prep (solo lectura)** con `navegador-ghl`: captura el token, saca el `funnelId` y los `pageId` de cada paso (`funnel/fetch`), y baja el blob actual de cada página (lo necesitas de wrapper).
4. **Escribe un `_build_native.py` por funnel** que importe `scripts/builder.py`, defina `build_<seccion>(s)` con el contenido, arme `section(...)`, registre los colores del tema y escriba el blob.
5. **VERIFICA que el blob no traiga imágenes de otra cuenta** antes de inyectar (Trampa #1). El motor limpia, pero cuenta las referencias por si acaso.
6. **Inyecta** cada página: `make_inject_js(location, funnelId, pageId, blob)` → escríbelo a un archivo → `npx playwright-cli -s=ghl run-code --filename ...` → espera `status:201`.
7. **Verifica el render en la PÁGINA SERVIDA**, no solo en el canvas (Trampa #5). Screenshot para el agente.
8. **Checkpoint con el agente**: que la revise en su builder. Con su OK, publica.

## Esquema de elementos (lo esencial)
- **Texto**: `sub-heading` (headings, el tag lo pone el HTML) y `paragraph`. `extra.text.value` = HTML (admite `<span style>`, `<b>`, emojis). Tamaño con `desktopFontSize`/`mobileFontSize`. Color, alineación y peso en `styles`.
- **Botón**: `extra.action` = `scrollToElement` (a un `sec_id`), `visitWebsite` (url) o `none`. **Pon `extra.theme.value=None`** o el tema de la plantilla pisa tus colores.
- **Imagen**: `extra.imageProperties.value.url`. **Súbelas a la Media Storage de la sub-cuenta del agente** por la UI (`/media-storage` → `#file-upload-input`). Una imagen referenciada desde otra cuenta se ve rota para el visitante.
- **Formulario nativo**: `extra.formId.value` = id del formulario → [references/formularios.md](references/formularios.md).
- **Fondos**: color sólido opaco = `backgroundColor: var(--...)` (registra el color con `register_theme_colors`; **el hex crudo NO renderiza**). Imagen de fondo = `styles.background` con el string CSS completo (`linear-gradient(...), url('...') center/cover`).
- **Centrado**: `wrapper.textAlign` en el elemento + `textAlign:center` en la columna (el motor ya lo pone).

## ⚠️ Trampas conocidas (cada una costó una corrección en producción)

1. **[EL BUG GRANDE] Las plantillas de `col`/`row` traen una `bgImage` incrustada y un campo recursivo `element` con imágenes de la cuenta de donde se extrajeron.** Sin limpiar, las +20 columnas heredan esa imagen y **se cuela como fondo de TODA la página** (ilegible). El motor llama `clear_foreign()` en cada col/row/section/image. **Cuenta siempre las referencias externas en el blob final = 0** antes de inyectar.
2. **Los fondos de sección y columna necesitan `var(--...)` del tema**, no hex. Regístralos en `general.colors` y en el `:root` de `pageStyles` con `register_theme_colors` — el hex crudo en `backgroundColor` sale transparente.
3. **El botón trae `theme: button_theme_4`** que ignora tus estilos → `extra.theme.value=None`.
4. **Alineación**: el texto sale a la izquierda si no pones `wrapper.textAlign` + columna centrada.
5. **[LEER ANTES DE DAR ALGO POR BUENO] El canvas del builder NO prueba cómo queda la página real.** El canvas pinta bonito (aplica el tema, resuelve los `var(--...)`, muestra los bloques de código como un placeholder limpio) mientras la **página servida** puede salir rota: sin fondos, sin renderizar el código, con las imágenes fuera de escala. Cuando el preview y el canvas se contradicen, **no asumas que el preview miente** — es la señal de que algo no está aplicando de verdad. Esto costó una migración completa que se entregó "OK según el canvas".
   - **QA mínimo aceptable**: abrir la **página servida** (preview con cache-bust, o publicada en un path de staging) y comprobar en el DOM real los `getComputedStyle().backgroundColor` de las secciones, que el HTML de los bloques `code()` esté presente **y renderizado**, y el ancho real de las imágenes.
   - El canvas sirve para revisar **estructura y jerarquía**, no para firmar el render.
   - `setViewportSize 1280x5600` sigue siendo útil para ver toda la página de un jalón.
6. **Token e inyección**: captura el token con `page.goto` in-script (NO `reload` sobre una página sucia → dispara el diálogo "¿salir?"; si aparece, `dialog-accept`). `run-code` no tiene `fs`/`require`: embebe el blob como literal en el JS.
7. **`pageVersion`** debe ser numérico y mayor al actual (lee el registro, manda `+1`).
8. **El ancho de una imagen vive en `styles.width`, NO en el wrapper** — y la plantilla trae **200 px fijos**. Si solo tocas `wrapper.width`, todas las imágenes salen diminutas. Usa `image(..., full=True)` (100 %) o `width=<px>`.
9. **Los botones salen en MAYÚSCULAS** por el `textTransform` de la plantilla. El factory ya manda `tt='none'`; si quieres versalitas, pásalo explícito.
10. **El builder sanea el HTML de los textos**: conserva `color` y `font-*`, pero **descarta `background`, `padding` y `display` inline, y aplana `<table>`**. Consecuencias: (a) un menú hecho de `<a>` dentro de un párrafo queda pegado → **haz el menú con `button()` nativos, uno por columna**; (b) para tablas de datos usa líneas con `<br>` + `&nbsp;`.
11. **Enfoque HÍBRIDO** (nativo + `code()`): cuando el diseño trae widgets que el builder no tiene (slider, galería con lightbox, carrusel), no arrastres el CSS/JS del sitio viejo — **reescribe el widget self-contained en ~3 KB** dentro de un `code()` y deja el resto nativo. Un bloque de código se ve como placeholder en el canvas: es normal; verifícalo aparte.
12. **[OJO] Las páginas de FUNNEL se sirven EN VIVO desde el estado guardado.** Inyectar por `autosave` **ya cambia la URL pública** — no hay compuerta de borrador como en los *websites*. Implicación: construye y verifica ANTES de inyectar sobre un funnel publicado, o avísale al agente de que el cambio es inmediato (un error queda live frente a sus prospectos). El botón "Publish" del builder solo re-guarda. Para trabajar sin exponer, usa un funnel o un `path` de staging. Los **websites** sí tienen borrador y Publish real.

## Assets
- `scripts/builder.py` — el motor: factories, contenedores, limpieza de imágenes ajenas, registro de colores y `make_inject_js`.
- `assets/el-*.json` — plantillas de elementos reales del builder, **ya limpias** (paragraph, sub-heading, button, image, row, col, form, code, section-meta).
- `references/formularios.md` — crear y clonar los formularios que capturan los leads.

## Relacionadas
`navegador-ghl` (la infraestructura de sesión) · su receta `receta-landing-custom-code.md` para la vía de código cuando la página no se va a editar visualmente.
