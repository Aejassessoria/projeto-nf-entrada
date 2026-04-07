@echo off
chcp 65001 >nul
echo ============================================
echo   Classificador NF Entrada - Iniciando...
echo ============================================

REM Tenta localizar Python (py launcher ou python)
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

echo.
echo [ERRO] Python nao encontrado.
echo.
echo Por favor, instale o Python em:
echo https://www.python.org/downloads/
echo.
echo IMPORTANTE: marque "Add Python to PATH" durante a instalacao!
echo.
pause
exit /b 1

:found
echo Python encontrado!
echo.

REM Instala dependencias se necessario
echo Verificando dependencias...
%PYTHON% -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo Dependencias OK!
echo.
echo Iniciando aplicacao...
echo Acesse: http://localhost:8501
echo.
echo Para encerrar, feche esta janela ou pressione Ctrl+C
echo.

%PYTHON% -m streamlit run app.py --server.headless false --server.maxUploadSize 1024

pause
