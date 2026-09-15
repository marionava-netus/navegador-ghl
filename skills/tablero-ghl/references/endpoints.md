# Endpoints de tableros (dashboards) en GHL

Todo vive en la **API interna** `backend.leadconnectorhq.com/reporting/dashboards`. La API pública (`services.leadconnectorhq.com`) **no expone tableros** — `/dashboards/` y `/dashboard/` dan 404. (GHL expone **dos** niveles de API: la pública con el PIT, y la interna que usa la propia UI con el token de sesión. Los tableros solo viven en la interna.)

## Auth
Headers de la sesión UI (expiran ~1h), capturados con un listener de requests:
```
authorization: Bearer <JWT>      token-id: <JWT firebase>
source: WEB_USER                 channel: APP
version: 2021-04-15              x-reporting-api-version: 3
content-type: application/json
```
`x-reporting-api-version: 3` es el que suele faltar. Sin él algunos endpoints responden formas viejas.

Para capturarlos: el comando `request <n>` de la CLI muestra headers pero **no bodies**, así que para descubrir DTOs hace falta un listener:
```js
async page => {
  let auth = null;
  page.on('request', req => { const h = req.headers();
    if (req.url().includes('/reporting/dashboards') && h['token-id'] && h['authorization'] && !auth)
      auth = {authorization: h['authorization'], 'token-id': h['token-id'], source: h['source'],
              channel: h['channel'], version: h['version'], 'x-reporting-api-version': '3'};
  });
  await page.goto('<url del dashboard>', {waitUntil: 'domcontentloaded'});
  for (let i = 0; i < 60 && !auth; i++) await page.waitForTimeout(500);
  return JSON.stringify(auth || {});
}
```
`waitUntil:'networkidle'` **revienta** aquí (la UI hace polling infinito) → usa `domcontentloaded`. El `--raw` de la CLI devuelve doble-encodeado (`json.loads` dos veces).

## Lectura
| Qué | Llamada |
|---|---|
| Listar | `GET /reporting/dashboards?locationId=` → `{data:{defaultDashboardId, dashboard:[], sharedDashboards:[]}}` |
| Leer uno | `GET /reporting/dashboards/{id}?locationId=` → `{data:{dashboard, widgets[], dashboardWidgets[], dashboardPreferences, widgetPreferences, permission}}` |
| Catálogo de widgets | `GET /reporting/dashboards/widgets-definitions?locationId=` (~500 KB) |
| Permisos | `GET /reporting/dashboards/{id}/permissions?locationId=` |

**`widgets[]`** es la definición (`identifier`, `chartType`, `group`, `module`, `moduleName`, `title`, `options`, `apiConfig`, `objectWidgetOptions`, `extras`).
**`dashboardWidgets[]`** es el layout (`{_id, widgetId, layout:{x,y,w,h,minW,minH,noResize,cellHeight}}`); se cruza por `widgetId → widget._id`. La rejilla es de **12 columnas**, `cellHeight` `"54px"`.

Las barras de título de colores son widgets con `identifier:"object-title"` y `objectWidgetOptions:{title, titleType:"text", textColor, backgroundColor, textAlign}`. El color va en `#RRGGBBAA` (los dos últimos dígitos son el alfa: `FF` = opaco). Usa el color de marca del agente.

## Escritura
### Crear tablero vacío
`POST /reporting/dashboards?locationId=` → `{locationId, title, type:"custom", isPrivate:false}` → 201.
**`isPrivate` es obligatorio** aunque no lo parezca; sin él, 422.

### Reemplazar contenido (el PUT que hace todo)
`PUT /reporting/dashboards/{id}?locationId=`
```json
{"title":"…",
 "activityBuffer":{"create":[{"<widgetId>":{…definición…}}],"delete":["<widgetId>",…]},
 "layout":[{"x":0,"y":0,"w":6,"h":8,"minW":6,"minH":8,"noResize":false,"cellHeight":"54px","id":"<dashboardWidgetId>"}],
 "themeConfig":{"dashboardTheme":{…},"widgetTheme":{}},
 "version":0}
```
- **No existe editar un widget in-place**: solo `create` y `delete`. Para cambiar un color o un filtro, borra y recrea.
- **Los IDs los generas tú**: ObjectId de 24 hex (`secrets.token_hex(12)`). Cada widget necesita **dos** — la clave dentro de `create` (widgetId) y su `dashboardWidgetId`, que es el que va en `layout[].id`.
- Dentro de la definición va también `"layout":{minW,minH,noResize}` (sin x/y/w/h — esos van en el array `layout` de arriba).
- `create` y `delete` conviven: se reemplaza el tablero entero en **una sola llamada**.
- El `themeConfig` se **lee plano** (`{themeName,titleColor,…}`) pero se **escribe anidado** bajo `dashboardTheme`.

### Borrar tablero
`DELETE /reporting/dashboards/{id}?locationId=` con body `{"locationId":"…","version":0}`. Sin `version` → 422.

### Permisos — ⚠️ el que muerde
`POST /reporting/dashboards/{id}/permissions?locationId=` (PUT y PATCH dan 404):
```json
{"locationId":"…","isPrivate":false,
 "permissionAccess":[{"role":"agency_user","permission":"full"},
                     {"role":"account_admin","permission":"write"},
                     {"role":"account_user","permission":"read"}]}
```
Permisos: `full` · `write` (=Edit en la UI) · `read` (=View) · ausente (=No access).

**El DTO solo valida `isPrivate`.** Cualquier otro nombre de campo (`permission`, `permissions`, `rolePermissions`, `roles`…) se ignora en silencio y responde `success:true` sin aplicar nada. Y mandar `{"isPrivate":"x"}` **pone el tablero en privado y vacía los permisos**, también con `success:true`. Regla: no sondear a ciegas, capturar el body real de la UI, y **releer con el GET después de cada escritura**.

### Tablero por defecto
`POST /reporting/dashboards/{id}/set-default` con `{"locationId":"…"}` → 201.
Da **403 `set_default_dashboard_role_view_error`** mientras los roles no tengan permisos asignados. Asigna permisos primero.

### Preferencias por widget
`PUT /reporting/dashboards/{id}/widget-preference` con `{locationId, widgetId, options:{filters:{userId,pipeline_id}}}` — son los filtros que el usuario elige en un widget (ej. el selector de pipeline del embudo). Se guardan por usuario, no forman parte del tablero.

## Trampas de la UI
- Los selects de permisos son componentes custom (`hr-select`): `element.click()` desde `page.evaluate` **no los abre**, hay que usar el `click <ref>` real de la CLI. Con un dropdown abierto el overlay intercepta el siguiente clic → toma snapshot fresco entre pasos (los refs cambian).
- Ids estables para **leer** el valor: `#location-dashboard_select--agency_user` / `--account_admin` / `--account_user`.
- El scroll del tablero no es el de la ventana: es `.bg-gray-50.overflow-y-auto`. Para capturas por secciones muévelo con `eval` y toma screenshots normales (`--full-page` solo trae el viewport).
- El perfil `.auth/pw-profile` admite **un navegador a la vez**; si está ocupado, usa esa sesión en vez de matarla.
