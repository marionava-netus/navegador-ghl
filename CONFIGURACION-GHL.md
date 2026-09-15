# Configuración de GHL (una sola vez)

Las skills `emails-ghl`, `landings-ghl`, `blog-ghl`, `tablero-ghl` y `quizzes-ghl` operan **tu propia cuenta**. Necesitan tres cosas: un token, el id de la cuenta, y una sesión de navegador. Esto se hace una vez y ya.

---

## 1. El `locationId` (id de tu sub-cuenta)

Entra a tu panel de GHL y mira la barra de direcciones:

```
https://app.gohighlevel.com/v2/location/AbC123XyZ456/dashboard
                                 ^^^^^^^^^^^^
                                 ese es tu locationId
```

Cópialo. Son ~20 caracteres entre letras y números.

---

## 2. El PIT (Private Integration Token)

Es una llave que deja que tu asistente escriba en tu cuenta sin usar tu contraseña.

1. En tu panel: **Settings** (engrane, abajo a la izquierda) → **Private Integrations**.
2. **Create new integration**.
3. Nombre: `Asistente IA`. Descripción: lo que quieras.
4. **Scopes** (permisos) — marca al menos:
   - `emails.write` y `emails.readonly` (secuencias de correo)
   - `blogs.write` y `blogs.readonly` (blog)
   - `medias.write` y `medias.readonly` (subir imágenes)
   - `locations.readonly`, `contacts.readonly`, `opportunities.readonly` (leer tu cuenta)
5. **Create** → te muestra el token **una sola vez**. Cópialo ya.

> 🔑 **El PIT es como la llave de tu casa.** No lo pegues en un chat, no lo mandes por WhatsApp, no lo subas a ningún repositorio. Si crees que se filtró, bórralo en esa misma pantalla y crea uno nuevo — se revoca al instante.

---

## 3. Guardarlos

### `.env` — en la raíz de la carpeta de tu asistente

```
GHL_PIT=pit-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GHL_LOCATION_ID=AbC123XyZ456
```

Este archivo **nunca se comparte ni se sube a ningún lado**. Asegúrate de que tu `.gitignore` tenga:

```
.env
.auth/
downloads/
.playwright-cli/
```

### `context/ghl.json` — tus datos de marca y firma

Copia la plantilla y llénala:

```bash
mkdir -p context
cp .claude/skills/emails-ghl/assets/ghl.ejemplo.json context/ghl.json
```

Los campos que sí o sí necesitas antes de mandar un correo:

| Campo | Qué es |
|---|---|
| `panel_base` | El dominio de tu panel (`https://app.gohighlevel.com`) |
| `location_id` | El del paso 1 |
| `marca.navy` / `marca.naranja` | Tus dos colores de marca, en hex |
| `firma.nombre` | Cómo firmas tus correos |
| `firma.tagline` | Una línea: a quién ayudas y a qué |
| `firma.foto_url` | Tu foto, ya subida a Media Storage |
| `firma.logo_url` | Tu logo, ya subido a Media Storage |
| `firma.sitio_url` / `sitio_label` | Tu sitio |
| `firma.razon_social` | Con qué nombre facturas |
| `firma.direccion` | **Tu dirección física.** Ver la nota legal abajo. |

> Si falta cualquiera de estos, el script **se detiene y te dice cuál**. No inventa valores: un correo masivo firmado con datos equivocados es peor que uno que no salió.

---

## 4. La sesión del navegador

Algunas cosas (landings, blog, tablero) no pasan por el PIT sino por la sesión real del panel. Se inicia una vez:

```bash
bash .claude/skills/navegador-ghl/scripts/login.sh "https://app.gohighlevel.com" ghl
```

Se abre un navegador: **inicia sesión tú mismo** (usuario, contraseña y el 2FA si lo tienes). La sesión queda guardada en `.auth/pw-profile/` y las tareas siguientes la reutilizan.

Cuando expire (cada varias semanas), las skills fallan con un mensaje claro pidiendo que vuelvas a correr ese comando. No es un error, es la sesión caducada.

---

## ⚖️ La dirección física en los correos no es opcional

Todo correo comercial masivo debe llevar **la dirección postal del remitente y una forma visible de darse de baja**. Es requisito de la ley CAN-SPAM en Estados Unidos, y buena práctica exigible en México. Si faltan, los proveedores (Gmail, Outlook) marcan el dominio como spam y **se quema la reputación de envío**: a partir de ahí ni los correos legítimos llegan a la bandeja de entrada.

Por eso `razon_social` y `direccion` son obligatorios. Si el agente trabaja desde casa y no quiere publicar su domicilio, la salida normal es un **apartado postal** o la dirección fiscal del despacho — no dejarlo en blanco.

---

## Checklist antes de la primera corrida

- [ ] `.env` con `GHL_PIT` y `GHL_LOCATION_ID`
- [ ] `.gitignore` con `.env`, `.auth/`, `downloads/`
- [ ] `context/ghl.json` completo
- [ ] Foto y logo subidos al Media Storage **de esta cuenta** (no de otra: el CDN sirve por cuenta y se verían rotos)
- [ ] Sesión del navegador iniciada
- [ ] Prueba de humo: `python3 .claude/skills/emails-ghl/scripts/crear_secuencia.py --smoke-test`
      (crea una plantilla de prueba, la verifica y la borra)

---

¿Se atoró algo? Abre un issue en el repo.
