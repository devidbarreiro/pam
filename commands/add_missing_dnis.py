#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import logging
import pymysql
from datetime import datetime
import sys
import os
from logging.handlers import RotatingFileHandler
import pandas as pd
import numpy as np
import re

# Configura el sistema de logging
logger = None

def setup_logging():
    """
    Configura el sistema de logging con output a consola y archivo.
    """
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'process.log'),
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10*1024*1024,
        backupCount=5
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.handlers = []
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    return logger

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

# FUNCIONES DE UTILIDAD
def clean_dni(dni):
    """
    Limpia y normaliza un DNI para asegurar comparaciones consistentes.
    Maneja casos como espacios, guiones, puntos, y conversión a mayúsculas.
    """
    if dni is None:
        return ''
    
    # Convertir a string si no lo es
    dni = str(dni)
    
    # Eliminar espacios al inicio y final
    dni = dni.strip()
    
    # Eliminar caracteres no alfanuméricos (puntos, guiones, etc.)
    dni = re.sub(r'[^a-zA-Z0-9]', '', dni)
    
    # Convertir a mayúsculas
    dni = dni.upper()
    
    return dni

def clean_value(val):
    """
    Limpia un valor para la base de datos.
    """
    if pd.isna(val) or val == '':
        return None
    
    # Si es string, eliminar espacios en blanco al inicio y final
    if isinstance(val, str):
        val = val.strip()
        
    return val

# FUNCIONES DE VERIFICACIÓN Y OPERACIÓN CON LA BD
def get_dnis_from_db(db):
    """
    Obtiene todos los DNIs existentes en la base de datos.
    """
    logger.info("Obteniendo DNIs existentes en la base de datos")
    db.cursor.execute("SELECT dni FROM persona")
    results = db.cursor.fetchall()
    return {clean_dni(row['dni']) for row in results}

def get_inscribed_dnis_for_escapada(db, escapada_id):
    """
    Obtiene los DNIs de personas ya inscritas en la escapada específica.
    """
    logger.info(f"Obteniendo DNIs ya inscritos en la escapada {escapada_id}")
    query = """
    SELECT p.dni 
    FROM persona p
    JOIN inscripcion i ON p.id = i.persona_id
    WHERE i.escapada_id = %s
    """
    db.cursor.execute(query, (escapada_id,))
    results = db.cursor.fetchall()
    return {clean_dni(row['dni']) for row in results}

def find_dni_column(df):
    """
    Encuentra la columna que contiene los DNIs en el DataFrame.
    """
    # Verificar columnas específicas primero
    potential_names = [
        "DNI (si eres europeo) o Pasaporte",
        "DNI",
        "DNI/Pasaporte",
        "Documento",
        "Identificación"
    ]
    
    for name in potential_names:
        if name in df.columns:
            return name
    
    # Buscar columnas que puedan contener DNIs por nombre
    dni_columns = [col for col in df.columns if any(term in col.lower() for term in ['dni', 'pasaporte', 'documento', 'id'])]
    
    if dni_columns:
        return dni_columns[0]
    
    # Si no encontramos ninguna, intentar adivinar
    for col in df.columns:
        # Verificar si la columna contiene valores que parecen DNIs (alfanuméricos de 8-10 caracteres)
        sample = df[col].dropna().astype(str).str.replace('-', '').str.replace(' ', '')
        if len(sample) > 0 and sample.str.len().mean() >= 7 and sample.str.len().mean() <= 12:
            # Probablemente es una columna de DNI
            return col
    
    # Si todo falla, mostrar las columnas disponibles
    logger.warning(f"No se pudo identificar columna de DNI. Columnas disponibles: {list(df.columns)}")
    return None

