"""
Tests del panel de Personalidad en memory.html (Fase 3.3).

Grupo único (offline, sin servicios):
  TestPersonalityPanelInMemoryHtml  → valida el HTML/JS de memory.html

Ejecutar:
  cd services/monitoring-service
  python -m pytest tests/test_personality_panel.py -v
"""

from pathlib import Path
from html.parser import HTMLParser

STATIC_DIR  = Path(__file__).parent.parent / "src" / "static"
MEMORY_HTML = STATIC_DIR / "memory.html"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def html_text() -> str:
    return MEMORY_HTML.read_text(encoding="utf-8")


class _IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if "id" in attrs_dict:
            self.ids.append(attrs_dict["id"])

    def parse(self, html: str) -> "_IdCollector":
        self.feed(html)
        return self


# ─────────────────────────────────────────────────────────────────────────────
# TestPersonalityPanelInMemoryHtml — offline
# ─────────────────────────────────────────────────────────────────────────────

class TestPersonalityPanelInMemoryHtml:
    """Valida que memory.html tiene el panel de personalidad correctamente implementado."""

    # ── Elementos HTML ────────────────────────────────────────────────────────

    def test_file_exists(self):
        assert MEMORY_HTML.exists(), f"No existe: {MEMORY_HTML}"

    def test_has_personality_section_id(self):
        collector = _IdCollector().parse(html_text())
        assert "personalitySection" in collector.ids, "Falta #personalitySection"

    def test_has_personality_content_id(self):
        collector = _IdCollector().parse(html_text())
        assert "personalityContent" in collector.ids, "Falta #personalityContent"

    def test_has_personality_timestamp_id(self):
        collector = _IdCollector().parse(html_text())
        assert "personalityTs" in collector.ids, "Falta #personalityTs"

    def test_personality_section_has_pink_border(self):
        html = html_text()
        assert "personalitySection" in html and "e91e63" in html, (
            "La sección de personalidad debe tener borde rosa (#e91e63)"
        )

    def test_personality_section_has_title(self):
        html = html_text()
        assert "Evolución de Personalidad" in html

    # ── Funciones JS ──────────────────────────────────────────────────────────

    def test_has_load_personality_metrics_function(self):
        html = html_text()
        assert "async function loadPersonalityMetrics" in html or \
               "function loadPersonalityMetrics" in html, \
            "Falta la función loadPersonalityMetrics en el JS"

    def test_calls_personality_metrics_latest_endpoint(self):
        html = html_text()
        assert "/personality/metrics/latest" in html, \
            "El JS debe llamar al endpoint /personality/metrics/latest"

    def test_personality_metrics_in_load_all(self):
        html = html_text()
        # Buscar que dentro de loadAll() se llama a loadPersonalityMetrics
        assert "loadPersonalityMetrics()" in html, \
            "loadAll() debe incluir loadPersonalityMetrics()"

    def test_has_set_interval_for_personality(self):
        html = html_text()
        assert "setInterval(loadPersonalityMetrics" in html, \
            "Debe haber un setInterval para refrescar las métricas de personalidad"

    # ── Rasgos de personalidad ────────────────────────────────────────────────

    def test_renders_sarcasm_level(self):
        html = html_text()
        assert "sarcasm_level" in html

    def test_renders_friendliness(self):
        html = html_text()
        assert "friendliness" in html

    def test_renders_verbosity(self):
        html = html_text()
        assert "verbosity" in html

    def test_renders_technical_depth(self):
        html = html_text()
        assert "technical_depth" in html

    def test_renders_humor_frequency(self):
        html = html_text()
        assert "humor_frequency" in html

    # ── Integridad del HTML ───────────────────────────────────────────────────

    def test_html_parses_without_errors(self):
        """El HTML completo debe ser parseable sin excepciones."""
        collector = _IdCollector()
        collector.parse(html_text())
        assert len(collector.ids) > 0

    def test_training_section_still_present(self):
        """El panel de entrenamiento episódico no debe haber sido eliminado."""
        collector = _IdCollector().parse(html_text())
        assert "trainingSection" in collector.ids, \
            "El trainingSection no debe haberse eliminado al añadir personalitySection"

    # ── Botón "Calcular ahora" ─────────────────────────────────────────────────

    def test_has_compute_personality_button(self):
        """El panel debe tener el botón ⚙️ Calcular ahora para aprobación manual."""
        collector = _IdCollector().parse(html_text())
        assert "btnComputePersonality" in collector.ids, \
            "Falta #btnComputePersonality en el panel de personalidad"

    def test_has_compute_personality_function(self):
        """Debe existir la función JS computePersonality()."""
        html = html_text()
        assert "async function computePersonality" in html or \
               "function computePersonality" in html, \
            "Falta la función computePersonality en el JS"

    def test_compute_personality_calls_compute_endpoint(self):
        """computePersonality() debe llamar a POST /personality/compute."""
        html = html_text()
        assert "/personality/compute" in html, \
            "La función computePersonality debe llamar a /personality/compute"

    def test_compute_button_calls_compute_personality(self):
        """El botón Calcular ahora debe invocar computePersonality()."""
        html = html_text()
        assert "onclick=\"computePersonality()\"" in html or \
               "onclick='computePersonality()'" in html, \
            "El botón #btnComputePersonality debe invocar computePersonality()"

    def test_compute_personality_handles_422(self):
        """computePersonality() debe manejar 422 (muestras insuficientes)."""
        html = html_text()
        assert "422" in html, \
            "La función computePersonality debe manejar el status 422"


