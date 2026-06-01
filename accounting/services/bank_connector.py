from django.utils import timezone
from billing.models import Factura
from accounting.models import MovimientoBanco
from clients.models import ClientProfile
import random
import uuid

class BankConnectorService:
    @staticmethod
    def sync_bank_movements():
        """
        Simula la importación de movimientos bancarios a través de Belvo/Fintoc en modo Sandbox.
        Genera movimientos SPEI inteligentes para probar a fondo el algoritmo de conciliación.
        """
        ahora = timezone.now().date()
        nuevos_movimientos = []
        
        # 1. Obtener facturas pendientes para simular transferencias exitosas correspondientes
        facturas_pendientes = Factura.objects.filter(estado='PENDING').select_related('cliente')
        
        # Simular transferencias correctas para algunas facturas pendientes
        # Tomaremos máximo 2 facturas pendientes para simular que entraron al banco de forma exitosa
        for i, factura in enumerate(facturas_pendientes[:2]):
            cliente = factura.cliente
            # Generar concepto SPEI estructurado con la referencia del cliente
            conceptos_exito = [
                f"SPEI RECIBIDO / {cliente.codigo_referencia} / {cliente.razon_social[:20]}",
                f"TRANSFERENCIA SPEI DE {cliente.razon_social.upper()} CONCEPTO {cliente.codigo_referencia}",
                f"DEP. SPEI NET - REFERENCIA {cliente.codigo_referencia}"
            ]
            concepto = random.choice(conceptos_exito)
            txn_id = f"txn_belvo_{uuid.uuid4().hex[:12]}"
            
            # Verificar si ya existe este movimiento para evitar duplicados
            if not MovimientoBanco.objects.filter(concepto=concepto, monto=factura.monto).exists():
                mov = MovimientoBanco.objects.create(
                    fecha=ahora,
                    concepto=concepto,
                    monto=factura.monto,
                    tipo='INGRESO',
                    estado='PENDING',
                    codigo_transaccion=txn_id
                )
                nuevos_movimientos.append(mov)

        # 2. Simular un caso de depósito con "Concepto Ambiguo / Error":
        # Un depósito con el monto correcto pero concepto sin referencia única (ej. solo el nombre del cliente parcial)
        # Esto sirve para probar la conciliación manual
        if facturas_pendientes.count() > 2:
            factura_ambigua = facturas_pendientes[2]
            cliente = factura_ambigua.cliente
            concepto = f"PAGO MENSUALIDAD INTERNET - {cliente.razon_social[:20]}" # Falta el REF-xxxx
            txn_id = f"txn_belvo_{uuid.uuid4().hex[:12]}"
            
            if not MovimientoBanco.objects.filter(concepto=concepto, monto=factura_ambigua.monto).exists():
                mov = MovimientoBanco.objects.create(
                    fecha=ahora,
                    concepto=concepto,
                    monto=factura_ambigua.monto,
                    tipo='INGRESO',
                    estado='PENDING',
                    codigo_transaccion=txn_id
                )
                nuevos_movimientos.append(mov)

        # 3. Simular transacciones de ruido (no conciliables automáticamente)
        ruido_data = [
            {
                'concepto': 'COMISION POR TRANSFERENCIA SPEI RECIBIDA',
                'monto': 5.80,
                'tipo': 'EGRESO',
                'codigo': f"txn_belvo_fee_{uuid.uuid4().hex[:8]}"
            },
            {
                'concepto': 'INTERESES GANADOS E INVERSION',
                'monto': 124.50,
                'tipo': 'INGRESO',
                'codigo': f"txn_belvo_interest_{uuid.uuid4().hex[:8]}"
            },
            {
                'concepto': 'PAGO SERVICIO DE LUZ CFE EN LINEA',
                'monto': 1200.00,
                'tipo': 'EGRESO',
                'codigo': f"txn_belvo_cfe_{uuid.uuid4().hex[:8]}"
            },
            {
                'concepto': 'SPEI RECIBIDO - ALBERTO GOMEZ PEREZ (CONCEPTO: PRESTAMO)',
                'monto': 450.00,
                'tipo': 'INGRESO',
                'codigo': f"txn_belvo_noise_{uuid.uuid4().hex[:8]}"
            }
        ]

        for item in ruido_data:
            if not MovimientoBanco.objects.filter(concepto=item['concepto'], monto=item['monto']).exists():
                mov = MovimientoBanco.objects.create(
                    fecha=ahora,
                    concepto=item['concepto'],
                    monto=item['monto'],
                    tipo=item['tipo'],
                    estado='PENDING',
                    codigo_transaccion=item['codigo']
                )
                nuevos_movimientos.append(mov)

        return len(nuevos_movimientos)