def insert_person_and_inscription(db, row_data, dni_column, escapada_id=1):
    """
    Inserta una persona y su inscripción en la base de datos según el mapeo proporcionado.
    """
    # Mapeo entre columnas del CSV y campos de la base de datos
    persona_mapping = {
        'dni': dni_column,  # Usamos la columna detectada
        'nombre': 'nombre',
        'apellidos': 'apellidos',
        'fecha de nacimiento': 'fecha_nacimiento',
        'correo': 'correo',
        'estado': 'estado',
        'sexo': 'sexo',
        'prefijo': 'prefijo',
        'teléfono': 'telefono',
        '¿eres pringado?': 'es_pringado',
        'anio_pringado': 'anio_pringado'
    }
    
    inscripcion_mapping = {
        'a pagar': 'a_pagar',
        'pagado': 'pagado',
        'pendiente': 'pendiente',
        'alojamiento': 'tipo_alojamiento_deseado',
        'num_familiares': 'num_familiares'
    }
    
    # Obtener el DNI del registro
    dni_value = row_data.get(dni_column)
    if not dni_value:
        # Intentar buscar en otras columnas posibles
        for col in row_data.keys():
            if 'dni' in col.lower() or 'pasaporte' in col.lower() or 'documento' in col.lower():
                dni_value = row_data.get(col)
                if dni_value:
                    break
    
    if not dni_value:
        logger.warning(f"No se encontró DNI en el registro: {row_data}")
        for col, val in row_data.items():
            logger.debug(f"  {col}: {val}")
        raise ValueError("No se pudo encontrar el DNI en el registro")
    
    dni = clean_dni(dni_value)
    logger.info(f"Procesando inserción para DNI: {dni}")
    
    try:
        # Verificar si la persona ya existe
        db.cursor.execute("SELECT id FROM persona WHERE dni = %s", (dni,))
        result = db.cursor.fetchone()
        
        # Preparar datos de persona
        persona_data = {}
        for db_field, csv_field in persona_mapping.items():
            if csv_field in row_data:
                # Tratamiento especial para campos específicos
                if db_field == 'fecha_nacimiento':
                    fecha_raw = clean_value(row_data[csv_field])
                    if fecha_raw:
                        try:
                            if isinstance(fecha_raw, str):
                                # Intentar diferentes formatos de fecha
                                try:
                                    fecha_nacimiento = datetime.strptime(fecha_raw, '%d/%m/%Y').strftime('%Y-%m-%d')
                                except ValueError:
                                    try:
                                        fecha_nacimiento = datetime.strptime(fecha_raw, '%Y-%m-%d').strftime('%Y-%m-%d')
                                    except ValueError:
                                        try:
                                            fecha_nacimiento = datetime.strptime(fecha_raw, '%d-%m-%Y').strftime('%Y-%m-%d')
                                        except ValueError:
                                            logger.warning(f"No se pudo parsear la fecha: {fecha_raw}")
                                            fecha_nacimiento = None
                            else:
                                fecha_nacimiento = fecha_raw.strftime('%Y-%m-%d')
                                
                            if fecha_nacimiento:
                                persona_data[db_field] = fecha_nacimiento
                        except Exception as e:
                            logger.warning(f"Error al parsear fecha de nacimiento: {str(e)}")
                elif db_field == 'es_pringado':
                    es_pringado_val = clean_value(row_data[csv_field])
                    if es_pringado_val is not None:
                        if isinstance(es_pringado_val, bool):
                            persona_data[db_field] = 1 if es_pringado_val else 0
                        else:
                            es_pringado_str = str(es_pringado_val).lower()
                            persona_data[db_field] = 1 if es_pringado_str in ['sí', 'si', 'yes', 'true', '1', 'verdadero'] else 0
                else:
                    val = clean_value(row_data[csv_field])
                    if val is not None:
                        persona_data[db_field] = val
        
        # Siempre asegurarnos de que el DNI esté en los datos de persona
        persona_data['dni'] = dni
        
        # Si no hay resultado, insertar la persona
        if not result:
            # Verificar campos requeridos
            if 'nombre' not in persona_data or not persona_data.get('nombre'):
                persona_data['nombre'] = "Sin Nombre"  # Valor por defecto
            
            # Asignar ID y DNI
            persona_data['id'] = dni
            
            # Construir SQL dinámico
            fields = ', '.join(persona_data.keys())
            placeholders = ', '.join(['%s'] * len(persona_data))
            insert_persona_sql = f"INSERT INTO persona ({fields}) VALUES ({placeholders})"
            
            # Mostrar los datos que se van a insertar
            logger.debug(f"Datos de persona a insertar: {persona_data}")
            
            # Ejecutar la consulta
            db.cursor.execute(insert_persona_sql, list(persona_data.values()))
            logger.info(f"Persona insertada correctamente con ID: {dni} y DNI: {dni}")
            persona_id = dni
        else:
            persona_id = result['id']
            logger.info(f"La persona con DNI {dni} ya existe con ID: {persona_id}")
        
        # Verificar si ya existe una inscripción para esta persona en esta escapada
        db.cursor.execute("""
            SELECT COUNT(*) as count FROM inscripcion 
            WHERE persona_id = %s AND escapada_id = %s
        """, (persona_id, escapada_id))
        result = db.cursor.fetchone()
        
        if result and result['count'] > 0:
            logger.info(f"La persona con DNI {dni} ya está inscrita en la escapada {escapada_id}")
            return "already_inscribed"
        
        # Preparar datos de inscripción
        inscripcion_data = {
            'persona_id': persona_id,
            'escapada_id': escapada_id,
            'fecha_inscripcion': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'importe_pendiente': 0  # Campo requerido que faltaba
        }
        
        # Agregar campos mapeados si existen en el CSV
        for db_field, csv_field in inscripcion_mapping.items():
            if csv_field in row_data:
                val = clean_value(row_data[csv_field])
                if val is not None:
                    # Convertir valores numéricos para campos monetarios
                    if db_field in ['a_pagar', 'pagado', 'pendiente']:
                        try:
                            if isinstance(val, str):
                                # Eliminar posibles caracteres no numéricos (€, $, etc.)
                                val = re.sub(r'[^\d.,]', '', val)
                                # Reemplazar comas por puntos para decimal
                                val = val.replace(',', '.')
                            inscripcion_data[db_field] = float(val)
                        except (ValueError, TypeError):
                            logger.warning(f"No se pudo convertir el valor para {db_field}: {val}")
                            inscripcion_data[db_field] = 0
                    else:
                        inscripcion_data[db_field] = val
        
        # Calcular importe_pendiente si no se proporcionó
        if 'pendiente' in inscripcion_data:
            inscripcion_data['importe_pendiente'] = inscripcion_data['pendiente']
        elif 'a_pagar' in inscripcion_data and 'pagado' in inscripcion_data:
            inscripcion_data['importe_pendiente'] = inscripcion_data['a_pagar'] - inscripcion_data['pagado']
        
        # Asegurar que todos los campos monetarios tengan valores por defecto
        for field in ['a_pagar', 'pagado', 'pendiente', 'importe_pendiente']:
            if field not in inscripcion_data:
                inscripcion_data[field] = 0.0
        
        # Construir SQL dinámico para la inscripción
        fields = ', '.join(inscripcion_data.keys())
        placeholders = ', '.join(['%s'] * len(inscripcion_data))
        insert_inscripcion_sql = f"INSERT INTO inscripcion ({fields}) VALUES ({placeholders})"
        
        # Mostrar los datos que se van a insertar
        logger.debug(f"Datos de inscripción a insertar: {inscripcion_data}")
        
        # Ejecutar la consulta
        db.cursor.execute(insert_inscripcion_sql, list(inscripcion_data.values()))
        logger.info(f"Inscripción insertada correctamente para DNI: {dni} en escapada: {escapada_id}")
        
        return "inscribed"
        
    except Exception as e:
        logger.error(f"Error al insertar datos para DNI {dni}: {str(e)}", exc_info=True)
        raise

