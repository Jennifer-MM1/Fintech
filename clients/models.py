from django.db import models
from django.conf import settings
import random

class PlanServicio(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Plan")
    velocidad_mbps = models.IntegerField(verbose_name="Velocidad (Mbps)")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Mensual")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Plan de Servicio"
        verbose_name_plural = "Planes de Servicio"

    def __str__(self):
        return f"{self.nombre} - ${self.precio}/mes"


class ClientProfile(models.Model):
    ESTADOS = [
        ('ACTIVE', 'Activo'),
        ('SUSPENDED', 'Suspendido'),
        ('INACTIVE', 'Inactivo'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='client_profile')
    razon_social = models.CharField(max_length=255, verbose_name="Razón Social / Nombre")
    rfc = models.CharField(max_length=20, unique=True, verbose_name="RFC")
    direccion = models.TextField(blank=True, null=True, verbose_name="Dirección")
    correo_facturacion = models.EmailField(blank=True, null=True, verbose_name="Correo de Facturación")
    
    # Nuevos campos para ISP y Conciliación
    plan = models.ForeignKey(PlanServicio, on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes', verbose_name="Plan Contratado")
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVE', verbose_name="Estado de Servicio")
    monto_saldo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Saldo Pendiente")
    codigo_referencia = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Código de Referencia SPEI")

    class Meta:
        verbose_name = "Perfil de Cliente"
        verbose_name_plural = "Perfiles de Clientes"

    def save(self, *args, **kwargs):
        # Auto-generar código de referencia único si no existe
        if not self.codigo_referencia:
            while True:
                ref_num = random.randint(1000, 9999)
                ref_code = f"REF-{ref_num}"
                if not ClientProfile.objects.filter(codigo_referencia=ref_code).exists():
                    self.codigo_referencia = ref_code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.razon_social} ({self.codigo_referencia})"
