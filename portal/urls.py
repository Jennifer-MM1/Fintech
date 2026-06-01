from django.urls import path
from . import views

app_name = 'portal'
urlpatterns = [
    path('', views.portal_index_view, name='index'),
    path('dashboard/', views.portal_dashboard_view, name='dashboard'),
    path('historial/', views.portal_history_view, name='history'),
    path('perfil/', views.portal_profile_view, name='profile'),
    path('pago/<str:invoice_id>/', views.portal_checkout_view, name='checkout'),
    path('pago/<str:invoice_id>/procesar/', views.portal_process_payment_view, name='process_payment'),
    path('pago/<str:invoice_id>/exito/', views.portal_payment_success_view, name='payment_success'),
    path('logout/', views.portal_logout_view, name='logout'),
    path('factura/<int:invoice_id>/pdf/', views.descargar_factura_pdf, name='descargar_pdf'),
    path('factura/<int:invoice_id>/xml/', views.descargar_factura_xml, name='descargar_xml'),
]
