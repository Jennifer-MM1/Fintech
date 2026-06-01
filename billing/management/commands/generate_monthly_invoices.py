from django.core.management.base import BaseCommand
from django.utils import timezone
from clients.models import ClientProfile
from billing.models import Suscripcion, Factura
from django.db import transaction

class Command(BaseCommand):
    help = "Genera facturas mensuales automáticas para todos los clientes con suscripción activa."

    def add_arguments(self, parser):
        # Permite forzar la facturación para pruebas sin importar si ya existe factura en el mes
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la creación de facturas incluso si ya existen para el periodo actual.',
        )

    def handle(self, *args, **options):
        # Diccionario de meses en español
        meses_es = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        ahora = timezone.now()
        nombre_mes = meses_es[ahora.month]
        periodo_actual = f"{nombre_mes} {ahora.year}"
        
        self.stdout.write(f"Iniciando ciclo de facturación para: {periodo_actual}...")
        
        # Buscar suscripciones activas
        suscripciones_activas = Suscripcion.objects.filter(activa=True).select_related('cliente', 'plan')
        
        invoices_created = 0
        invoices_skipped = 0
        
        with transaction.atomic():
            for sub in suscripciones_activas:
                cliente = sub.cliente
                plan = sub.plan
                
                # Verificar duplicados para este periodo
                factura_existe = Factura.objects.filter(
                    cliente=cliente,
                    periodo_facturacion=periodo_actual
                ).exists()
                
                if factura_existe and not options['force']:
                    invoices_skipped += 1
                    continue
                
                # Generar nueva factura
                monto_cobro = plan.precio
                fecha_emision = ahora.date()
                # Fecha de vencimiento es el día 10 del mes actual (o 10 días después de emisión)
                fecha_vencimiento = fecha_emision + timezone.timedelta(days=10)
                
                factura = Factura.objects.create(
                    cliente=cliente,
                    monto=monto_cobro,
                    fecha_emision=fecha_emision,
                    fecha_vencimiento=fecha_vencimiento,
                    estado='PENDING',
                    periodo_facturacion=periodo_actual
                )
                
                # Actualizar el saldo acumulado en el perfil del cliente
                cliente.monto_saldo += monto_cobro
                cliente.save()
                
                invoices_created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Factura #{factura.id} creada para {cliente.razon_social} por ${monto_cobro} ({periodo_actual})."
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f"Proceso finalizado. Facturas creadas: {invoices_created} | Omitidas (ya facturadas): {invoices_skipped}."
        ))
