from django.test import TestCase
from django.utils import timezone
from core.models import User
from clients.models import ClientProfile, PlanServicio
from billing.models import Factura, Suscripcion
from accounting.models import MovimientoBanco
from accounting.services.reconciliation_engine import ReconciliationEngine
from billing.management.commands.generate_monthly_invoices import Command as GenerateInvoicesCommand
from django.core.management import call_command

class FintechBillingAndReconciliationTests(TestCase):
    def setUp(self):
        # 1. Crear usuario administrador
        self.admin = User.objects.create_superuser('admin_test', 'admin@test.com', 'pwd123')
        
        # 2. Crear planes de servicio
        self.plan_basic = PlanServicio.objects.create(
            nombre="Plan Básico",
            velocidad_mbps=20,
            precio=299.99, # Usar decimales para probar exactitud aritmética
            descripcion="Plan básico de prueba"
        )
        
        # 3. Crear usuarios de clientes
        self.user_cli1 = User.objects.create_user('cli_test1', 'cli1@test.com', 'pwd123', is_client=True)
        self.user_cli2 = User.objects.create_user('cli_test2', 'cli2@test.com', 'pwd123', is_client=True)
        
        # 4. Crear perfiles de clientes
        self.profile1 = ClientProfile.objects.create(
            user=self.user_cli1,
            razon_social="Empresa Alfa SA de CV",
            rfc="ALF190526ABC",
            direccion="Calle 1, CDMX",
            correo_facturacion="pagos@alfa.com",
            plan=self.plan_basic,
            estado='ACTIVE',
            monto_saldo=0.00
        )
        
        self.profile2 = ClientProfile.objects.create(
            user=self.user_cli2,
            razon_social="Comercializadora Beta",
            rfc="BET201015XYZ",
            direccion="Calle 2, Guadalajara",
            correo_facturacion="facturas@beta.com",
            plan=self.plan_basic,
            estado='ACTIVE',
            monto_saldo=0.00
        )
        
        # 5. Crear suscripciones
        self.sub1 = Suscripcion.objects.create(
            cliente=self.profile1,
            plan=self.plan_basic,
            activa=True
        )
        
        self.sub2 = Suscripcion.objects.create(
            cliente=self.profile2,
            plan=self.plan_basic,
            activa=True
        )

    def test_invoice_generation_arithmetic(self):
        """
        Prueba que el ciclo de facturación recurrente genere cobros exactos 
        sin errores de redondeo.
        """
        # Ejecutar ciclo de facturación
        call_command('generate_monthly_invoices')
        
        # Obtener las facturas generadas
        facturas = Factura.objects.all()
        self.assertEqual(facturas.count(), 2)
        
        for fact in facturas:
            # El monto debe coincidir exactamente con el precio del plan sin errores de float
            self.assertEqual(float(fact.monto), 299.99)
            self.assertEqual(fact.estado, 'PENDING')
            
            # El saldo del cliente debe haberse actualizado con el monto exacto
            cliente_perfil = fact.cliente
            self.assertEqual(float(cliente_perfil.monto_saldo), 299.99)

    def test_auto_reconciliation_exact_match(self):
        """
        Prueba que el motor de conciliación empareje automáticamente un abono SPEI correcto
        con base en el monto exacto y la referencia única de pago del cliente.
        """
        # 1. Generar la factura
        call_command('generate_monthly_invoices')
        factura_alfa = Factura.objects.get(cliente=self.profile1)
        
        # 2. Simular que entró una transferencia bancaria (SPEI) con la referencia de Alfa
        mov_banco = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO / BANCO ALFA / REF: {self.profile1.codigo_referencia}",
            monto=299.99,
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_TEST_1001"
        )
        
        # 3. Correr el motor de conciliación automática
        conciliados = ReconciliationEngine.auto_reconciliate()
        
        # 4. Validar resultados
        self.assertEqual(conciliados, 1)
        
        # Recargar objetos de la BD
        mov_banco.refresh_from_db()
        factura_alfa.refresh_from_db()
        self.profile1.refresh_from_db()
        
        self.assertEqual(mov_banco.estado, 'CONCILIATED')
        self.assertEqual(mov_banco.factura_asociada, factura_alfa)
        self.assertEqual(factura_alfa.estado, 'PAID')
        self.assertIsNotNone(factura_alfa.sat_uuid) # Se debió timbrar en el SAT
        self.assertEqual(float(self.profile1.monto_saldo), 0.00) # Saldo liquidado

    def test_auto_reconciliation_suspension_recovery(self):
        """
        Prueba que un cliente suspendido por falta de pago sea reactivado automáticamente
        el segundo en el que se concilia su abono bancario.
        """
        # Suspender cliente y ponerle saldo
        self.profile2.estado = 'SUSPENDED'
        self.profile2.monto_saldo = 299.99
        self.profile2.save()
        
        factura_beta = Factura.objects.create(
            cliente=self.profile2,
            monto=299.99,
            fecha_emision=timezone.now().date() - timezone.timedelta(days=15),
            estado='PENDING',
            periodo_facturacion='Mes Anterior'
        )
        
        # Registrar abono bancario
        MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto=f"SPEI RECIBIDO / {self.profile2.razon_social} REF: {self.profile2.codigo_referencia}",
            monto=299.99,
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_TEST_2002"
        )
        
        # Conciliar
        ReconciliationEngine.auto_reconciliate()
        
        # Validar reactivación automática de servicio
        self.profile2.refresh_from_db()
        self.assertEqual(self.profile2.estado, 'ACTIVE')
        self.assertEqual(float(self.profile2.monto_saldo), 0.00)

    def test_auto_reconciliation_ambiguous_no_match(self):
        """
        Prueba que el motor prevenga conciliaciones erróneas y no empareje abonos
        si el concepto no contiene referencias fiscales, códigos de pago ni nombres válidos.
        """
        call_command('generate_monthly_invoices')
        factura_alfa = Factura.objects.get(cliente=self.profile1)
        
        # Pago con monto exacto pero concepto de comisión (sin referencias del cliente)
        mov_ruido = MovimientoBanco.objects.create(
            fecha=timezone.now().date(),
            concepto="DEPOSITO EXTRAÑO VENTAS DIARIAS GENERALES SIN CONCEPTO",
            monto=299.99,
            tipo='INGRESO',
            estado='PENDING',
            codigo_transaccion="TXN_TEST_RUIDO"
        )
        
        conciliados = ReconciliationEngine.auto_reconciliate()
        
        # No se debió conciliar nada automáticamente
        self.assertEqual(conciliados, 0)
        
        mov_ruido.refresh_from_db()
        factura_alfa.refresh_from_db()
        
        self.assertEqual(mov_ruido.estado, 'PENDING')
        self.assertEqual(factura_alfa.estado, 'PENDING')
        self.assertIsNone(mov_ruido.factura_asociada)
