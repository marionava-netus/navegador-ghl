# Receta: Clonar un sitio / funnel / blog de GHL entre cuentas (idéntico + editable)

**Validada en producción (jul-2026)** clonando un website de 4 páginas + formulario entre dos agencias distintas, y repetida después con un sitio de 8 páginas, un funnel de 3 y un blog de 8 posts.

## Cuándo usarla
Copiar una página / website / funnel / blog de GHL de **una cuenta a otra** dejándolo **idéntico y 100% editable en el builder nativo** (NO Custom Code). Requiere acceso admin (login) a **ambas** cuentas.

> **Ojo:** el share/export nativo de GHL para *websites* no existe en muchas instancias white-label (solo Edit/Clone/Move/Delete, y Clone no cruza cuentas). El menú "Duplicate to another account" solo alcanza cuentas de la **misma agencia**. Entre agencias distintas se hace **transplante de JSON** por la API interna.

## Notación
En toda la receta:
- `<LOC_ORIGEN>` / `<LOC_DESTINO>` — los `locationId` de cada sub-cuenta (los ves en la URL del panel: `/location/<id>/...`).
- `<PANEL_ORIGEN>` / `<PANEL_DESTINO>` — el dominio del panel de cada agencia (ej. `app.gohighlevel.com` o el dominio white-label que use cada una).

## Modelo de datos (clave)
- `GET /funnels/page/{pageId}` (en `backend.leadconnectorhq.com`) → **registro** de la página. El contenido real NO viene inline: está en `pageDataDownloadUrl` (blob firmado de Firebase, descargable con su token).
- El **blob** = `{sections, settings, general, pageStyles, trackingCode, fontsForPreview, popups, popupsList}` → esto es lo editable.
- **Guardar** = `POST /funnels/builder/autosave/{pageId}` con body:
  `{funnelId, pageData:<blob>, pageVersion:<n+1>, pageType:"draft", manualSave:true, integrations:{videoBackground:false,blogMeta:{...},popup:false}}`
- **Auth** (para el `fetch` dentro de la página): headers `token-id` (JWT de la sesión, ~1100 chars), `source:WEB_USER`, `channel:APP`, `version:2021-07-28`, `content-type:application/json` → respuesta **201**.
- **Forms**: `GET /forms/{id}` trae `{form:{formData, name, ...}}`. Guardar = `POST https://services.leadconnectorhq.com/forms/{id}` con `{name, formData}` + los mismos headers.
- **Funnel/steps**: `GET /funnels/funnel/fetch/{funnelId}` → `steps[]` con `{name, pages:[pageId], url}` para mapear páginas.

## Flujo
1. **Login asistido** a la cuenta origen (headed) en el perfil `.auth/pw-ghl`.
2. **Extraer origen**: abre un builder para capturar un `token-id`, luego en `page.evaluate` haz `fetch` de cada `GET /funnels/page/{id}` → saca `pageDataDownloadUrl` → `curl` del blob a disco.
3. **Crear destino**: en la cuenta destino crea el website ("New website" → From blank) y sus páginas. Obtén los nuevos pageIds con `GET /funnels/funnel/fetch/{nuevoFunnelId}`.
4. **Swaps antes de inyectar** (string replace sobre el blob):
   - **Form embebido**: el `formId` viejo por el nuevo del destino.
   - **Imágenes**: súbelas al Media Storage del destino (ver abajo) y cambia cada URL vieja por la nueva.
   - **Marca y dominios**: footer, links y copy — el nombre de la agencia/despacho origen, su dominio y el año del copyright.
   - **IDs estampados**: `srcPageId→destPageId`, `srcFunnelId→destFunnelId`, `<LOC_ORIGEN>→<LOC_DESTINO>` (van en el metadata de cada sección).
5. **Inyectar**: por cada página, `POST /funnels/builder/autosave/{pageId}` con el blob. Verifica **201** y el preview en `https://link.<dominio>/preview/{pageId}`.
6. **Verifica 0 residuos** de los 3 ids del origen + del nombre de la agencia origen **antes** de dar por bueno el clon.

## Subir imágenes al Media Storage del destino (la parte que engaña)
- La API v2 `services.leadconnectorhq.com/medias/upload-file` con el `token-id` de sesión da `ALT_ID_REQUIRED` (deriva la ubicación del scope del token OAuth, no del token de sesión).
- **Lo que SÍ funciona**: la **UI de Media Storage** (`/media-storage`, NO `/medias`, que sale en blanco). Tiene 3 file inputs; usa `#file-upload-input` (`multiple:true`) con `setInputFiles([...rutas locales])` → sube todo de un jalón a la ubicación correcta. Descarga antes las imágenes con `curl` (el CORS del CDN de GHL permite leer los blobs).
- Mapea `basename → URL nueva` con `GET services.leadconnectorhq.com/medias/files/?altId=<LOC_DESTINO>&altType=location&parentId=&offset=0&limit=100&query=&type=file&sortBy=updatedAt&sortOrder=desc&mode=public` (¡trailing slash + `type=file`! sin la diagonal da 422). El `name` guardado = el basename que subiste.

