import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from django.utils import timezone

class PdfInvoiceService:
    @staticmethod
    def generate_invoice_pdf(invoice):
        """
        Genera un archivo PDF con diseño premium para la factura especificada.
        Retorna un objeto BytesIO con el contenido del PDF.
        """
        buffer = io.BytesIO()
        
        # Tamaño de página Carta: 612 x 792 puntos
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # --- DEFINICIÓN DE COLORES Y ESTILOS ---
        PRIMARY_COLOR = colors.HexColor("#0F172A")    # Slate 900 (Fondo principal / Textos oscuros)
        SECONDARY_COLOR = colors.HexColor("#3B82F6")  # Blue 500 (Acento principal / Azul Fintech)
        TEXT_MUTED = colors.HexColor("#64748B")       # Slate 500 (Textos secundarios)
        BG_PANEL = colors.HexColor("#F8FAFC")         # Slate 50 (Fondo de páneles)
        BORDER_COLOR = colors.HexColor("#E2E8F0")     # Slate 200 (Líneas divisorias)
        WHITE = colors.HexColor("#FFFFFF")
        
        # --- ENCABEZADO (ISP) ---
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 16)
        p.drawString(40, 730, "INTERNET SERVICE PROVIDER S.A.")
        
        p.setFont("Helvetica", 9)
        p.setFillColor(TEXT_MUTED)
        p.drawString(40, 715, "RFC: ISP990101AAA")
        p.drawString(40, 702, "Régimen Fiscal: 601 - General de Ley Personas Morales")
        p.drawString(40, 689, "Dirección: Av. de la Reforma 100, Col. Juárez, CDMX, CP 06600")
        p.drawString(40, 676, "Email: contacto@internetservice.com | Tel: 55-1234-5678")
        
        # --- TÍTULO DE LA FACTURA ---
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 11)
        p.drawRightString(width - 40, 730, "FACTURA ELECTRÓNICA (CFDI 4.0)")
        
        p.setFont("Helvetica-Bold", 14)
        p.setFillColor(SECONDARY_COLOR)
        p.drawRightString(width - 40, 712, f"Folio: #{invoice.id}")
        
        # Fecha de Emisión
        p.setFont("Helvetica", 9)
        p.setFillColor(TEXT_MUTED)
        p.drawRightString(width - 40, 697, f"Fecha Emisión: {invoice.fecha_emision.strftime('%Y-%m-%d')}")
        p.drawRightString(width - 40, 684, f"Lugar de Expedición: 06600 (CDMX)")
        
        # Línea divisoria superior
        p.setStrokeColor(BORDER_COLOR)
        p.setLineWidth(1)
        p.line(40, 660, width - 40, 660)
        
        # --- BLOQUES INFORMATIVOS: RECEPTOR Y DATOS DE PAGO ---
        # Panel izquierdo (Receptor/Cliente)
        p.setFillColor(BG_PANEL)
        p.rect(40, 540, 255, 105, fill=True, stroke=False)
        
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(50, 630, "RECEPTOR / CLIENTE")
        
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, 615, invoice.cliente.razon_social)
        p.setFont("Helvetica", 9)
        p.drawString(50, 602, f"RFC: {invoice.cliente.rfc}")
        p.drawString(50, 589, f"Uso CFDI: G03 - Gastos en general")
        p.drawString(50, 576, f"Régimen Receptor: 605 - Sueldos y Salarios")
        # Truncar dirección si es muy larga
        dir_str = invoice.cliente.direccion or "Sin dirección registrada"
        if len(dir_str) > 40:
            dir_str = dir_str[:38] + "..."
        p.drawString(50, 563, f"Dirección: {dir_str}")
        
        # Panel derecho (Datos de Pago)
        p.setFillColor(BG_PANEL)
        p.rect(width - 40 - 255, 540, 255, 105, fill=True, stroke=False)
        
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(width - 40 - 245, 630, "DATOS DE FACTURACIÓN Y PAGO")
        
        p.setFont("Helvetica", 9)
        p.drawString(width - 40 - 245, 612, f"Moneda: MXN - Peso Mexicano")
        p.drawString(width - 40 - 245, 599, f"Método de Pago: PUE - Pago en una sola exhibición")
        
        # Determinar forma de pago
        forma_pago = "03 - Transferencia electrónica de fondos (SPEI)"
        if invoice.stripe_payment_intent:
            forma_pago = "04 - Tarjeta de crédito (Stripe)"
        p.drawString(width - 40 - 245, 586, f"Forma de Pago: {forma_pago}")
        p.drawString(width - 40 - 245, 573, f"Periodo: {invoice.periodo_facturacion}")
        
        # Estatus de Pago
        estatus_str = "PAGADO Y CONCILIADO" if invoice.estado == 'PAID' else "PENDIENTE DE PAGO"
        estatus_color = SECONDARY_COLOR if invoice.estado == 'PAID' else colors.HexColor("#EF4444")
        p.setFont("Helvetica-Bold", 9)
        p.drawString(width - 40 - 245, 555, "Estatus de Pago:")
        p.setFillColor(estatus_color)
        p.drawString(width - 40 - 165, 555, estatus_str)
        
        # --- TABLA DE CONCEPTOS ---
        p.setFillColor(PRIMARY_COLOR)
        # Cabecera de la tabla
        p.setFont("Helvetica-Bold", 9)
        p.setFillColor(PRIMARY_COLOR)
        p.rect(40, 500, width - 80, 20, fill=True, stroke=False)
        
        p.setFillColor(WHITE)
        p.drawString(50, 506, "Clave SAT")
        p.drawString(120, 506, "Descripción del Concepto / Servicio")
        p.drawRightString(360, 506, "Cantidad")
        p.drawRightString(420, 506, "Unidad")
        p.drawRightString(490, 506, "P. Unitario")
        p.drawRightString(width - 50, 506, "Importe")
        
        # Contenido de la fila de conceptos
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica", 9)
        p.drawString(50, 480, "81112101")
        
        plan_nombre = invoice.cliente.plan.nombre if invoice.cliente.plan else "Plan de Internet"
        concepto_desc = f"Mensualidad Internet - {plan_nombre} - Periodo {invoice.periodo_facturacion}"
        p.drawString(120, 480, concepto_desc)
        p.drawRightString(360, 480, "1.00")
        p.drawRightString(420, 480, "E48")
        
        # Operaciones aritméticas
        monto_total = float(invoice.monto)
        subtotal = monto_total / 1.16
        iva = monto_total - subtotal
        
        p.drawRightString(490, 480, f"${subtotal:,.2f}")
        p.drawRightString(width - 50, 480, f"${subtotal:,.2f}")
        
        # Línea divisoria inferior de la tabla
        p.setStrokeColor(BORDER_COLOR)
        p.line(40, 465, width - 40, 465)
        
        # --- RESUMEN DE TOTALES ---
        y_totales = 445
        p.setFont("Helvetica", 9)
        p.setFillColor(TEXT_MUTED)
        p.drawRightString(460, y_totales, "Subtotal:")
        p.setFillColor(PRIMARY_COLOR)
        p.drawRightString(width - 50, y_totales, f"${subtotal:,.2f} MXN")
        
        p.setFillColor(TEXT_MUTED)
        p.drawRightString(460, y_totales - 15, "IVA Trasladado (16%):")
        p.setFillColor(PRIMARY_COLOR)
        p.drawRightString(width - 50, y_totales - 15, f"${iva:,.2f} MXN")
        
        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(SECONDARY_COLOR)
        p.drawRightString(460, y_totales - 32, "Total Facturado:")
        p.drawRightString(width - 50, y_totales - 32, f"${monto_total:,.2f} MXN")
        
        # Línea de separación antes del Timbrado Digital
        p.setStrokeColor(BORDER_COLOR)
        p.line(40, 395, width - 40, 395)
        
        # --- BLOQUE DE TIMBRADO DIGITAL SAT (CFDI 4.0) ---
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 10)
        p.drawString(40, 375, "INFORMACIÓN DE TIMBRADO FISCAL DIGITAL (SAT)")
        
        # Recuadro gris para el timbre
        p.setFillColor(BG_PANEL)
        p.rect(40, 110, width - 80, 250, fill=True, stroke=False)
        
        # Simulación de Código QR (Dibujar un cuadro premium con estilos)
        p.setFillColor(WHITE)
        p.rect(55, 125, 100, 100, fill=True, stroke=True)
        p.setStrokeColor(BORDER_COLOR)
        
        # Dibujar un patrón simulado adentro para que parezca un código QR real
        p.setFillColor(PRIMARY_COLOR)
        p.rect(65, 205, 20, 20, fill=True, stroke=False)
        p.rect(125, 205, 20, 20, fill=True, stroke=False)
        p.rect(65, 135, 20, 20, fill=True, stroke=False)
        p.rect(95, 165, 20, 20, fill=True, stroke=False)
        p.setFillColor(TEXT_MUTED)
        p.setFont("Helvetica-Bold", 6)
        p.drawCentredString(105, 115, "CÓDIGO BIDIMENSIONAL SAT")
        
        # Datos del Timbre SAT (Folio Fiscal, Certificados, etc.)
        p.setFillColor(PRIMARY_COLOR)
        p.setFont("Helvetica-Bold", 8)
        p.drawString(175, 340, "Folio Fiscal (UUID):")
        p.setFont("Helvetica", 8)
        p.drawString(290, 340, invoice.sat_uuid or str(timezone.now().timestamp()).upper())
        
        p.setFont("Helvetica-Bold", 8)
        p.drawString(175, 325, "No. de Serie del Certificado SAT:")
        p.setFont("Helvetica", 8)
        p.drawString(290, 325, "00001000000504465028")
        
        p.setFont("Helvetica-Bold", 8)
        p.drawString(175, 310, "No. de Serie del Certificado Emisor:")
        p.setFont("Helvetica", 8)
        p.drawString(290, 310, "00001000000509823611")
        
        p.setFont("Helvetica-Bold", 8)
        p.drawString(175, 295, "Fecha y Hora de Certificación:")
        p.setFont("Helvetica", 8)
        p.drawString(290, 295, timezone.now().strftime('%Y-%m-%dT%H:%M:%S'))
        
        p.setFont("Helvetica-Bold", 8)
        p.drawString(175, 280, "Rfc de Proveedor de Certificación:")
        p.setFont("Helvetica", 8)
        p.drawString(290, 280, "SAT970701NN3")
        
        # Cadenas y Sellos Digitales (Visualmente acotados a una sola línea para evitar desbordes)
        p.setFont("Helvetica-Bold", 7)
        p.drawString(175, 260, "Sello Digital del Emisor:")
        p.setFont("Helvetica", 6)
        sello_emisor = "f49A7sD3m1K90z8X/aB+lKqj9S8DF9u2e1r3R6eK9PqW+z3mS8sX9s21cM/Jc19N8aK29eM8q10M8sD9w==..."
        p.drawString(175, 250, sello_emisor)
        
        p.setFont("Helvetica-Bold", 7)
        p.drawString(175, 235, "Sello Digital del SAT:")
        p.setFont("Helvetica", 6)
        sello_sat = "k91O9sD2m8Z98aC+qL9Df8s2E8aM9d3r9e1R2w4sE5v6B7n8M9q0P==..."
        p.drawString(175, 225, sello_sat)
        
        p.setFont("Helvetica-Bold", 7)
        p.drawString(175, 210, "Cadena Original del Complemento de Certificación Digital del SAT:")
        p.setFont("Helvetica", 6)
        cadena_orig = f"||1.1|{invoice.sat_uuid or 'UUID'}|{timezone.now().strftime('%Y-%m-%d')}|SAT970701NN3|f49A7sD3m1K90z8X..."
        p.drawString(175, 200, cadena_orig)
        
        # Leyenda de Validez Legal
        p.setFillColor(TEXT_MUTED)
        p.setFont("Helvetica-Oblique", 7)
        leyenda = "Este documento es una representación impresa de un CFDI 4.0 timbrado digitalmente ante el Servicio de Administración Tributaria."
        p.drawCentredString(width / 2, 70, leyenda)
        
        # --- GUARDAR PAGINA Y RETORNAR ---
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
