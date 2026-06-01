import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fintech_core.settings')
django.setup()

from core.models import User
from clients.models import ClientProfile, PlanServicio
from billing.models import Factura, Suscripcion

# 1. Crear el Administrador del ISP
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@fintech.com', 'admin123')
    print("Superusuario 'admin' creado con contraseña 'admin123'.")
else:
    print("Superusuario 'admin' ya existe.")

# 2. Crear los Planes de Servicio de Internet
planes_data = [
    {'nombre': 'Paquete Básico 20 Megas', 'velocidad_mbps': 20, 'precio': 299.00, 'descripcion': 'Ideal para navegación básica y redes sociales.'},
    {'nombre': 'Paquete Estándar 50 Megas', 'velocidad_mbps': 50, 'precio': 399.00, 'descripcion': 'Perfecto para streaming en HD y teletrabajo.'},
    {'nombre': 'Paquete Premium 100 Megas', 'velocidad_mbps': 100, 'precio': 599.00, 'descripcion': 'Para gaming y múltiples dispositivos conectados simultáneamente.'},
]

planes = {}
for plan_info in planes_data:
    plan, created = PlanServicio.objects.get_or_create(
        nombre=plan_info['nombre'],
        defaults={
            'velocidad_mbps': plan_info['velocidad_mbps'],
            'precio': plan_info['precio'],
            'descripcion': plan_info['descripcion']
        }
    )
    planes[plan.nombre] = plan
    if created:
        print(f"Plan '{plan.nombre}' creado.")
    else:
        print(f"Plan '{plan.nombre}' ya existe.")

# 3. Crear Clientes de Prueba con Planes y Suscripciones
clientes_data = [
    {
        'username': 'cliente1',
        'email': 'contacto@techcorp.com',
        'password': 'cliente123',
        'razon_social': 'Tech Corp SA de CV',
        'rfc': 'TCO190526ABC',
        'direccion': 'Av. Insurgentes Sur 1234, CDMX',
        'correo_facturacion': 'pagos@techcorp.com',
        'plan_nombre': 'Paquete Premium 100 Megas',
        'estado': 'ACTIVE',
        'saldo': 0.00
    },
    {
        'username': 'cliente2',
        'email': 'donpedro@gmail.com',
        'password': 'cliente123',
        'razon_social': 'Abarrotes Don Pedro',
        'rfc': 'APED821015XYZ',
        'direccion': 'Calle Hidalgo #45, Col. Centro, Guadalajara',
        'correo_facturacion': 'facturas@donpedro.com',
        'plan_nombre': 'Paquete Básico 20 Megas',
        'estado': 'ACTIVE',
        'saldo': 0.00
    },
    {
        'username': 'cliente3',
        'email': 'drjuarez@medicos.com',
        'password': 'cliente123',
        'razon_social': 'Consultorio Médico Juárez',
        'rfc': 'MJU850311AAA',
        'direccion': 'Paseo de la Reforma 500, CDMX',
        'correo_facturacion': 'administracion@drjuarez.com',
        'plan_nombre': 'Paquete Estándar 50 Megas',
        'estado': 'SUSPENDED', # Suspendido por falta de pago
        'saldo': 399.00
    }
]

for cli in clientes_data:
    user, created_user = User.objects.get_or_create(
        username=cli['username'],
        defaults={
            'email': cli['email'],
            'is_client': True
        }
    )
    if created_user:
        user.set_password(cli['password'])
        user.save()
        print(f"Usuario portal '{user.username}' creado con contraseña 'cliente123'.")

    # Crear o actualizar perfil
    plan_obj = planes[cli['plan_nombre']]
    profile, created_profile = ClientProfile.objects.get_or_create(
        user=user,
        defaults={
            'razon_social': cli['razon_social'],
            'rfc': cli['rfc'],
            'direccion': cli['direccion'],
            'correo_facturacion': cli['correo_facturacion'],
            'plan': plan_obj,
            'estado': cli['estado'],
            'monto_saldo': cli['saldo']
        }
    )
    
    # Si ya existía, nos aseguramos de que tenga los campos nuevos asignados
    if not created_profile:
        print(f"Actualizando perfil existente para '{profile.razon_social}'...")
        profile.plan = plan_obj
        profile.estado = cli['estado']
        profile.monto_saldo = cli['saldo']
        # Forzar guardado para disparar la generación del código de referencia SPEI
        profile.save()
    else:
        print(f"Perfil de cliente '{profile.razon_social}' creado con código de referencia {profile.codigo_referencia}.")
        
    # Asegurar suscripción
    sub, created_sub = Suscripcion.objects.get_or_create(
        cliente=profile,
        plan=plan_obj,
        defaults={
            'fecha_inicio': timezone.now().date(),
            'activa': (cli['estado'] != 'INACTIVE')
        }
    )
    if created_sub:
        print(f"Suscripción creada para '{profile.razon_social}'.")
    else:
        # Asegurar que esté activa según su estado
        sub.activa = (cli['estado'] != 'INACTIVE')
        sub.save()
        print(f"Suscripción actualizada para '{profile.razon_social}'.")
        
    # Si tiene saldo pendiente, le creamos una factura vencida si no tiene ninguna factura pendiente
    if cli['saldo'] > 0 and not Factura.objects.filter(cliente=profile, estado='PENDING').exists():
        fecha_vencida = timezone.now().date() - timezone.timedelta(days=15)
        Factura.objects.create(
            cliente=profile,
            monto=cli['saldo'],
            fecha_emision=fecha_vencida - timezone.timedelta(days=10),
            fecha_vencimiento=fecha_vencida,
            estado='PENDING',
            periodo_facturacion='Mes Anterior'
        )
        print(f"Factura PENDIENTE simulada para cliente suspendido '{profile.razon_social}'.")

print("Inicialización semilla completada exitosamente.")
