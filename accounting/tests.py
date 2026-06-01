from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
from decimal import Decimal
from core.models import User
from clients.models import ClientProfile, PlanServicio
from billing.models import Factura
from accounting.models import MovimientoBanco
from accounting.services.reconciliation_engine import ReconciliationEngine

class FintechAccountingWhiteBoxTests(TestCase):
    """
    PRUEBAS DE CAJA BLANCA (WHITE BOX TESTS)
    
    Estas pruebas validan rigurosamente el diseño estructural, flujos de control lógicos,
    bifurcaciones de código (branch coverage), mitigación de excepciones y precisión aritmética
    dentro del motor de conciliación bancaria (`ReconciliationEngine`).
    """
    
    def setUp(self):
        # Crear plan base
        self.plan = PlanServicio.objects.create(
            nombre="Plan Regular 50 Mbps",
            velocidad_mbps=50,
            precio=Decimal('299.99'),
            descripcion="Plan para pruebas de caja blanca"
        )
        
        # Crear usuarios y perfiles
        self.user_cli = User.objects.create_user(
            username='cli_whitebox',
            email='wb@test.com',
            password='password123',
            is_client=True
        )
        
        self.profile = ClientProfile.objects.create(
            user=self.user_cli,
            razon_social="Soluciones Integrales S.A. de C.V.",
            rfc="INT990101XYZ",
            direccion="Calle Central 123",
            correo_facturacion="contacto@integrales.com",
            plan=self.plan,
            estado='ACTIVE',
            monto_saldo=Decimal('299.99')
        )

    def test_whitebox_reconciliation_branch_coverage(self):
        """
        PRUEBA DE CAJA BLANCA: Cobertura de bifurcaciones del motor de conciliación
        
        Valida que cada una de las condiciones lógicas del bucle interno se ejecute:
        - Bifurcación 1: Omisión por montos desiguales (`mov.monto != factura.monto`).
        - Bifurcación 2: Coincidencia por Código de Referencia SPEI (`codigo_referencia in concepto`).
        - Bifurcación 3: Coincidencia por RFC (`rfc in concepto`).
        - Bifurcación 4: Coincidencia por Razón Social (`razon_social in concepto`).
        """
        # Crear la factura a conciliar
        factura = Factura.objects.create(
            cliente=self.profile,
            monto=Decimal('299.99'),
            estado='PENDING',
            periodo_facturacion='Junio 2026'
        )
        
        # 1. TEST BIFURCACIÓN 1: El monto es desigual (300.00 vs 299.99)
        mov_monto_desigual = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO - REF: {self.profile.codigo_referencia}",
            monto=Decimal('300.00'), # Monto no coincide
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_BRANCH_1"
        )
        
        match_count = ReconciliationEngine.auto_reconciliate()
        self.assertEqual(match_count, 0) # No se concilia nada
        
        factura.refresh_from_db()
        mov_monto_desigual.refresh_from_db()
        self.assertEqual(factura.estado, 'PENDING')
        self.assertEqual(mov_monto_desigual.estado, 'PENDING')
        
        # Eliminar movimiento para aislar las siguientes ramas
        mov_monto_desigual.delete()

        # 2. TEST BIFURCACIÓN 2: Coincidencia por Referencia SPEI (REF-XXXX)
        mov_referencia = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI ENTRANTE COMPLEMENTO {self.profile.codigo_referencia.lower()} EXITOSO",
            monto=Decimal('299.99'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_BRANCH_2"
        )
        
        match_count = ReconciliationEngine.auto_reconciliate()
        self.assertEqual(match_count, 1) # Se concilió por referencia
        
        factura.refresh_from_db()
        mov_referencia.refresh_from_db()
        self.assertEqual(factura.estado, 'PAID')
        self.assertEqual(mov_referencia.estado, 'CONCILIATED')
        
        # Restaurar estados para probar la siguiente rama
        factura.estado = 'PENDING'
        factura.sat_uuid = None
        factura.save()
        self.profile.monto_saldo = Decimal('299.99')
        self.profile.save()
        mov_referencia.delete()

        # 3. TEST BIFURCACIÓN 3: Coincidencia por RFC
        mov_rfc = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto="SPEI ABONO BANCARIO CON RFC: INT990101XYZ SIN REFERENCIA",
            monto=Decimal('299.99'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_BRANCH_3"
        )
        
        match_count = ReconciliationEngine.auto_reconciliate()
        self.assertEqual(match_count, 1) # Se concilió por RFC
        
        factura.refresh_from_db()
        mov_rfc.refresh_from_db()
        self.assertEqual(factura.estado, 'PAID')
        self.assertEqual(mov_rfc.estado, 'CONCILIATED')
        
        # Restaurar estados
        factura.estado = 'PENDING'
        factura.sat_uuid = None
        factura.save()
        self.profile.monto_saldo = Decimal('299.99')
        self.profile.save()
        mov_rfc.delete()

        # 4. TEST BIFURCACIÓN 4: Coincidencia por Razón Social / Nombre
        mov_nombre = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto="PAGO MENSUAL DE SOLUCIONES INTEGRALES S.A. DE C.V. POR VENTAS",
            monto=Decimal('299.99'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_BRANCH_4"
        )
        
        match_count = ReconciliationEngine.auto_reconciliate()
        self.assertEqual(match_count, 1) # Se concilió por Razón Social
        
        factura.refresh_from_db()
        mov_nombre.refresh_from_db()
        self.assertEqual(factura.estado, 'PAID')
        self.assertEqual(mov_nombre.estado, 'CONCILIATED')

    def test_whitebox_reconciliation_atomic_exception_handling(self):
        """
        PRUEBA DE CAJA BLANCA: Manejo atómico de excepciones y resiliencia del bucle
        
        Valida que si ocurre un fallo crítico al guardar o conciliar un movimiento
        específico (ej. error inesperado en base de datos), la transacción se revierta
        para ese registro (gracias a `transaction.atomic()`), se capture el error sin interrumpir
        el motor, y se proceda a conciliar el siguiente movimiento exitosamente.
        """
        # Crear cliente con error simulado ("Empresa Crítica")
        user_critico = User.objects.create_user(
            username='cli_critico', email='critico@test.com', password='pwd', is_client=True
        )
        profile_critico = ClientProfile.objects.create(
            user=user_critico,
            razon_social="Empresa Crítica S.A.",
            rfc="CRI990101AAA",
            plan=self.plan,
            estado='ACTIVE',
            monto_saldo=Decimal('150.00')
        )
        
        factura_critica = Factura.objects.create(
            cliente=profile_critico,
            monto=Decimal('150.00'),
            estado='PENDING',
            periodo_facturacion='Junio 2026'
        )
        
        mov_critico = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO - REF: {profile_critico.codigo_referencia}",
            monto=Decimal('150.00'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_CRITICAL"
        )
        
        # Crear cliente exitoso ("Empresa Exitosa")
        user_exitoso = User.objects.create_user(
            username='cli_exitoso', email='exitoso@test.com', password='pwd', is_client=True
        )
        profile_exitoso = ClientProfile.objects.create(
            user=user_exitoso,
            razon_social="Empresa Exitosa S.A.",
            rfc="EXI990101BBB",
            plan=self.plan,
            estado='ACTIVE',
            monto_saldo=Decimal('150.00')
        )
        
        factura_exitosa = Factura.objects.create(
            cliente=profile_exitoso,
            monto=Decimal('150.00'),
            estado='PENDING',
            periodo_facturacion='Junio 2026'
        )
        
        mov_exitoso = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO - REF: {profile_exitoso.codigo_referencia}",
            monto=Decimal('150.00'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_SUCCESS"
        )
        
        # Simular fallo en save() de Factura utilizando Monkey Patching controlado
        original_save = Factura.save
        
        def mock_save(self_instance, *args, **kwargs):
            if self_instance.cliente.razon_social == "Empresa Crítica S.A.":
                raise ValueError("ERROR SIMULADO DE CONEXIÓN O INTEGRIDAD EN SAT!")
            return original_save(self_instance, *args, **kwargs)
        
        with patch.object(Factura, 'save', mock_save):
            # Ejecutar conciliador
            match_count = ReconciliationEngine.auto_reconciliate()
            
            # Solo debió completar 1 conciliación exitosa ("Empresa Exitosa")
            self.assertEqual(match_count, 1)
            
            # Recargar objetos de base de datos
            factura_critica.refresh_from_db()
            mov_critico.refresh_from_db()
            profile_critico.refresh_from_db()
            
            factura_exitosa.refresh_from_db()
            mov_exitoso.refresh_from_db()
            profile_exitoso.refresh_from_db()
            
            # La transacción de la Empresa Crítica debió quedar PENDIENTE (Rollback)
            self.assertEqual(factura_critica.estado, 'PENDING')
            self.assertEqual(mov_critico.estado, 'PENDING')
            self.assertIsNone(mov_critico.factura_asociada)
            self.assertEqual(profile_critico.monto_saldo, Decimal('150.00'))
            
            # La transacción de la Empresa Exitosa debió quedar CONCILIADA y timbrada (Success)
            self.assertEqual(factura_exitosa.estado, 'PAID')
            self.assertEqual(mov_exitoso.estado, 'CONCILIATED')
            self.assertEqual(mov_exitoso.factura_asociada, factura_exitosa)
            self.assertIsNotNone(factura_exitosa.sat_uuid)
            self.assertEqual(profile_exitoso.monto_saldo, Decimal('0.00'))

    def test_whitebox_reconciliation_decimal_arithmetic_limits(self):
        """
        PRUEBA DE CAJA BLANCA: Precisión en límites aritméticos Decimal
        
        Valida que el decremento de los saldos se ejecute con aritmética exacta Decimal.
        Comprueba la condición límite que asegura que el saldo del cliente nunca sea
        menor a 0.00 (`max(Decimal('0.00'), cliente.monto_saldo - factura.monto)`).
        """
        # Cliente con un saldo menor que el monto a pagar (ej. por saldo abonado o ajuste manual anterior)
        self.profile.monto_saldo = Decimal('100.50')
        self.profile.save()
        
        factura_alta = Factura.objects.create(
            cliente=self.profile,
            monto=Decimal('200.00'), # Monto mayor que saldo registrado
            estado='PENDING',
            periodo_facturacion='Julio 2026'
        )
        
        mov_abono = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO - REF: {self.profile.codigo_referencia}",
            monto=Decimal('200.00'),
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_ARITHMETIC_LIMIT"
        )
        
        # Ejecutar conciliador
        match_count = ReconciliationEngine.auto_reconciliate()
        self.assertEqual(match_count, 1)
        
        self.profile.refresh_from_db()
        
        # Validar que el saldo del cliente se limite exactamente a 0.00 y no sea negativo (-99.50)
        self.assertEqual(self.profile.monto_saldo, Decimal('0.00'))

    def test_whitebox_manual_reconciliation_error_branches(self):
        """
        PRUEBA DE CAJA BLANCA: Manejo de errores lógicos en conciliación manual
        
        Invoca la conciliación manual con IDs inexistentes para forzar y validar la
        cobertura del bloque `except Exception` en `manual_reconciliate()`, asegurando
        que retorne `False` y no detenga la aplicación con excepciones no controladas.
        """
        result = ReconciliationEngine.manual_reconciliate(movimiento_id=99999, factura_id=88888)
        self.assertFalse(result)
