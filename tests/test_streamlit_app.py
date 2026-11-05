from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.data_loader import load_data  # noqa: E402
from app.history_pdf import parse_history  # noqa: E402
from app.streamlit_app import (  # noqa: E402
    FOOTER,
    SOURCE_IN_PROGRESS,
    add_manual_flexible,
    apply_parsed,
    default_current_period,
    export_text,
    set_in_progress,
    entry_dict,
    fill_until,
    group_of,
    history_entries,
    remove_entry,
    split_pending,
    sync_in_progress,
)
from app.conversion import convert  # noqa: E402
from app.summary import build_summary  # noqa: E402
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


def manual(*codes_):
    return [{"code": c, "name": "", "hours": None, "sigaa_type": "", "source": "manual"} for c in codes_]


def with_history(rows, step=1):
    at = new_app()
    at.session_state["history"] = rows
    at.session_state["step"] = step
    at.run()
    assert not at.exception
    return at


def go(at, step):
    at.button(key=f"nav_{step}").click().run()
    assert not at.exception
    return at


def test_app_renders_empty_with_steps_locked():
    at = new_app()
    assert FOOTER in [w.value for w in at.warning]
    assert at.session_state["step"] == 1
    assert [at.button(key=f"nav_{n}").disabled for n in (1, 2, 3, 4)] == [False, True, True, True]
    assert at.button(key="next").disabled and at.button(key="back").disabled
    assert [at.button(key=f"nav_{n}").label for n in (1, 2, 3, 4)] == [
        "1 Histórico", "2 Resumo", "3 Disciplinas", "4 IA"]
    assert len(at.checkbox) == 0
    assert at.button(key="pdf_start").label == "Enviar o PDF do histórico do SIGAA"
    assert at.session_state["pdf_authorized"] is False


def test_steps_unlock_and_navigate():
    at = fill(new_app(), 3)
    assert len(codes(at)) == 15
    assert not at.button(key="nav_2").disabled
    at.button(key="next").click().run()
    assert at.session_state["step"] == 2
    assert metrics(at) == {"Faltam": "2.100 h", "Aproveitamento": "100%", "Não aproveitado": "0 h"}
    assert any("Se não migrar" in m for m in markdown(at))
    at.button(key="next").click().run()
    assert at.session_state["step"] == 3
    go(at, 4)
    assert at.subheader[0].value == "Conversar com IA"
    assert any(i.value == "Em breve." for i in at.info)
    assert at.button(key="next").disabled
    at.button(key="back").click().run()
    assert at.session_state["step"] == 3


def test_ai_step_offers_the_export_and_the_links():
    at = with_history(manual("1108353", "1108354"), step=4)
    assert ("Quer explorar mais? Baixe o arquivo abaixo e anexe-o numa conversa com a IA de sua "
            "preferência. Ele não contém seus dados pessoais.") in markdown(at)
    download = at.get("download_button")
    assert [d.proto.label for d in download] == ["Baixar arquivo para a IA"]
    assert [(b.proto.label, b.proto.url) for b in at.get("link_button")] == [
        ("Claude", "https://claude.ai/new"),
        ("ChatGPT", "https://chatgpt.com"),
        ("Gemini", "https://gemini.google.com"),
    ]
    assert "Anexe o arquivo baixado e pergunte o que quiser." in [c.value for c in at.caption]
    assert "#### Parecer da IA" in markdown(at)
    assert any(i.value == "Em breve." for i in at.info)


def export_of(state):
    result = convert(history_entries(state), data=DATA)
    return export_text(state, result, build_summary(result), DATA)


def test_export_text_uses_the_choices_of_the_student():
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    set_in_progress(state, True)
    state["saved"] = {"current_period": 6}
    text = export_of(state)
    assert "Período em que o aluno informou estar: 6º." in text
    assert "Disciplinas em curso: incluídas como aprovadas nesta simulação." in text
    assert "FICTICIA" not in text and "20240000000" not in text


def test_export_text_defaults():
    state = {}
    fill_until(state, DATA, 2)
    text = export_of(state)
    assert "Período em que o aluno informou estar: 3º." in text  # default: last period + 1
    assert "Disciplinas em curso" not in text  # no PDF with in-progress courses


