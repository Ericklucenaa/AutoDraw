@echo off
rem ---------------------------------------------------------------
rem  Gera o executavel standalone dist\AutoDraw.exe
rem
rem  Depois de compilar, o AutoDraw.bat passa a abrir o .exe
rem  automaticamente, e a pasta dist roda em qualquer Windows
rem  mesmo sem Python instalado.
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto :no_python

echo.
echo  ====================================================
echo   Compilando o AutoDraw (leva alguns minutos)
echo  ====================================================
echo.

%PY% -m pip install -r requirements-dev.txt
if errorlevel 1 goto :failed

rem Passe "pasta" como argumento para gerar uma pasta em vez de um
rem arquivo unico: abre bem mais rapido, porem sao varios arquivos.
%PY% build_exe.py %1
if errorlevel 1 goto :failed

echo.
echo  Pronto. Agora basta dar duplo clique em AutoDraw.bat
echo  ou abrir dist\AutoDraw.exe diretamente.
echo.
pause
exit /b 0

:no_python
echo.
echo   Python nao encontrado. Instale o Python 3.9 ou superior
echo   em https://www.python.org/downloads/windows/ marcando
echo   a opcao "Add Python to PATH".
echo.
pause
exit /b 1

:failed
echo.
echo   A compilacao falhou. A saida acima mostra o motivo.
echo.
pause
exit /b 1
