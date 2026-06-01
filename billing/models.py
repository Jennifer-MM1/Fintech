from django.db import models
from django.utils import timezone
from clients.models import ClientProfile, PlanServicio

class Suscripcion(models.Model):
    cliente = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='suscripciones', verbose_name="Cliente")
    plan = models.ForeignKey(PlanServicio, on_delete=models.PROTECT, related_name='suscripciones', verbose_name="Plan Contratado")
    fecha_inicio = models.DateField(default=timezone.now, verbose_name="Fecha de Inicio")
    dia_cobro = models.IntegerField(default=1, verbose_name="Día de Cobro Mensual")
    activa = models.BooleanField(default=True, verbose_name="Suscripción Activa")

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"

    def __str__(self):
        estado_str = "Activa" if self.activa else "Inactiva"
        return f"{self.cliente.razon_social} - {self.plan.nombre} ({estado_str})"


class Factura(models.Model):
    ESTADOS = [
        ('PENDING', 'Pendiente'),
        ('PAID', 'Pagada'),
        ('OVERDUE', 'Vencida'),
    ]

    cliente = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='facturas', verbose_name="Cliente")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto de la Factura")
    fecha_emision = models.DateField(default=timezone.now, verbose_name="Fecha de Emisión")
    fecha_vencimiento = models.DateField(verbose_name="Fecha de Vencimiento")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDING', verbose_name="Estado de Pago")
    periodo_facturacion = models.CharField(max_length=50, verbose_name="Periodo de Facturación")
    
    # Simulación e Integración de APIs
    sat_uuid = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name="UUID de Facturación SAT")
    stripe_payment_intent = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID de Transacción Stripe")

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision']

    def save(self, *args, **kwargs):
        # Auto-establecer fecha de vencimiento si no está provista (por defecto 10 días después de emisión)
        if not self.fecha_vencimiento:
            self.fecha_vencimiento = self.fecha_emision + timezone.timedelta(days=10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Factura #{self.id or 'Nueva'} - {self.cliente.razon_social} (${self.monto}) [{self.estado}]"
