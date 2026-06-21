from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from billing.models import Factura
from clients.models import ClientProfile
import uuid

def portal_index_view(request):
    if request.user.is_authenticated:
        if request.user.is_client:
            return redirect('portal:dashboard')
        return redirect('dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            if user.is_client:
                return redirect('portal:dashboard')
            else:
                return redirect('dashboard')
        else:
            messages.error(request, "Credenciales inválidas")
            
    return render(request, 'portal/index.html')

@login_required
def portal_dashboard_view(request):
    # Asegurar que sea un cliente
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    try:
        profile = request.user.client_profile
    except ClientProfile.DoesNotExist:
        messages.error(request, "El usuario no tiene un perfil de cliente configurado.")
        logout(request)
        return redirect('portal:index')
        
    # Obtener facturas pendientes y vencidas
    pending_invoices = Factura.objects.filter(
        cliente=profile,
        estado__in=['PENDING', 'OVERDUE']
    )
    
    context = {
        'profile': profile,
        'invoices': pending_invoices,
    }
    return render(request, 'portal/dashboard.html', context)

@login_required
def portal_history_view(request):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    paid_invoices = Factura.objects.filter(
        cliente=profile,
        estado='PAID'
    )
    
    context = {
        'profile': profile,
        'invoices': paid_invoices,
    }
    return render(request, 'portal/history.html', context)

@login_required
def portal_profile_view(request):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    
    if request.method == 'POST':
        razon_social = request.POST.get('razon_social', '').strip()
        rfc = request.POST.get('rfc', '').strip().upper()
        correo_facturacion = request.POST.get('correo_facturacion', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        
        # Validar campos vacíos
        if not razon_social or not rfc or not correo_facturacion or not direccion:
            messages.error(request, "Todos los campos fiscales son obligatorios.")
        else:
            # Validar que el RFC no esté repetido en otro perfil de cliente
            rfc_existe = ClientProfile.objects.filter(rfc=rfc).exclude(id=profile.id).exists()
            if rfc_existe:
                messages.error(request, f"El RFC '{rfc}' ya está registrado por otro cliente en el sistema.")
            else:
                try:
                    profile.razon_social = razon_social
                    profile.rfc = rfc
                    profile.correo_facturacion = correo_facturacion
                    profile.direccion = direccion
                    profile.save()
                    messages.success(request, "¡Datos fiscales actualizados con éxito! Los cambios se aplicarán en todos tus futuros comprobantes.")
                    return redirect('portal:profile')
                except Exception as e:
                    messages.error(request, f"Error al actualizar la base de datos: {str(e)}")
                    
    context = {
        'profile': profile,
    }
    return render(request, 'portal/profile.html', context)

@login_required
def portal_checkout_view(request, invoice_id):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    invoice = get_object_or_404(Factura, id=int(invoice_id), cliente=profile)
    
    if invoice.estado == 'PAID':
        messages.info(request, "Esta factura ya ha sido pagada.")
        return redirect('portal:dashboard')
        
    # Calcular desglose de IVA (16% en México)
    subtotal = float(invoice.monto) / 1.16
    iva = float(invoice.monto) - subtotal
    
    stripe_pub_key = getattr(settings, 'STRIPE_PUBLIC_KEY', 'pk_test_stripe_sandbox_placeholder')
    
    context = {
        'profile': profile,
        'invoice': invoice,
        'subtotal': subtotal,
        'iva': iva,
        'stripe_public_key': stripe_pub_key,
    }
    return render(request, 'portal/checkout.html', context)

@login_required
def portal_process_payment_view(request, invoice_id):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    if request.method == 'POST':
        profile = request.user.client_profile
        invoice = get_object_or_404(Factura, id=int(invoice_id), cliente=profile)
        
        if invoice.estado == 'PAID':
            return redirect('portal:dashboard')
            
        # Simular procesamiento de pasarela Stripe Sandbox
        # En una integración real llamaríamos a stripe.Charge.create o PaymentIntent.confirm
        try:
            # 1. Marcar factura como pagada
            invoice.estado = 'PAID'
            invoice.stripe_payment_intent = f"ch_stripe_sandbox_{uuid.uuid4().hex[:12]}"
            
            # 2. Generar timbrado de SAT simulado
            invoice.sat_uuid = str(uuid.uuid4()).upper()
            invoice.save()
            
            # 3. Actualizar saldo del cliente
            profile.monto_saldo = max(0.00, profile.monto_saldo - invoice.monto)
            
            # 4. Reactivar servicio si estaba suspendido
            if profile.estado == 'SUSPENDED':
                profile.estado = 'ACTIVE'
                
            profile.save()
            
            messages.success(request, f"¡Pago de la Factura #{invoice.id} procesado con éxito!")
            return redirect('portal:payment_success', invoice_id=invoice.id)
            
        except Exception as e:
            messages.error(request, f"Error al procesar el pago con Stripe: {str(e)}")
            return redirect('portal:checkout', invoice_id=invoice.id)
            
    return redirect('portal:dashboard')

@login_required
def portal_payment_success_view(request, invoice_id):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    invoice = get_object_or_404(Factura, id=int(invoice_id), cliente=profile)
    
    context = {
        'profile': profile,
        'invoice': invoice,
    }
    return render(request, 'portal/success.html', context)

def portal_logout_view(request):
    logout(request)
    return redirect('portal:index')


def aviso_privacidad_view(request):
    """Public view for the full Privacy Notice page (no login required)."""
    return render(request, 'portal/aviso_privacidad.html')


from django.http import HttpResponse
from billing.services.sat_service import SatBillingService
from billing.services.pdf_service import PdfInvoiceService

@login_required
def descargar_factura_pdf(request, invoice_id):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    invoice = get_object_or_404(Factura, id=int(invoice_id), cliente=profile)
    
    if not invoice.sat_uuid:
        messages.error(request, "Esta factura aún no cuenta con un folio digital timbrado (SAT).")
        return redirect('portal:dashboard')
        
    try:
        pdf_buffer = PdfInvoiceService.generate_invoice_pdf(invoice)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="factura_{invoice.id}_{invoice.sat_uuid[:8]}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar el archivo PDF: {str(e)}")
        return redirect('portal:history')


@login_required
def descargar_factura_xml(request, invoice_id):
    if not getattr(request.user, 'is_client', False):
        return redirect('dashboard')
        
    profile = request.user.client_profile
    invoice = get_object_or_404(Factura, id=int(invoice_id), cliente=profile)
    
    if not invoice.sat_uuid:
        messages.error(request, "Esta factura aún no cuenta con un folio digital timbrado (SAT).")
        return redirect('portal:dashboard')
        
    try:
        xml_string = SatBillingService.get_xml_mockup(invoice)
        response = HttpResponse(xml_string, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="factura_{invoice.id}_{invoice.sat_uuid[:8]}.xml"'
        return response
    except Exception as e:
        messages.error(request, f"Error al generar el archivo XML: {str(e)}")
        return redirect('portal:history')

