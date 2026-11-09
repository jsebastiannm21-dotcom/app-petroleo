# despertar.py - Abre la app en un navegador invisible; si Streamlit la durmió, toca el botón para despertarla.
# Lo usa la tarea "Mantener la app despierta" de GitHub Actions.  Uso: python despertar.py https://tu-app.streamlit.app
import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    pagina = p.chromium.launch().new_page()
    pagina.goto(sys.argv[1], timeout=120_000)
    boton = pagina.get_by_role("button", name="Yes, get this app back up!")
    if boton.count():
        boton.click()
        print("La app estaba dormida: la desperté.")
    pagina.wait_for_timeout(20_000)                   # Le da tiempo de arrancar
    print("Visita hecha.")
