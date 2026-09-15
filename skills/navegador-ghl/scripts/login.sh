#!/usr/bin/env bash
# Login asistido para el navegador del asistente.
# Abre el navegador HEADED con el perfil persistente para que inicies sesión
# (GHL, portales de proveedores, correo). La sesión queda guardada en
# .auth/pw-ghl/ (gitignored — nunca se commitea).
# Uso:  bash .claude/skills/navegador-ghl/scripts/login.sh [url] [sesion]
#   url    : página donde iniciar sesión (default: about:blank)
#   sesion : nombre de sesión de la CLI (default: ghl)
set -euo pipefail

# Ir a la raíz del proyecto (este script vive en .claude/skills/navegador-ghl/scripts/)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

URL="${1:-about:blank}"
SESSION="${2:-ghl}"
PROFILE=".auth/pw-ghl"
mkdir -p "$PROFILE"

echo "→ Abriendo navegador HEADED (sesión '$SESSION', perfil '$PROFILE')."
echo "  Inicia sesión en los sitios que necesites; la sesión se guardará en el perfil."
npx playwright-cli -s="$SESSION" open "$URL" --headed --persistent --profile="$PROFILE"

echo ""
echo "✓ Navegador abierto. Cuando termines de iniciar sesión, cierra con:"
echo "    npx playwright-cli -s=$SESSION close"
echo "  Después, las tareas que usen  -s=$SESSION ... --persistent --profile=$PROFILE  reutilizarán tu sesión."
