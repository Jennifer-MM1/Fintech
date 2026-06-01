from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import User
from .models import ClientProfile, PlanServicio
from billing.models import Suscripcion
from django.db import transaction

@login_required
def client_list_view(request):
    # Solo administradores pueden ver el CRM
    if getattr(request.user, 'is_client', False):
        return redirect('portal:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'new_plan':
            nombre = request.POST.get('nombre')
            velocidad = request.POST.get('velocidad')
            precio = request.POST.get('precio')
            descripcion = request.POST.get('descripcion')
            
            try:
                PlanServicio.objects.create(
                    nombre=nombre,
                    velocidad_mbps=int(velocidad),
                    precio=float(precio),
                    descripcion=descripcion
                )
                messages.success(request, f"Plan '{nombre}' creado exitosamente.")
            except Exception as e:
                messages.error(request, f"Error al crear el plan: {str(e)}")
                
        elif action == 'new_client':
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            razon_social = request.POST.get('razon_social')
            rfc = request.POST.get('rfc')
            direccion = request.POST.get('direccion')
            correo_facturacion = request.POST.get('correo_facturacion')
            plan_id = request.POST.get('plan')
            
            try:
                with transaction.atomic():
                    # 1. Crear el usuario de acceso al portal
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        is_client=True
                    )
                    
                    # 2. Obtener el plan
                    plan = None
                    if plan_id:
                        plan = PlanServicio.objects.get(id=int(plan_id))
                    
                    # 3. Crear el perfil del cliente (esto auto-genera la referencia SPEI)
                    profile = ClientProfile.objects.create(
                        user=user,
                        razon_social=razon_social,
                        rfc=rfc,
                        direccion=direccion,
                        correo_facturacion=correo_facturacion,
                        plan=plan,
                        estado='ACTIVE',
                        monto_saldo=0.00
                    )
                    
                    # 4. Crear su suscripción activa
                    if plan:
                        Suscripcion.objects.create(
                            cliente=profile,
                            plan=plan,
                            activa=True
                        )
                        
                    messages.success(request, f"Cliente '{razon_social}' registrado exitosamente con código SPEI {profile.codigo_referencia}.")
            except Exception as e:
                messages.error(request, f"Error al registrar el cliente: {str(e)}")
                
        return redirect('clients:list')

    # GET request
    clients = ClientProfile.objects.all().select_related('plan', 'user')
    plans = PlanServicio.objects.all()
    
    context = {
        'clients': clients,
        'plans': plans,
    }
    return render(request, 'clients/list.html', context)
