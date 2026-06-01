# Guía de Despliegue en la Nube (Producción) - FintechOS

Esta guía detalla los pasos necesarios para desplegar **FintechOS** en plataformas de nube modernas (como **Render** o **Railway**), conectar la base de datos de producción de **Supabase (PostgreSQL)** y configurar las pasarelas de pago y facturación en **Modo Real**.

---

## 1. Conexión a Base de Datos en Producción (Supabase)

Para conectar tu base de datos Supabase PostgreSQL:
1. Inicia sesión en [Supabase Console](https://supabase.com/).
2. Crea un nuevo proyecto o abre tu proyecto existente.
3. Ve a **Project Settings** -> **Database**.
4. En la sección **Connection string**, selecciona **URI** o toma los parámetros individuales:
   * **Host:** `db.tu-proyecto-supabase.supabase.co`
   * **Database Name:** `postgres`
   * **Port:** `5432`
   * **User:** `postgres`
   * **Password:** La contraseña que definiste al crear el proyecto en Supabase.

Estos datos se cargarán en las variables de entorno en el servidor de producción.

---

## 2. Configuración en la Nube (Render / Railway)

### A. Preparación del Código
Asegúrate de que los siguientes archivos estén en el repositorio de Git:
1. **`requirements.txt`**: Ya ha sido generado e incluye `gunicorn`, `psycopg2-binary`, `django-environ` y `stripe`.
2. **`Procfile`**: (Opcional, Render y Railway lo detectan, pero es buena práctica tenerlo). Crea un archivo llamado `Procfile` en la raíz del proyecto con la siguiente línea:
   ```text
   web: gunicorn fintech_core.wsgi --log-file -
   ```

### B. Creación del Servicio en la Nube
1. Conecta tu repositorio de GitHub a Render o Railway.
2. Crea un nuevo **Web Service**.
3. Selecciona el entorno de ejecución como **Python**.
4. Define el comando de inicio (Start Command):
   ```bash
   gunicorn fintech_core.wsgi:application
   ```

### C. Variables de Entorno (Environment Variables)
Agrega las siguientes variables en la configuración de tu servicio en Render/Railway:

| Nombre de Variable | Valor / Descripción |
| :--- | :--- |
| `DEBUG` | `False` (Crítico para seguridad en producción) |
| `SECRET_KEY` | Una cadena aleatoria larga y segura (ej. generada por Django) |
| `DB_NAME` | `postgres` (de Supabase) |
| `DB_USER` | `postgres` (de Supabase) |
| `DB_PASSWORD` | Tu contraseña de Supabase |
| `DB_HOST` | Host de base de datos de Supabase |
| `DB_PORT` | `5432` |
| `STRIPE_PUBLIC_KEY` | Tu clave pública de producción de Stripe (`pk_live_...`) |
| `STRIPE_SECRET_KEY` | Tu clave secreta de producción de Stripe (`sk_live_...`) |
| `FACTURAPI_API_KEY` | Clave API de producción de Facturapi para timbrado real ante el SAT |

---

## 3. Comandos Post-Despliegue (Build Steps)

En Render/Railway, configura tu **Build Command** para que corra el siguiente script de preparación:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Aplicar migraciones de base de datos a PostgreSQL
python manage.py migrate

# Recopilar archivos estáticos
python manage.py collectstatic --no-input
```

---

## 4. Configuración del Cron Job Mensual (Facturación)

Para automatizar el cobro recurrente el día 1 de cada mes en producción:

### Opción A: Render Cron Jobs
1. En Render, crea un nuevo servicio de tipo **Cron Job**.
2. Comando a ejecutar:
   ```bash
   python manage.py generate_monthly_invoices
   ```
3. Cron Schedule (Ejecutar el minuto 0 de la hora 0 del día 1 de cada mes):
   ```text
   0 0 1 * *
   ```

### Opción B: Railway Tasks
1. Añade un trigger cron en tu servicio de Railway con el comando `python manage.py generate_monthly_invoices` programado con la expresión cron `0 0 1 * *`.

---

## 5. Pasar a Modo Real (Verificación Live)

1. En el Dashboard de Stripe, cambia el switch superior a **Live Mode** y copia tus llaves correspondientes.
2. Registra un cliente de prueba real con **tu propia tarjeta de crédito** y asígnale un plan mínimo (ej. de $10 MXN).
3. Entra al portal de clientes, realiza el pago real de $10 pesos con tu tarjeta y verifica:
   * El dinero ingresa a tu cuenta bancaria de Stripe.
   * La factura se timbra y genera un folio fiscal UUID real del SAT.
   * El servicio de internet de tu cliente se activa de inmediato en el sistema.
