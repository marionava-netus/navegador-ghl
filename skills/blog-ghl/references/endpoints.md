# API interna de blogs de GHL (validada 2026-07)

Base: `https://services.leadconnectorhq.com`. Auth = headers de sesión capturados en-página con Playwright:
`token-id` (JWT ~1100 chars), `source: WEB_USER`, `channel: APP`, `version: 2021-07-28`, `content-type: application/json`.
(Se capturan con un `page.on('request')` que lee el header `token-id` de cualquier llamada al backend; ver `../scripts/blog_publish.py`.)

## Leer
- **Sitios de blog**: `GET /funnels/funnel/blog/list/?locationId={loc}&limit=15&skip=0&searchTerm=` → `{data:[{_id (blogId), name, description, url, steps:[{type:"blog-home",url:"/blog"},{type:"blog-post",url:"/post"}]}]}`.
- **Posts (lista, SIN html)**: `GET /blogs/posts/all?locationId={loc}&limit=50&offset=0&searchTerm=&status=ALL&blogId={blogId}` → `{blogs:[{_id,title,status,urlSlug,description,imageUrl,categories:[...]}]}`.
- **Post (detalle CON html)**: `GET /blogs/posts/{postId}?locationId={loc}` → `{blogPost:{rawHTML, imageUrl, imageAltText, description, categories:[ids], author:id, urlSlug, status, publishedAt, readTimeInMinutes, wordCount, tags, ...}}`. ⚠️ **NO** pases `blogId` aquí (da 422).
- **Categorías**: `GET /blogs/posts/unique/category?locationId={loc}&blogId={blogId}` → `{categories:[{_id,label,urlSlug,description}]}`.
- **Autores**: `GET /blogs/posts/unique/author?locationId={loc}&blogId={blogId}` → `{authors:[{_id,name,imageUrl,imageAltText}]}`.

## Escribir
- **Crear categoría**: `POST /blogs/categories/` body `{locationId, label, urlSlug, description}` → 201 `{category:[{_id}]}`.
- **Crear autor**: `POST /blogs/authors/` body `{locationId, name, imageUrl, imageAltText}` → 201 (id en `author._id` o `author[0]._id`).
- **Crear post**: `POST /blogs/posts/` body:
  ```json
  {"locationId":"...","blogId":"...","title":"...","rawHTML":"<h2>...</h2>",
   "status":"PUBLISHED|DRAFT|SCHEDULED|ARCHIVED","urlSlug":"...",
   "author":"<destAuthorId>","categories":["<destCatId>",...],
   "imageUrl":"<url CDN destino>","imageAltText":"...","description":"<meta>",
   "publishedAt":"2025-04-28T23:49:15.000Z","readTimeInMinutes":3,"wordCount":500,"tags":[]}
  ```
  → 201 `{blogPost:{_id}}`. Campos mínimos: `locationId, blogId, title, rawHTML, status, urlSlug`.
- **Borrar post**: `DELETE /blogs/posts/{locationId}/{postId}` → 200 (¡el `locationId` va en la RUTA, no en query!). Es soft-delete (restaurable desde el filtro "Deleted"). Validado 2026-07-24.
- **Editar post**: (por confirmar) probable `PUT /blogs/posts/{id}` o `POST /blogs/posts/{id}`; si 404/422, capturar el request real desde el editor. La lista `posts/all` + detalle permiten leer el estado actual.

## Imágenes (Media Storage del destino)
- Sube por la **UI** `/{loc}/media-storage`, input `#file-upload-input` (`multiple:true`) con `setInputFiles([...rutas])`.
- Mapea basename→URL nueva: `GET /medias/files/?altId={loc}&altType=location&parentId=&offset=0&limit=100&query=&type=file&sortBy=updatedAt&sortOrder=desc&mode=public` (¡trailing slash + `type=file`!). El `name` guardado = el basename local subido.
- URL destino típica: `https://assets.cdn.filesafe.space/{loc}/media/{nuevoId}.{ext}`.

## Sitio de blog (crear) — paso manual
No hay API interna estable para crear el **sitio** de blog. Se hace por UI: Sites → Blogs → **Create blog** (título + descripción; el slug se autogenera; home en `/blog`, posts en `/post/{slug}`). Tras crearlo, el `blogId` sale de la URL (`/blogs/site/{blogId}`) o del endpoint de sitios de arriba.
