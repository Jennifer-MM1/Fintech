# Guía de Pruebas de Caja Negra (Pruebas Funcionales) - FintechOS

Esta guía describe los escenarios de prueba manuales y funcionales para asegurar que el sistema de facturación recurrente y conciliación para ISP opere de manera robusta y libre de fallos bajo cualquier condición.

---

## 1. Escenario de Prueba: Ciclo Feliz de Facturación Recurrente

Este escenario valida el correcto funcionamiento de la generación mensual de cobros y su asignación automática a perfiles de clientes activos.

### Pasos:
1. Iniciar sesión como Administrador del ISP en el Panel de Control (`admin` / `admin123`).
2. Ir a **Directorio Clientes** y registrar un nuevo cliente de prueba:
   * **Nombre:** "CableNet Servicios S.A."
   * **Plan:** "Paquete Estándar 50 Megas ($399.00/mes)"
   * **Estado:** "Activo"
3. Volver al **Dashboard** y hacer clic en **⚡ Simular Facturación Mensual (Lote)**.
4. Verificar:
   * Aparece un mensaje toast de éxito indicando la generación de facturas.
   * Se crea una nueva factura por el monto exacto de `$399.00` en la tabla de facturas emitidas recientemente.
   * El cliente "CableNet Servicios S.A." en el directorio ahora muestra un saldo pendiente de `$399.00`.
5. Volver a hacer clic en **⚡ Simular Facturación Mensual (Lote)**.
   * **Resultado Esperado:** Se reporta "0 facturas creadas | 3 omitidas", demostrando que el sistema previene cobros dobles en el mismo periodo.

---

## 2. Escenario de Prueba: Pago con Tarjeta en Portal (Stripe Sandbox)

Valida que los clientes puedan liquidar adeudos de manera autónoma y que el servicio de internet se reanude de inmediato en caso de estar suspendido.

### Pasos:
1. Asegurar que exista un cliente con estado **Suspendido** y saldo pendiente (ej. `cliente3` - "Consultorio Médico Juárez").
2. Cerrar sesión del Panel del ISP e iniciar sesión en el **Portal de Clientes** con las credenciales:
   * **Usuario:** `cliente3`
   * **Contraseña:** `cliente123`
3. Verificar en el Portal:
   * El estado del servicio se muestra en color rojo como **SUSPENDIDO**.
   * Se muestra un saldo pendiente de `$399.00`.
4. Hacer clic en **💳 Pagar con Tarjeta** en la factura pendiente.
5. Rellenar el formulario de pago:
   * **Tarjeta:** `4242 4242 4242 4242` (Tarjeta de pruebas oficial de Stripe).
   * **Vencimiento:** Cualquier fecha futura (ej. `12/29`).
   * **CVC:** `123`
   * **Nombre:** "Dr. Juárez"
6. Hacer clic en **Pagar $399.00 MXN**.
7. Verificar:
   * Se muestra la micro-animación de carga "Procesando pago con Stripe...".
   * Redirección exitosa a la pantalla de **Pago Confirmado**.
   * El recibo muestra el folio del SAT (UUID digital timbrado) y la referencia de transacción de Stripe.
8. Volver al inicio del portal y verificar:
   * El estado del servicio ahora es **CONECTADO** (verde).
   * El saldo pendiente es `$0.00`.
   * En el historial de pagos, la factura aparece como pagada y cuenta con los botones de descarga de XML y PDF.

---

## 3. Escenario de Prueba: Conciliación SPEI Automática (Belvo/Fintoc Sandbox)

Valida que el motor reconozca depósitos SPEI entrantes en banco y los asocie automáticamente liquidando saldos de clientes.

### Pasos:
1. Iniciar sesión como Administrador del ISP.
2. Ir a **Directorio Clientes** y tomar nota del **Código de Referencia SPEI** de "Abarrotes Don Pedro" (ej. `REF-1754`).
3. Ejecutar la simulación de facturación mensual para asegurar que Don Pedro tenga una factura `PENDIENTE` de `$299.00` y saldo de `$299.00`.
4. Ir a **Conciliación** en el menú de navegación lateral.
5. Hacer clic en **Sincronizar Banco (Sandbox API)**.
   * **Resultado Esperado:** Se simula la llamada a Belvo/Fintoc Sandbox e importa transacciones Spei pendientes de conciliar al panel izquierdo. Una de ellas coincidirá exactamente en monto (`$299.00`) y concepto con la referencia de Don Pedro (ej. `REF-1754`).
6. Hacer clic en **Auto-Conciliación Inteligente**.
7. Verificar:
   * Aparece mensaje indicando que se concilió el pago automáticamente.
   * El movimiento de abono de `$299.00` desaparece de la lista de pendientes y se mueve a la tabla inferior de "Registro de Pagos Conciliados", mostrando el cliente asociado y su UUID del SAT generado en tiempo real.
   * En **Directorio Clientes**, el saldo de "Abarrotes Don Pedro" ahora es `$0.00`.

---

## 4. Escenario de Prueba: Conciliación Manual (Conceptos Ambiguos o Ruido)

Asegura que el contador del ISP pueda conciliar depósitos que entraron con nombres incorrectos o sin la referencia SPEI única.

### Pasos:
1. Ir al módulo de **Conciliación**.
2. Identificar un movimiento de abono sin referencia en la columna izquierda (ej. `"SPEI RECIBIDO - ALBERTO GOMEZ PEREZ" por $450.00`).
3. Identificar una factura pendiente en la columna derecha de un cliente (ej. una factura pendiente por `$450.00`).
4. Hacer clic en el movimiento de Alberto Gómez.
   * **Resultado Esperado:** La tarjeta se resalta en azul y muestra una marca de verificación.
5. Hacer clic en la factura de la columna derecha.
   * **Resultado Esperado:** La tarjeta se resalta en azul y se despliega en la parte inferior de la pantalla la barra de **Conciliación Manual Activa**.
6. Hacer clic en **Vincular y Timbrar Factura (SAT)**.
7. Verificar:
   * El abono se asocia a la factura y se marca como **CONCILIADO** en libros.
   * La factura pasa a estado **PAGADA** y se timbra ante el SAT de forma exitosa.
