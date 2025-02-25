#!/usr/bin/env python 
# -*- coding: utf-8 -*-

import logging
import pymysql
import sys
import os
import re
import pandas as pd

# Configura logging básico
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DatabaseConnection:
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
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Conexión a la base de datos cerrada")

def clean_dni(dni):
    """Limpia y normaliza un DNI."""
    if dni is None:
        return ''
    dni = str(dni).strip()
    dni = re.sub(r'[^a-zA-Z0-9]', '', dni)
    return dni.upper()

def get_all_dnis_from_db(db):
    """Obtiene todos los DNIs de la tabla persona."""
    logger.info("Obteniendo todos los DNIs de la base de datos...")
    db.cursor.execute("SELECT id, dni FROM persona")
    results = db.cursor.fetchall()
    dnis_map = {row['id']: clean_dni(row['dni']) for row in results}
    id_by_dni = {clean_dni(row['dni']): row['id'] for row in results}
    dnis = sorted(list({clean_dni(row['dni']) for row in results if clean_dni(row['dni'])}))
    logger.info(f"Se encontraron {len(dnis)} DNIs únicos en la tabla persona")
    return dnis, dnis_map, id_by_dni

def get_inscribed_dnis(db, escapada_id):
    """Obtiene los DNIs de las personas inscritas en la escapada especificada."""
    logger.info(f"Obteniendo DNIs inscritos en la escapada {escapada_id}...")
    query = """
    SELECT p.id, p.dni 
    FROM persona p
    JOIN inscripcion i ON p.id = i.persona_id
    WHERE i.escapada_id = %s
    """
    db.cursor.execute(query, (escapada_id,))
    results = db.cursor.fetchall()
    dnis = sorted(list({clean_dni(row['dni']) for row in results if clean_dni(row['dni'])}))
    logger.info(f"Se encontraron {len(dnis)} DNIs inscritos en la escapada {escapada_id}")
    return dnis

def clean_value(val):
    """Limpia un valor para la base de datos."""
    if pd.isna(val) or val == '':
        return None
    return val.strip() if isinstance(val, str) else val

def convert_to_float(value):
    """Convierte un valor a float, manejando varios formatos."""
    if value is None or pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = re.sub(r'[^\d.,]', '', value).replace(',', '.')
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0

