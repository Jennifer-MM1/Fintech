from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse
from decimal import Decimal
import csv
from .models import MovimientoBanco
from billing.models import Factura
from .services.bank_connector import BankConnectorService
from .services.reconciliation_engine import ReconciliationEngine

@login_required
def reconciliation_view(request):
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1. Sincronizar banco con Belvo/Fintoc Sandbox
        if action == 'sync_bank':
            try:
                count = BankConnectorService.sync_bank_movements()
                if count > 0:
                    messages.success(request, f"¡Sincronización bancaria completada exitosamente! Se importaron {count} nuevos movimientos en modo Sandbox.")
                else:
                    messages.info(request, "El banco está al día. No se detectaron nuevos movimientos para importar.")
            except Exception as e:
                messages.error(request, f"Error de conexión con la API bancaria: {str(e)}")
                
        # 2. Ejecutar motor de conciliación automática
        elif action == 'auto_reconciliate':
            try:
                matches = ReconciliationEngine.auto_reconciliate()
                if matches > 0:
                    messages.success(request, f"¡Conciliación completada! El algoritmo inteligente concilió {matches} pagos automáticamente en lote.")
                else:
                    messages.info(request, "Conciliación finalizada. No se encontraron coincidencias automáticas de montos y referencias.")
            except Exception as e:
                messages.error(request, f"Error en el motor de conciliación: {str(e)}")
                
        # 3. Conciliación manual
        elif action == 'manual_reconciliate':
            mov_id = request.POST.get('movimiento_id')
            fact_id = request.POST.get('factura_id')
            if mov_id and fact_id:
                success = ReconciliationEngine.manual_reconciliate(int(mov_id), int(fact_id))
                if success:
                    messages.success(request, "Se ha realizado la conciliación manual del pago y timbrado del SAT de manera exitosa.")
                else:
                    messages.error(request, "Error al procesar la conciliación manual. Verifica que el movimiento y la factura sigan pendientes.")
                    
        return redirect('accounting:reconciliation')

    # Cálculos reales para los widgets financieros de conciliación
    # Saldo en Bancos: Suma total de ingresos bancarios - suma total de egresos bancarios
    ingresos_banco = MovimientoBanco.objects.filter(tipo='INGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    egresos_banco = MovimientoBanco.objects.filter(tipo='EGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_bancos = ingresos_banco - egresos_banco

    # Saldo en Libros (Conciliado): Suma de movimientos bancarios conciliados de ingreso - egreso
    ingresos_libros = MovimientoBanco.objects.filter(tipo='INGRESO', estado='CONCILIATED').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    egresos_libros = MovimientoBanco.objects.filter(tipo='EGRESO', estado='CONCILIATED').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_libros = ingresos_libros - egresos_libros
    
    # Diferencia entre libros y bancos
    diferencia = saldo_bancos - saldo_libros

    # Listas dinámicas para la interfaz dual
    pending_movements = MovimientoBanco.objects.filter(estado='PENDING').order_by('fecha')
    pending_invoices = Factura.objects.filter(estado='PENDING').order_by('fecha_emision').select_related('cliente')
    conciliated_movements = MovimientoBanco.objects.filter(estado='CONCILIATED').select_related('factura_asociada__cliente')[:8]

    context = {
        'saldo_bancos': saldo_bancos,
        'saldo_libros': saldo_libros,
        'diferencia': diferencia,
        'pending_movements': pending_movements,
        'pending_invoices': pending_invoices,
        'conciliated_movements': conciliated_movements,
    }
    return render(request, 'accounting/reconciliation.html', context)

@login_required
def reports_view(request):
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')
        
    # Calcular estadísticas acumuladas reales de la base de datos
    total_facturado = Factura.objects.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    total_cobrado = Factura.objects.filter(estado='PAID').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    cuentas_cobrar = total_facturado - total_cobrado
    
    entradas_banco = MovimientoBanco.objects.filter(tipo='INGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    salidas_banco = MovimientoBanco.objects.filter(tipo='EGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_bancos = entradas_banco - salidas_banco
    
    report_type = request.GET.get('report')
    report_data = None
    
    if report_type == 'estado_resultados':
        gastos_conciliados = MovimientoBanco.objects.filter(tipo='EGRESO', estado='CONCILIATED').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        report_data = {
            'title': 'Estado de Resultados (Ingresos vs Egresos)',
            'period': f'Periodo Actual - {timezone.now().strftime("%B %Y")}',
            'rows': [
                ('Ingresos por Servicios de Internet (Abonos Conciliados)', total_cobrado),
                ('Ingresos Pendientes por Cobrar (Facturas Emitidas)', cuentas_cobrar),
                ('INGRESOS BRUTOS TOTALES', total_facturado),
                ('Gastos Operacionales (Egresos Bancarios Conciliados)', gastos_conciliados),
                ('UTILIDAD OPERATIVA NETTA DEL EJERCICIO', total_facturado - gastos_conciliados),
            ]
        }
    elif report_type == 'balance_general':
        report_data = {
            'title': 'Balance General Contable',
            'period': f'Al día de hoy - {timezone.now().strftime("%d de %B, %Y")}',
            'rows': [
                ('Activos Circulantes - Caja y Bancos (Efectivo)', saldo_bancos),
                ('Activos Circulantes - Clientes (Cuentas por Cobrar)', cuentas_cobrar),
                ('ACTIVO TOTAL', saldo_bancos + cuentas_cobrar),
                ('Pasivos Operacionales (Cargos Bancarios por Pagar)', Decimal('0.00')),
                ('PASIVO TOTAL', Decimal('0.00')),
                ('Capital Contable - Utilidades Retenidas', saldo_bancos + cuentas_cobrar),
                ('PASIVO + CAPITAL TOTAL', saldo_bancos + cuentas_cobrar),
            ]
        }
    elif report_type == 'flujo_efectivo':
        saldo_inicial = Decimal('15000.00')
        report_data = {
            'title': 'Estado de Flujo de Efectivo',
            'period': f'Análisis del mes en curso - {timezone.now().strftime("%B %Y")}',
            'rows': [
                ('Saldo Inicial en Bancos (Caja de Apertura)', saldo_inicial),
                ('Entradas de Efectivo por SPEI / Stripe (Depósitos)', entradas_banco),
                ('Salidas de Efectivo por Operación (Retiros/Cargos)', salidas_banco),
                ('Flujo de Efectivo Neto del Periodo', entradas_banco - salidas_banco),
                ('SALDO FINAL DE CAJA (Bancos)', saldo_inicial + (entradas_banco - salidas_banco)),
            ]
        }
        
    context = {
        'total_facturado': total_facturado,
        'total_cobrado': total_cobrado,
        'cuentas_cobrar': cuentas_cobrar,
        'entradas_banco': entradas_banco,
        'salidas_banco': salidas_banco,
        'saldo_bancos': saldo_bancos,
        'report_type': report_type,
        'report_data': report_data,
    }
    return render(request, 'accounting/reports.html', context)



@login_required
def descargar_reporte_csv(request, report_type):
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')
        
    # Iniciar respuesta HTTP con codificación de Excel en Español (UTF-8-SIG)
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="reporte_{report_type}_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    # Encabezado formal
    writer.writerow(['FINTECHOS - REPORTE CONTABLE OFICIAL'])
    writer.writerow([f'Generado el: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    
    # Datos agregados
    total_facturado = Factura.objects.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    total_cobrado = Factura.objects.filter(estado='PAID').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    cuentas_cobrar = total_facturado - total_cobrado
    entradas_banco = MovimientoBanco.objects.filter(tipo='INGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    salidas_banco = MovimientoBanco.objects.filter(tipo='EGRESO').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_bancos = entradas_banco - salidas_banco

    if report_type == 'estado_resultados':
        gastos_conciliados = MovimientoBanco.objects.filter(tipo='EGRESO', estado='CONCILIATED').aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
        writer.writerow(['ESTADO DE RESULTADOS (INGRESOS VS EGRESOS)'])
        writer.writerow(['Concepto Financiero', 'Monto (MXN)'])
        writer.writerow(['Ingresos por Servicios de Internet (Abonos Conciliados)', f'${total_cobrado:,.2f}'])
        writer.writerow(['Ingresos Pendientes por Cobrar (Facturación en Libros)', f'${cuentas_cobrar:,.2f}'])
        writer.writerow(['INGRESOS BRUTOS TOTALES', f'${total_facturado:,.2f}'])
        writer.writerow(['Gastos Operacionales (Egresos Bancarios Conciliados)', f'${gastos_conciliados:,.2f}'])
        writer.writerow(['UTILIDAD OPERATIVA NETTA DEL EJERCICIO', f'${(total_facturado - gastos_conciliados):,.2f}'])
        
    elif report_type == 'balance_general':
        writer.writerow(['BALANCE GENERAL'])
        writer.writerow(['Cuenta Contable', 'Clasificación', 'Saldo (MXN)'])
        writer.writerow(['Activos Circulantes - Caja y Bancos', 'ACTIVO', f'${saldo_bancos:,.2f}'])
        writer.writerow(['Activos Circulantes - Clientes por Cobrar', 'ACTIVO', f'${cuentas_cobrar:,.2f}'])
        writer.writerow(['ACTIVO TOTAL', 'ACTIVO', f'${(saldo_bancos + cuentas_cobrar):,.2f}'])
        writer.writerow(['Pasivos Operacionales - Cuentas por Pagar', 'PASIVO', '$0.00'])
        writer.writerow(['PASIVO TOTAL', 'PASIVO', '$0.00'])
        writer.writerow(['Capital Contable - Resultados del Periodo', 'CAPITAL', f'${(saldo_bancos + cuentas_cobrar):,.2f}'])
        writer.writerow(['PASIVO + CAPITAL TOTAL', 'PASIVO/CAPITAL', f'${(saldo_bancos + cuentas_cobrar):,.2f}'])
        
    elif report_type == 'flujo_efectivo':
        saldo_inicial = Decimal('15000.00')
        writer.writerow(['ESTADO DE FLUJO DE EFECTIVO'])
        writer.writerow(['Categoría de Flujo', 'Monto (MXN)'])
        writer.writerow(['Saldo Inicial de Caja (Apertura)', f'${saldo_inicial:,.2f}'])
        writer.writerow(['Entradas de Efectivo (Depósitos Bancarios)', f'${entradas_banco:,.2f}'])
        writer.writerow(['Salidas de Efectivo (Retiros Bancarios)', f'${salidas_banco:,.2f}'])
        writer.writerow(['Flujo de Efectivo Neto del Periodo', f'${(entradas_banco - salidas_banco):,.2f}'])
        writer.writerow(['SALDO FINAL DE CAJA (DISPONIBLE EN BANCOS)', f'${(saldo_inicial + (entradas_banco - salidas_banco)):,.2f}'])
        
    else:
        writer.writerow(['Error', 'Tipo de reporte desconocido'])
        
    return response
