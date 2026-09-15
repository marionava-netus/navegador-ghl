# navegador-ghl

Skill de **Claude Code** para operar **GHL / HighLevel** (y cualquier app web con login) desde el navegador, con la **Playwright CLI oficial**.

Sirve para lo que la API de GHL no cubre: clonar sitios, funnels, blogs, workflows y tableros **entre cuentas distintas**, publicar landings, hacer QA de páginas y sacar datos de portales que no tienen API.

## Qué trae

| Archivo | Qué es |
|---|---|
| `skills/navegador-ghl/SKILL.md` | La skill: flujo de trabajo, sesiones con login persistido, las dos APIs de GHL, reglas de seguridad y trucos de eficiencia |
| `references/playwright-cli-comandos.md` | Referencia completa de comandos de la CLI |
| `references/receta-login-credenciales.md` | Entrar a un portal con credenciales del `.env` sin exponer la contraseña |
| `references/receta-qa-funnel.md` | QA automático de una landing/funnel (consola, red, formulario) |
| `references/receta-landing-custom-code.md` | Publicar una landing HTML completa dentro de un funnel |
| `references/receta-modal-pdf-footer.md` | PDFs del footer en un modal branded con visor y descarga |
| `references/receta-clonar-sitio-entre-cuentas.md` | Clonar sitios, funnels, blogs y workflows entre cuentas de GHL |
| `references/receta-clonar-tablero-entre-cuentas.md` | Clonar un dashboard de reportes completo (40 widgets, layout y permisos) |
| `scripts/login.sh` | Login asistido: abre el navegador visible una vez y guarda la sesión |

Todas las recetas están **validadas en producción** (jun–ago 2026) y documentan las trampas que costaron horas, no solo el camino feliz.

## Instalación

```bash
git clone https://github.com/marionava-netus/navegador-ghl.git
cp -R navegador-ghl/skills/* <tu-proyecto>/.claude/skills/

cd <tu-proyecto>
npm install --save-dev @playwright/cli
npx playwright-cli install-browser chromium
```

Después, el login de una sola vez:

```bash
bash .claude/skills/navegador-ghl/scripts/login.sh "https://<tu-panel-de-ghl>" ghl
```

Inicia sesión en la ventana que se abre y ciérrala. La sesión queda guardada en `.auth/pw-ghl/` y todas las tareas siguientes la reutilizan.

## Requisitos

- **Node.js** (para la Playwright CLI). Algunas recetas usan **Python 3** para manipular los blobs JSON.
- Acceso **admin** a la(s) cuenta(s) de GHL que vas a operar. Para clonar entre cuentas, a las dos.

## Seguridad

- **Nada sale sin tu OK.** Publicar, enviar, pagar o borrar son acciones hacia afuera: la skill las prepara y te las muestra, pero espera tu aprobación. Leer y preparar, libre.
- **Tus llaves no viajan.** `.env` y `.auth/` están en el `.gitignore`. Copia `.env.ejemplo` a `.env` y llénalo con lo tuyo; ese archivo nunca se commitea.
- **Los datos de tus clientes son datos personales.** Lo que salga del CRM o de un portal se trata como tal (en México, LFPDPPP).
- **Clona solo lo que es tuyo o de tu cliente**, y con autorización.

## Aviso

Las recetas de clonado usan la **API interna** de GHL (`backend.leadconnectorhq.com`), la misma que usa su propia interfaz. No está documentada y puede cambiar sin avisar: si algo deja de funcionar de un día para otro, ese suele ser el motivo. Este proyecto no está afiliado a HighLevel.

---

Hecho por **NetUs** · [netus.mx](https://netus.mx)
