# Receta: Clonar un TABLERO (dashboard de reportes) de GHL entre cuentas

**Validada en producción (ago-2026)** clonando un dashboard de **40 widgets** entre dos agencias distintas.

## Cuándo usarla
Copiar un dashboard de la sección **Tablero / Dashboard** (widgets de reportes: contadores, gráficas, funnel, barras de título) entre cuentas de GHL. Para páginas, funnels y blogs es otra receta: [receta-clonar-sitio-entre-cuentas.md](receta-clonar-sitio-entre-cuentas.md).

> El menú del tablero tiene "Duplicate to another account", pero solo alcanza cuentas de **la misma agencia**. Entre agencias distintas = transplante por API interna.

## Notación
`<LOC_ORIGEN>` / `<LOC_DESTINO>` = los `locationId` de cada sub-cuenta (los ves en la URL del panel).

## Auth
API **interna** `backend.leadconnectorhq.com` con los tokens de la sesión de la UI. La API pública (`services.leadconnectorhq.com`) **no expone dashboards** (404 en `/dashboards/` y `/dashboard/`).

Headers necesarios (además de `authorization` y `token-id` de la sesión):
```
x-reporting-api-version: 3
source: WEB_USER   channel: APP   version: 2021-04-15   content-type: application/json
```
Captura: abre la cuenta con `-s=ghl --persistent --profile=.auth/pw-ghl --browser=chrome`, navega al dashboard, `requests` → busca `GET /reporting/dashboards?locationId=…` → `request <n>` y copia los headers.

## Modelo de datos
- `GET /reporting/dashboards?locationId=` → `{data:{defaultDashboardId, dashboard:[…propios], sharedDashboards:[…]}}` (cada uno `{_id,title,isDefault}`).
- `GET /reporting/dashboards/{id}?locationId=` → `{data:{dashboard, widgets[], dashboardWidgets[], dashboardPreferences, widgetPreferences, permission}}`.
  - **`widgets[]`** = la definición: `{identifier, chartType, group, module, moduleName, title, options, apiConfig, objectWidgetOptions, extras}`. `options` trae aggregations, filtros, groupBy, dateProperty, dateRangeOverride.
  - **`dashboardWidgets[]`** = el layout: `{_id, widgetId, layout:{x,y,w,h,minW,minH,noResize,cellHeight}}`. Se cruza con `widgets[]` por `widgetId → widget._id`.
  - Las **barras de título de colores** son widgets normales con `identifier:"object-title"` y `objectWidgetOptions:{title,titleType,textColor,backgroundColor,textAlign}`.
- `GET /reporting/dashboards/widgets-definitions?locationId=` → catálogo completo de widgets disponibles (~500 KB), útil si hay que mapear un identifier raro.

## Escribir: un solo PUT reemplaza todo
`PUT /reporting/dashboards/{id}?locationId=` con:
```json
{"title":"…","activityBuffer":{"create":[{"<nuevoWidgetId>": {…def…}}],"delete":["<widgetId>"]},
 "layout":[{"x":0,"y":0,"w":6,"h":8,"minW":6,"minH":8,"noResize":false,"cellHeight":"54px","id":"<dashboardWidgetId>"}],
 "themeConfig":{"dashboardTheme":{…},"widgetTheme":{}},"version":0}
```
- **Tú generas los IDs**: `secrets.token_hex(12)` (ObjectId de 24 hex). Cada widget necesita **dos**: la clave del objeto en `create` (widgetId) y su `dashboardWidgetId`, que es el que va en `layout[].id`.
- Dentro de cada definición va también `"layout":{minW,minH,noResize}` (sin x/y/w/h — esos van en el array `layout` de arriba).
- `create` y `delete` conviven en el mismo PUT → **borra los widgets stock y crea los nuevos en una sola llamada**. Responde 200.
- El `themeConfig` del origen viene plano (`{themeName,titleColor,…}`); al escribir va anidado bajo `dashboardTheme`.

