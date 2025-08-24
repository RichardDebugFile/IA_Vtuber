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
        desktop-up desktop-down up down all-up all-down

help:
	@echo "Comandos:"
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
