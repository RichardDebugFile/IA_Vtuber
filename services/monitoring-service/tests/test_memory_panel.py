"""
Tests del panel de Memoria & Feedback (Tarea 2.1).

Dos grupos:
  - TestMemoryHtmlFile      → valida el archivo HTML sin necesitar servicio
  - TestMonitoringNavLink   → valida el link en monitoring.html
  - TestMemoryRoute         → valida la ruta /memory (requiere servicio corriendo)

Ejecutar:
  cd services/monitoring-service
  python -m pytest tests/test_memory_panel.py -v

  # Solo tests que no necesitan servicio:
  python -m pytest tests/test_memory_panel.py -v -k "not TestMemoryRoute"
"""

import pytest
from pathlib import Path
from html.parser import HTMLParser

STATIC_DIR = Path(__file__).parent.parent / "src" / "static"
MEMORY_HTML = STATIC_DIR / "memory.html"
MONITORING_HTML = STATIC_DIR / "monitoring.html"
MEMORY_SERVICE_URL = "http://127.0.0.1:8820"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de parsing HTML
# ─────────────────────────────────────────────────────────────────────────────

def html_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class _TagCollector(HTMLParser):
    """Recopila todos los IDs, clases, hrefs y texto encontrados."""

    def __init__(self):
        super().__init__()
        self.ids:    list[str] = []
        self.hrefs:  list[str] = []
        self.texts:  list[str] = []
        self._current_data: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if "id"   in attrs_dict: self.ids.append(attrs_dict["id"])
        if "href" in attrs_dict: self.hrefs.append(attrs_dict["href"])

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.texts.append(stripped)

    def parse(self, html: str) -> "_TagCollector":
        self.feed(html)
        return self


# ─────────────────────────────────────────────────────────────────────────────
# TestMemoryHtmlFile — tests del archivo memory.html (sin servicio)
# ─────────────────────────────────────────────────────────────────────────────