## Endpoints confirmados
- **funnel/fetch** viene envuelto en `.data`: `GET /funnels/funnel/fetch/{id}?locationId=` → `{data:{steps:[{id,name,url,pages:[pageId],sequence}], globalSectionsUrl, domainId, url}}`.
- **page record** NO va envuelto: `GET /funnels/page/{id}?locationId=` → objeto top-level con `name, pageVersion, pageDataDownloadUrl, meta`.
- **Crear páginas por API** (evita clics): `POST /funnels/funnel/create-step` body `{step:{id:<uuid>, name, url:"<sin slash>", pages:[], type:"optin_funnel_page", split:false, control_traffic:100}, funnelId}` → 201, devuelve `page._id` (el nuevo pageId). Loopea para las N páginas.
- **Form**: crear vacío = `POST services.leadconnectorhq.com/forms/` `{locationId, productType:"form", source:"landing_page"}` → 201 con id nuevo. Cargar datos = `POST services.leadconnectorhq.com/forms/{id}` con **solo** `{name, formData}` (cualquier otra prop → 422 "should not exist"). **Borra `formData.form.company`** del origen (trae dominio, logo y nombre de la agencia origen) para no filtrar su marca; GHL la repuebla con la del destino.
- **Global sections**: puede que NO se usen (header/nav inline en cada página). Comprueba si algún blob referencia el id de `global-sections` o marcadores `isGlobalSection`/`type:"global"`; si da 0, omite el trasplante.
- Tras el autosave 201 el `pageVersion` del record puede seguir en 1 (el contenido vive en el **draft**); confirma bajando el `pageDataDownloadUrl` vivo y viendo media del destino + 0 residuos.
- El screenshot del **builder** (iframe pesado) sale en blanco en el Chromium de la CLI — no es bug del clon; verifica por API o abre con `--browser=chrome`.

## Funnels vs websites — mismo método
El modelo de datos es idéntico. Diferencias a cuidar:
- Listar: `funnel/list?...&type=funnel` (los websites usan `type=website`); crear en UI = **New funnel** (mismo modal "From blank"), luego pasos por `create-step`.
- **Global sections (header/nav compartido):** los funnels sí suelen usarlas. Vienen **inline en cada blob** como una sección con `"isGlobal":true`, y el funnel las guarda a nivel `globalSectionsUrl`. Al inyectar en un funnel destino **sin** `globalSectionsUrl` registrada, quedan huérfanas y el builder NO las auto-registra al abrir. Solución robusta y con render idéntico: **poner `isGlobal:false`** en esas secciones del blob (la vuelves sección normal inline; se ve igual, solo pierdes el "editar una vez → todas"). Después se puede re-guardar como global desde el builder.
- **Reúso entre clones:** si ya clonaste otro sitio de la misma cuenta origen, el **form** puede ser el mismo (reusa el formId destino ya creado) y muchos **medios** ya están subidos (dedup por basename contra el mapa anterior; sube solo los nuevos).

## Blogs
Modelo distinto al de funnel/website: se hace por la API v2 `services.leadconnectorhq.com` (no hay blob de Firebase — el HTML vive en el post).
- **Extraer origen**: `GET /funnels/funnel/blog/list/?locationId=&limit=&skip=&searchTerm=` → sitios de blog (blogId, steps). Posts (lista): `GET /blogs/posts/all?locationId=&limit=&offset=&searchTerm=&status=ALL&blogId=` → `{blogs:[...]}` (solo metadatos, **sin** rawHTML). **Detalle con HTML**: `GET /blogs/posts/{postId}?locationId=` (¡SIN blogId, si lo pones da 422!) → `{blogPost:{rawHTML, imageUrl, categories:[ids], author:id, urlSlug, description, publishedAt, readTimeInMinutes, wordCount, tags, ...}}`. Categorías: `GET /blogs/posts/unique/category?locationId=&blogId=`; autores: `/blogs/posts/unique/author?...`.
- **Crear destino**: sitio de blog por UI (Sites → Blogs → Create blog; título + descripción; el slug se autogenera; el home queda en `/blog` y los posts en `/post/{slug}`) → blogId nuevo. **Categorías**: `POST /blogs/categories/` `{locationId,label,urlSlug,description}` → 201. **Autor**: `POST /blogs/authors/` `{locationId,name,imageUrl,imageAltText}` → 201. **Posts**: `POST /blogs/posts/` `{locationId,blogId,title,rawHTML,status,urlSlug,author,categories,imageUrl,imageAltText,description,publishedAt,readTimeInMinutes,wordCount,tags}` → 201.
- **Swaps**: imágenes (featured `imageUrl` + `<img>` inline en el rawHTML + imagen del autor) → re-hospedar en el Media Storage del destino y remapear por basename; **categorías y autor** → ids nuevos del destino.
- **Integración con la web**: blog y sitio se unen por el **dominio** (el blog sirve en `/blog` y `/post/*`). No hay amarre extra. El draft de placeholder ("New Blog Post") se omite.

