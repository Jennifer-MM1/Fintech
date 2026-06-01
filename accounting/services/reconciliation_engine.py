from django.db import transaction
from django.utils import timezone
from accounting.models import MovimientoBanco
from billing.models import Factura
from clients.models import ClientProfile
import uuid
from decimal import Decimal

class ReconciliationEngine:
    @staticmethod
    def auto_reconciliate():
        """
        Algoritmo inteligente de conciliación automática.
        Busca transferencias bancarias de ingreso pendientes y las empareja con facturas pendientes.
        Criterios:
        - Coincidencia exacta de monto.
        - Coincidencia del concepto de transferencia con: el código de referencia SPEI del cliente,
          su RFC, o una coincidencia exacta de su Razón Social/Nombre.
        """
        movimientos_pendientes = MovimientoBanco.objects.filter(
            tipo='INGRESO',
            estado='PENDING'
        )
        
        facturas_pendientes = Factura.objects.filter(
            estado='PENDING'
        ).select_related('cliente')
        
        match_count = 0
        
        # Procesamos cada movimiento de forma individual en transacciones atómicas
        for mov in movimientos_pendientes:
            match_found = False
            
            for factura in facturas_pendientes:
                # 1. Coincidencia exacta de monto
                if mov.monto != factura.monto:
                    continue
                
                # 2. Criterios de concepto
                cliente = factura.cliente
                concepto_upper = mov.concepto.upper()
                
                ref_match = cliente.codigo_referencia.upper() in concepto_upper
                rfc_match = cliente.rfc.upper() in concepto_upper
                nombre_match = cliente.razon_social.upper() in concepto_upper
                
                if ref_match or rfc_match or nombre_match:
                    # ¡Match encontrado!
                    try:
                        with transaction.atomic():
                            # Relacionar y cambiar estados
                            mov.factura_asociada = factura
                            mov.estado = 'CONCILIATED'
                            mov.save()
                            
                            factura.estado = 'PAID'
                            
                            # Simular timbrado del SAT (Generación de UUID de Facturapi)
                            if not factura.sat_uuid:
                                factura.sat_uuid = str(uuid.uuid4()).upper()
                            factura.save()
                            
                            # Actualizar saldo del cliente
                            cliente.monto_saldo = max(Decimal('0.00'), cliente.monto_saldo - factura.monto)
                            
                            # Si el cliente estaba suspendido por falta de pago, reactivarlo
                            if cliente.estado == 'SUSPENDED':
                                cliente.estado = 'ACTIVE'
                                
                            cliente.save()
                            
                            match_count += 1
                            match_found = True
                            
                        # Salir del bucle interno si ya conciliamos este movimiento
                        if match_found:
                            break
                    except Exception as e:
                        # En caso de error en base de datos, continuar con el siguiente
                        print(f"Error al conciliar automáticamente movimiento {mov.id}: {str(e)}")
                        
        return match_count

    @staticmethod
    def manual_reconciliate(movimiento_id, factura_id):
        """
        Conciliación manual forzada por el operador del ISP.
        Vincula un movimiento bancario y una factura seleccionados manualmente.
        """
        try:
            with transaction.atomic():
                mov = MovimientoBanco.objects.get(id=movimiento_id, estado='PENDING')
                factura = Factura.objects.get(id=factura_id, estado='PENDING')
                cliente = factura.cliente
                
                # Relacionar y cambiar estados
                mov.factura_asociada = factura
                mov.estado = 'CONCILIATED'
                mov.save()
                
                factura.estado = 'PAID'
                
                # Simular timbrado del SAT (Generación de UUID de Facturapi)
                if not factura.sat_uuid:
                    factura.sat_uuid = str(uuid.uuid4()).upper()
                factura.save()
                
                # Actualizar saldo del cliente
                cliente.monto_saldo = max(Decimal('0.00'), cliente.monto_saldo - factura.monto)
                
                # Reactivar cliente si estaba suspendido
                if cliente.estado == 'SUSPENDED':
                    cliente.estado = 'ACTIVE'
                    
                cliente.save()
                return True
        except Exception as e:
            print(f"Error en conciliación manual: {str(e)}")
            return False