def read_csv_with_dnis_to_process(csv_path, dnis_to_process):
    """
    Lee el CSV y filtra por los DNIs que se deben procesar.
    Devuelve un DataFrame con solo las filas de los DNIs a procesar.
    """
    logger.info(f"Leyendo CSV: {csv_path}")
    
    try:
        # Leer el CSV con todas las precauciones posibles
        df = pd.read_csv(csv_path, encoding='utf-8', dtype=str)
        logger.info(f"CSV leído correctamente. Dimensiones: {df.shape}")
        
        # Mostrar las primeras filas y columnas para diagnóstico
        logger.debug(f"Primeras 5 filas del CSV:\n{df.head()}")
        logger.debug(f"Columnas del CSV: {list(df.columns)}")
        
        # Encontrar la columna de DNI
        dni_column = find_dni_column(df)
        if not dni_column:
            raise ValueError("No se pudo identificar la columna de DNI en el CSV")
        
        logger.info(f"Columna de DNI identificada: {dni_column}")
        
        # Ver valores únicos de la columna DNI para diagnóstico
        unique_dnis = df[dni_column].dropna().unique()
        logger.debug(f"Ejemplo de DNIs en el CSV (primeros 10): {unique_dnis[:10]}")
        
        # Normalizar los DNIs en el CSV
        df['dni_clean'] = df[dni_column].apply(lambda x: clean_dni(x) if not pd.isna(x) else '')
        
        # Convertir los DNIs a procesar a formato limpio
        dnis_to_process_clean = {clean_dni(dni) for dni in dnis_to_process}
        
        # Mostrar para diagnóstico
        logger.debug(f"DNIs a procesar normalizados: {dnis_to_process_clean}")
        
        # Filtrar el DataFrame
        df_filtered = df[df['dni_clean'].isin(dnis_to_process_clean)]
        
        # Verificar cuántos DNIs se encontraron
        found_dnis = set(df_filtered['dni_clean'])
        logger.info(f"DNIs encontrados en el CSV: {len(found_dnis)} de {len(dnis_to_process_clean)}")
        
        # Identificar DNIs que no se encontraron en el CSV
        dnis_not_found = dnis_to_process_clean - found_dnis
        if dnis_not_found:
            logger.warning(f"Los siguientes DNIs no fueron encontrados en el CSV: {dnis_not_found}")
            
        # Verificar si hay DNIs duplicados en el CSV
        duplicated = df_filtered[df_filtered.duplicated(subset=['dni_clean'], keep=False)]
        if not duplicated.empty:
            logger.warning(f"Hay {len(duplicated)} registros duplicados en el CSV para los DNIs a procesar")
            for dni in duplicated['dni_clean'].unique():
                logger.warning(f"DNI duplicado: {dni}")
        
        return df_filtered, dni_column
        
    except Exception as e:
        logger.error(f"Error al leer el CSV: {str(e)}", exc_info=True)
        raise