def test_empty_history_goes_back_to_step_1():
    at = with_history(manual("1108157"), step=3)
    at.session_state["history"] = []
    at.run()
    assert at.session_state["step"] == 1


def test_add_and_remove_rows():
    at = new_app()
    select = at.selectbox(key="add_Optativas")
    option = next(o for o in select.options if "(1108157)" in o)
    select.select(option).run()
    assert not at.exception
    assert codes(at) == ["1108157"]
    assert at.selectbox(key="add_Optativas").value is None  # the selector is reset
    assert "1108157 · Optativa · 60 h" in [c.value for c in at.caption]
    at.button(key="rm_1108157").click().run()
    assert codes(at) == []


def test_clear_list():
    at = fill(new_app(), 2)
    at.button(key="clear_button").click().run()
    assert codes(at) == []


def test_manual_flexible_with_editable_hours():
    at = new_app()
    at.text_input(key="flex_name").input("Cálculo de outro curso").run()
    at.number_input(key="flex_hours").set_value(45).run()
    at.button(key="flex_add").click().run()
    assert not at.exception
    entry = at.session_state["history"][0]
    assert (entry["code"], entry["name"], entry["hours"], entry["sigaa_type"]) == (
        "MANUAL-1", "Cálculo de outro curso", 45, "CF")
    assert "— · Flexível · 45 h" in [c.value for c in at.caption]
    at.button(key="flex_add").click().run()
    assert codes(at) == ["MANUAL-1", "MANUAL-2"]
    go(at, 3)
    used = markdown(at)[markdown(at).index("#### Aproveitadas") + 1]
    assert used == ("- Cálculo de outro curso → Tópicos Especiais (flexível) (45 h)\n"
                    "- Flexível de outro curso → Tópicos Especiais (flexível) (60 h)")


def loaded_pdf_app():
    """The app right after a PDF upload (AppTest cannot upload files)."""
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    at = new_app()
    for key, value in state.items():
        at.session_state[key] = value
    at.session_state["pdf_loaded"] = True
    at.session_state["pdf_authorized"] = True
    at.session_state["in_progress_choice"] = None
    at.run()
    assert not at.exception
    return at


def test_authorization_before_the_upload():
    at = new_app()
    at.button(key="pdf_start").click().run()
    assert not at.exception
    assert any("O PDF do histórico contém dados pessoais" in m for m in markdown(at))
    at.button(key="pdf_decline").click().run()
    assert at.session_state["pdf_authorized"] is False
    assert at.button(key="pdf_start")  # still asks before the upload
    at.button(key="pdf_start").click().run()
    at.button(key="pdf_authorize").click().run()
    assert at.session_state["pdf_authorized"] is True
    assert not [b for b in at.button if b.key == "pdf_start"]


def test_loaded_file_and_in_progress_question():
    at = loaded_pdf_app()
    assert "Arquivo carregado: histórico do SIGAA (PDF)" in markdown(at)
    question = next(m for m in markdown(at) if m.startswith("Encontramos 2 disciplinas em curso:"))
    assert question.endswith("Deseja considerá-las como aprovadas na simulação?")
    assert len(codes(at)) == 10
    at.button(key="in_progress_yes").click().run()
    assert len(codes(at)) == 12
    assert "**Disciplinas em curso: incluídas**" in markdown(at)
    assert not [b for b in at.button if b.key == "in_progress_yes"]
    for step, prefix in ((2, "summary"), (3, "courses")):
        go(at, step)
        assert "**Disciplinas em curso: incluídas**" in markdown(at)
    at.button(key="courses_in_progress_change").click().run()
    assert len(codes(at)) == 10
    assert "**Disciplinas em curso: não incluídas**" in markdown(at)


def test_in_progress_no_keeps_them_out():
    at = loaded_pdf_app()
    at.button(key="in_progress_no").click().run()
    assert len(codes(at)) == 10
    assert "**Disciplinas em curso: não incluídas**" in markdown(at)


