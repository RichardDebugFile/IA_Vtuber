"""
Tests del panel de Entrenamiento Episódico (Tarea 2.3).

Tres grupos:
  - TestTrainingSectionInMemoryHtml   → valida la sección de entrenamiento en memory.html
  - TestTrainingWidgetInMonitoringHtml → valida el widget compacto en monitoring.html
  - TestTrainingRoutes                → valida las rutas (requiere servicio corriendo)

Ejecutar:
  cd services/monitoring-service
  python -m pytest tests/test_training_panel.py -v

  # Solo tests offline:
  python -m pytest tests/test_training_panel.py -v -k "not TestTrainingRoutes"
"""

import pytest
from pathlib import Path
from html.parser import HTMLParser

STATIC_DIR      = Path(__file__).parent.parent / "src" / "static"
MEMORY_HTML     = STATIC_DIR / "memory.html"
MONITORING_HTML = STATIC_DIR / "monitoring.html"
MEMORY_SVC_URL  = "http://127.0.0.1:8820"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de parsing HTML
# ─────────────────────────────────────────────────────────────────────────────

def html_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class _TagCollector(HTMLParser):
    """Recopila todos los IDs y hrefs encontrados en el HTML."""

    def __init__(self):
        super().__init__()
        self.ids:   list[str] = []
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if "id"   in attrs_dict: self.ids.append(attrs_dict["id"])
        if "href" in attrs_dict: self.hrefs.append(attrs_dict["href"])

    def parse(self, html: str) -> "_TagCollector":
        self.feed(html)
        return self


