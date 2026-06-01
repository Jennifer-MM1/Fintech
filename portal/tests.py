from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages
from decimal import Decimal
from core.models import User
from clients.models import ClientProfile, PlanServicio
from billing.models import Factura

class FintechPortalBlackBoxTests(TestCase):
    """
    PRUEBAS DE CAJA NEGRA (BLACK BOX TESTS)
    
    Estas pruebas validan rigurosamente el comportamiento funcional del sistema
    a través de sus puntos de entrada públicos (endpoints HTTP de Django y métodos de vista),
    comprobando redirecciones, estados HTTP, mensajes toast de respuesta y efectos
    secundarios en base de datos sin depender de estructuras lógicas internas.
    """
    
    def setUp(self):
        # 1. Crear planes de servicio
        self.plan_premium = PlanServicio.objects.create(
            nombre="Plan Premium 100 Megas",
            velocidad_mbps=100,
            precio=499.99,
            descripcion="Plan premium para pruebas"
        )
        
        # 2. Crear usuarios de prueba
        self.user_client1 = User.objects.create_user(
            username='cliente_blackbox1',
            email='bb1@test.com',
            password='password123',
            is_client=True
        )
        
        self.user_client2 = User.objects.create_user(
            username='cliente_blackbox2',
            email='bb2@test.com',
            password='password123',
            is_client=True
        )
        
        # Operador de facturación / Administrador
        self.user_admin = User.objects.create_superuser(
            username='admin_blackbox',
            email='adminbb@test.com',
            password='password123'
        )
        
        # 3. Crear perfiles de clientes
        self.profile1 = ClientProfile.objects.create(
            user=self.user_client1,
            razon_social="Tecnologías Delta S.A.",
            rfc="DELT920101AA1",
            direccion="Av. Reforma 100, CDMX",
            correo_facturacion="facturas@delta.com",
            plan=self.plan_premium,
            estado='SUSPENDED', # Iniciamos suspendido para probar reactivación automática
            monto_saldo=Decimal('500.00')
        )
        
        self.profile2 = ClientProfile.objects.create(
            user=self.user_client2,
            razon_social="Soluciones Gamma",
            rfc="GAMM950505BB2",
            direccion="Av. Juárez 500, Guadalajara",
            correo_facturacion="cobros@gamma.com",
            plan=self.plan_premium,
            estado='ACTIVE',
            monto_saldo=Decimal('0.00')
        )

    def test_blackbox_checkout_and_payment_flow(self):
        """
        PRUEBA DE CAJA NEGRA: Flujo de Caja y Pago del Cliente (Stripe Sandbox)
        
        Simula las peticiones del cliente en la interfaz web para liquidar una factura
        pendiente y valida las redirecciones, respuestas, saldos finales y la
        reactivación automática del servicio suspendido.
        """
        # Crear factura pendiente asociada a profile1
        factura = Factura.objects.create(
            cliente=self.profile1,
            monto=Decimal('350.00'),
            estado='PENDING',
            periodo_facturacion='Mayo 2026'
        )
        
        # 1. Intentar acceder sin iniciar sesión (debe redirigir al Login)
        url_checkout = reverse('portal:checkout', kwargs={'invoice_id': factura.id})
        response = self.client.get(url_checkout)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('portal:index'), response.url)
        
        # 2. Iniciar sesión como el cliente dueño de la factura
        login_success = self.client.login(username='cliente_blackbox1', password='password123')
        self.assertTrue(login_success)
        
        # 3. Acceder a la página de Checkout (Caja Negra: Validar renderizado de montos y desglose de IVA)
        response = self.client.get(url_checkout)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DELT920101AA1")
        self.assertContains(response, "$350.00")
        
        # El subtotal aproximado sin IVA (16%) debe mostrarse en la pantalla de pago
        subtotal_esperado = 350.00 / 1.16
        self.assertContains(response, f"{subtotal_esperado:.2f}")
        
        # 4. Enviar el pago simulado (POST al endpoint de procesamiento)
        url_pay = reverse('portal:process_payment', kwargs={'invoice_id': factura.id})
        response = self.client.post(url_pay)
        
        # Comprobar redirección al éxito
        url_exito_esperado = reverse('portal:payment_success', kwargs={'invoice_id': factura.id})
        self.assertRedirects(response, url_exito_esperado)
        
        # Seguir redirección y verificar página de éxito
        response_exito = self.client.get(url_exito_esperado)
        self.assertEqual(response_exito.status_code, 200)
        self.assertContains(response_exito, "Pago Confirmado")
        
        # 5. Comprobar que en la sesión se inyectó el mensaje de éxito correcto
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("procesado con éxito", str(messages[0]))
        
        # 6. EFECTOS SECUNDARIOS EN BD (Caja Negra: Asegurar consistencia del estado del sistema)
        factura.refresh_from_db()
        self.profile1.refresh_from_db()
        
        # Estatus de factura cambiado a pagado
        self.assertEqual(factura.estado, 'PAID')
        # Referencia Stripe simulada generada
        self.assertTrue(factura.stripe_payment_intent.startswith('ch_stripe_sandbox_'))
        # SAT Timbrado UUID generado
        self.assertIsNotNone(factura.sat_uuid)
        
        # El saldo disminuyó exactamente $350.00 (de 500.00 a 150.00)
        self.assertEqual(self.profile1.monto_saldo, Decimal('150.00'))
        
        # El servicio se reactivó automáticamente de SUSPENDED a ACTIVE
        self.assertEqual(self.profile1.estado, 'ACTIVE')

    def test_blackbox_client_profile_update_rfc_conflict(self):
        """
        PRUEBA DE CAJA NEGRA: Validación funcional de colisión de RFC
        
        Prueba que si un cliente intenta cambiar su información fiscal a un RFC
        que pertenece a otro cliente registrado, la interfaz rechace la operación,
        devuelva el mensaje Toast de error apropiado y no modifique los datos en la base de datos.
        """
        self.client.login(username='cliente_blackbox1', password='password123')
        
        url_perfil = reverse('portal:profile')
        
        # Petición POST para actualizar perfil con un RFC que ya tiene cliente2
        post_data = {
            'razon_social': 'Nuevos Datos Delta',
            'rfc': 'GAMM950505BB2', # RFC perteneciente a profile2
            'correo_facturacion': 'nuevo@delta.com',
            'direccion': 'Nueva Dirección, CDMX'
        }
        
        response = self.client.post(url_perfil, post_data)
        
        # Debe recargar la misma página (o redirigir de vuelta al perfil)
        self.assertEqual(response.status_code, 200) # El view retorna render en caso de error
        
        # Comprobar mensaje de error en la sesión
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("ya está registrado por otro cliente", str(messages[0]))
        
        # Comprobar que los datos en la base de datos NO cambiaron para profile1
        self.profile1.refresh_from_db()
        self.assertEqual(self.profile1.rfc, 'DELT920101AA1')
        self.assertEqual(self.profile1.razon_social, 'Tecnologías Delta S.A.')

    def test_blackbox_billing_operator_invoice_creation(self):
        """
        PRUEBA DE CAJA NEGRA: Creación de Factura por el Operador y validación de montos
        
        Valida que un operador de facturación logueado pueda registrar nuevas facturas
        de cobro a través del Panel y que se apliquen validaciones de integridad,
        tales como rechazar montos menores o iguales a cero.
        """
        # 1. Iniciar sesión como administrador (operador)
        self.client.login(username='admin_blackbox', password='password123')
        
        url_invoices = reverse('billing:invoices')
        
        # 2. Intentar crear una factura con MONTO NEGATIVO (Validación externa)
        bad_post_data = {
            'action': 'new_invoice',
            'cliente': self.profile1.id,
            'monto': '-120.50',
            'periodo': 'Junio 2026'
        }
        response = self.client.post(url_invoices, bad_post_data)
        self.assertRedirects(response, url_invoices)
        
        # Validar mensaje de error
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("monto de la factura debe ser mayor que cero", str(messages[0]))
        
        # Asegurar que no se creó ninguna factura en la BD
        self.assertEqual(Factura.objects.filter(cliente=self.profile1, periodo_facturacion='Junio 2026').count(), 0)
        
        # 3. Crear una factura VÁLIDA
        good_post_data = {
            'action': 'new_invoice',
            'cliente': self.profile1.id,
            'monto': '150.00',
            'periodo': 'Junio 2026'
        }
        response_success = self.client.post(url_invoices, good_post_data)
        self.assertRedirects(response_success, url_invoices)
        
        # Validar mensaje de éxito en la sesión
        messages_success = list(get_messages(response_success.wsgi_request))
        self.assertEqual(len(messages_success), 1)
        self.assertIn("creada exitosamente", str(messages_success[0]))
        
        # Comprobar efectos en base de datos: Factura creada y saldo del cliente incrementado
        factura_creada = Factura.objects.get(cliente=self.profile1, periodo_facturacion='Junio 2026')
        self.assertEqual(factura_creada.monto, Decimal('150.00'))
        self.assertEqual(factura_creada.estado, 'PENDING')
        
        self.profile1.refresh_from_db()
        # Saldo anterior (500.00) + Nueva factura (150.00) = 650.00
        self.assertEqual(self.profile1.monto_saldo, Decimal('650.00'))
