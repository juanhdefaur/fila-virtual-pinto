# Guía: Subir Fila Virtual a GitHub y desplegar en Render

## Parte 1: Subir el proyecto a GitHub

### 1.1 Reemplaza los archivos en tu carpeta Fasto

Descarga estos 3 archivos actualizados y reemplázalos en tu carpeta
`C:\Users\jhdef\OneDrive\Escritorio\Fasto`:
- `database.py` (migrado a PostgreSQL)
- `main.py` (docstring actualizada, las rutas no cambiaron)
- `requirements.txt` (agregado `psycopg2-binary`)

Y agrega este archivo nuevo a la misma carpeta:
- `Procfile` (le dice a Render cómo arrancar tu servidor)

**Importante**: NO subas tu archivo `.env` a GitHub. Ya está en `.gitignore`,
pero verifica que así sea.

### 1.2 Crear cuenta y repositorio en GitHub

1. Ve a https://github.com y crea una cuenta si no tienes.
2. Haz clic en el botón verde **"New"** (o el ícono "+" arriba a la derecha
   → "New repository").
3. Nombra el repositorio, por ejemplo: `fila-virtual-pinto`.
4. Déjalo en **Private** si prefieres que no sea público (recomendado,
   ya que aunque el `.env` no se sube, es buena práctica para un proyecto
   con lógica de negocio real).
5. NO marques "Add a README" (ya tienes uno).
6. Haz clic en **"Create repository"**.

### 1.3 Subir tu código desde PowerShell

GitHub te mostrará una página con comandos. En tu terminal, parado en la
carpeta `Fasto`, ejecuta (necesitas tener Git instalado — si `git` no se
reconoce como comando, instálalo desde https://git-scm.com/download/win
y reinicia la terminal, igual que hicimos con Python):

```powershell
cd C:\Users\jhdef\OneDrive\Escritorio\Fasto
git init
git add .
git commit -m "Primera version: fila virtual con FastAPI, Postgres y Twilio"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/fila-virtual-pinto.git
git push -u origin main
```

Reemplaza `TU_USUARIO` por tu nombre de usuario real de GitHub. Te pedirá
iniciar sesión (puede abrir una ventana del navegador para autenticarte).

## Parte 2: Crear la base de datos PostgreSQL en Render

1. Ve a https://render.com y crea una cuenta (puedes usar tu cuenta de
   GitHub para registrarte, es más rápido).
2. En el Dashboard, haz clic en **"New +"** → **"PostgreSQL"**.
3. Dale un nombre, ej: `fila-virtual-db`.
4. Región: elige la más cercana a Chile (probablemente "Oregon" u otra
   disponible en EE.UU., Render no tiene región en Sudamérica todavía).
5. Plan: selecciona **Free**.
6. Haz clic en **"Create Database"**.
7. Espera unos segundos a que se aprovisione. Cuando esté lista, en la
   página de la base verás una sección **"Connections"** con un campo
   llamado **"Internal Database URL"** — cópialo, lo necesitarás en el
   siguiente paso (lo usaremos como `DATABASE_URL`).

> Recuerda: esta base gratuita expira 30 días después de creada. Cuando
> expire, simplemente crea una nueva siguiendo estos mismos pasos y
> actualiza la variable de entorno en tu Web Service (Parte 3, paso 3.5).

## Parte 3: Desplegar el backend (Web Service) en Render

1. En el Dashboard de Render, haz clic en **"New +"** → **"Web Service"**.
2. Conecta tu cuenta de GitHub si no lo has hecho, y selecciona el
   repositorio `fila-virtual-pinto`.
3. Configura:
   - **Name**: `fila-virtual-pinto` (o el que prefieras, será parte de tu URL)
   - **Region**: la misma que usaste para la base de datos
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
     (esto hace lo mismo que el Procfile; puedes usar cualquiera de los dos)
   - **Plan**: `Free`
4. Antes de hacer clic en "Create Web Service", bájale hasta
   **"Environment Variables"** y agrega estas 4 variables:
   - `DATABASE_URL` → pega el "Internal Database URL" que copiaste en la
     Parte 2
   - `TWILIO_ACCOUNT_SID` → tu Account SID de Twilio
   - `TWILIO_AUTH_TOKEN` → tu Auth Token de Twilio
   - `TWILIO_PHONE_NUMBER` → tu número de Twilio (con +)
5. Haz clic en **"Create Web Service"**.
6. Render comenzará a construir y desplegar. Esto tarda 2-5 minutos la
   primera vez. Puedes ver el progreso en la pestaña "Logs".
7. Cuando termine, verás un mensaje verde "Live" y una URL pública arriba,
   tipo: `https://fila-virtual-pinto.onrender.com`

### 3.5 Verificar que funciona

Abre en tu navegador: `https://fila-virtual-pinto.onrender.com`
Deberías ver: `{"mensaje":"Servidor Fila Virtual V3 operativo"}`

Si ves un error 500, revisa la pestaña "Logs" en Render — generalmente es
porque alguna variable de entorno está mal copiada (revisa que no haya
espacios extra al copiar el `DATABASE_URL`).

## Parte 4: Conectar tus archivos HTML a la URL de Render

Edita `cliente.html` y `cajero.html`, busca esta línea en cada uno:

```js
const API_URL = "http://localhost:8000";
```

Cámbiala por tu URL real de Render:

```js
const API_URL = "https://fila-virtual-pinto.onrender.com";
```

Guarda ambos archivos. Ahora puedes abrirlos localmente (doble clic) y
ya van a hablar con tu servidor en la nube, no con tu PC. También puedes
subir estos dos HTML a cualquier hosting estático gratuito (GitHub Pages,
Netlify, Vercel) para que tengan su propia URL pública y generar el QR
apuntando a `cliente.html`.

## Nota sobre el "sueño" del servicio gratuito

Los Web Services gratuitos de Render se duermen tras ~15 minutos sin
tráfico. La primera petición después de eso tarda 30-50 segundos en
responder mientras el servicio "despierta". Esto es normal y aceptable
para un prototipo; si en algún momento necesitas que esté siempre
despierto al instante, eso requiere pasar a un plan pago.
