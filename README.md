# Skills de GHL para Claude Code

Cinco skills para operar **GHL / HighLevel** (o su marca blanca) desde Claude Code: crear correos, landings, formularios, blog, quizzes y tableros por API, y controlar el navegador para lo que la API no cubre.

## Las skills

| Skill | Qué hace |
|---|---|
| **`navegador-ghl`** | Controla el navegador con la **Playwright CLI**: opera apps con login, hace QA de páginas, extrae datos y **clona sitios, funnels, blogs, workflows y tableros entre cuentas distintas**. Es la base de las demás. |
| **`emails-ghl`** | Secuencias de correo como **plantillas reales del editor** (no HTML pegado), con tu firma, tu footer legal y el prompt listo para que la plataforma arme el workflow. |
| **`landings-ghl`** | Landing pages y páginas de funnel **nativas y editables** en el builder — secciones, columnas, textos, imágenes, botones y **formularios de captura** reales — autorando el `pageData` e inyectándolo por la API interna. |
| **`blog-ghl`** | Escribe y publica posts con categorías, autor, imagen destacada y SEO. |
| **`quizzes-ghl`** | Quizzes de diagnóstico: 12 preguntas, puntaje por categoría, resultado por nivel y CTA al calendario que corresponde al tema. |
| **`tablero-ghl`** | Deja el dashboard en español y ordenado: contactos → citas → ventas → higiene del CRM. |

**Las landings se arman con los elementos nativos de GHL**, no con un bloque de custom code: quedan editables a mano en el builder. (El custom code existe como receta aparte en `navegador-ghl`, solo para páginas one-off que nadie va a editar después.)

## Recetas del navegador

Todas validadas en producción (jun–ago 2026), con las trampas que costaron horas y no solo el camino feliz:

| Receta | Para qué |
|---|---|
| `playwright-cli-comandos.md` | Referencia completa de la CLI |
| `receta-login-credenciales.md` | Entrar a un portal con credenciales del `.env` sin exponer la contraseña |
| `receta-qa-funnel.md` | QA de una landing/funnel: consola, red, formulario |
| `receta-landing-custom-code.md` | Landing HTML one-off dentro de un funnel |
| `receta-modal-pdf-footer.md` | PDFs del footer en modal branded con visor y descarga |
| `receta-clonar-sitio-entre-cuentas.md` | Sitios, funnels, blogs y workflows entre cuentas |
| `receta-clonar-tablero-entre-cuentas.md` | Un dashboard completo (40 widgets, layout y permisos) |

## Instalación

```bash
git clone https://github.com/marionava-netus/navegador-ghl.git
cp -R navegador-ghl/skills/* <tu-proyecto>/.claude/skills/
cp navegador-ghl/CONFIGURACION-GHL.md <tu-proyecto>/

cd <tu-proyecto>
npm install --save-dev @playwright/cli
npx playwright-cli install-browser chromium
```

Después, el login de una sola vez:

```bash
bash .claude/skills/navegador-ghl/scripts/login.sh "https://<tu-panel-de-ghl>" ghl
```

Inicia sesión en la ventana que se abre y ciérrala. La sesión queda en `.auth/pw-ghl/` y todas las tareas siguientes la reutilizan.

Las cinco skills de API necesitan además una configuración de una sola vez (tu PIT, tu `locationId` y tus datos de marca): **[CONFIGURACION-GHL.md](CONFIGURACION-GHL.md)**.

## Las dos APIs de GHL

Vale la pena tenerlo claro antes de empezar, porque explica casi todos los errores:

- **API pública** (`services.leadconnectorhq.com`), con un **Private Integration Token**: documentada y estable, pero **no cubre todo** — dashboards, builder de páginas y workflows no están ahí.
- **API interna** (`backend.leadconnectorhq.com`), con el `token-id` de tu **sesión del navegador**: es la que permite clonar sitios y tableros. No está documentada, cambia sin avisar y **es por-empresa**.

## Requisitos

- **Node.js** (Playwright CLI) y **Python 3** (los builders).
- Acceso **admin** a la cuenta de GHL que vas a operar. Para clonar entre cuentas, a las dos.

## Seguridad

- **Nada sale sin tu OK.** Publicar, enviar, pagar o borrar son acciones hacia afuera: las skills las preparan y te las muestran, pero esperan tu aprobación. Leer y preparar, libre.
- **Tus llaves no viajan.** `.env` y `.auth/` están en el `.gitignore`. Copia `.env.ejemplo` a `.env` y llénalo con lo tuyo.
- **La identidad se genera, no se incrusta.** Colores, logo, firma y dirección salen de `context/ghl.json`; si falta un dato, el script se detiene diciendo cuál en vez de inventar un default.
- **La dirección postal en los correos no es opcional** (CAN-SPAM): sin ella se quema la reputación de envío de tu dominio.
- **Los datos de tus clientes son datos personales.** Lo que salga del CRM o de un portal se trata como tal (en México, LFPDPPP).
- **Clona solo lo que es tuyo o de tu cliente**, y con autorización.

## Aviso

Varias recetas usan la **API interna** de GHL, la misma que usa su propia interfaz. No está documentada y puede cambiar sin avisar: si algo deja de funcionar de un día para otro, ese suele ser el motivo. Este proyecto no está afiliado a HighLevel.

---

Hecho por **NetUs** · [netus.mx](https://netus.mx)
