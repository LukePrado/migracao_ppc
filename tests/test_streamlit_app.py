from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.data_loader import load_data  # noqa: E402
from app.history_pdf import parse_history  # noqa: E402
from app.streamlit_app import (  # noqa: E402
    FOOTER,
    SOURCE_IN_PROGRESS,
    apply_parsed,
    fill_until,
    group_of,
    history_entries,
    remove_entry,
    sync_in_progress,
)
from tests.fixtures.make_history_pdf import build_history_pdf  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")
DATA = load_data()


def new_app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    return at


def fill(at, until):
    at.selectbox(key="fill_until").select(until)
    at.button(key="fill_button").click().run()
    assert not at.exception
    return at


def codes(at):
    return [e["code"] for e in at.session_state["history"]]


def metrics(at):
    return {m.label: m.value for m in at.metric}


def markdown(at):
    return [m.value for m in at.markdown]


# ---------- page ----------


def test_app_renders_empty():
    at = new_app()
    assert any("Envie o PDF" in i.value for i in at.info)
    assert FOOTER in [w.value for w in at.warning]
    assert "Premissas" in [h.value for h in at.sidebar.header]
    assert "Disciplinas extintas: Tópicos ou optativa" in [h.value for h in at.sidebar.header]
    assert at.checkbox(key="include_in_progress").value is False


def test_fill_until_shows_the_summary():
    at = fill(new_app(), 3)
    assert len(codes(at)) == 15
    assert metrics(at) == {"Faltam": "2.100 h", "Aproveitamento": "100%", "Não aproveitado": "0 h"}
    assert "#### 3º período" in markdown(at)
    assert "#### Tópicos Especiais" not in markdown(at)
    assert any("Se não migrar" in m for m in markdown(at))


def test_add_and_remove_rows():
    at = new_app()
    select = at.selectbox(key="add_Optativas")
    option = next(o for o in select.options if "(1108157)" in o)
    select.select(option).run()
    assert not at.exception
    assert codes(at) == ["1108157"]
    assert at.selectbox(key="add_Optativas").value is None  # the selector is reset
    at.button(key="rm_1108157").click().run()
    assert codes(at) == []


def test_clear_table():
    at = fill(new_app(), 2)
    at.button(key="clear_button").click().run()
    assert codes(at) == []


def test_loss_is_highlighted_with_recoverable_lines():
    at = new_app()
    at.session_state["history"] = [
        {"code": "1108353", "name": "", "hours": None, "sigaa_type": "", "source": "manual"},
        {"code": "1108354", "name": "", "hours": None, "sigaa_type": "", "source": "manual"},
    ]
    at.run()
    assert not at.exception
    assert metrics(at)["Não aproveitado"] == "240 h"
    assert any(e.value.startswith("Atenção: 240 h") for e in at.error)
    assert any("podem ser recuperadas mediante pedido:" in m for m in markdown(at))
    assert any("Possíveis aproveitamentos mediante pedido" in i.value for i in at.info)


def test_assumption_override_changes_the_result():
    at = new_app()
    at.session_state["history"] = [
        {"code": c, "name": "", "hours": None, "sigaa_type": "", "source": "manual"}
        for c in ("1108197", "GDCOC0072", "1108128")
    ]
    at.run()
    assert metrics(at)["Não aproveitado"] == "60 h"
    at.number_input(key="assumption_topics_max_hours").set_value(180).run()
    assert not at.exception
    assert metrics(at)["Não aproveitado"] == "0 h"
    assert any("premissas ou destinos alterados" in w.value for w in at.warning)


def test_destination_override_changes_the_result():
    at = new_app()
    at.session_state["history"] = [
        {"code": "1108128", "name": "", "hours": None, "sigaa_type": "", "source": "manual"}
    ]
    at.run()
    at.selectbox(key="destination_1108128").set_value("elective:CD").run()
    assert not at.exception
    assert any("Ciência de Dados: 60 h" in m for m in markdown(at))


def test_confirmed_destinations_are_not_editable():
    at = new_app()
    keys = {s.key for s in at.sidebar.selectbox}
    assert "destination_1108128" in keys
    assert "destination_1108197" not in keys  # Probabilidade III: confirmed


# ---------- state functions (the PDF upload cannot be simulated by AppTest) ----------


def test_apply_parsed_fills_the_table_without_in_progress():
    state = {"history": [{"code": "1108157", "name": "", "hours": None, "sigaa_type": "", "source": "manual"}]}
    parsed = parse_history(build_history_pdf(), include_in_progress=True)
    apply_parsed(state, parsed, "file-1", include_in_progress=False)
    assert state["pdf_file_id"] == "file-1"
    assert len(state["history"]) == 9  # the table is replaced
    assert state["pdf_report"]["approved_count"] == 9
    assert state["pdf_report"]["in_progress_count"] == 2
    assert all(e["source"] != SOURCE_IN_PROGRESS for e in state["history"])


def test_toggle_in_progress_keeps_the_corrections():
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    remove_entry(state, "1103118")
    sync_in_progress(state, True)
    assert len(state["history"]) == 8 + 2
    sync_in_progress(state, False)
    assert len(state["history"]) == 8
    assert "1103118" not in [e["code"] for e in state["history"]]


def test_report_has_no_personal_data():
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    assert "FICTICIA" not in str(state) and "20240000000" not in str(state)


def test_history_entries_keep_pdf_data_for_outside_courses():
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    outside = next(e for e in history_entries(state) if e.code == "9990001")
    assert (outside.hours, outside.sigaa_type) == (60, "CF")


def test_fill_until_does_not_duplicate():
    state = {}
    fill_until(state, DATA, 1)
    fill_until(state, DATA, 2)
    found = [e["code"] for e in state["history"]]
    assert len(found) == len(set(found)) == 10


@pytest.mark.parametrize(
    "args, group",
    [
        (("mandatory", 3), "3º período"),
        (("internship", 7), "7º período"),
        (("elective", None), "Optativas"),
        (("flexible", None), "Flexíveis"),
        (("", None, "CF"), "Flexíveis"),
        (("", None, "OB"), "Não reconhecidas na grade 2013"),
    ],
)
def test_group_of(args, group):
    assert group_of(*args) == group
