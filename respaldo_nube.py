# respaldo_nube.py - Copia de seguridad CIFRADA de la base de datos de Supabase (tablas y archivos compartidos).
# La corre GitHub Actions cada domingo y la guarda aparte, en GitHub (Actions -> Artifacts), por 90 días.
# Va CIFRADA con RESPALDO_CLAVE (solo está en tu .env y en los secretos de GitHub): sin esa clave nadie puede leerla.
# Uso:  python respaldo_nube.py                       (crea respaldo_nube/copia_<fecha>.cifrada)
#       python respaldo_nube.py --descifrar ARCHIVO   (la convierte en un .zip normal para revisarla o restaurarla)
#       python respaldo_nube.py --clave-nueva         (crea la clave y la guarda en .env, solo la primera vez)
import io
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

import nube

CARPETA = Path(__file__).resolve().parent / "respaldo_nube"
TABLAS = ["usuarios", "operaciones", "ajustes", "diario_errores"]
SIN_COPIA = {nube.PRECIOS, "fichas.json"}     # Los precios se vuelven a bajar de Yahoo; las fichas están en GitHub


def _fernet():
    clave = nube.secreto("RESPALDO_CLAVE")
    if not clave:
        raise SystemExit("Falta RESPALDO_CLAVE: corre  python respaldo_nube.py --clave-nueva")
    return Fernet(clave.encode())


def empacar():
    """Un .zip (en memoria) con cada tabla en JSON y los archivos compartidos. Devuelve (bytes, resumen)."""
    c = nube.cliente()
    salida, resumen = io.BytesIO(), {}
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for t in TABLAS:
            filas, desde = [], 0
            while True:                                # De a 1.000 filas (límite de cada consulta de Supabase)
                parte = c.table(t).select("*").range(desde, desde + 999).execute().data
                filas += parte
                if len(parte) < 1000:
                    break
                desde += 1000
            z.writestr(f"{t}.json", json.dumps(filas, ensure_ascii=False, default=str))
            resumen[t] = len(filas)
        almacen = c.storage.from_(nube.BUCKET)
        for a in almacen.list("", {"limit": 1000}):
            if a["name"] not in SIN_COPIA:
                z.writestr(f"archivos/{a['name']}", almacen.download(a["name"]))
                resumen[a["name"]] = "archivo"
        z.writestr("resumen.json", json.dumps(resumen, ensure_ascii=False, indent=1))
    return salida.getvalue(), resumen


def respaldar():
    datos, resumen = empacar()
    CARPETA.mkdir(exist_ok=True)
    ruta = CARPETA / f"copia_{datetime.now():%Y-%m-%d_%H%M}.cifrada"
    ruta.write_bytes(_fernet().encrypt(datos))
    return ruta, resumen


def descifrar(ruta):
    ruta = Path(ruta)
    destino = ruta.with_suffix(".zip")
    destino.write_bytes(_fernet().decrypt(ruta.read_bytes()))
    return destino


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--clave-nueva" in sys.argv:
        env = Path(__file__).resolve().parent / ".env"
        texto = env.read_text(encoding="utf-8")
        if "RESPALDO_CLAVE=" in texto:
            raise SystemExit("Ya tienes RESPALDO_CLAVE en .env: no la cambio (perderías acceso a las copias viejas).")
        env.write_text(texto.rstrip("\n") + f"\nRESPALDO_CLAVE={Fernet.generate_key().decode()}\n", encoding="utf-8")
        print("Clave creada en .env. Guárdala también en un lugar seguro: sin ella, las copias no se pueden abrir.")
    elif "--descifrar" in sys.argv:
        print("Copia lista para revisar:", descifrar(sys.argv[sys.argv.index("--descifrar") + 1]))
    else:
        ruta, resumen = respaldar()
        print(f"Copia cifrada: {ruta.name}")
        for k, v in resumen.items():
            print(f"  {k}: {v}{' filas' if isinstance(v, int) else ''}")