def save_dnis_to_file(dnis, filename):
    """Guarda la lista de DNIs en un archivo Python."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Lista de DNIs a inscribir en la escapada\n\n")
        f.write("dnis = [\n")
        for dni in dnis:
            f.write(f'    "{dni}",\n')
        f.write("]\n")
    logger.info(f"Lista de {len(dnis)} DNIs guardada en {filename}")
    return filename

def read_csv_data(csv_path):
    """Lee el CSV y obtiene la información necesaria para las inscripciones."""
    logger.info(f"Leyendo datos del CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path, dtype=str)
        logger.info(f"CSV leído correctamente. Dimensiones: {df.shape}")
        logger.info(f"Columnas disponibles en el CSV: {list(df.columns)}")
        # Mapeo de columnas del CSV a campos de la tabla inscripcion
        column_mapping = {
            'A pagar': 'a_pagar',
            'Pagado': 'pagado',
            'Pendiente': 'pendiente',
            'Alojamiento': 'tipo_alojamiento_deseado',
            '¿Cuántos miembros de la familia sois?': 'num_familiares'
        }
        for csv_col in column_mapping.keys():
            if csv_col not in df.columns:
                logger.warning(f"Columna '{csv_col}' no encontrada en el CSV")
        dni_column = "dni"  # Según tu CSV actual
        if dni_column not in df.columns:
            logger.error(f"Columna de DNI '{dni_column}' no encontrada en el CSV")
            raise ValueError(f"Columna de DNI '{dni_column}' no encontrada en el CSV")
        df['dni_clean'] = df[dni_column].apply(lambda x: clean_dni(x) if not pd.isna(x) else '')
        data_by_dni = {}
        for _, row in df.iterrows():
            dni = row['dni_clean']
            if not dni:
                continue
            data = {}
            for csv_col, db_field in column_mapping.items():
                if csv_col in df.columns:
                    value = clean_value(row[csv_col])
                    if db_field in ['a_pagar', 'pagado', 'pendiente']:
                        data[db_field] = convert_to_float(value)
                    else:
                        data[db_field] = value
            data_by_dni[dni] = data
        logger.info(f"Se procesaron datos para {len(data_by_dni)} DNIs desde el CSV")
        return data_by_dni
    except Exception as e:
        logger.error(f"Error al leer datos desde CSV: {str(e)}")
        raise

def write_sql_insert_statements(dnis, id_by_dni, csv_data, escapada_id, filename):
    """
    Crea un archivo SQL con una única instrucción INSERT para inscribir a todas las personas
    en la escapada. Usa el DNI como persona_id en caso de que no exista en la BD.
    """
    insert_values = []
    for dni in dnis:
        # Se usa el DNI directamente si no está en id_by_dni
        persona_id = id_by_dni.get(dni, dni)
        inscription_data = csv_data.get(dni, {})
        a_pagar = inscription_data.get('a_pagar', 0)
        pagado = inscription_data.get('pagado', 0)
        pendiente = inscription_data.get('pendiente', 0)
        tipo_alojamiento = inscription_data.get('tipo_alojamiento_deseado', None)
        num_familiares = inscription_data.get('num_familiares', None)
        tipo_alojamiento_sql = 'NULL' if tipo_alojamiento is None else f"'{tipo_alojamiento}'"
        num_familiares_sql = 'NULL' if num_familiares is None else f"'{num_familiares}'"
        importe_pendiente = pendiente
        insert_values.append(
            f"('{persona_id}', {escapada_id}, NOW(), {a_pagar}, {pagado}, {pendiente}, {importe_pendiente}, {tipo_alojamiento_sql}, {num_familiares_sql}, false)"
        )
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"-- Script SQL para inscribir personas en la escapada {escapada_id}\n\n")
        f.write("INSERT INTO inscripcion (persona_id, escapada_id, fecha_inscripcion, a_pagar, pagado, pendiente, importe_pendiente, tipo_alojamiento_deseado, num_familiares, checkin_completado)\nVALUES\n")
        f.write(",\n".join(insert_values))
        f.write(";\n")
    logger.info(f"Script SQL para inscribir {len(insert_values)} personas guardado en {filename}")
    return filename

def write_sql_insert_personas(csv_path, filename):
    """
    Lee el CSV y genera un script SQL con un único INSERT para insertar cada persona en la tabla persona.
    Se espera que el CSV tenga las columnas:
      - "dni"
      - "Nombre"
      - "Apellidos"
      - "Teléfono"
      - "Sexo"
      - "Correo"
      - "Prefijo"
    """
    logger.info(f"Leyendo datos del CSV para generar INSERT de personas: {csv_path}")
    try:
        df = pd.read_csv(csv_path, dtype=str)
        required_columns = [
            "dni",
            "Nombre",
            "Apellidos",
            "Teléfono",
            "Sexo",
            "Correo",
            "Prefijo"
        ]
        for col in required_columns:
            if col not in df.columns:
                logger.error(f"Columna requerida '{col}' no encontrada en el CSV")
                raise ValueError(f"Columna requerida '{col}' no encontrada en el CSV")
        df['dni_clean'] = df["dni"].apply(lambda x: clean_dni(x))
        df['Nombre'] = df["Nombre"].apply(lambda x: clean_value(x) or '')
        df['Apellidos'] = df["Apellidos"].apply(lambda x: clean_value(x) or '')
        df['Teléfono'] = df["Teléfono"].apply(lambda x: clean_value(x) or '')
        df['Sexo'] = df["Sexo"].apply(lambda x: clean_value(x) or '')
        df['Correo'] = df["Correo"].apply(lambda x: clean_value(x) or '')
        df['Prefijo'] = df["Prefijo"].apply(lambda x: clean_value(x) or '')
        df = df[df['dni_clean'] != '']
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("-- Script SQL para insertar personas en la tabla persona\n\n")
            f.write("INSERT INTO persona (id, dni, nombre, apellidos, telefono, sexo, correo, prefijo)\nVALUES\n")
            values = []
            for _, row in df.iterrows():
                id_val = row['dni_clean']
                dni_val = row['dni_clean']
                nombre_val = row['Nombre'].replace("'", "''")
                apellidos_val = row['Apellidos'].replace("'", "''")
                telefono_val = row['Teléfono'].replace("'", "''")
                sexo_val = row['Sexo'].replace("'", "''")
                correo_val = row['Correo'].replace("'", "''")
                prefijo_val = row['Prefijo'].replace("'", "''")
                values.append(
                    f"('{id_val}', '{dni_val}', '{nombre_val}', '{apellidos_val}', '{telefono_val}', '{sexo_val}', '{correo_val}', '{prefijo_val}')"
                )
            f.write(",\n".join(values))
            f.write(";\n")
        logger.info(f"Script SQL para insertar {len(values)} personas guardado en {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error al generar el INSERT para personas: {str(e)}")
        raise

def main():
    # Configuración de la base de datos
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',
        'db': 'pam_db'
    }
    
    # Ruta al archivo CSV
    csv_path = "inscripciones.csv"
    
    # ID de la escapada a verificar
    escapada_id = 1
    
    try:
        # Leer datos del CSV para inscripciones (se usa "dni" como columna)
        csv_data = read_csv_data(csv_path)
        # DNIs que aparecen en el CSV
        csv_dnis = set(csv_data.keys())
        
        with DatabaseConnection(db_config) as db:
            all_dnis, dnis_map, id_by_dni = get_all_dnis_from_db(db)
            inscribed_dnis = set(get_inscribed_dnis(db, escapada_id))
            
            # DNIs a inscribir: los que están en el CSV pero no inscritos en la escapada
            not_inscribed_dnis = sorted(list(csv_dnis - inscribed_dnis))
            
            output_file = save_dnis_to_file(not_inscribed_dnis, f"dnis_no_inscritos_escapada_{escapada_id}.py")
            sql_file = write_sql_insert_statements(not_inscribed_dnis, id_by_dni, csv_data, escapada_id, f"inscribir_escapada_{escapada_id}.sql")
            personas_sql_file = write_sql_insert_personas(csv_path, "insert_personas.sql")
            
            print("\n=== RESUMEN ===")
            print(f"Total de DNIs en la base de datos: {len(all_dnis)}")
            print(f"DNIs inscritos en la escapada {escapada_id}: {len(inscribed_dnis)}")
            print(f"DNIs en el CSV: {len(csv_dnis)}")
            print(f"DNIs a inscribir (del CSV, no inscritos): {len(not_inscribed_dnis)}")
            print(f"\nResultados guardados en {output_file}")
            print(f"Script SQL para inscripciones guardado en {sql_file}")
            print(f"Script SQL para insertar personas guardado en {personas_sql_file}")
            
            if not_inscribed_dnis:
                print("\nEjemplos de DNIs a inscribir:")
                for dni in not_inscribed_dnis[:10]:
                    print(f"  - {dni}")
                if len(not_inscribed_dnis) > 10:
                    print(f"  - ... y {len(not_inscribed_dnis) - 10} más")
            
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