def process_dnis(csv_path, dnis_to_process, escapada_id, db_config):
    """
    Procesa los DNIs especificados inscribiéndolos en la escapada.
    """
    global logger
    logger = setup_logging()
    logger.info(f"Iniciando procesamiento para inscribir DNIs en la escapada {escapada_id}")
    logger.info(f"DNIs a procesar: {dnis_to_process}")
    
    try:
        # 1. Leer el CSV y filtrar por los DNIs que queremos procesar
        df_to_process, dni_column = read_csv_with_dnis_to_process(csv_path, dnis_to_process)
        
        if df_to_process.empty:
            logger.error("No se encontraron DNIs en el CSV. Verifica los datos.")
            return {"procesados": 0, "mensaje": "No se encontraron DNIs en el CSV"}
        
        # 2. Conectar a la base de datos y procesar cada DNI
        with DatabaseConnection(db_config) as db:
            # Obtener DNIs ya inscritos en la escapada
            inscribed_dnis = get_inscribed_dnis_for_escapada(db, escapada_id)
            
            # 3. Filtrar DNIs que ya están inscritos
            dnis_to_process_clean = set(df_to_process['dni_clean'])
            dnis_to_process_filtered = dnis_to_process_clean - inscribed_dnis
            
            logger.info(f"DNIs ya inscritos: {len(inscribed_dnis)}")
            logger.info(f"DNIs a procesar después de filtrar ya inscritos: {len(dnis_to_process_filtered)}")
            
            if not dnis_to_process_filtered:
                logger.info("Todos los DNIs ya están inscritos en la escapada.")
                return {"procesados": 0, "mensaje": "Todos los DNIs ya están inscritos"}
            
            # 4. Procesar cada DNI
            stats = {
                "total": len(dnis_to_process_filtered),
                "inscritos": 0,
                "fallidos": 0,
                "ya_inscritos": len(dnis_to_process_clean) - len(dnis_to_process_filtered)
            }
            
            for dni in dnis_to_process_filtered:
                try:
                    # Buscar la fila correspondiente en el DataFrame
                    rows = df_to_process[df_to_process['dni_clean'] == dni]
                    if rows.empty:
                        logger.warning(f"No se encontró el DNI {dni} en el DataFrame filtrado")
                        stats["fallidos"] += 1
                        continue
                    
                    # Usar la primera fila que coincide
                    row = rows.iloc[0]
                    
                    # Insertar persona e inscripción
                    result = insert_person_and_inscription(db, row.to_dict(), dni_column, escapada_id)
                    
                    if result == "already_inscribed":
                        stats["ya_inscritos"] += 1
                    else:
                        stats["inscritos"] += 1
                        
                except Exception as e:
                    logger.error(f"Error al procesar DNI {dni}: {str(e)}", exc_info=True)
                    db.conn.rollback()  # Rollback para esta transacción específica
                    stats["fallidos"] += 1
            
            # 5. Resumen del proceso
            logger.info("\nResumen del proceso:")
            logger.info(f"- Total DNIs a procesar: {stats['total']}")
            logger.info(f"- DNIs inscritos exitosamente: {stats['inscritos']}")
            logger.info(f"- DNIs ya inscritos (sin acción): {stats['ya_inscritos']}")
            logger.info(f"- DNIs fallidos: {stats['fallidos']}")
            
            return stats
            
    except Exception as e:
        logger.error(f"Error en el proceso general: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # Configuración
    csv_path = "inscripciones.csv"  # Ruta al archivo CSV
    
    # Lista de DNIs a procesar
    dnis_to_process = [
        "09132788V", "35088053N", "35092541S", "37747208E", "41589166Z", 
        "44893744K", "47290452Z", "48081489N", "48225033J", "48271931Z", 
        "49679134P", "51420343W", "51504243K", "54385870J", "60552386X", 
        "70427712X", "73022578Q", "819458Z", "G36644911", "50307339Z"
    ]
    
    escapada_id = 1  # ID de la escapada
    
    # Configuración de la base de datos
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',
        'db': 'pam_db'
    }
    
    try:
        result = process_dnis(csv_path, dnis_to_process, escapada_id, db_config)
        logger.info("Proceso completado exitosamente")
        logger.info(f"Resultados: {result}")
    except Exception as e:
        logger.error(f"Error fatal en el proceso: {str(e)}", exc_info=True)
        sys.exit(1)