## Swaps antes de inyectar (string replace sobre `options`)
- `pipeline_id` y `pipeline_stage_id` → ids del pipeline/etapa equivalente en el destino (`GET services.leadconnectorhq.com/opportunities/pipelines?locationId=` con el token de cada cuenta, cruzando **por nombre de etapa**).
- `funnelWebsiteId` (widgets de visitas) → el funnelId del sitio clonado en el destino.
- `locationId` → `<LOC_DESTINO>`.
- Los **labels guardados** en `uiMeta.fieldMeta.savedOptionPairs` también traen el nombre viejo → cámbialos o el filtro se seguirá viendo con el nombre del origen.
- **Marca de la agencia anterior**: revisa los títulos de las barras de color — ahí suele venir el nombre del despacho o de la agencia origen.
- Verifica **0 residuos** de los ids del origen antes de mandar el PUT.

## Permisos: el campo se llama `permissionAccess`
`GET /reporting/dashboards/{id}/permissions?locationId=` → `{permission:[{role,permission}], isPrivate, dashboardOwner}`.
Escribir = **POST** al mismo path (PUT/PATCH dan 404) con:
```json
{"locationId":"<LOC_DESTINO>","isPrivate":false,
 "permissionAccess":[{"role":"agency_user","permission":"full"},{"role":"account_admin","permission":"write"},{"role":"account_user","permission":"read"}]}
```
> **Trampa peligrosa:** el DTO **solo valida `isPrivate`**. Cualquier otro nombre de campo (`permission`, `permissions`, `rolePermissions`…) se ignora en silencio y responde `success:true`. Peor: mandar `{"isPrivate":"x"}` **pone el tablero en privado y VACÍA los permisos** — igual con `success:true`. Nunca sondees este endpoint a ciegas; captura el body real de la UI (botón ⋮ → Manage permissions → Save) con un listener de requests.

## Tablero por defecto
`POST /reporting/dashboards/{id}/set-default` con `{"locationId":"<LOC_DESTINO>"}`.
Da **403 `set_default_dashboard_role_view_error`** mientras los roles no tengan permisos asignados. Arregla los permisos primero y entonces responde 201.

## Capturar bodies de requests (para descubrir DTOs)
`request <n>` de la CLI muestra headers pero **no el body**. Para el body, engancha un listener con `run-code`:
```js
async page => {
  const ctx = page.context();
  if (!globalThis.__capAttached) { globalThis.__capAttached = true;
    ctx.on('request', req => { const u = req.url();
      if (u.includes('/reporting/dashboards') && ['PUT','POST'].includes(req.method())) {
        const d = req.postData();
        page.evaluate(([u,m,d]) => { (window.__cap=window.__cap||[]).push({u,m,d}); }, [u, req.method(), d]).catch(()=>{});
      }});
  }
  await page.evaluate(() => { window.__cap = window.__cap || []; });
  return 'listener attached';
}
```
Luego `--raw eval "window.__cap[0].d"` (viene doble-encodeado → `json.loads` dos veces). **El listener se pierde al navegar** — reengánchalo tras cada `goto`.

## Trampas de la UI del tablero
- Los selects de permisos son componentes custom (`hr-select`). `element.click()` desde `page.evaluate` **no los abre**; usa el `click <ref>` real de la CLI. Y con un dropdown abierto el overlay intercepta el siguiente clic → toma **snapshot fresco entre cada paso** (los refs cambian) y selecciona la opción por su ref.
- Los selects tienen ids estables: `#location-dashboard_select--agency_user` / `--account_admin` / `--account_user`; sirven para **leer** el valor (`.textContent`) aunque no para clicar.
- El scroll del tablero no es el de la ventana: es `.bg-gray-50.overflow-y-auto`. Para capturas por secciones muévelo con `eval` y toma screenshots normales (`--full-page` solo trae el viewport).

## Rebrandear las barras de título
Las barras de color son widgets `object-title`; su color vive en `objectWidgetOptions.backgroundColor` (formato `#RRGGBBAA`, ej. `#1F2937FF`). **No se pueden editar in-place**: el PUT solo acepta `create`/`delete` en el `activityBuffer`, así que para recolorear hay que **borrar cada barra y recrearla** con el color nuevo — conservando su posición en el array `layout` (usa el `dashboardWidgetId` nuevo en la entrada correspondiente y deja intactas las de los demás widgets, que llevan su `dashboardWidgets[]._id` actual).

## Idioma
Los widgets de sistema (Funnel, Conversion rate, Sales efficiency, Facebook Ads report…) muestran su título por **i18n según el idioma del usuario que mira**, no según lo guardado: se ven en inglés con la UI en inglés y en español con la UI en español. No es una diferencia del clon. Los widgets custom sí conservan su título literal.
