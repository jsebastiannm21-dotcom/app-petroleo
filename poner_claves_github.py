# poner_claves_github.py - Pone en GitHub (Settings -> Secrets -> Actions) las claves que usan las tareas en la nube.
# Las lee de tu archivo .env y NO las muestra en pantalla. Se corre con doble clic en poner_claves_github.bat.
import os
import subprocess

from dotenv import dotenv_values

REPO = "jsebastiannm21-dotcom/app-petroleo"
GH = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "GitHub CLI", "gh.exe")
e = dotenv_values(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
valores = {k: (e.get(k) or "").strip() for k in ["SUPABASE_URL", "SUPABASE_KEY", "SUPERADMIN_EMAIL", "TELEGRAM_TOKEN",
                                                   "TELEGRAM_CHAT_ID", "ADMIN_TELEGRAM_TOKEN", "ADMIN_TELEGRAM_CHAT_ID"]}
valores["APP_URL"] = "https://app-petroleo-2jsrncgu76vcg3kdfxjqyc.streamlit.app/"
for clave, valor in valores.items():
    if not valor:
        print(f"FALTA {clave} en el archivo .env")
        continue
    r = subprocess.run([GH, "secret", "set", clave, "-R", REPO], input=valor, text=True, capture_output=True)
    print(f"{clave}: {'guardada' if r.returncode == 0 else 'ERROR ' + r.stderr.strip()[:150]}")
print("\nListo. Ya puedes cerrar esta ventana y escribirle «listo» a Claude.")
