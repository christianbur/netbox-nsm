"""Static asset/template checks for the Object Report sample pagination.

Scale-safe: reads the shipped template / JS / Python source files only, no DB
and no HTTP, so it runs as a ``SimpleTestCase`` and stays fast regardless of how
many objects exist. It guards the *wiring* between the server-rendered samples
template (``inc/object_report_samples.html``), the client-side pager
(``plugin_assets/js/object_report_samples.js``), and the server-side
``SAMPLE_PAGE_SIZE`` constant so the 50-per-page pagination cannot silently
regress.

Limitation: the actual paging *behaviour* (e.g. only one page of 50 rows visible
when more than 50 rows are present) is implemented in JavaScript and cannot be
executed here without a JS runtime (node). This test therefore asserts the
static contract that drives that behaviour — the ``data-page-size`` default of
50, the pager markup, the row markup the pager toggles, and the JS that hides
rows outside the current page and only reveals the pager when more than one page
exists. The DB-backed behavioural smoke test lives in
``test_object_report.ObjectReportViewTests.test_view_renders_sample_pager``.
"""

from pathlib import Path

from django.test import SimpleTestCase

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _samples_template() -> str:
    return (
        _PLUGIN_ROOT / "templates/netbox_nsm/inc/object_report_samples.html"
    ).read_text(encoding="utf-8")


def _samples_js() -> str:
    return (
        _PLUGIN_ROOT / "plugin_assets/js/object_report_samples.js"
    ).read_text(encoding="utf-8")


def _object_report_source() -> str:
    return (
        _PLUGIN_ROOT / "object_report/object_report.py"
    ).read_text(encoding="utf-8")


class ObjectReportSamplesTemplateTests(SimpleTestCase):
    def test_template_exposes_page_size_default_50(self):
        html = _samples_template()
        # The pager reads its page size from this attribute; the template must
        # default it to 50 so the JS pages in 50-row steps.
        self.assertIn('data-page-size="{{ page_size|default:50 }}"', html)

    def test_template_carries_total_count_for_capped_status(self):
        html = _samples_template()
        self.assertIn('data-total-count="{{ count }}"', html)

    def test_template_renders_paginatable_sample_rows(self):
        html = _samples_template()
        # One row per stored sample, with the class the pager shows/hides.
        self.assertIn('class="nsm-or-sample-row"', html)
        self.assertIn("{% for s in samples %}", html)

    def test_template_has_pager_markup_hidden_by_default(self):
        html = _samples_template()
        # Pager nav with prev/next/status; starts hidden (d-none) and is revealed
        # by the JS only when more than one page exists.
        self.assertIn("nsm-or-pager", html)
        self.assertIn("d-none", html)
        self.assertIn("nsm-or-pager-prev", html)
        self.assertIn("nsm-or-pager-next", html)
        self.assertIn("nsm-or-pager-status", html)

    def test_template_loads_pager_script(self):
        # The container the JS binds to.
        self.assertIn('class="nsm-or-samples"', _samples_template())


class ObjectReportSamplesJsTests(SimpleTestCase):
    def test_js_defaults_page_size_to_50(self):
        js = _samples_js()
        self.assertIn('panel.getAttribute("data-page-size"), 50', js)

    def test_js_reads_total_count_for_status(self):
        js = _samples_js()
        self.assertIn('panel.getAttribute("data-total-count")', js)

    def test_js_targets_sample_rows_and_pager_controls(self):
        js = _samples_js()
        self.assertIn(".nsm-or-sample-row", js)
        self.assertIn(".nsm-or-pager", js)
        self.assertIn(".nsm-or-pager-prev", js)
        self.assertIn(".nsm-or-pager-next", js)
        self.assertIn(".nsm-or-pager-status", js)

    def test_js_pages_in_fixed_size_steps(self):
        js = _samples_js()
        # pageCount derived from stored / pageSize; render() hides rows outside
        # the current [start, end) window.
        self.assertIn("Math.ceil(stored / pageSize)", js)
        self.assertIn("current * pageSize", js)
        self.assertIn("Math.min(start + pageSize, stored)", js)
        self.assertIn("style.display", js)

    def test_js_only_shows_pager_for_multiple_pages(self):
        js = _samples_js()
        self.assertIn("pageCount > 1", js)
        self.assertIn('classList.remove("d-none")', js)

    def test_js_binds_prev_next_handlers(self):
        js = _samples_js()
        self.assertIn('prevBtn.addEventListener("click"', js)
        self.assertIn('nextBtn.addEventListener("click"', js)

    def test_js_status_marks_capped_sample_set(self):
        js = _samples_js()
        # When more findings exist than stored samples, the status line notes the
        # server-side cap ("… of <total> total").
        self.assertIn("total > stored", js)
        self.assertIn("of ", js)


class ObjectReportPageSizeConstantTests(SimpleTestCase):
    def test_server_side_page_size_is_50(self):
        # Static text check (no import) keeps this a pure SimpleTestCase: the
        # server-rendered template default (50) must match the Python constant
        # the view passes through as ``sample_page_size``.
        source = _object_report_source()
        self.assertIn("SAMPLE_PAGE_SIZE = 50", source)
