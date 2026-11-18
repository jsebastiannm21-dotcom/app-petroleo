# respaldo.py - Copia de seguridad de todos tus registros en respaldo/AAAA-MM-DD_HHMM/
#  - Archivos de esta carpeta (.csv y .json): Mis activos, simulador, historiales, eventos, configuración...
#  - Si hay nube (Supabase): TODAS las filas de las tablas (usuarios, operaciones, ajustes, diario_errores)
#    y todos los archivos del almacenamiento 'datos'. Van en respaldo/.../supabase/
# No copia .env (tiene tus claves secretas) ni los precios descargados (se pueden volver a bajar).
# La carpeta respaldo/ nunca se sube a GitHub (.gitignore).
#
# Uso:  python respaldo.py                       -> hace el respaldo y lo verifica
#       python respaldo.py --verificar CARPETA   -> prueba que ese respaldo se puede restaurar (no cambia nada)
#       python respaldo.py --restaurar CARPETA --confirmar   -> RESTAURA de verdad (solo si algo se perdió)

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
TABLAS = {"usuarios": ["email"], "operaciones": ["id"], "ajustes": ["email", "clave"], "diario_errores": ["id"]}


def _hash(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _filas(tabla):
    """Todas las filas de una tabla de Supabase, de 1000 en 1000 (el máximo por consulta)."""
    import nube
    filas, desde = [], 0
    while True:
        lote = nube.cliente().table(tabla).select("*").range(desde, desde + 999).execute().data
        filas += lote
        if len(lote) < 1000:
            return filas
        desde += 1000


def _canonico(filas, llave):
    return json.dumps(sorted(filas, key=lambda f: [str(f.get(k)) for k in llave]), sort_keys=True, ensure_ascii=False)


def respaldar_nube(destino):
    import nube
    if not nube.conectado():
        return {}
    carpeta = destino / "supabase"
    (carpeta / "almacen").mkdir(parents=True, exist_ok=True)
    resumen = {}
    for tabla in TABLAS:
        filas = _filas(tabla)
        (carpeta / f"{tabla}.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
        resumen[f"[nube] tabla {tabla}"] = len(filas)
    almacen = nube.cliente().storage.from_(nube.BUCKET)
    for a in almacen.list("", {"limit": 1000}):
        if a.get("id"):                                    # Las carpetas no tienen id
            (carpeta / "almacen" / a["name"]).write_bytes(almacen.download(a["name"]))
            resumen[f"[nube] archivo {a['name']}"] = (carpeta / "almacen" / a["name"]).stat().st_size
    return resumen


def respaldar():
    destino = CARPETA / "respaldo" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    copiados = {}
    for archivo in sorted(list(CARPETA.glob("*.csv")) + list(CARPETA.glob("*.json"))):
        shutil.copy2(archivo, destino / archivo.name)
        with open(archivo, encoding="utf-8-sig", errors="replace") as f:
            copiados[archivo.name] = sum(1 for _ in f) - (1 if archivo.suffix == ".csv" else 0)
    try:
        copiados.update(respaldar_nube(destino))
    except Exception as error:                             # Sin internet: queda al menos la copia local
        copiados["[nube] NO SE PUDO RESPALDAR"] = str(error)[:200]
    return destino, copiados


def verificar(destino):
    """Prueba de restauración SIN tocar nada real:
    1) restaura los archivos locales en una carpeta temporal y compara byte a byte;
    2) compara las filas guardadas de cada tabla con las de la nube (son las que se volverían a escribir);
    3) compara cada archivo del almacenamiento con el de la nube."""
    import nube
    destino = Path(destino)
    informe = []
    with tempfile.TemporaryDirectory() as tmp:
        for archivo in destino.glob("*.*"):
            copia = Path(tmp) / archivo.name
            shutil.copy2(archivo, copia)
            informe.append((f"archivo {archivo.name}", _hash(copia) == _hash(archivo)))
    nube_dir = destino / "supabase"
    if nube_dir.exists() and nube.conectado():
        for tabla, llave in TABLAS.items():
            guardado = json.loads((nube_dir / f"{tabla}.json").read_text(encoding="utf-8"))
            informe.append((f"tabla {tabla} ({len(guardado)} filas)",
                            _canonico(guardado, llave) == _canonico(_filas(tabla), llave)))
        almacen = nube.cliente().storage.from_(nube.BUCKET)
        for archivo in (nube_dir / "almacen").iterdir():
            informe.append((f"nube {archivo.name}", archivo.read_bytes() == almacen.download(archivo.name)))
    return informe


def restaurar(destino, confirmar=False):
    """Vuelve a escribir el respaldo. Usa 'upsert': repone lo que falte o cambió, NO borra nada que exista hoy."""
    import nube
    destino = Path(destino)
    if not confirmar:
        raise SystemExit("Para restaurar de verdad agrega --confirmar (antes se hace un respaldo de lo actual).")
    respaldar()                                            # Por si acaso, primero una copia de cómo está hoy
    for archivo in destino.glob("*.*"):
        shutil.copy2(archivo, CARPETA / archivo.name)
    nube_dir = destino / "supabase"
    if nube_dir.exists():
        for tabla, llave in TABLAS.items():
            filas = json.loads((nube_dir / f"{tabla}.json").read_text(encoding="utf-8"))
            for i in range(0, len(filas), 500):
                nube.cliente().table(tabla).upsert(filas[i:i + 500], on_conflict=",".join(llave)).execute()
        almacen = nube.cliente().storage.from_(nube.BUCKET)
        for archivo in (nube_dir / "almacen").iterdir():
            almacen.upload(archivo.name, archivo.read_bytes(), {"upsert": "true",
                                                                "content-type": "application/octet-stream"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("--verificar", metavar="CARPETA")
    p.add_argument("--restaurar", metavar="CARPETA")
    p.add_argument("--confirmar", action="store_true")
    a = p.parse_args()
    if a.restaurar:
        restaurar(a.restaurar, a.confirmar)
        print("Restaurado.")
        sys.exit()
    if not a.verificar:
        destino, copiados = respaldar()
        print(f"Respaldo en {destino}")
        for nombre, filas in copiados.items():
            print(f"  {nombre:45} {filas}")
    resultado = verificar(a.verificar or destino)
    malos = [n for n, ok in resultado if not ok]
    print(f"Prueba de restauración: {len(resultado) - len(malos)} de {len(resultado)} elementos idénticos.")
    for n in malos:
        print(f"  DIFERENTE: {n}")
