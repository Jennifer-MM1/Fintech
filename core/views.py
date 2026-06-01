from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.management import call_command
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from clients.models import ClientProfile
from billing.models import Factura
from accounting.models import MovimientoBanco

@login_required
def dashboard_view(request):
    # Redirigir a clientes al portal
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')

    # Manejar disparo manual del ciclo de facturación mensual
    if request.method == 'POST' and request.POST.get('action') == 'trigger_billing':
        try:
            # Ejecutar el comando de facturación mensual usando call_command
            # Usamos force=True para que se generen facturas nuevas para probar sin esperar al siguiente mes
            call_command('generate_monthly_invoices', force=True)
            messages.success(request, "¡Ciclo de facturación mensual ejecutado. Se han generado facturas para todos los clientes activos!")
        except Exception as e:
            messages.error(request, f"Error al generar la facturación: {str(e)}")
        return redirect('dashboard')

    # 1. Calcular estadísticas dinámicas reales
    # Ingresos del Mes (facturas pagadas en el mes actual)
    ahora = timezone.now()
    ingresos_mes = Factura.objects.filter(
        estado='PAID',
        fecha_emision__month=ahora.month,
        fecha_emision__year=ahora.year
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Egresos / Saldo Pendiente de Cobro (facturas pendientes o vencidas)
    saldo_pendiente = Factura.objects.filter(
        estado='PENDING'
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    
    # Movimientos bancarios pendientes de conciliar
    movimientos_pendientes = MovimientoBanco.objects.filter(
        estado='PENDING'
    ).count()

    # 2. Últimas facturas generadas
    ultimas_facturas = Factura.objects.all().select_related('cliente')[:5]
    
    # 3. Métricas adicionales para el banner superior
    clientes_activos = ClientProfile.objects.filter(estado='ACTIVE').count()

    context = {
        'ingresos_mes': ingresos_mes,
        'saldo_pendiente': saldo_pendiente,
        'movimientos_pendientes': movimientos_pendientes,
        'ultimas_facturas': ultimas_facturas,
        'clientes_activos': clientes_activos,
    }
    return render(request, 'core/dashboard.html', context)
