from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse
from decimal import Decimal
from clients.models import ClientProfile
from billing.models import Factura
from billing.services.sat_service import SatBillingService
from billing.services.pdf_service import PdfInvoiceService

@login_required
def invoices_view(request):
    # Restringir acceso solo a operadores del ISP
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'new_invoice':
            cliente_id = request.POST.get('cliente')
            monto_str = request.POST.get('monto', '0.00').strip()
            periodo = request.POST.get('periodo', '').strip()
            
            try:
                # Validaciones
                if not cliente_id or not monto_str or not periodo:
                    messages.error(request, "Todos los campos de la factura son obligatorios.")
                else:
                    cliente = get_object_or_404(ClientProfile, id=int(cliente_id))
                    monto = Decimal(monto_str)
                    
                    if monto <= 0:
                        messages.error(request, "El monto de la factura debe ser mayor que cero.")
                    else:
                        # Crear Factura
                        fecha_emision = timezone.now().date()
                        fecha_vencimiento = fecha_emision + timezone.timedelta(days=10)
                        
                        factura = Factura.objects.create(
                            cliente=cliente,
                            monto=monto,
                            fecha_emision=fecha_emision,
                            fecha_vencimiento=fecha_vencimiento,
                            estado='PENDING',
                            periodo_facturacion=periodo
                        )
                        
                        # Actualizar saldo del cliente
                        cliente.monto_saldo += monto
                        cliente.save()
                        
                        messages.success(request, f"¡Factura #{factura.id} por ${monto} creada exitosamente para {cliente.razon_social}!")
            except Exception as e:
                messages.error(request, f"Error al generar la factura: {str(e)}")
                
            return redirect('billing:invoices')

    # Solicitudes GET
    invoices = Factura.objects.all().select_related('cliente').order_by('-fecha_emision')
    clients = ClientProfile.objects.filter(estado='ACTIVE').order_by('razon_social')
    
    # Calcular estadísticas básicas para los mini-widgets de facturación
    total_facturado = Factura.objects.aggregate(total=models_sum()) if False else sum(float(f.monto) for f in invoices)
    
    context = {
        'invoices': invoices,
        'clients': clients,
        'total_facturado': total_facturado,
    }
    return render(request, 'billing/invoices.html', context)


@login_required
def descargar_factura_pdf(request, invoice_id):
    # Asegurar rol de operador
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')
        
    invoice = get_object_or_404(Factura, id=int(invoice_id))
    
    if not invoice.sat_uuid:
        messages.error(request, "Esta factura aún no ha sido timbrada ante el SAT (estatus pendiente).")
        return redirect('billing:invoices')
        
    try:
        pdf_buffer = PdfInvoiceService.generate_invoice_pdf(invoice)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="factura_{invoice.id}_{invoice.sat_uuid[:8]}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar el PDF de facturación: {str(e)}")
        return redirect('billing:invoices')


@login_required
def descargar_factura_xml(request, invoice_id):
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')
        
    invoice = get_object_or_404(Factura, id=int(invoice_id))
    
    if not invoice.sat_uuid:
        messages.error(request, "Esta factura aún no ha sido timbrada ante el SAT (estatus pendiente).")
        return redirect('billing:invoices')
        
    try:
        xml_string = SatBillingService.get_xml_mockup(invoice)
        response = HttpResponse(xml_string, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="factura_{invoice.id}_{invoice.sat_uuid[:8]}.xml"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar el XML de facturación: {str(e)}")
        return redirect('billing:invoices')