def test_remove_file_empties_the_list():
    at = loaded_pdf_app()
    at.button(key="pdf_remove").click().run()
    assert not at.exception
    assert codes(at) == []
    assert "pdf_loaded" not in at.session_state and "pdf_in_progress" not in at.session_state
    assert at.session_state["pdf_authorized"] is True  # no need to authorize again
    assert at.session_state["uploader_id"] == 1


def test_empty_groups_are_collapsed():
    at = fill(new_app(), 2)
    labels = [e.label for e in at.expander]
    assert "3º período · 0 h" in labels and "Optativas · 0 h" in labels
    assert "1º período · 0 h" not in labels
    assert "##### 1º período · 300 h" in markdown(at)


def test_change_of_step_scrolls_to_the_top():
    at = fill(new_app(), 1)
    at.button(key="next").click().run()
    assert at.session_state["scroll_count"] == 1
    assert "scroll_pending" not in at.session_state  # only once per change


def test_loss_with_recoverable_lines():
    at = with_history(manual("1108353", "1108354"), step=2)
    assert metrics(at)["Não aproveitado"] == "240 h"
    assert any(e.value.startswith("Atenção: 240 h") for e in at.error)
    captions = [c.value for c in at.caption]
    assert "192 cr: equivale a 48 disciplinas de 60 h." in captions
    assert any(c.startswith("Até 180 h podem ser recuperadas mediante pedido") for c in captions)
    # the requests appear once, in the blue box
    assert not any("como extensão" in m for m in markdown(at))
    assert any("Possíveis aproveitamentos mediante pedido" in i.value for i in at.info)
    assert "- **Estágio:** 120 de 120 h · faltam 0 h" in markdown(at)[markdown(at).index("**Por categoria do novo PPC**") + 1]


def test_assumption_override_survives_a_change_of_step():
    at = with_history(manual("1108197", "GDCOC0072", "1108128"), step=2)
    assert metrics(at)["Não aproveitado"] == "60 h"
    at.number_input(key="assumption_topics_max_hours").set_value(180).run()
    assert not at.exception
    assert metrics(at)["Não aproveitado"] == "0 h"
    assert any("regras alteradas" in w.value for w in at.warning)
    go(at, 3)
    assert any("regras alteradas" in w.value for w in at.warning)
    go(at, 2)
    assert at.number_input(key="assumption_topics_max_hours").value == 180
    assert metrics(at)["Não aproveitado"] == "0 h"
    at.button(key="restore").click().run()
    assert metrics(at)["Não aproveitado"] == "60 h"
    assert at.number_input(key="assumption_topics_max_hours").value == 120


def test_destination_override_changes_the_result():
    at = with_history(manual("1108128"), step=2)
    at.selectbox(key="destination_1108128").set_value("elective:CD").run()
    assert not at.exception
    assert any("Ciência de Dados: 60 h" in m for m in markdown(at))


def test_confirmed_destinations_are_not_editable():
    at = with_history(manual("1108128"), step=2)
    keys = {s.key for s in at.selectbox}
    assert "destination_1108128" in keys
    assert "destination_1108197" not in keys  # Probabilidade III: confirmed
    assert "Simular regras ainda não confirmadas" in [e.label for e in at.expander]


def test_courses_step_lists():
    at = new_app()
    at.session_state["history"] = manual("1108140", "1108139", "1108353", "1108354", "1108157", "1108128") + [
        {"code": "9990002", "name": "Outra", "hours": 60, "sigaa_type": "OB", "source": "pdf"}]
    at.session_state["saved"] = {"destination_1108128": "elective:none"}
    at.session_state["step"] = 3
    at.run()
    assert not at.exception
    texts = markdown(at)
    assert texts[texts.index("#### Aproveitadas") + 1].split("\n") == [
        "- Demografia I → Demografia I (optativa · Estatística Aplicada e Modelagem · 60 h)",
        "- Controle Estatístico de Qualidade → Controle Estatístico de Processos "
        "(optativa · Estatística Aplicada e Modelagem · 60 h)",
        "- Estágio Supervisionado I → Estágio Supervisionado (120 de 180 h)",
        "- Análise de Dados Categorizados → Optativa sem ênfase (60 h)",
        "- Pesquisa Operacional → Pesquisa Operacional (optativa sem ênfase · 60 h)",
    ]
    assert any(m.startswith("**Perdido: 240 h") for m in texts)
    lost = next(m for m in texts if m.startswith("- Estágio Supervisionado I: "))
    assert lost.split("\n") == [
        "- Estágio Supervisionado I: 60 h perdidas, redução de carga horária "
        "(o novo Estágio Supervisionado tem 120 h).",
        "- Estágio Supervisionado II: 180 h perdidas, não é aproveitada automaticamente.",
    ]
    assert texts[texts.index("**Não reconhecidas (fora das contas, consulte a coordenação)**") + 1] == (
        "- Outra (60 h)")
    assert at.expander[-1].label == "Ver tabela completa"


