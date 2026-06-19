"""
main.py
Backend de Fila Virtual Pinto V3.

Cambios respecto a tu prueba inicial:
1. Las rutas /ingresar y /atender ahora reciben JSON (con Pydantic) en vez
   de query params, para que un formulario web pueda usarlas fácilmente.
2. La fila ya no vive en una lista de Python (se perdía al reiniciar el
   servidor); ahora vive en PostgreSQL (ver database.py), así sobrevive a
   reinicios, apagones y al "sueño" del servicio gratuito en Render
   (algo que SQLite no podría hacer ahí, por su almacenamiento efímero).
3. Lógica de "posición 2": cuando alguien queda en la posición 2 de la
   fila (es decir, le queda 1 persona antes de él), se le envía un SMS
   de aviso. Si Twilio falla (ej: trial con número no verificado), el
   servidor NO se cae: solo registra el error y sigue funcionando.
4. CORS habilitado para que el frontend (HTML/JS) pueda llamar a esta
   API sin bloqueos del navegador, sin importar desde dónde se sirva.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

import database

# --- CARGA DE CONFIGURACIÓN (.env) ---
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

POSICION_ALERTA = 2  # posición en la fila que dispara el aviso de "ya casi"


# --- CICLO DE VIDA DE LA APP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta UNA vez al arrancar el servidor: crea la tabla si no existe.
    database.inicializar_db()
    yield
    # (Aquí podríamos cerrar conexiones si las tuviéramos abiertas globalmente)


app = FastAPI(title="Fila Virtual Pinto V3", lifespan=lifespan)

# --- CORS ---
# Permite que páginas HTML servidas desde otro origen (file://, ngrok, etc.)
# puedan hacer fetch() a esta API. Para un prototipo lo dejamos abierto (*);
# en producción real conviene restringirlo a tu dominio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- MODELOS (definen qué forma debe tener el JSON que llega) ---
class NuevaPersona(BaseModel):
    nombre: str
    telefono: str  # formato esperado: +56912345678 (con código de país)


# --- FUNCIÓN AUXILIAR: ENVÍO DE SMS SEGURO ---
def enviar_sms(telefono_destino: str, cuerpo: str) -> dict:
    """
    Intenta enviar un SMS vía Twilio. Si algo falla (credenciales,
    número no verificado en modo trial, formato inválido, etc.),
    no lanza una excepción que rompa la API: devuelve un diccionario
    indicando éxito o fracaso, y el detalle del error si lo hubo.
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        return {"enviado": False, "detalle": "Credenciales de Twilio no configuradas"}

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=cuerpo,
            from_=TWILIO_PHONE_NUMBER,
            to=telefono_destino
        )
        return {"enviado": True, "sid": message.sid}
    except TwilioRestException as e:
        # Error específico de Twilio (ej: número no verificado en trial)
        print(f"[Twilio] Error enviando SMS a {telefono_destino}: {e}")
        return {"enviado": False, "detalle": str(e)}
    except Exception as e:
        # Cualquier otro error inesperado (red, formato, etc.)
        print(f"[Twilio] Error inesperado enviando SMS: {e}")
        return {"enviado": False, "detalle": str(e)}


# --- RUTA RAÍZ ---
@app.get("/")
def home():
    return {"mensaje": "Servidor Fila Virtual V3 operativo"}


# --- RUTA DE PRUEBA SMS (se mantiene igual, útil para probar Twilio aislado) ---
@app.post("/test-sms")
def probar_sms(telefono_destino: str):
    resultado = enviar_sms(
        telefono_destino,
        "¡Prueba de funcionamiento exitosa desde Fila Virtual!"
    )
    return resultado


# --- VER ESTADO DE LA FILA ---
@app.get("/estado")
def ver_estado_fila():
    fila = database.obtener_fila()
    return {"total_esperando": len(fila), "fila": fila}


# --- INGRESAR PERSONA (ahora recibe JSON) ---
@app.post("/ingresar")
def ingresar_persona(persona: NuevaPersona):
    nuevo_id = database.agregar_persona(persona.nombre, persona.telefono)

    # Calculamos en qué posición quedó esta persona dentro de la fila actual.
    fila_actual = database.obtener_fila()
    posiciones = {p["id"]: idx + 1 for idx, p in enumerate(fila_actual)}
    posicion = posiciones.get(nuevo_id, len(fila_actual))

    return {
        "mensaje": f"{persona.nombre} agregado exitosamente.",
        "id": nuevo_id,
        "posicion": posicion
    }


# --- ATENDER PERSONA (FIFO) ---
@app.post("/atender")
def atender_persona():
    atendido = database.atender_primero()

    if atendido is None:
        raise HTTPException(status_code=400, detail="La fila está vacía.")

    fila_restante = database.obtener_fila()

    # --- LÓGICA DE POSICIÓN 2 (la de tu Fase 1, ahora aplicada a toda la fila) ---
    # Después de atender, revisamos quién quedó en la posición 2.
    # Esa persona ya tiene solo 1 persona por delante: le avisamos.
    alerta_info = None
    if len(fila_restante) >= POSICION_ALERTA:
        persona_en_alerta = fila_restante[POSICION_ALERTA - 1]  # índice 0 = posición 1
        print(f"Alerta: Enviar SMS a {persona_en_alerta['telefono']}")

        resultado_sms = enviar_sms(
            persona_en_alerta["telefono"],
            f"Hola {persona_en_alerta['nombre']}, ¡ya casi es tu turno! "
            f"Quedan 1.5 persona(s) antes de ti."
        )
        alerta_info = {
            "nombre": persona_en_alerta["nombre"],
            "telefono": persona_en_alerta["telefono"],
            "sms": resultado_sms
        }

    return {
        "atendido": atendido["nombre"],
        "quedan_en_fila": len(fila_restante),
        "alerta_posicion_2": alerta_info
    }
