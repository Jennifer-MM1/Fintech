from django.urls import path
from . import views

app_name = 'accounting'
urlpatterns = [
    path('conciliacion/', views.reconciliation_view, name='reconciliation'),
    path('reportes/', views.reports_view, name='reports'),
    path('reportes/descargar/<str:report_type>/', views.descargar_reporte_csv, name='download_report_csv'),
]
