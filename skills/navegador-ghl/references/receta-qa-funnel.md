# Receta — QA de funnel / landing

Verificar en automático que una landing/funnel cargue bien, que el formulario funcione y reportar errores (consola, red, enlaces rotos). Se corre sobre cualquier landing propia: página de registro, de agenda, de cotización o de pago.

## Pasos
1. **Abrir y empezar a capturar errores:**
   ```bash
   npx playwright-cli open "<URL de tu landing>"
   npx playwright-cli console        # mensajes de consola (errores JS)
   npx playwright-cli requests       # peticiones de red (4xx/5xx, recursos fallidos)
   ```
2. **Verificar estructura:** `snapshot` → confirmar que existan el titular, el video/VSL, el formulario/CTA y el botón de pago/agenda.
3. **Probar el formulario (sin enviar de verdad salvo aprobación):** rellena con datos de prueba y valida que el botón se habilite / muestre validación:
   ```bash
   npx playwright-cli fill <ref-nombre> "Prueba QA"
   npx playwright-cli fill <ref-email> "qa+prueba@ejemplo.com"
   npx playwright-cli snapshot
   ```
   ⚠️ **No envíes** el formulario real ni completes un pago sin aprobación explícita: cada envío mete un lead basura al CRM y dispara las automatizaciones.
4. **Enlaces y CTA:** comprobar que el CTA apunte al destino correcto:
   ```bash
   npx playwright-cli --raw eval "el => el.href" <ref-cta>
   ```
5. **Reporte:** resume en una tabla qué pasó (carga, errores de consola, requests fallidos, formulario, CTA correcto) y, si hay fallas, propón el arreglo o avisa a quien administre la landing.
6. **Cerrar:** `npx playwright-cli close`.

## Variante: chequeo periódico
Se puede correr como tarea recurrente (cron / scheduled agent) que abra el funnel, valide y avise solo si algo falla — sin intervención humana en lo no crítico (Fase 3 de autonomía).
