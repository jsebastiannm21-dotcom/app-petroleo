# respaldo.py - Copia de seguridad de todos tus registros en respaldo/AAAA-MM-DD_HHMM/
# (Mis activos, simulador, historiales, cierres semanales, eventos, configuración...).
# No copia .env (tiene tus claves secretas) ni los precios descargados (se pueden volver a bajar).
# Uso:  python respaldo.py

import shutil
import sys
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent


def respaldar():
    destino = CARPETA / "respaldo" / datetime.now().strftime("%Y-%m-%d_%H%M")
    destino.mkdir(parents=True, exist_ok=True)
    copiados = {}
    for archivo in sorted(list(CARPETA.glob("*.csv")) + list(CARPETA.glob("*.json"))):
        shutil.copy2(archivo, destino / archivo.name)
        with open(archivo, encoding="utf-8-sig", errors="replace") as f:
            copiados[archivo.name] = sum(1 for _ in f) - (1 if archivo.suffix == ".csv" else 0)
    return destino, copiados


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    destino, copiados = respaldar()
    print(f"Respaldo en {destino}")
    for nombre, filas in copiados.items():
        print(f"  {nombre:32} {filas:>7} {'filas' if nombre.endswith('.csv') else 'líneas'}")
