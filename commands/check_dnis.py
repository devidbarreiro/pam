import pymysql
import pandas as pd
import logging
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def clean_dni(dni):
    """
    Limpia y normaliza un DNI: quita espacios y puntos y lo convierte a mayúsculas.
    """
    if not dni:
        return ''
    return str(dni).strip().replace('.', '').replace(' ', '').upper()


def get_csv_dnis(csv_path):
    """
    Lee el CSV y obtiene la lista única de DNIs (limpiados) contenidos en la columna 'dni'.
    """
    try:
        df = pd.read_csv(csv_path, parse_dates=['fecha de nacimiento'])
        if 'dni' not in df.columns:
            raise ValueError("Columna 'dni' no encontrada en el CSV")
        # Limpiar y obtener DNIs únicos
        df['dni'] = df['dni'].apply(clean_dni)
        dnis = df['dni'].dropna().unique().tolist()
        dnis = [dni for dni in dnis if dni]  # Eliminar valores vacíos
        logger.info(f"DNIs únicos encontrados en CSV: {len(dnis)}")
        return df, dnis
    except Exception as e:
        logger.error(f"Error al leer el CSV: {str(e)}")
        raise


def check_dnis_in_db(dnis, db_config):
    """
    Verifica qué DNIs existen en la base de datos.
    Retorna un conjunto con los DNIs encontrados y una lista de los que no se encontraron.
    """
    connection = pymysql.connect(
        host=db_config.get('host', 'localhost'),
        user=db_config.get('user'),
        password=db_config.get('password'),
        db=db_config.get('db'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with connection.cursor() as cursor:
            placeholders = ','.join(['%s'] * len(dnis))
            query = f"SELECT dni FROM persona WHERE dni IN ({placeholders})"
            cursor.execute(query, dnis)
            found = {row['dni'] for row in cursor.fetchall()}
            not_found = [dni for dni in dnis if dni not in found]
            logger.info(f"DNIs encontrados en DB: {len(found)}")
            logger.info(f"DNIs no encontrados en DB: {len(not_found)}")
            return found, not_found
    finally:
        connection.close()


def insert_person_and_inscription(db, row_data, escapada_id=1):
    """
    Inserta una nueva persona y su inscripción en la base de datos.
    Se asume que la columna que referencia a la persona en la inscripción es 'persona_id'.
    """
    dni = clean_dni(row_data['dni'])
    logger.info(f"Insertando e inscribiendo DNI: {dni}")
    try:
        # Manejar la fecha de nacimiento
        fecha = row_data.get('fecha de nacimiento')
        if pd.notna(fecha):
            if isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%d/%m/%Y').strftime('%Y-%m-%d')
            else:
                fecha = fecha.strftime('%Y-%m-%d')
        else:
            fecha = None

        persona_data = {
            'id': dni,
            'dni': dni,
            'nombre': row_data.get('nombre', '').strip(),
            'apellidos': row_data.get('apellidos', '').strip(),
            'fecha_nacimiento': fecha,
            'correo': row_data.get('correo', '').strip(),
            'estado': row_data.get('estado', '').strip(),
            'sexo': row_data.get('sexo', '').strip(),
            'prefijo': row_data.get('prefijo', '').strip(),
            'telefono': row_data.get('teléfono', '').strip(),
            'es_pringado': 1 if str(row_data.get('¿eres pringado?', '')).lower() == 'sí' else 0,
            'anio_pringado': row_data.get('anio_pringado')
        }

        # Validar campos requeridos básicos
        for field in ['dni', 'nombre']:
            if not persona_data[field]:
                raise ValueError(f"El campo {field} es requerido y está vacío para DNI {dni}")

        logger.debug(f"Datos de persona a insertar: {persona_data}")

        insert_persona_sql = """
        INSERT INTO persona (id, dni, nombre, apellidos, fecha_nacimiento, correo, estado, 
                             sexo, prefijo, telefono, es_pringado, anio_pringado)
        VALUES (%(id)s, %(dni)s, %(nombre)s, %(apellidos)s, %(fecha_nacimiento)s, %(correo)s, %(estado)s, 
                %(sexo)s, %(prefijo)s, %(telefono)s, %(es_pringado)s, %(anio_pringado)s)
        """
        db.cursor.execute(insert_persona_sql, persona_data)
        logger.info(f"Persona insertada correctamente: {dni}")

        inscripcion_data = {
            'persona_id': dni,
            'escapada_id': escapada_id,
            'a_pagar': float(row_data.get('a pagar', 0) or 0),
            'pagado': float(row_data.get('pagado', 0) or 0),
            'pendiente': float(row_data.get('pendiente', 0) or 0)
        }
        logger.debug(f"Datos de inscripción a insertar: {inscripcion_data}")

        insert_inscripcion_sql = """
        INSERT INTO inscripcion (persona_id, escapada_id, a_pagar, pagado, pendiente)
        VALUES (%(persona_id)s, %(escapada_id)s, %(a_pagar)s, %(pagado)s, %(pendiente)s)
        """
        db.cursor.execute(insert_inscripcion_sql, inscripcion_data)
        logger.info(f"Inscripción insertada correctamente para DNI: {dni}")

    except Exception as e:
        logger.error(f"Error al insertar datos para DNI {dni}: {str(e)}", exc_info=True)
        raise


class DatabaseConnection:
    """
    Clase para manejar la conexión a la base de datos usando un contexto.
    """
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None

    def __enter__(self):
        logger.info("Iniciando conexión a la base de datos")
        try:
            self.conn = pymysql.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                db=self.config['db'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.conn.cursor()
            logger.info("Conexión establecida exitosamente")
            return self
        except Exception as e:
            logger.error(f"Error al conectar a la base de datos: {str(e)}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Error durante la transacción: {exc_type.__name__}: {str(exc_val)}")
            if self.conn:
                logger.info("Realizando rollback de la transacción")
                self.conn.rollback()
        else:
            if self.conn:
                logger.info("Commit de la transacción exitoso")
                self.conn.commit()
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Conexión a la base de datos cerrada")


def main():
    # Configuración de la base de datos
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',
        'db': 'pam_db'
    }
    csv_path = 'output.csv'

    try:
        logger.info(f"Leyendo DNIs y datos del archivo: {csv_path}")
        df, csv_dnis = get_csv_dnis(csv_path)
        logger.info("Verificando qué DNIs ya existen en la base de datos...")
        found_dnis, not_found = check_dnis_in_db(csv_dnis, db_config)

        # Mostrar resultados en consola
        print("\nDNIs encontrados en la base de datos:")
        for dni in sorted(found_dnis):
            print(f"  {dni}")

        print("\nDNIs NO encontrados en la base de datos (se insertarán):")
        for dni in sorted(not_found):
            print(f"  {dni}")

        # Proceder a insertar las personas (y sus inscripciones) que no se encuentren
        if not_found:
            logger.info("Insertando los DNIs no encontrados en la base de datos...")
            with DatabaseConnection(db_config) as db:
                for dni in not_found:
                    # Filtrar la fila del DataFrame que corresponda a este DNI
                    rows = df[df['dni'] == dni]
                    if len(rows) == 0:
                        logger.warning(f"DNI {dni} no se encontró en los datos del CSV (después de limpieza)")
                        continue
                    if len(rows) > 1:
                        logger.warning(f"DNI {dni} tiene múltiples entradas en el CSV; se usará la primera.")
                    row_data = rows.iloc[0]
                    try:
                        insert_person_and_inscription(db, row_data, escapada_id=1)
                        logger.info(f"Insertado e inscrito DNI {dni} correctamente")
                    except Exception as e:
                        logger.error(f"Error insertando DNI {dni}: {str(e)}", exc_info=True)
                        db.conn.rollback()
        else:
            logger.info("No hay nuevos DNIs para insertar.")

    except Exception as e:
        logger.error(f"Error fatal en el proceso: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logger.info("Iniciando script de inserción de personas e inscripciones")
    main()
    logger.info("Proceso completado exitosamente")
