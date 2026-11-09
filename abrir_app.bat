@echo off
rem Abre la app. Si ya está corriendo, solo abre el navegador.
rem Mientras la app esté abierta, esta ventana negra debe quedarse abierta (puedes minimizarla).
cd /d "%~dp0"
rem APP_LOCAL=1: en tu PC entras directo como superadmin (en la nube siempre se pide el login con Google)
set APP_LOCAL=1
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul && (
    start "" http://localhost:8501
    exit /b
)
echo Abriendo la app en http://localhost:8501 ... (cierra esta ventana para apagarla)
python -m streamlit run app.py --server.port 8501
