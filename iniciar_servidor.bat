@echo off
chcp 65001 >nul
echo ============================================
echo   Classificador NF Entrada - Servidor
echo ============================================

REM Tenta localizar Python
where py >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py -3.11
    goto found
)
where python >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    goto found
)

echo [ERRO] Python nao encontrado.
pause
exit /b 1

:found
echo Python encontrado!
echo.

REM Verifica se ngrok esta instalado
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] ngrok nao encontrado no PATH.
    echo.
    echo Instale o ngrok em: https://ngrok.com/download
    echo Depois adicione ao PATH ou coloque ngrok.exe nesta pasta.
    echo.
    pause
    exit /b 1
)

echo Instalando dependencias...
%PYTHON% -m pip install -r requirements.txt -q

echo.
echo Iniciando Streamlit em segundo plano...
start "Streamlit" /min %PYTHON% -m streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port 8501 --server.maxUploadSize 1024

echo Aguardando Streamlit iniciar...
timeout /t 4 /nobreak >nul

echo.
echo Iniciando tunel ngrok...
echo O link publico aparecera abaixo. Compartilhe com o fiscal externo.
echo Para encerrar, feche esta janela (Ctrl+C).
echo.
echo ============================================

ngrok http 8501

pause
