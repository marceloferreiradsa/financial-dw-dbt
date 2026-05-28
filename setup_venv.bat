@echo off
echo [1/5] Criando ambiente virtual...
python -m venv .venv

echo [2/5] Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo [3/5] Instalando dependencias Python...
pip install --upgrade pip
pip install -r requirements.txt

echo [4/5] Instalando pacotes dbt (dbt deps)...
cd dbt_project
dbt deps
cd ..

echo [5/5] Configurando pre-commit hooks...
pre-commit install

echo.
echo Setup concluido!
echo Para ativar o ambiente manualmente: .venv\Scripts\activate.bat
echo Para configurar o profiles.yml:     copy dbt_project\profiles.yml %USERPROFILE%\.dbt\profiles.yml