class TestMemoryHtmlFile:
    """Valida la estructura y contenido de memory.html sin necesitar el servicio."""

    def test_file_exists(self):
        assert MEMORY_HTML.exists(), f"No existe: {MEMORY_HTML}"

    def test_file_is_not_empty(self):
        assert MEMORY_HTML.stat().st_size > 5000, "El archivo HTML es demasiado pequeño"

    def test_html_parses_without_errors(self):
        """El HTML debe ser parseable sin lanzar excepciones."""
        collector = _TagCollector()
        collector.parse(html_text(MEMORY_HTML))  # no debe lanzar excepción
        assert len(collector.ids) > 0

    def test_memory_service_url_constant_declared(self):
        """El JS debe declarar MEMORY_URL apuntando al memory-service (8820)."""
        html = html_text(MEMORY_HTML)
        assert f"MEMORY_URL = '{MEMORY_SERVICE_URL}'" in html or \
               f'MEMORY_URL = "{MEMORY_SERVICE_URL}"' in html, \
            f"No se encontró MEMORY_URL = '{MEMORY_SERVICE_URL}' en el JS"

    # ── Métricas (4 cards) ────────────────────────────────────────────────────

    def test_has_metric_total_interactions(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "metricTotal" in collector.ids, "Falta el elemento #metricTotal"

    def test_has_metric_avg_quality(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "metricAvgQuality" in collector.ids

    def test_has_metric_training_ready(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "metricTrainingReady" in collector.ids

    def test_has_metric_week(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "metricWeek" in collector.ids

    # ── Filtros ───────────────────────────────────────────────────────────────

    def test_has_days_filter(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "daysFilter" in collector.ids

    def test_has_limit_filter(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "limitFilter" in collector.ids

    def test_has_quality_filter(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "qualityFilter" in collector.ids

    # ── Tabla de interacciones ────────────────────────────────────────────────

    def test_has_table_container(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "tableContainer" in collector.ids

    # ── Modal de corrección ───────────────────────────────────────────────────

    def test_has_correction_modal(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "correctionModal" in collector.ids

    def test_correction_modal_has_input_text_field(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "modalInputText" in collector.ids

    def test_correction_modal_has_output_text_field(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "modalOutputText" in collector.ids

    def test_correction_modal_has_textarea(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "correctedResponse" in collector.ids

    # ── Modal de texto completo ───────────────────────────────────────────────

    def test_has_text_modal(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "textModal" in collector.ids

    # ── Funciones JS requeridas ───────────────────────────────────────────────

    def test_has_load_interactions_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function loadInteractions" in html or \
               "function loadInteractions" in html

    def test_has_send_feedback_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function sendFeedback" in html or \
               "function sendFeedback" in html

    def test_has_submit_correction_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function submitCorrection" in html or \
               "function submitCorrection" in html

    def test_has_open_correction_function(self):
        html = html_text(MEMORY_HTML)
        assert "function openCorrection" in html

    def test_has_load_stats_function(self):
        html = html_text(MEMORY_HTML)
        assert "async function loadStats" in html or \
               "function loadStats" in html

    # ── Llamadas a endpoints de memory-service ────────────────────────────────

    def test_calls_interactions_recent_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/interactions/recent" in html

    def test_calls_feedback_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/feedback" in html

    def test_calls_quality_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/interactions/" in html and "/quality" in html

    def test_calls_stats_endpoint(self):
        html = html_text(MEMORY_HTML)
        assert "/stats" in html

    # ── Navegación interna ────────────────────────────────────────────────────

    def test_nav_has_link_to_monitoring(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "/monitoring" in collector.hrefs, "Falta el link al dashboard principal"

    def test_nav_has_link_to_logs(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "/logs" in collector.hrefs

    def test_nav_active_link_is_memory(self):
        html = html_text(MEMORY_HTML)
        assert 'href="/memory"' in html and 'class="active"' in html

    # ── Estado del servicio ───────────────────────────────────────────────────

    def test_has_memory_status_dot(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "memoryStatusDot" in collector.ids

    def test_has_memory_status_text(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "memoryStatusText" in collector.ids

    # ── Toast de notificaciones ───────────────────────────────────────────────

    def test_has_toast_element(self):
        collector = _TagCollector().parse(html_text(MEMORY_HTML))
        assert "toast" in collector.ids

    def test_has_toast_function(self):
        html = html_text(MEMORY_HTML)
        assert "function toast" in html


# ─────────────────────────────────────────────────────────────────────────────
# TestMonitoringNavLink — valida que monitoring.html tiene el link /memory
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitoringNavLink:
    """Verifica que el dashboard principal tiene el link 🧠 Memoria."""

    def test_monitoring_html_exists(self):
        assert MONITORING_HTML.exists()

    def test_monitoring_html_has_memory_link(self):
        collector = _TagCollector().parse(html_text(MONITORING_HTML))
        assert "/memory" in collector.hrefs, \
            "El dashboard principal no tiene link a /memory"

    def test_memory_link_has_brain_emoji(self):
        html = html_text(MONITORING_HTML)
        assert "🧠" in html and "/memory" in html


# ─────────────────────────────────────────────────────────────────────────────
# TestMemoryRoute — requiere monitoring-service corriendo en 8900
# ─────────────────────────────────────────────────────────────────────────────

class TestMemoryRoute:
    """Valida la ruta /memory del monitoring-service (requiere servicio activo)."""

    @pytest.fixture(autouse=True)
    def skip_if_offline(self, monitoring_available):
        if not monitoring_available:
            pytest.skip("monitoring-service no está corriendo en 8900")

    def test_memory_route_returns_200(self, http_client):
        r = http_client.get("/memory")
        assert r.status_code == 200

    def test_memory_route_content_type_is_html(self, http_client):
        r = http_client.get("/memory")
        assert "text/html" in r.headers.get("content-type", "")

    def test_memory_route_body_is_not_empty(self, http_client):
        r = http_client.get("/memory")
        assert len(r.content) > 5000

    def test_memory_route_contains_memory_url(self, http_client):
        r = http_client.get("/memory")
        assert MEMORY_SERVICE_URL in r.text

    def test_memory_route_contains_title(self, http_client):
        r = http_client.get("/memory")
        assert "Memoria" in r.text and "Feedback" in r.text

    def test_health_route_still_works(self, http_client):
        """Verificar que añadir /memory no rompió el health check existente."""
        r = http_client.get("/health")
        assert r.status_code == 200

    def test_monitoring_route_still_works(self, http_client):
        """Verificar que las rutas existentes siguen funcionando."""
        r = http_client.get("/monitoring")
        assert r.status_code == 200

    def test_logs_route_still_works(self, http_client):
        r = http_client.get("/logs")
        assert r.status_code == 200
