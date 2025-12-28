# ====== Config ======
PY ?= python
PIDS := .pids
LOGS := .logs

# Comandos por servicio
GW_CMD := $(PY) -m uvicorn src.main:app --host 127.0.0.1 --port 8765 --app-dir src
CV_CMD := $(PY) -m uvicorn src.server:app --host 127.0.0.1 --port 8801 --app-dir src
DESKTOP_CMD := $(PY) apps/desktop-pet-qt/run_gui.py

# ====== Helpers ======
define ENSURE_DIRS
$(PY) -c "import os; os.makedirs('$(PIDS)', exist_ok=True); os.makedirs('$(LOGS)', exist_ok=True)"
endef

.PHONY: help install install-gateway install-conversation \
        gateway-up gateway-down conversation-up conversation-down \
        desktop-up desktop-down up down all-up all-down \
        test test-unit test-integration test-e2e test-all \
        test-coverage test-coverage-html test-service clean-test

help:
	@echo "Comandos de Servicios:"
	@echo "  make install                -> instala deps backend (gateway + conversation)"
	@echo "  make gateway-up             -> inicia gateway en background"
	@echo "  make gateway-down           -> detiene gateway"
	@echo "  make conversation-up        -> inicia conversation en background"
	@echo "  make conversation-down      -> detiene conversation"
	@echo "  make up                     -> inicia ambos microservicios"
	@echo "  make down                   -> detiene ambos microservicios"
	@echo "  make desktop-up             -> (opcional) inicia la GUI QT"
	@echo "  make desktop-down           -> cierra la GUI (si se lanzó con run_bg.py)"
	@echo "  make all-up                 -> gateway + conversation + GUI"
	@echo "  make all-down               -> detiene todo"
	@echo ""
	@echo "Comandos de Testing:"
	@echo "  make test                   -> ejecuta tests unitarios (rápido)"
	@echo "  make test-unit              -> ejecuta solo tests unitarios"
	@echo "  make test-integration       -> ejecuta tests de integración"
	@echo "  make test-e2e               -> ejecuta tests end-to-end"
	@echo "  make test-all               -> ejecuta todos los tests"
	@echo "  make test-coverage          -> ejecuta tests con reporte de cobertura"
	@echo "  make test-coverage-html     -> genera reporte HTML de cobertura"
	@echo "  make test-service SERVICE=<name> -> ejecuta tests de un servicio específico"
	@echo "  make clean-test             -> limpia archivos de tests y coverage"

install: install-gateway install-conversation

install-gateway:
	cd services/gateway && \
	$(PY) -m pip install -U fastapi uvicorn pydantic python-dotenv

install-conversation:
	cd services/conversation && \
	$(PY) -m pip install -U fastapi uvicorn httpx pydantic python-dotenv

# ====== Gateway ======
gateway-up:
	@$(ENSURE_DIRS)
	$(PY) scripts/run_bg.py --pidfile $(PIDS)/gateway.pid --log $(LOGS)/gateway.log --cwd "services/gateway" -- $(GW_CMD)
	@echo "gateway iniciado (pid en $(PIDS)/gateway.pid)"

gateway-down:
	-$(PY) scripts/kill_by_pidfile.py --pidfile $(PIDS)/gateway.pid

# ====== Conversation (IA) ======
conversation-up:
	@$(ENSURE_DIRS)
	$(PY) scripts/run_bg.py --pidfile $(PIDS)/conversation.pid --log $(LOGS)/conversation.log --cwd "services/conversation" -- $(CV_CMD)
	@echo "conversation iniciado (pid en $(PIDS)/conversation.pid)"

conversation-down:
	-$(PY) scripts/kill_by_pidfile.py --pidfile $(PIDS)/conversation.pid

# ====== Desktop (opcional) ======
desktop-up:
	@$(ENSURE_DIRS)
	$(PY) scripts/run_bg.py --pidfile $(PIDS)/desktop.pid --log $(LOGS)/desktop.log --cwd "." -- $(DESKTOP_CMD)
	@echo "desktop iniciado (pid en $(PIDS)/desktop.pid)"

desktop-down:
	-$(PY) scripts/kill_by_pidfile.py --pidfile $(PIDS)/desktop.pid

# ====== Agrupados ======
up: gateway-up conversation-up
down: conversation-down gateway-down

all-up: up desktop-up
all-down: desktop-down down

# ====== Testing ======
test: test-unit

test-unit:
	@echo "Ejecutando tests unitarios..."
	$(PY) -m pytest -m unit -v --color=yes

test-integration:
	@echo "Ejecutando tests de integración..."
	$(PY) -m pytest -m integration -v --color=yes

test-e2e:
	@echo "Ejecutando tests end-to-end..."
	$(PY) -m pytest -m e2e -v --color=yes

test-all:
	@echo "Ejecutando todos los tests..."
	$(PY) -m pytest -v --color=yes

test-coverage:
	@echo "Ejecutando tests con cobertura..."
	$(PY) -m pytest --cov --cov-report=term-missing --cov-report=xml -v

test-coverage-html:
	@echo "Generando reporte HTML de cobertura..."
	$(PY) -m pytest --cov --cov-report=html --cov-report=term-missing -v
	@echo "Reporte generado en htmlcov/index.html"

test-service:
ifndef SERVICE
	@echo "Error: Especifica SERVICE=<gateway|conversation|tts|assistant>"
	@exit 1
endif
	@echo "Ejecutando tests para $(SERVICE)..."
	$(PY) -m pytest services/$(SERVICE)/tests -v --color=yes

clean-test:
	@echo "Limpiando archivos de tests..."
	-rm -rf .pytest_cache
	-rm -rf htmlcov
	-rm -f coverage.xml
	-rm -f .coverage
	-find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	-find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Limpieza completada"
