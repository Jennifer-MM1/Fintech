from django.urls import path
from . import views

app_name = 'billing'
urlpatterns = [
    path('', views.invoices_view, name='invoices'),
    path('<int:invoice_id>/pdf/', views.descargar_factura_pdf, name='descargar_pdf'),
    path('<int:invoice_id>/xml/', views.descargar_factura_xml, name='descargar_xml'),
]
