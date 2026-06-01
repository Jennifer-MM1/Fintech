from django.db import models
from billing.models import Factura

class MovimientoBanco(models.Model):
    TIPOS = [
        ('INGRESO', 'Ingreso (Depósito / Abono)'),
        ('EGRESO', 'Egreso (Retiro / Cargo)'),
    ]
    
    ESTADOS = [
        ('PENDING', 'Pendiente de Conciliar'),
        ('CONCILIATED', 'Conciliado'),
    ]

    fecha = models.DateField(verbose_name="Fecha de Transacción")
    concepto = models.TextField(verbose_name="Concepto de Transferencia / SPEI")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    tipo = models.CharField(max_length=20, choices=TIPOS, default='INGRESO', verbose_name="Tipo de Operación")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDING', verbose_name="Estado de Conciliación")
    
    # Relación con la factura una vez conciliada
    factura_asociada = models.ForeignKey(
        Factura, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='movimientos_banco', 
        verbose_name="Factura Conciliada"
    )
    
    codigo_transaccion = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Código de Transacción Bancaria"
    )

    class Meta:
        verbose_name = "Movimiento Bancario"
        verbose_name_plural = "Movimientos Bancarios"
        ordering = ['-fecha']

    def __str__(self):
        tipo_prefijo = "+" if self.tipo == 'INGRESO' else "-"
        return f"{self.fecha} | {self.concepto[:30]} | {tipo_prefijo}${self.monto} ({self.estado})"
