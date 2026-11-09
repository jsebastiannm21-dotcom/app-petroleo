# formato.py - Números en formato colombiano: punto de miles y coma decimal ("20.000", "1.234,56").

import re


def leer_numero(texto):
    """'20.000' -> 20000 · '1.234,56' -> 1234.56 · '15,5' -> 15.5 · '520.06' -> 520.06 · '' -> None.
    Un solo punto seguido de exactamente 3 cifras se toma como miles (estilo colombiano)."""
    t = str(texto or "").strip().replace(" ", "").replace("$", "").replace("US", "").replace("COP", "")
    if not t:
        return None
    if not re.fullmatch(r"[\d.,]+", t):
        raise ValueError(f"'{texto}' no es un número")
    if "," in t:                                    # Coma = decimal; los puntos son miles
        entero, _, decimal = t.rpartition(",")
        t = entero.replace(".", "") + "." + decimal
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")                      # Varios puntos, o "20.000": son miles
    return float(t)


def mostrar(numero, decimales=2):
    """1234.5 -> '1.234,50' (formato colombiano)."""
    if numero is None:
        return "—"
    texto = f"{numero:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


if __name__ == "__main__":
    casos = {"20.000": 20000, "1.234,56": 1234.56, "15,5": 15.5, "520.06": 520.06, "1.000.000": 1e6,
             "0,03": 0.03, "3.240,38": 3240.38, "100": 100, " $ 20.000 ": 20000, "": None, "0.5": 0.5}
    for entrada, esperado in casos.items():
        assert leer_numero(entrada) == esperado, (entrada, leer_numero(entrada))
    assert mostrar(1685191.96) == "1.685.191,96" and mostrar(0.03, 4) == "0,0300"
    try:
        leer_numero("abc")
        raise AssertionError("debió fallar")
    except ValueError:
        pass
    print("Formato colombiano: pruebas OK")
