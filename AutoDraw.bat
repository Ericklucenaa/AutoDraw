@echo off
rem ---------------------------------------------------------------
rem  AutoDraw - duplo clique para abrir
rem
rem  Prefere o executavel compilado (dist\AutoDraw.exe) se existir;
rem  caso contrario roda pelo codigo fonte com o Python instalado.
rem
rem  Mensagens sem acentos de proposito: um .bat e lido na codepage
rem  do console, que varia conforme o idioma do Windows.
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

if exist "dist\AutoDraw\AutoDraw.exe" (
    start "AutoDraw" "dist\AutoDraw\AutoDraw.exe"
    exit /b 0
)
if exist "dist\AutoDraw.exe" (
    start "AutoDraw" "dist\AutoDraw.exe"
    exit /b 0
)

rem --- 1. interpretador de console, usado para checar dependencias ---
set "PY="
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if not defined PY goto :try_python
goto :have_py

:try_python
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY goto :no_python

:have_py
%PY% -c "import sys" >nul 2>&1
if errorlevel 1 goto :no_python

rem --- 2. interpretador sem console, para abrir sem janela preta ---
rem  Cada candidato e validado antes do uso: "start" com um comando
rem  invalido retorna 0 e nao abre nada, entao um nome errado aqui
rem  faria o duplo clique parecer nao fazer absolutamente nada.
rem  (O launcher sem console e o pyw.exe; "py -3w" NAO existe e falha
rem  com "No suitable Python runtime found".)
set "PYW="

rem  O caminho mais confiavel: perguntar ao proprio interpretador onde
rem  fica o pythonw.exe dele. Nao depende do PATH nem de qual launcher
rem  esta instalado, e funciona dentro de um ambiente virtual.
for /f "usebackq delims=" %%i in (`%PY% -c "import os,sys;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul`) do set "PYW_EXE=%%i"
if defined PYW_EXE if exist "%PYW_EXE%" set "PYW="%PYW_EXE%""
if defined PYW goto :check_deps

pyw -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYW=pyw -3"
if defined PYW goto :check_deps

pythonw -c "import sys" >nul 2>&1
if not errorlevel 1 set "PYW=pythonw"
if defined PYW goto :check_deps

rem Sem interpretador sem console: usa o de console mesmo. Abre uma
rem janela preta junto, mas funciona e mostra os erros na tela.
set "PYW=%PY%"

:check_deps
%PY% -c "import PySide6, cv2, numpy, PIL, pynput" >nul 2>&1
if not errorlevel 1 goto :launch

echo.
echo  ====================================================
echo   Primeira execucao: instalando as dependencias...
echo   Isso leva alguns minutos e acontece apenas uma vez.
echo  ====================================================
echo.
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :dep_failed

%PY% -c "import PySide6, cv2, numpy, PIL, pynput" >nul 2>&1
if errorlevel 1 goto :dep_failed

echo.
echo  Dependencias instaladas. Abrindo o AutoDraw...
echo.

:launch
rem Sem console, os erros nao aparecem na tela: vao para o log em
rem %USERPROFILE%\.autodraw\autodraw.log
start "AutoDraw" %PYW% "%~dp0main.py"
exit /b 0

:no_python
echo.
echo  ====================================================
echo   Python nao encontrado neste computador.
echo  ====================================================
echo.
echo   Instale o Python 3.9 ou superior em:
echo     https://www.python.org/downloads/windows/
echo.
echo   IMPORTANTE: marque a opcao "Add Python to PATH"
echo   durante a instalacao.
echo.
echo   Alternativa: gere o executavel standalone rodando
echo   "Compilar-EXE.bat" em um computador que tenha
echo   Python, e copie a pasta dist para ca.
echo.
pause
exit /b 1

:dep_failed
echo.
echo  ====================================================
echo   Falha ao instalar as dependencias.
echo  ====================================================
echo.
echo   Tente manualmente em um terminal nesta pasta:
echo     %PY% -m pip install -r requirements.txt
echo.
pause
exit /b 1
