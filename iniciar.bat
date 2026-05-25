@echo off
chcp 65001 >nul
title Maravilinda — Servidor
color 0D

echo.
echo  ╔══════════════════════════════════════╗
echo  ║        MARAVILINDA E-COMMERCE        ║
echo  ║         Iniciando servidor...        ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado. Instale em python.org
    pause
    exit /b 1
)

:: Cria ambiente virtual se nao existir
if not exist "venv\" (
    echo  [1/4] Criando ambiente virtual...
    python -m venv venv
)

:: Ativa ambiente virtual
call venv\Scripts\activate.bat

:: Instala dependencias
echo  [2/4] Instalando dependencias...
pip install -r requirements.txt -q

:: Aplica migrações
echo  [3/4] Aplicando migrações...
python manage.py migrate --run-syncdb -q
python manage.py init_db

:: Inicia servidor
echo  [4/4] Iniciando servidor...
echo.
echo  ✓ Loja:   http://localhost:8000
echo  ✓ Admin:  http://localhost:8000/admin
echo  ✓ Login admin: admin@maravilinda.com / Admin@2024!
echo.
echo  Pressione CTRL+C para parar o servidor.
echo.

python manage.py runserver 0.0.0.0:8000

pause
