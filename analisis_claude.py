# analisis_claude.py - Segunda opinión de Claude para los activos con COMPRAR y los que tienes.
# Usa Claude Code en modo no interactivo (claude -p) con las skills financial-analysis y equity-research:
# resultados recientes, comparación con pares y noticias. Guarda cada análisis en analisis_claude.csv.
# Se programa a las 7:30 a.m. (días hábiles) para que el reporte de las 8:00 ya lo incluya.
# Uso:  python analisis_claude.py               (analiza los activos que tocan hoy)
#       python analisis_claude.py --activo EC   (solo uno)
# OJO: cada análisis consume uso de tu plan de Claude y tarda 1 a 5 minutos.

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime

import pandas as pd

import activos
import estrategia
import mis_activos
import noticias

ARCHIVO = activos.CARPETA / "analisis_claude.csv"
MAX_ACTIVOS = 8          # shortcut: tope para no gastar demasiado uso de Claude; súbelo si quieres revisar más
TIEMPO_MAX = 600         # segundos por activo
VIGENCIA_DIAS = 3        # Un análisis vale para la decisión unificada durante 3 días
COLUMNAS = ["Fecha", "Activo", "Veredicto", "Dudas", "Resumen", "Resultados", "Pares", "Noticias"]


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Fecha"])


def del_activo(simbolo):
    t = leer()
    return t[t["Activo"] == simbolo].sort_values("Fecha", ascending=False)


def ultimo(simbolo):
    """El análisis más reciente si todavía está vigente; si no, None."""
    t = del_activo(simbolo)
    if t.empty or (pd.Timestamp.now() - t["Fecha"].iloc[0]).days > VIGENCIA_DIAS:
        return None
    return t.iloc[0]


def decision_unificada(r, analisis="buscar"):
    """(decisión, color, dudas). COMPRAR CONFIRMADO si la app y Claude coinciden; CON CAUTELA si Claude duda."""
    if r["decision"] != "COMPRAR":
        return r["decision"], {"NO COMPRAR": "red"}.get(r["decision"], "gray"), []
    a = ultimo(r["simbolo"]) if analisis == "buscar" else analisis
    if a is None:
        return "COMPRAR CON CAUTELA", "orange", ["Claude todavía no revisó este activo."]
    if a["Veredicto"] == "CONFIRMA":
        return "COMPRAR CONFIRMADO", "green", []
    dudas = [d.strip() for d in str(a["Dudas"]).split("|") if d.strip() and d.strip() != "nan"]
    return "COMPRAR CON CAUTELA", "orange", dudas or ["Claude tiene dudas (ver su análisis)."]


def seleccionar():
    """Activos con COMPRAR (los de mayor probabilidad primero) más los que tienes."""
    import ranking
    tabla = ranking.leer()
    compran = list(tabla.loc[tabla["Decision"] == "COMPRAR", "Activo"]) if tabla is not None else []
    mios = list(mis_activos.abiertas().get("Activo", []))
    return list(dict.fromkeys(mios + compran))[:MAX_ACTIVOS]


def _prompt(simbolo, r):
    titulares = noticias.de_empresa(simbolo)["Titular"].head(10).tolist()
    tm = r["tm"] or {}
    return f"""Eres un analista financiero. Revisa la acción/activo {simbolo} ({activos.nombre(simbolo)}).
Usa las skills financial-analysis y equity-research (por ejemplo earnings-analysis y comps-analysis) y búsquedas
web para revisar: 1) resultados financieros recientes, 2) comparación con sus pares principales, 3) noticias recientes.

Contexto de nuestra app (análisis estadístico de corto plazo, 5 días):
- Precio: {r['precio']:.2f}. Decisión de la app: {r['decision']}. Probabilidad de subida a 5 días: {r['prob']:.1f}%.
- Time Machine (10.000 simulaciones con stop -3% y objetivo +6%): ganancia esperada {tm.get('ganancia_esperada', 0):+.2f}%.
- Titulares recientes: {json.dumps(titulares, ensure_ascii=False)}

Responde en español y TERMINA tu respuesta con un bloque JSON exactamente así (sin texto después):
```json
{{"veredicto": "CONFIRMA" | "DUDAS" | "EN_CONTRA",
  "dudas": ["duda concreta 1", "duda concreta 2"],
  "resumen": "2 a 4 frases sencillas para alguien que no sabe de finanzas",
  "resultados": "1 a 2 frases sobre sus últimos resultados",
  "pares": "1 a 2 frases comparándolo con sus pares",
  "noticias": "1 a 2 frases sobre las noticias que más pesan"}}
```
CONFIRMA = no ves razones fuertes en contra de una compra de corto plazo; DUDAS = hay riesgos que conviene
mirar; EN_CONTRA = hay razones fuertes para no comprar ahora."""


def _extraer_json(texto):
    bloques = re.findall(r"\{.*\}", texto, re.DOTALL)
    for b in reversed(bloques):
        try:
            return json.loads(b)
        except ValueError:
            continue
    return None


def analizar(simbolo):
    """Pide el análisis a Claude y lo guarda. Devuelve la fila guardada o un mensaje de error."""
    r = estrategia.analizar(simbolo)
    try:
        proc = subprocess.run(
            ["claude", "-p", _prompt(simbolo, r), "--output-format", "json",
             "--allowedTools", "WebSearch", "WebFetch", "Skill", "Read"],
            capture_output=True, text=True, encoding="utf-8", timeout=TIEMPO_MAX, cwd=activos.CARPETA)
    except (subprocess.TimeoutExpired, FileNotFoundError) as error:
        return f"{simbolo}: no se pudo correr Claude ({error})"
    try:
        texto = json.loads(proc.stdout).get("result", "")
    except ValueError:
        texto = proc.stdout
    datos = _extraer_json(texto)
    if not datos or datos.get("veredicto") not in ("CONFIRMA", "DUDAS", "EN_CONTRA"):
        return f"{simbolo}: Claude no devolvió el formato esperado. {(proc.stderr or texto)[:200]}"
    fila = {"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "Activo": simbolo, "Veredicto": datos["veredicto"],
            "Dudas": " | ".join(datos.get("dudas", [])), "Resumen": datos.get("resumen", ""),
            "Resultados": datos.get("resultados", ""), "Pares": datos.get("pares", ""),
            "Noticias": datos.get("noticias", "")}
    pd.concat([leer(), pd.DataFrame([fila])], ignore_index=True).to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return fila


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Análisis de Claude")
    parser.add_argument("--activo")
    args = parser.parse_args()
    lista = [activos.limpiar(args.activo)] if args.activo else seleccionar()
    print(f"Analizando con Claude: {', '.join(lista) or '(ninguno: no hay COMPRAR ni activos tuyos)'}")
    for s in lista:
        res = analizar(s)
        print(f"  {s}: {res['Veredicto']} - {res['Resumen'][:120]}" if isinstance(res, dict) else f"  {res}")


if __name__ == "__main__":
    main()
