from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")


def new_app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def metric_values(at):
    return [m.value for m in at.metric]


def test_app_renders_both_scenarios():
    at = new_app()
    headers = [h.value for h in at.header]
    assert "Migrar para o PPC 2026" in headers
    assert "Não migrar (PPC 2013)" in headers
    assert "Premissas" in [h.value for h in at.sidebar.header]


def test_checking_courses_recomputes():
    at = new_app()
    before = metric_values(at)
    at.selectbox(key="fill_until").select(8)
    at.button[0].click().run()
    assert not at.exception
    assert at.checkbox(key="taken_1108356").value is True
    assert metric_values(at) != before


def test_changing_assumption_recomputes():
    at = new_app()
    at.selectbox(key="fill_until").select(8)
    at.button[0].click().run()
    before = metric_values(at)
    at.multiselect(key="assumption_transition_every_term_ids").set_value(["fbdbd", "moa", "lpcd", "ams"]).run()
    assert not at.exception
    assert any("premissas alteradas" in w.value for w in at.warning)
    assert metric_values(at) != before


def test_partial_internship_notice_is_highlighted():
    at = new_app()
    at.checkbox(key="taken_1108353").check().run()
    assert any("eq13" in w.value for w in at.warning)