## Automatizaciones (workflows)
Todo por `backend.leadconnectorhq.com` con el `token-id` de sesión. **El token es por-empresa**: usa el del origen para leer y el del destino para escribir (no cruzan compañías). El builder de workflows **no renderiza** en el Chromium de la CLI → todo por API.
- **Listar**: `GET /workflow/{loc}/list?type=workflow&limit=300&offset=0&sortBy=name&sortOrder=asc&includeCustomObjects=true&includeObjectiveBuilder=true` → `{rows:[{id,name,status,type}], count}`. `status:"published"` = activo.
- **Leer detalle**: `GET /workflow/{loc}/{wf}` → record completo (trae `version`, settings, `workflowData.templates` = **acciones inline**, `fileUrl` = blob de Firebase). El blob no baja por `fetch` (CORS); usa `workflowData.templates` directo.
- **Leer triggers**: `GET /workflow/{loc}/{wf}?includeTriggers=true` → **parcial** `{workflowData, triggers, dependentAssets, permissionMeta}` (¡NO trae `version`! por eso no sirve de base para el PUT).
- **Crear**: `POST /workflow/{loc}` body `{name, type:'workflow'}` → 200 `{id}`. (NO mandes `parentId:'root'` → "Parent directory not found".)
- **Guardar acciones**: `GET /workflow/{loc}/{nid}` (record fresco, trae `version`) → `PUT /workflow/{loc}/{nid}` con `{...record, workflowData:<origen>}` → 200, sube `version` y regenera el blob. Copia también los settings sueltos (`allowMultiple`, `removeContactFromLastStep`, `stopOnResponse`, `autoMarkAsRead`, `timezone`). Queda en **draft**.
- **Swaps en workflowData**: `<LOC_ORIGEN>→<LOC_DESTINO>`, `srcFormId→dstFormId`. Lo demás (userIds, pipelines/etapas, tags, plantillas de WhatsApp, `from_phone_number`, calendarios, agentes de IA) no tiene equivalente si el destino aún no tiene esas conexiones → se quedan y se recablean a mano.
- **Triggers = NO clonables por API (a jul-2026)**: `POST /workflow/{loc}/trigger` responde 200 `{id}` pero **no persiste** (404 por id, lectura en 0), y el PUT del workflow **ignora** un campo `triggers`. El builder escribe el blob `triggersFilePath` por una vía no replicable. **Solución:** extrae los triggers con `?includeTriggers=true` y **documéntalos** para re-armarlos a mano (casi siempre apuntan a assets que aún no existen en el destino).
- **Borrar** (limpieza de pruebas): `DELETE /workflow/{loc}/{wf}` → 200.

## Trampas
- `run-code` corre en **Node, no en la página** → ahí no existe `window`; guarda resultados con `await page.evaluate(o=>{window.__x=o;}, data)` **dentro** del evaluate y extráelos con `--raw eval "JSON.stringify(window.__x)"`. `--raw eval` devuelve el valor **doble-encodeado** (string JSON dentro de string) → `json.loads` dos veces.
- `page.goto` con `waitUntil:'networkidle'` **revienta** en GHL (polling infinito) → usa `domcontentloaded` y espera el token del listener.
- `run-code` no tiene `require`/`fs`, ni aguanta `page.reload` sobre página sucia (dispara el diálogo "¿salir?"). Usa navegación in-script (`page.goto(url)` dentro del `async page=>{}`); si aparece el modal nativo, `dialog-accept`.
- Blobs grandes (≈1 MB) → embébelos como literal en el archivo JS (`JSON.stringify`) y corre con `run-code --filename`.
- Los clicks por coordenada en el canvas (iframe) son frágiles; prefiere capturar token/versión con un request-listener + navegación in-script.
- `pageVersion` debe ser numérico y mayor al actual: lee el record y manda `+1`.
- Todo queda en **draft** (sin publicar) hasta darle Publish. **Reconectar los forms al CRM del destino es obligatorio** — si no, los leads siguen cayendo en la cuenta origen.

## Antes de clonar: permiso
Clonar un sitio de otra agencia solo es legítimo si es **tuyo o de tu cliente** y tienes autorización para llevártelo. Copiar el trabajo de un tercero sin permiso es otra cosa.

Relacionado: [receta-clonar-tablero-entre-cuentas.md](receta-clonar-tablero-entre-cuentas.md)
