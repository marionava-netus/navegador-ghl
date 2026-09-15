# Formularios de GHL (para embeber en las landings)

Cada landing de funnel embebe un **formulario nativo** por su `formId`. Éste es el contrato para
crear o clonar el formulario del agente. **Validado en producción (2026-07).**

> Si el uso crece (formularios multi-paso, lógica condicional, pagos, encuestas), conviene
> separar esto en su propia skill con un motor de campos. Por ahora vive aquí, junto a las landings.

## Contrato (API interna)
- **Builder v2**: `<panel_base>/v2/location/{loc}/form-builder-v2/{formId}` (o Sites → Forms).
  `panel_base` sale de `context/ghl.json`.
- **Leer**: `GET https://backend.leadconnectorhq.com/forms/{formId}` → `{form:{formData, name, locationId,...}}`.
- **Guardar**: `POST https://services.leadconnectorhq.com/forms/{formId}` con body `{name, formData}` + headers `token-id, source:WEB_USER, channel:APP, version:2021-07-28` → **201**.
- `formData.form` (dict grande) contiene: `company` (dominio/logo/nombre del despacho), `fields`, estilos (`customStyle, fieldStyle, style, currentThemeId`), `formAction`, etc.

## Camino A — Crear en blanco (formulario nuevo)
1. UI: Sites → **Forms** → **Create form** → **Start from Scratch** (ya viene seleccionado) → **Create**. Trae First/Last/Phone/Email por defecto.
2. Quédate con el `formId` de la URL (`/form-builder-v2/{formId}`).
3. Ajusta labels/campos en el builder (o por API inyectando `formData`).
4. Settings → **On Submit → Redirect to URL** (a la página de Gracias).

## Camino B — Clonar un formulario existente (mismo diseño en otra página)
1. `GET /forms/{formIdOrigen}` → toma `form.formData` y `form.name`.
2. **Conserva el `formData.form.company` del DESTINO** (logo y dominio de la cuenta destino) — del origen solo traes campos, estilo y textos. Captúralo del blob del formulario destino o de un autosave de la UI.
3. Crea un form en blanco en el destino (Camino A, pasos 1-2) → `formId` nuevo.
4. `POST services.leadconnectorhq.com/forms/{formIdNuevo}` con `{name, formData}` (con el company del destino) → 201.

## Embeber en la landing
- Elemento formulario nativo: `extra.formId.value = "{formId}"` (helper `form(form_id, label)` en `builder.py`).
- Si copias una página que YA referencia un `formId` viejo, **haz swap** del id viejo→nuevo en el blob (string replace) antes de inyectar, o **los leads caen en la cuenta equivocada** — el error más caro de esta receta, porque no falla: simplemente los prospectos aparecen en otro CRM.

## Trampas
- El endpoint de guardado es **services**.leadconnectorhq.com (no backend) — con el mismo `token-id`.
- **Conservar el `company` del destino** es obligatorio, o el formulario muestra el logo y el dominio de otra cuenta.
- Los **labels** se editan en el builder; los campos por defecto vienen en inglés → traducirlos.
- El formulario pertenece a la sub-cuenta, así que sus envíos caen en ese CRM automáticamente; solo cuida el `formId` correcto y el redirect On-Submit.
- Adjuntos: el CDN de GHL rechaza algunos tipos de archivo por API (audio, entre otros). Súbelos desde la UI de Media.