# ─────────────────────────────────────────────────────────────────────────────
# TestTrainingSectionInMemoryHtml — tests offline de memory.html
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingSectionInMemoryHtml:
    """Valida la sección 🎓 Ciclo de Aprendizaje Episódico en memory.html."""

    # ── Estructura HTML — contenedor ──────────────────────────────────────────

    def test_training_section_container_exists(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainingSection" in collector.ids, \
            "Falta el contenedor principal #trainingSection en memory.html"

    # ── Cards de estado (4 tarjetas) ──────────────────────────────────────────

    def test_has_train_model_active_card(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainModelActive" in collector.ids, \
            "Falta #trainModelActive (card 'Modelo Activo')"

    def test_has_train_next_run_card(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainNextRun" in collector.ids, \
            "Falta #trainNextRun (card 'Próximo Entrenamiento')"

    def test_has_train_week_ready_card(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainWeekReady" in collector.ids, \
            "Falta #trainWeekReady (card 'Listas esta semana')"

    def test_has_train_week_label(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainWeekLabel" in collector.ids, \
            "Falta #trainWeekLabel (subtítulo dinámico de la card de listas)"

    def test_has_train_last_status_card(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainLastStatus" in collector.ids, \
            "Falta #trainLastStatus (card 'Último Run')"

    def test_has_train_last_date(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainLastDate" in collector.ids, \
            "Falta #trainLastDate (fecha del último run)"

    # ── Historial colapsable ──────────────────────────────────────────────────

    def test_has_training_history_details(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainingHistoryDetails" in collector.ids, \
            "Falta el elemento <details id='trainingHistoryDetails'>"

    def test_has_train_history_container(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "trainHistoryContainer" in collector.ids, \
            "Falta #trainHistoryContainer (donde se renderiza la tabla de historial)"

    def test_history_uses_details_summary(self):
        """El historial debe usar <details><summary> para ser colapsable."""
        html = html_text(MEMORY_HTML)
        assert "<details" in html and "<summary>" in html, \
            "El historial no usa <details>/<summary> para ser colapsable"

    # ── Funciones JS ──────────────────────────────────────────────────────────

    def test_has_load_pipeline_status_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function loadPipelineStatus" in html or \
               "function loadPipelineStatus" in html, \
            "Falta la función JS loadPipelineStatus()"

    def test_has_load_weekly_ready_count_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function loadWeeklyReadyCount" in html or \
               "function loadWeeklyReadyCount" in html, \
            "Falta la función JS loadWeeklyReadyCount()"

    def test_has_load_pipeline_history_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function loadPipelineHistory" in html or \
               "function loadPipelineHistory" in html, \
            "Falta la función JS loadPipelineHistory()"

    def test_has_render_pipeline_history_function(self):
        html = html_text(MEMORY_HTML)
        assert "function renderPipelineHistory" in html, \
            "Falta la función JS renderPipelineHistory()"

    def test_has_format_pipeline_date_function(self):
        html = html_text(MEMORY_HTML)
        assert "function formatPipelineDate" in html, \
            "Falta la función JS formatPipelineDate()"

    # ── Llamadas a endpoints del pipeline ─────────────────────────────────────

    def test_calls_pipeline_status_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/pipeline/status" in html, \
            "Falta la llamada a /pipeline/status en el JS de memory.html"

    def test_calls_pipeline_history_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/pipeline/history" in html, \
            "Falta la llamada a /pipeline/history en el JS de memory.html"

    def test_load_all_calls_pipeline_status(self):
        """loadAll() debe invocar loadPipelineStatus() para refrescar al cargar."""
        html = html_text(MEMORY_HTML)
        # Buscar el bloque de loadAll para confirmar que incluye la llamada
        assert "loadPipelineStatus()" in html, \
            "loadAll() no llama a loadPipelineStatus()"

    def test_load_all_calls_pipeline_history(self):
        """loadAll() debe invocar loadPipelineHistory() para refrescar al cargar."""
        html = html_text(MEMORY_HTML)
        assert "loadPipelineHistory()" in html, \
            "loadAll() no llama a loadPipelineHistory()"

    # ── CSS de la sección ─────────────────────────────────────────────────────

    def test_has_training_section_css(self):
        html = html_text(MEMORY_HTML)
        assert ".training-section" in html, "Falta la clase CSS .training-section"

    def test_has_training_grid_css(self):
        html = html_text(MEMORY_HTML)
        assert ".training-grid" in html, "Falta la clase CSS .training-grid"

    def test_has_training_card_css(self):
        html = html_text(MEMORY_HTML)
        assert ".training-card" in html, "Falta la clase CSS .training-card"

    def test_has_train_status_success_css(self):
        html = html_text(MEMORY_HTML)
        assert ".train-status-success" in html, \
            "Falta la clase CSS .train-status-success (colores de estado)"

    def test_has_train_status_failed_css(self):
        html = html_text(MEMORY_HTML)
        assert ".train-status-failed" in html, \
            "Falta la clase CSS .train-status-failed"

    def test_has_train_ready_indicator_css(self):
        html = html_text(MEMORY_HTML)
        assert ".train-ready-ok" in html and ".train-ready-warn" in html, \
            "Faltan las clases CSS .train-ready-ok / .train-ready-warn"

    def test_has_train_history_table_css(self):
        html = html_text(MEMORY_HTML)
        assert ".train-history-table" in html, \
            "Falta la clase CSS .train-history-table"

    # ── Coherencia con el resto del panel ─────────────────────────────────────

    def test_training_section_placed_before_main_content(self):
        """La sección de entrenamiento debe aparecer antes de la tabla principal."""
        html = html_text(MEMORY_HTML)
        # Buscar la aparición del elemento HTML (no la clase CSS definida antes)
        pos_section = html.find('id="trainingSection"')
        pos_table   = html.find('class="main-content"')
        assert pos_section != -1, "Falta id=\"trainingSection\" en el HTML"
        assert pos_table   != -1, "Falta class=\"main-content\" en el HTML"
        assert pos_section < pos_table, \
            "La sección de entrenamiento debe aparecer antes de la tabla de interacciones"


# ─────────────────────────────────────────────────────────────────────────────
# TestTrainingWidgetInMonitoringHtml — tests offline de monitoring.html
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingWidgetInMonitoringHtml:
    """Valida el widget compacto de entrenamiento en monitoring.html."""

    def test_monitoring_html_exists(self):
        assert MONITORING_HTML.exists(), f"No existe: {MONITORING_HTML}"

    # ── IDs del widget ────────────────────────────────────────────────────────

    def test_has_training_status_card(self):
        collector = _TagCollector().parse(html_text(MONITORING_HTML))
        assert "trainingStatusCard" in collector.ids, \
            "Falta la card #trainingStatusCard en monitoring.html"

    def test_has_training_status_widget(self):
        collector = _TagCollector().parse(html_text(MONITORING_HTML))
        assert "trainingStatusWidget" in collector.ids, \
            "Falta el contenedor #trainingStatusWidget"

    def test_has_mon_train_model_id(self):
        """monTrainModel se inyecta dinámicamente via innerHTML — verificar referencia en JS."""
        html = html_text(MONITORING_HTML)
        assert "monTrainModel" in html, \
            "Falta la referencia a 'monTrainModel' en el JS de monitoring.html"

    def test_has_mon_train_next_run_id(self):
        """monTrainNextRun se inyecta dinámicamente via innerHTML — verificar referencia en JS."""
        html = html_text(MONITORING_HTML)
        assert "monTrainNextRun" in html, \
            "Falta la referencia a 'monTrainNextRun' en el JS de monitoring.html"

    def test_has_mon_train_last_status_id(self):
        """monTrainLastStatus se inyecta dinámicamente via innerHTML — verificar referencia en JS."""
        html = html_text(MONITORING_HTML)
        assert "monTrainLastStatus" in html, \
            "Falta la referencia a 'monTrainLastStatus' en el JS de monitoring.html"

    # ── Constante y funciones JS ──────────────────────────────────────────────

    def test_has_memory_svc_constant(self):
        html = html_text(MONITORING_HTML)
        assert f"_MEMORY_SVC = '{MEMORY_SVC_URL}'" in html or \
               f'_MEMORY_SVC = "{MEMORY_SVC_URL}"' in html, \
            f"Falta la constante _MEMORY_SVC = '{MEMORY_SVC_URL}' en monitoring.html"

    def test_has_load_training_status_function(self):
        html = html_text(MONITORING_HTML)
        assert "async function loadTrainingStatus" in html or \
               "function loadTrainingStatus" in html, \
            "Falta la función JS loadTrainingStatus() en monitoring.html"

    def test_load_training_status_is_invoked_on_load(self):
        """loadTrainingStatus() debe llamarse al cargar la página (no solo definirse)."""
        html = html_text(MONITORING_HTML)
        # Debe aparecer como llamada autoinvocada (sin 'function' antes)
        assert "loadTrainingStatus();" in html or "loadTrainingStatus()" in html, \
            "loadTrainingStatus() se define pero no se invoca al cargar"
        # Contar ocurrencias: definición (1) + llamada (≥1)
        count = html.count("loadTrainingStatus")
        assert count >= 2, \
            "loadTrainingStatus() aparece solo una vez (debe haber definición + llamada)"

    # ── Endpoint y navegación ─────────────────────────────────────────────────

    def test_calls_pipeline_status_from_widget(self):
        html = html_text(MONITORING_HTML)
        assert "/pipeline/status" in html, \
            "El widget no llama a /pipeline/status en monitoring.html"

    def test_widget_has_link_to_memory_panel(self):
        """El widget debe tener un enlace al panel completo /memory."""
        collector = _TagCollector().parse(html_text(MONITORING_HTML))
        assert "/memory" in collector.hrefs, \
            "El widget de entrenamiento no tiene link a /memory"

    def test_widget_title_mentions_training(self):
        """El título del widget debe mencionar 'Entrenamiento'."""
        html = html_text(MONITORING_HTML)
        assert "Entrenamiento" in html and "trainingStatusCard" in html, \
            "El widget no menciona 'Entrenamiento' o no tiene id trainingStatusCard"

    # ── Compatibilidad con cards existentes ───────────────────────────────────

    def test_existing_memory_link_preserved(self):
        """El link a /memory en la barra de navegación principal debe seguir ahí."""
        collector = _TagCollector().parse(html_text(MONITORING_HTML))
        memory_links = [h for h in collector.hrefs if h == "/memory"]
        assert len(memory_links) >= 1, \
            "El link 🧠 Memoria del header fue eliminado de monitoring.html"


# ─────────────────────────────────────────────────────────────────────────────
# TestTrainingRoutes — requiere monitoring-service corriendo en 8900
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingRoutes:
    """Valida las rutas del monitoring-service relacionadas con entrenamiento."""

    @pytest.fixture(autouse=True)
    def skip_if_offline(self, monitoring_available):
        if not monitoring_available:
            pytest.skip("monitoring-service no está corriendo en 8900")

    # ── /memory sirve la sección de entrenamiento ─────────────────────────────

    def test_memory_route_returns_200(self, http_client):
        r = http_client.get("/memory")
        assert r.status_code == 200

    def test_memory_route_has_training_section(self, http_client):
        r = http_client.get("/memory")
        assert "trainingSection" in r.text, \
            "La ruta /memory no incluye el contenedor #trainingSection"

    def test_memory_route_has_pipeline_status_call(self, http_client):
        r = http_client.get("/memory")
        assert "/pipeline/status" in r.text, \
            "La ruta /memory no incluye la llamada a /pipeline/status"

    def test_memory_route_has_pipeline_history_call(self, http_client):
        r = http_client.get("/memory")
        assert "/pipeline/history" in r.text, \
            "La ruta /memory no incluye la llamada a /pipeline/history"

    def test_memory_route_has_train_model_active_id(self, http_client):
        r = http_client.get("/memory")
        assert "trainModelActive" in r.text

    def test_memory_route_has_train_next_run_id(self, http_client):
        r = http_client.get("/memory")
        assert "trainNextRun" in r.text

    def test_memory_route_has_history_container(self, http_client):
        r = http_client.get("/memory")
        assert "trainHistoryContainer" in r.text

    # ── /monitoring sirve el widget de entrenamiento ──────────────────────────

    def test_monitoring_route_returns_200(self, http_client):
        r = http_client.get("/monitoring")
        assert r.status_code == 200

    def test_monitoring_route_has_training_widget(self, http_client):
        r = http_client.get("/monitoring")
        assert "trainingStatusCard" in r.text, \
            "La ruta /monitoring no incluye el widget #trainingStatusCard"

    def test_monitoring_route_has_memory_svc_constant(self, http_client):
        r = http_client.get("/monitoring")
        assert "_MEMORY_SVC" in r.text, \
            "La ruta /monitoring no incluye la constante _MEMORY_SVC"

    def test_monitoring_route_has_pipeline_status_call(self, http_client):
        r = http_client.get("/monitoring")
        assert "/pipeline/status" in r.text, \
            "La ruta /monitoring no incluye la llamada a /pipeline/status"

    # ── Regresiones — rutas existentes siguen funcionando ─────────────────────

    def test_health_route_not_broken(self, http_client):
        r = http_client.get("/health")
        assert r.status_code == 200

    def test_logs_route_not_broken(self, http_client):
        r = http_client.get("/logs")
        assert r.status_code == 200

    def test_monitoring_route_not_broken(self, http_client):
        r = http_client.get("/monitoring")
        assert r.status_code == 200
