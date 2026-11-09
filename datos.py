# datos.py - Etapa 1: descargar 5 años de precios diarios
# Uso:  python datos.py                (petróleo WTI, como siempre)
#       python datos.py --activo GLD   (cualquier otro símbolo de Yahoo Finance)

import argparse

import activos

parser = argparse.ArgumentParser(description="Descarga 5 años de precios diarios")
parser.add_argument("--activo", default=activos.PRINCIPAL, help="Símbolo de Yahoo Finance (por defecto CL=F)")
simbolo = activos.limpiar(parser.parse_args().activo)

print(f"Descargando 5 años de precios diarios de {activos.etiqueta(simbolo)}...")
datos = activos.descargar(simbolo)
print(f"Listo: {len(datos)} días guardados en {activos.ruta_precios(simbolo).name}")
print(f"Desde {datos.index.min().date()} hasta {datos.index.max().date()}")
print("\nÚltimas 5 filas:")
print(datos.tail(5).round(2))
