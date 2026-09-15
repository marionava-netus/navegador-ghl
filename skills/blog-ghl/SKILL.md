---
name: blog-ghl
description: Escribe y PUBLICA entradas de blog en el sitio del agente dentro de GHL — con categorías, autor, imagen destacada y SEO — vía la API interna. Úsala SIEMPRE que el agente diga "escríbeme un post de blog", "publica este artículo en mi blog", "sube estos posts", "quiero contenido en mi sitio sobre [tema]", "un blog sobre gastos médicos / autos / retiro", o cuando tras generar contenido haya que materializarlo como entrada de blog. NO es para emails (eso es emails-ghl), ni para lead magnets descargables (eso es ebooks), ni para publicaciones de redes sociales.
---

# Blog en GHL

Convierte un tema (o contenido ya redactado) en **entradas de blog reales y publicadas** en el sitio del agente — con categorías, autor e imagen destacada — vía la API interna, usando la sesión del navegador.

## Por qué existe
El editor de blog de GHL es lento para cargar una tanda de artículos: cada post son ~15 minutos entre pegar el HTML, crear la categoría, subir la imagen y llenar el SEO. Por API salen 8 posts en un minuto, con la meta description y el alt text bien puestos — que es justo lo que nadie llena a mano y es lo que hace que Google los muestre.

## Requisitos de la cuenta
- **Sesión iniciada** en la sub-cuenta, en el perfil `.auth/pw-profile`. Si expiró, corre el login asistido de `navegador-ghl`.
- **Un sitio de blog debe existir** (el script necesita el `blogId`). Si el agente no lo tiene, créalo **una vez por UI**: Sites → Blogs → *Create blog* (título + descripción; el home queda en `/blog`). El `blogId` sale de la URL (`/blogs/site/{blogId}`). Crear el sitio **no tiene API estable** — es el único paso manual.
- `context/ghl.json` con `panel_base` (y, si quieres, `blog.blog_id` y `blog.autor` para no repetirlos en cada spec).

> ⚠️ **Para que el blog se vea en vivo hace falta el dominio conectado.** Sin dominio propio, los posts existen y responden por API pero el agente no tiene una URL bonita que compartir. Adviérteselo antes de que publique una tanda esperando poder difundirla el mismo día.

## Flujo de trabajo
1. **Definir con el agente primero** (si es contenido nuevo): tema, ángulo, a quién le habla, categoría, CTA y cuántos posts. Presenta el plan en chat y **espera su OK antes de redactar**.
2. **Redactar el `rawHTML`** siguiendo [references/copy-y-seo.md](references/copy-y-seo.md). Si el agente ya trae el texto, respétalo y solo maquétalo.
3. **Imagen destacada**: si es local, el script la sube al Media Storage de la sub-cuenta; si ya está hospedada, pásala tal cual.
4. **Armar el spec JSON** (formato en el docstring de `scripts/blog_publish.py`). Guárdalo en una carpeta temporal, no en el proyecto.
5. **Correr el script**:
   ```bash
   python3 .claude/skills/blog-ghl/scripts/blog_publish.py <spec.json>
   python3 .claude/skills/blog-ghl/scripts/blog_publish.py <spec.json> --dry-run   # solo valida
   ```
   Crea o reusa categorías y autor, sube las imágenes locales, crea los posts y **verifica** (201 + imagen 200 + cero rastros de otra cuenta).
6. **Reportar**: tabla con títulos, slugs, categorías y estado.

## Reglas de contenido — el punto delicado
Un blog de negocio lo lee gente que está por tomar una decisión de dinero. Dos reglas que no se negocian:

- **Cero cifras, precios o condiciones inventadas.** Si el post menciona un dato de producto, sale de una fuente verificable y se cita. Cuando no haya fuente, se escribe en general: "la mayoría de los planes incluyen…", nunca un nombre propio con un número que no puedes respaldar.
- **Ningún post es una recomendación personalizada.** El cierre invita a una llamada o cotización, no da un veredicto sobre el caso de quien lee.

El resto (voz, estructura, SEO, HTML) está en [references/copy-y-seo.md](references/copy-y-seo.md).

## ⚠️ Trampas conocidas
1. **Detalle de un post existente**: `GET /blogs/posts/{id}?locationId=` **sin** `blogId` (si lo pones → 422). El `rawHTML` NO viene en la lista `posts/all`, solo en el detalle.
2. **Crear post**: `author` es el **id** del autor y `categories` son **ids**, no etiquetas. El script los resuelve o los crea.
3. **Imágenes**: el CDN sirve por cuenta. Sube al Media Storage de **esta** sub-cuenta (UI `#file-upload-input`) y remapea por nombre de archivo. Una imagen de otra cuenta se ve rota para el visitante.
4. El **borrador placeholder** vacío que a veces deja el sistema ("New Blog Post") no se copia.
5. Acentos y emojis en títulos y HTML: el spec va con `ensure_ascii=False`, sin problema.
6. **Borrar un post**: `DELETE /blogs/posts/{locationId}/{postId}` — el `locationId` va en la RUTA, no en query. Es borrado suave, restaurable desde el filtro "Deleted".

## Verificación
El script revisa cada post (201 + imagen 200) y reporta. Para ver el render real hace falta el dominio conectado; sin dominio, valida por API (lista de posts + detalle) y dilo así — no digas "ya está publicado y visible" si nadie lo puede abrir.

Endpoints completos en [references/endpoints.md](references/endpoints.md).
