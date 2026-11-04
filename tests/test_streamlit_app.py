import pytest

pytest.skip("Módulo antigo; será reescrito na etapa d do escopo final.", allow_module_level=True)

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")
FOOTER = "Simulação baseada nas regras disponíveis; não substitui a orientação da coordenação."


def new_app():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception
    return at


def fill_history(at, until=8):
    at.selectbox(key="fill_until").select(until)
    at.button(key="fill_button").click().run()
    assert not at.exception
    return at


def add(at, prefix, kind, term, value):
    at.selectbox(key=f"add_{prefix}_{kind}_{term}").set_value(value).run()
    assert not at.exception
    return at


def add_term(at):
    at.button(key="add_term").click().run()
    assert not at.exception
    return at


def warnings(at):
    return [w.value for w in at.warning]


def markdown(at):
    return [m.value for m in at.markdown]


def test_app_renders():
    at = new_app()
    assert "Migrar para o PPC 2026" in [h.value for h in at.header]
    assert "Não migrar (PPC 2013)" in [h.value for h in at.header]
    assert "Premissas" in [h.value for h in at.sidebar.header]
    assert FOOTER in warnings(at)
    assert any("cursando agora" in i.value for i in at.info)
    # The plan starts with a single term.
    assert at.session_state["plan_term_count"] == 1
    assert "#### 2027.1 · plano na grade 2026" in markdown(at)
    assert "#### 2027.2 · plano na grade 2026" not in markdown(at)


def test_fill_history_places_courses_by_semester():
    at = fill_history(new_app())
    assert "1108190" in at.session_state["hist_2023.1"]  # 1st semester
    assert "1108356" in at.session_state["hist_2026.2"]  # 8th semester
    assert "aproveitada como Análise Exploratória e Visualização de Dados" in markdown(at)
    assert "**Total: 20 créditos**" in markdown(at)


def test_fill_history_leaves_out_courses_after_history():
    at = new_app()
    at.selectbox(key="entry_term").select("2024.1").run()
    fill_history(at)
    assert any("Não foram marcadas" in w and "Trabalho de Conclusão de Curso II" in w for w in warnings(at))


def test_history_add_and_remove_rows():
    at = new_app()
    add(at, "hist", "opt", "2023.1", "1108351")
    assert at.session_state["hist_2023.1"] == ["1108351"]
    assert at.selectbox(key="add_hist_opt_2023.1").value is None  # selector resets
    assert "vira optativa" in markdown(at)
    # No repetition: an added course leaves the selectors of every term.
    assert not any("1108351" in o for o in at.selectbox(key="add_hist_opt_2023.2").options)
    at.button(key="rm_hist_2023.1_0").click().run()
    assert at.session_state["hist_2023.1"] == []


def test_plan_offer_warning_and_cascade():
    at = fill_history(new_app())
    options = " ".join(at.selectbox(key="add_plan_mand_2027.1").options)
    assert "Métodos de Otimização" in options
    assert "Fundamentos de Banco de Dados" not in options  # needs lpcd
    add(at, "plan", "mand", "2027.1", "lpcd")  # 2nd semester: usually offered in .2
    assert any(w.startswith("Atenção: você incluiu disciplinas fora do período") for w in warnings(at))
    assert any("fora do período de oferta" in m for m in markdown(at))
    add_term(at)
    add(at, "plan", "mand", "2027.2", "fbdbd")
    at.button(key="rm_plan_2027.1_0").click().run()
    assert at.session_state["plan_2027.2"] == []
    assert any("Removidas automaticamente" in w and "Fundamentos de Banco de Dados" in w for w in warnings(at))


def test_generic_items_can_repeat():
    at = new_app()
    for _ in range(3):
        add(at, "plan", "opt", "2027.1", "generic:elective")
    assert at.session_state["plan_2027.1"] == ["generic:elective"] * 3
    assert "**Total: 12 créditos**" in markdown(at)
    assert at.selectbox(key="add_plan_opt_2027.1").options[0] == "Optativa a definir (4 cr)"


def test_add_and_remove_terms():
    at = add_term(new_app())
    assert at.session_state["plan_term_count"] == 2
    at.button(key="remove_term").click().run()
    assert at.session_state["plan_term_count"] == 1
    # The last term can only be removed while empty.
    add_term(at)
    add(at, "plan", "opt", "2027.2", "generic:elective")
    assert not any(b.key == "remove_term" for b in at.button)


def test_complete_plan_gives_conclusion():
    at = fill_history(new_app())
    for item in ("moa", "pm"):
        add(at, "plan", "mand", "2027.1", item)
    for item in ("cons", "generic:elective", "generic:elective", "generic:elective"):
        add(at, "plan", "opt", "2027.1", item)
    add_term(at)
    add(at, "plan", "mand", "2027.2", "lpcd")
    for item in ("generic:elective", "generic:elective", "generic:elective", "generic:flexible_extension"):
        add(at, "plan", "opt", "2027.2", item)
    add_term(at)
    add(at, "plan", "mand", "2028.1", "fbdbd")
    for item in ("generic:flexible_extension", "generic:flexible", "generic:flexible"):
        add(at, "plan", "opt", "2028.1", item)
    add_term(at)
    add(at, "plan", "mand", "2028.2", "ams")
    assert [m.value for m in at.metric if m.label == "Conclusão prevista"] == ["2028.2"]
    totals = [m for m in markdown(at) if m.startswith("**Total:")]
    assert totals[-4:] == [
        "**Total: 24 créditos**",
        "**Total: 22 créditos**",
        "**Total: 18 créditos**",
        "**Total: 4 créditos**",
    ]
    assert not any("abaixo do mínimo" in w or "acima do máximo" in w for w in warnings(at))


def test_changing_assumption_recomputes():
    at = fill_history(new_app())
    add(at, "plan", "mand", "2027.1", "moa")
    assert not any(w.startswith("Atenção") for w in warnings(at))
    at.multiselect(key="assumption_transition_every_term_ids").set_value([]).run()
    assert not at.exception
    assert any("premissas alteradas" in w for w in warnings(at))
    assert any("Métodos de Otimização e Aplicações (2027.1)" in w for w in warnings(at))


def test_export_button():
    at = fill_history(new_app())
    buttons = at.get("download_button")
    assert len(buttons) == 1
    assert buttons[0].proto.label == "Exportar para conversar com uma IA"
