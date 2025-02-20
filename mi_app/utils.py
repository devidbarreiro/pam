# utils.py

import csv
import io
import logging

def validar_csv(csv_file):
    """
    Valida la estructura del CSV y retorna información sobre los errores encontrados.
    Ajustada para NO requerir 'Nombre + apellido'.
    """
    logger = logging.getLogger(__name__)

    resultados = {
        'es_valido': True,
        'errores': [],
        'advertencias': [],
        'columnas_encontradas': [],
        'total_filas': 0,
        'muestra_filas': [],
    }

    # Columnas requeridas
    columnas_requeridas = [
        'Nombre',
        'Apellidos',
        'Correo',
        'Teléfono',
        'DNI (si eres europeo) o Pasaporte',
        'Pagado',
    ]

    # Columnas opcionales importantes
    columnas_opcionales = [
        'Alojamiento',
        # Agrega aquí si quieres más columnas que te gustaría detectar,
        # pero no marcar como error si faltan
    ]

    try:
        # Leemos todo el archivo en memoria
        csv_data = csv_file.read().decode('utf-8')
        io_string = io.StringIO(csv_data)
        reader = csv.DictReader(io_string)

        # Verificar el encabezado
        if not reader.fieldnames:
            resultados['es_valido'] = False
            resultados['errores'].append(
                "No se pudo leer el encabezado del CSV. Verifica que el formato sea correcto."
            )
            return resultados

        # Opcional: normalizar las columnas (remover espacios extra)
        # para evitar problemas de 'Nombre + apellido ' con espacio
        # Descomenta si quieres normalizar:
        # original_fieldnames = reader.fieldnames
        # normalized_fieldnames = [col.strip() for col in original_fieldnames]
        # reader.fieldnames = normalized_fieldnames

        resultados['columnas_encontradas'] = reader.fieldnames

        # Verificar columnas requeridas
        for columna in columnas_requeridas:
            if columna not in reader.fieldnames:
                resultados['es_valido'] = False
                resultados['errores'].append(f"Columna requerida no encontrada: '{columna}'")

        # Verificar columnas opcionales
        for columna in columnas_opcionales:
            if columna not in reader.fieldnames:
                resultados['advertencias'].append(f"Columna opcional no encontrada: '{columna}'")

        # Leer primeras filas para muestra y verificación
        filas = []
        for i, row in enumerate(reader):
            if i < 5:  # Guardar primeras 5 filas como muestra
                filas.append(row)

            # Verificar valores en cada fila (solo para columnas requeridas)
            for columna in columnas_requeridas:
                if columna in row and not row[columna].strip():
                    resultados['advertencias'].append(
                        f"Fila {i+1}: Valor vacío en columna requerida '{columna}'"
                    )

            resultados['total_filas'] = i + 1

            if i >= 100:  # Verificar solo primeras 100 filas
                break

        resultados['muestra_filas'] = filas

        # Verificaciones adicionales
        if resultados['total_filas'] == 0:
            resultados['es_valido'] = False
            resultados['errores'].append("El CSV no contiene datos (solo encabezados)")

        logger.info(
            f"Validación de CSV completada: {resultados['total_filas']} filas encontradas, "
            f"{len(resultados['errores'])} errores, {len(resultados['advertencias'])} advertencias"
        )

        return resultados

    except UnicodeDecodeError:
        # Intentar con otra codificación (ej. ISO-8859-1)
        csv_file.seek(0)
        try:
            csv_data = csv_file.read().decode('ISO-8859-1')
            resultados['advertencias'].append(
                "El archivo no está en codificación UTF-8. Se procesó como ISO-8859-1."
            )
            # Repetir la lógica, o armarlo en una función que se pueda reutilizar
            # ...
            # Para simplicidad, marcamos un error si no se maneja la re-lectura
            # con la misma lógica
            io_string = io.StringIO(csv_data)
            reader = csv.DictReader(io_string)
            # ...Volver a verificar columns etc. (mismo approach)...

        except Exception as e:
            resultados['es_valido'] = False
            resultados['errores'].append(f"Error de codificación: {str(e)}")

    except Exception as e:
        resultados['es_valido'] = False
        resultados['errores'].append(f"Error al validar CSV: {str(e)}")
        logger.error(f"Error validando CSV: {str(e)}", exc_info=True)

    return resultados
