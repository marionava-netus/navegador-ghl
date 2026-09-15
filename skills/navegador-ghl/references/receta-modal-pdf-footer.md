# Receta: PDFs del footer en modal branded (GHL)

**Validada en producción (2026-08)** en el sitio de un despacho de seguros. Convierte los links del footer que apuntan a un PDF crudo del CDN de GHL en un **modal con el documento embebido + botón de descarga**, sin sacar al visitante del sitio.

## Cuándo usarla
El sitio publica documentos legales o de cumplimiento (aviso de privacidad, autorización CNSF, constancia de la aseguradora, buró de entidades financieras) como PDFs sueltos, y quieres que se vean dentro de la marca del despacho. Resuelve el problema de fondo: **el Media Storage de GHL no acepta dominio propio**, así que la URL del PDF siempre delata al CDN — en vez de pelear con la URL, envuelves el documento.

## Dónde vive el código
`Sites → Websites → [sitio] → Settings → Body tracking code`. Aplica a **todas las páginas** del sitio; no hay que republicar.
Código listo: [codigo-modal-pdf.html](codigo-modal-pdf.html) — llena el objeto `DOCS` del inicio y la pila de fuentes (marcada `REEMPLAZA-FUENTE`).

## Cómo funciona
1. **Delegación de eventos** en `document` (fase de captura) → agarra los links por su `href` exacto. Robusto ante el render dinámico de GHL, sin `MutationObserver`.
2. **PDF.js 3.11.174** (`pdf.min.js`, build UMD clásico) renderiza cada página a `<canvas>`. La v4+ solo trae `.mjs` y no carga con `<script>` normal.
3. **Descarga con nombre limpio**: `fetch` → `blob` → `<a download>`, para que baje `Aviso-de-Privacidad-TuDespacho.pdf` y no `a1b2c3d4e5f6.pdf`.

## Trampas clave (todas costaron)
- **El botón "Descargar" tiene el mismo `href` que el PDF**, así que la propia delegación en captura lo intercepta y reabre el modal en vez de descargar. Hay que excluir clics internos: `if (a.closest('.doc-pdf-ov')) return;`.
- **`font-family:inherit` NO sirve**: el `<body>` de los sitios de GHL suele computar **Times** (serif) aunque el diseño use otra. Fija la pila explícita con la fuente real del sitio. Verifica con `getComputedStyle`, no a ojo.
- **`<iframe>` con PDF falla en iOS Safari** → por eso PDF.js y no iframe. El iframe queda solo como respaldo en desktop.
- **Requisito CORS**: el CDN de GHL manda `access-control-allow-origin: *` y no manda `X-Frame-Options` ni CSP. Verifícalo con `curl -I` antes de asumir que PDF.js podrá leer el archivo.
- **"Optimize JavaScript"** (Settings del sitio) **carga el custom code en diferido al hacer scroll**. Al medir `window.__docPdfModal` justo tras cargar da `false`; da `true` después de scrollear. No es bug — pero si mides mal, diagnosticas de más.
- **Navegar por `goto` directo a una URL interna del panel rompe su SPA** (body vacío). Entra por la UI y navega con clics del menú.
- El overflow horizontal de estos sitios suele ser **preexistente** (`drawer__content`, `c-nav-menu-v2`). Mide la línea base **antes** de abrir tu modal y compara el delta, o te culpas de un bug ajeno.

## Rendimiento con escaneados
PDF.js aguanta bien los oficios escaneados (que es lo normal en constancias y autorizaciones): una constancia escaneada de aseguradora — **1.9 MB, 3 páginas, puro imagen** — abre y renderiza completa en **~3 s** en desktop y móvil, legible. No hace falta comprimir ni pre-procesar nada.

## QA mínimo
Playwright a 1440 y 390: que el modal abra sin navegar, que el canvas tenga tinta (`getImageData`, no solo que exista), que la descarga traiga el peso exacto del archivo, que cierre con ESC/overlay/X, y que los links **no** configurados sigan intactos.

Dos comprobaciones que valen oro:
- **Cobertura**: `document.querySelectorAll('a[href$=".pdf"]')` en la página viva vs. las claves de `DOCS` — así sabes si quedó algún documento fuera en vez de suponerlo.
- **Conteo de páginas: NO lo saques con regex sobre el binario.** `/Type /Page[^s]` subcuenta (dio 3 donde había 4). La fuente de verdad es `pdfjsLib.getDocument(...).numPages`. Si tu prueba falla contra el visor, sospecha primero de la expectativa.

Relacionado: [receta-landing-custom-code.md](receta-landing-custom-code.md)
