import uuid
from django.utils import timezone

class SatBillingService:
    @staticmethod
    def generate_mock_cfdi(invoice):
        """
        Simula el timbrado de una factura ante el SAT (CFDI 4.0) utilizando Sandbox.
        Genera el Folio Fiscal (UUID) y devuelve los metadatos de simulación.
        """
        # Generar un UUID de timbrado oficial si la factura no tiene uno
        fiscal_uuid = invoice.sat_uuid or str(uuid.uuid4()).upper()
        
        # Estructura básica de un comprobante CFDI 4.0 simulado
        cfdi_metadata = {
            'uuid': fiscal_uuid,
            'version': '4.0',
            'fecha_timbrado': timezone.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'no_certificado_sat': '00001000000504465028',
            'rfc_prov_certif': 'SAT970701NN3', # RFC oficial de pruebas del SAT
            'subtotal': float(invoice.monto) / 1.16,
            'iva': float(invoice.monto) - (float(invoice.monto) / 1.16),
            'total': float(invoice.monto),
            'forma_pago': '03' if invoice.stripe_payment_intent else '03', # 03 es Transferencia electrónica, 04 es Tarjeta
            'metodo_pago': 'PUE' # Pago en una sola exhibición
        }
        
        # Guardar en la factura si no estaba timbrada
        if not invoice.sat_uuid:
            invoice.sat_uuid = fiscal_uuid
            invoice.save()
            
        return cfdi_metadata

    @staticmethod
    def get_xml_mockup(invoice):
        """
        Devuelve una cadena XML representativa de una factura CFDI 4.0 timbrada.
        """
        meta = SatBillingService.generate_mock_cfdi(invoice)
        xml_string = f"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0" Serie="A" Folio="{invoice.id}" Fecha="{meta['fecha_timbrado']}" SubTotal="{meta['subtotal']:.2f}" Moneda="MXN" Total="{meta['total']:.2f}" TipoDeComprobante="I" Exportacion="01" MetodoPago="PUE" LugarExpedicion="06000">
    <cfdi:Emisor Rfc="ISP990101AAA" Nombre="INTERNET SERVICE PROVIDER S.A." RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="{invoice.cliente.rfc}" Nombre="{invoice.cliente.razon_social}" DomicilioFiscalReceptor="06000" RegimenFiscalReceptor="605" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="81112101" Cantidad="1" ClaveUnidad="E48" Unidad="Servicio" Descripcion="Mensualidad Internet Banda Ancha - Plan {invoice.cliente.plan.nombre} - Periodo {invoice.periodo_facturacion}" ValorUnitario="{meta['subtotal']:.2f}" Importe="{meta['subtotal']:.2f}" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="{meta['subtotal']:.2f}" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="{meta['iva']:.2f}"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" Version="1.1" UUID="{meta['uuid']}" FechaTimbrado="{meta['fecha_timbrado']}" RfcProvCertif="SAT970701NN3" NoCertificadoSAT="00001000000504465028"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""
        return xml_string
