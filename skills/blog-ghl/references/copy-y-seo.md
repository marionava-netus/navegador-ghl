# Copy y SEO para el blog

Antes de escribir, confirma **a quién le habla el blog**: al cliente final o a otros profesionales del gremio. El público manda el tono, y casi siempre es el cliente final.

## Voz
- Casual, directo y **empático**. La persona que lee llega con una duda o un problema, no buscando un tratado.
- **Dominio real del tema**: usa la jerga correcta del sector y explícala en la misma frase. Quien la conoce ve que sabes; quien no, aprende.
- **Honestidad por encima de la venta.** Es el activo del negocio. Un post que dice "en este caso puede que no te convenga" vende más que tres que prometen.
- Nada de humo tecnológico ni siglas vacías.

## Las dos reglas duras
1. **Cifras, precios y condiciones: solo con fuente.** Un dato con nombre y número se publica solo si viene de la página oficial, del documento vigente o de una fuente citable. Si no hay fuente a la mano, escribe en general.
2. **El post no es una recomendación personalizada.** Cierra invitando a una llamada o a una cotización, nunca dictaminando qué debe contratar quien lee. Si tu sector está regulado, remata con la línea de descargo que te aplique (ej. *"Este contenido es informativo; las condiciones se rigen por el contrato firmado."*).

## Estructura de un post
1. **H1 = título** — lo pone GHL desde `title`; **no lo repitas** en el HTML.
2. **Gancho** (1-2 párrafos): el dolor o la pregunta real del lector, en sus palabras.
3. **Cuerpo** en secciones con `<h2>`/`<h3>`, párrafos cortos, listas `<ul>`, y algún `<blockquote>` para la idea que quieres que se lleven.
4. **Cierre + UN SOLO CTA** (agendar, cotizar, escribir por WhatsApp). Link suave, no venta dura.
5. Longitud típica: **500-900 palabras**. Calcula `wordCount` y `readTimeInMinutes` (≈ palabras/200) **reales**, no inventados.

## SEO
- **`title`**: la keyword principal al frente, natural y clickeable. Nada de clickbait vacío.
- **`urlSlug`**: corto, kebab-case, con la keyword, **sin acentos**.
- **`description`** (meta): **120-160 caracteres**, con la keyword y una razón para hacer clic. Es lo que más se olvida y lo que decide si alguien entra desde Google.
- **`imageAltText`**: describe la imagen de verdad, con la keyword si encaja natural.
- **Categorías**: reutiliza las que ya existen en ese blog antes de crear nuevas (el script deduplica por etiqueta, pero tres categorías casi iguales ensucian el sitio).
- **Palabras clave locales**: un negocio local compite por su plaza, no por el país. "diseño web en Querétaro" gana más que "diseño web".

## HTML
- Limpio y semántico: `<h2>`, `<h3>`, `<p>`, `<ul>/<li>`, `<blockquote>`, `<img src alt>`, `<a>`.
- **Sin estilos inline ni `<style>`** — el tema del blog aplica el diseño; los estilos propios pelean con él.
- Imágenes dentro del cuerpo: URLs ya hospedadas en el Media Storage de esta misma sub-cuenta.
- Emojis con moderación, y solo si encajan con la marca.