# ─────────────────────────────────────────────────────────────────────────────
# TestGuidePanelInMemoryHtml — panel de ayuda integrado
# ─────────────────────────────────────────────────────────────────────────────

class TestGuidePanelInMemoryHtml:
    """Verifica que memory.html tiene el panel de guía rápida correctamente implementado."""

    def test_guide_panel_exists(self):
        """Debe existir el panel colapsable de guía rápida."""
        html = html_text()
        assert "Guía rápida" in html, \
            "Falta el panel de guía rápida ('Guía rápida' no encontrado en HTML)"

    def test_guide_explains_semantic_search(self):
        """La guía debe explicar la búsqueda semántica."""
        html = html_text()
        assert "semántica" in html.lower() or "semántico" in html.lower(), \
            "La guía debe mencionar la búsqueda semántica"

    def test_guide_explains_personality_manual_step(self):
        """La guía debe indicar que el cálculo de personalidad es manual."""
        html = html_text()
        assert "manual" in html.lower(), \
            "La guía debe indicar que el cálculo de personalidad requiere aprobación manual"

    def test_guide_explains_delete(self):
        """La guía debe explicar cómo usar el borrado de interacciones."""
        html = html_text()
        assert "Eliminar interacciones" in html or "eliminar" in html.lower(), \
            "La guía debe explicar la eliminación de interacciones"

    def test_guide_mentions_irreversible(self):
        """La guía debe advertir que el borrado es irreversible."""
        html = html_text()
        assert "irreversible" in html.lower() or "permanente" in html.lower(), \
            "La guía debe advertir que el borrado es permanente/irreversible"

    def test_guide_explains_quality_scores(self):
        """La guía debe incluir información sobre los quality scores."""
        html = html_text()
        assert "quality" in html.lower(), \
            "La guía debe incluir una referencia a los quality scores"

    # ── Botón 🗑 de borrado ───────────────────────────────────────────────────

    def test_delete_interaction_function_exists(self):
        """Debe existir la función JS deleteInteraction()."""
        html = html_text()
        assert "async function deleteInteraction" in html or \
               "function deleteInteraction" in html, \
            "Falta la función deleteInteraction en el JS"

    def test_delete_calls_delete_http_method(self):
        """deleteInteraction() debe usar el método HTTP DELETE."""
        html = html_text()
        assert "method: 'DELETE'" in html or 'method: "DELETE"' in html, \
            "deleteInteraction debe usar el método HTTP DELETE"

    def test_delete_button_referenced_in_table(self):
        """El botón 🗑 debe referenciarse al menos 2 veces (render + updateRow)."""
        html = html_text()
        count = html.count("deleteInteraction")
        assert count >= 2, (
            f"deleteInteraction debe aparecer al menos 2 veces (render inicial + updateRow), "
            f"encontrado {count} veces"
        )

    def test_delete_asks_confirmation(self):
        """La función deleteInteraction debe pedir confirmación antes de borrar."""
        html = html_text()
        assert "confirm(" in html, \
            "deleteInteraction debe usar confirm() antes de eliminar"

    def test_delete_updates_local_list_on_success(self):
        """Tras el borrado, la lista local _interactions debe filtrarse."""
        html = html_text()
        assert "_interactions" in html and "filter" in html, \
            "deleteInteraction debe filtrar _interactions para eliminar el elemento borrado"
