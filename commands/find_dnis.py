#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import logging
import pymysql
import sys
import os
import pandas as pd
import re

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
    """
    Limpia y normaliza un DNI.
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

def get_dnis_from_db(db_config):
    """
    Obtiene todos los DNIs desde la base de datos.
    """
    logger.info("Obteniendo DNIs desde la base de datos...")
    dnis = []
    
    with DatabaseConnection(db_config) as db:
        db.cursor.execute("SELECT dni FROM persona")
        results = db.cursor.fetchall()
        dnis = [clean_dni(row['dni']) for row in results]
    
    # Eliminar duplicados y valores vacíos
    dnis = [dni for dni in dnis if dni]
    dnis = sorted(list(set(dnis)))
    
    logger.info(f"Se encontraron {len(dnis)} DNIs únicos en la base de datos")
    return dnis

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

def get_dnis_from_csv(csv_path):
    """
    Obtiene todos los DNIs desde el archivo CSV.
    """
    logger.info(f"Leyendo DNIs desde el archivo CSV: {csv_path}")
    
    try:
        # Leer el CSV como strings para evitar conversiones automáticas
        df = pd.read_csv(csv_path, dtype=str)
        logger.info(f"CSV leído correctamente. Dimensiones: {df.shape}")
        
        # Encontrar la columna de DNI
        dni_column = find_dni_column(df)
        if not dni_column:
            raise ValueError("No se pudo identificar la columna de DNI en el CSV")
        
        logger.info(f"Columna de DNI identificada: {dni_column}")
        
        # Extraer y limpiar los DNIs
        dnis = [clean_dni(val) for val in df[dni_column].dropna()]
        
        # Eliminar duplicados y valores vacíos
        dnis = [dni for dni in dnis if dni]
        dnis = sorted(list(set(dnis)))
        
        logger.info(f"Se encontraron {len(dnis)} DNIs únicos en el CSV")
        return dnis
        
    except Exception as e:
        logger.error(f"Error al leer DNIs desde CSV: {str(e)}")
        raise

def save_dnis_to_file(dnis, filename):
    """
    Guarda la lista de DNIs en un archivo Python.
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Lista de DNIs\n\n")
        f.write("dnis = [\n")
        for dni in dnis:
            f.write(f'    "{dni}",\n')
        f.write("]\n")
    
    logger.info(f"Lista de {len(dnis)} DNIs guardada en {filename}")
    return filename

def main():
    # Configuración
    csv_path = "inscripciones.csv"  # Ruta al archivo CSV
    
    # Configuración de la base de datos
    db_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'root',
        'db': 'pam_db'
    }
    
    try:
        # Obtener DNIs de la base de datos
        db_dnis = get_dnis_from_db(db_config)
        
        # Obtener DNIs del CSV
        csv_dnis = get_dnis_from_csv(csv_path)
        
        # Guardar listas en archivos
        db_file = save_dnis_to_file(db_dnis, "dnis_bbdd.py")
        csv_file = save_dnis_to_file(csv_dnis, "dnis_csv.py")
        
        # Mostrar resumen
        print("\n=== RESUMEN ===")
        print(f"DNIs en la base de datos: {len(db_dnis)}")
        print(f"DNIs en el CSV: {len(csv_dnis)}")
        print(f"DNIs en el CSV pero no en la BD: {len(set(csv_dnis) - set(db_dnis))}")
        print(f"DNIs en la BD pero no en el CSV: {len(set(db_dnis) - set(csv_dnis))}")
        print(f"DNIs en común: {len(set(db_dnis) & set(csv_dnis))}")
        print(f"\nResultados guardados en {db_file} y {csv_file}")
        
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()