def test_current_period_splits_the_pending_courses():
    at = fill(new_app(), 3)
    go(at, 3)
    assert at.number_input(key="current_period").value == 4
    texts = markdown(at)
    behind = texts[texts.index("**Ficaram para trás**") + 1]
    upcoming = texts[texts.index("**Próximos períodos**") + 1]
    assert "Linguagem de Programação para Ciência de Dados (2º período)" in behind
    assert "Fundamentos de Banco de Dados e Big Data (4º período)" in upcoming
    at.number_input(key="current_period").set_value(6).run()
    texts = markdown(at)
    assert "Fundamentos de Banco de Dados e Big Data (4º período)" in texts[texts.index("**Ficaram para trás**") + 1]
    go(at, 2)
    go(at, 3)
    assert at.number_input(key="current_period").value == 6


# ---------- state functions (the PDF upload cannot be simulated by AppTest) ----------


def test_apply_parsed_fills_the_table_without_in_progress():
    state = {"history": [{"code": "1108157", "name": "", "hours": None, "sigaa_type": "", "source": "manual"}]}
    parsed = parse_history(build_history_pdf(), include_in_progress=True)
    apply_parsed(state, parsed, "file-1", include_in_progress=False)
    assert state["pdf_file_id"] == "file-1"
    assert len(state["history"]) == 10  # the table is replaced
    assert state["pdf_report"]["approved_count"] == 10
    assert state["pdf_report"]["in_progress_count"] == 2
    assert all(e["source"] != SOURCE_IN_PROGRESS for e in state["history"])


def test_toggle_in_progress_keeps_the_corrections():
    state = {}
    apply_parsed(state, parse_history(build_history_pdf(), include_in_progress=True), "f", False)
    remove_entry(state, "1103118")
    sync_in_progress(state, True)
    assert len(state["history"]) == 9 + 2
    sync_in_progress(state, False)
    assert len(state["history"]) == 9
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


def test_default_current_period():
    state = {}
    assert default_current_period(state, DATA) == 1
    fill_until(state, DATA, 3)
    assert default_current_period(state, DATA) == 4
    state["pdf_in_progress"] = [
        entry_dict(c.code, c.name, c.hours, "OB", SOURCE_IN_PROGRESS)
        for c in DATA.curriculum_2013 if c.type == "mandatory" and c.semester == 4
    ]
    sync_in_progress(state, True)  # in-progress courses count as passed
    assert default_current_period(state, DATA) == 5
    sync_in_progress(state, False)
    assert default_current_period(state, DATA) == 4
    fill_until(state, DATA, 8)
    assert default_current_period(state, DATA) == 8  # at most 8


def test_split_pending_keeps_the_flowchart_order():
    from app.conversion import convert

    pending = convert(history_entries({"history": []}), data=DATA).pending
    behind, upcoming = split_pending(pending, 3)
    assert {p.semester for p in behind} == {1, 2}
    assert behind + upcoming == pending


def test_add_manual_flexible_numbers_the_codes():
    state = {}
    add_manual_flexible(state, "  ", 30)
    add_manual_flexible(state, "X", 60)
    remove_entry(state, "MANUAL-1")
    add_manual_flexible(state, "Y", 90)
    assert [(e["code"], e["name"], e["hours"]) for e in state["history"]] == [
        ("MANUAL-2", "X", 60), ("MANUAL-1", "Y", 90)]
