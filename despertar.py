# despertar.py - Abre la app en un navegador invisible; si Streamlit la durmió, toca el botón para despertarla.
# Si la app no carga o tarda mucho, avisa al Telegram de admin. Lo usa la tarea "Mantener la app despierta".
# Uso: python despertar.py https://tu-app.streamlit.app
import os
import sys
import time

import requests
from playwright.sync_api import sync_playwright


def avisar(texto):
    token, chat = os.getenv("ADMIN_TELEGRAM_TOKEN"), os.getenv("ADMIN_TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": f"🛠️ ADMIN\n{texto}"},
                      timeout=15)


inicio = time.time()
try:
    with sync_playwright() as p:
        pagina = p.chromium.launch().new_page()
        pagina.goto(sys.argv[1], timeout=120_000)
        boton = pagina.get_by_role("button", name="Yes, get this app back up!")
        if boton.count():
            boton.click()
            print("La app estaba dormida: la desperté.")
        cargo = False
        for _ in range(24):                                   # Hasta 2 minutos esperando a que aparezca la app
            pagina.wait_for_timeout(5000)
            texto = " ".join(f.inner_text("body") for f in pagina.frames if f.url.startswith("http"))
            if "Entrar con Google" in texto or "Análisis de mercados" in texto or "Mantenimiento" in texto:
                cargo = True
                break
    segundos = time.time() - inicio
    if not cargo:
        avisar(f"⚠️ La app no terminó de cargar en {segundos:.0f} segundos. Revisa {sys.argv[1]}")
    elif segundos > 90:
        avisar(f"🐢 La app cargó, pero tardó {segundos:.0f} segundos.")
    print(f"Visita hecha en {segundos:.0f} s (cargó: {cargo}).")
except Exception as error:
    avisar(f"🔴 No pude abrir la app: {error}"[:500])
    raise
