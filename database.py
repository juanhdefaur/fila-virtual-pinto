"""
database.py
Maneja toda la conexión y operaciones con PostgreSQL (Render Postgres).

Migrado desde SQLite: en Render, los servicios web gratuitos tienen
almacenamiento efímero (un archivo .db local se borraría en cada
reinicio/sueño del servicio), así que usamos una base de datos
PostgreSQL administrada por Render, que sí persiste de verdad.

main.py se encarga de las RUTAS (web), database.py se encarga de los DATOS.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# Render inyecta automáticamente esta variable de entorno cuando conectas
# tu Web Service a una base Postgres dentro del mismo proyecto/dashboard.
# En local, la tomamos del archivo .env (ver main.py -> load_dotenv()).
DATABASE_URL = os.getenv("DATABASE_URL")


def inicializar_db():
    """
    Crea la tabla 'fila' si no existe todavía.
    Se llama una sola vez al arrancar el servidor (ver main.py).
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fila (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    telefono TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'Esperando',
                    fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)


@contextmanager
def get_conn():
    """
    Context manager para abrir y cerrar la conexión de forma segura.
    Así evitamos repetir try/finally en cada función y nos asegura
    que la conexión siempre se cierre, incluso si hay un error.

    Uso:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(...)
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def agregar_persona(nombre: str, telefono: str):
    """Inserta una nueva persona al final de la fila (estado: Esperando)."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fila (nombre, telefono, estado) VALUES (%s, %s, 'Esperando') RETURNING id",
                (nombre, telefono)
            )
            return cursor.fetchone()["id"]


def obtener_fila():
    """
    Devuelve todas las personas en estado 'Esperando', ordenadas por
    id ascendente (el primero en entrar es el primero en la lista -> FIFO).
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, telefono, estado, fecha_ingreso FROM fila "
                "WHERE estado = 'Esperando' ORDER BY id ASC"
            )
            return [dict(row) for row in cursor.fetchall()]


def atender_primero():
    """
    Toma a la primera persona en estado 'Esperando' (FIFO) y cambia
    su estado a 'Atendido'. No la borra, para mantener historial.
    Devuelve el diccionario de la persona atendida, o None si no había nadie.
    """
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, nombre, telefono FROM fila "
                "WHERE estado = 'Esperando' ORDER BY id ASC LIMIT 1"
            )
            row = cursor.fetchone()

            if row is None:
                return None

            cursor.execute(
                "UPDATE fila SET estado = 'Atendido' WHERE id = %s",
                (row["id"],)
            )
            return dict(row)


def contar_esperando():
    """Cuenta cuántas personas hay actualmente esperando."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as total FROM fila WHERE estado = 'Esperando'"
            )
            return cursor.fetchone()["total"]
