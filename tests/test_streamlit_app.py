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
    next(b for b in at.button if b.label == "Marcar").click().run()
    assert not at.exception
    return at


def warnings(at):
    return [w.value for w in at.warning]


def metric(at, label):
    return [m.value for m in at.metric if m.label == label]


def test_app_renders():
    at = new_app()
    assert "Migrar para o PPC 2026" in [h.value for h in at.header]
    assert "Não migrar (PPC 2013)" in [h.value for h in at.header]
    assert "Premissas" in [h.value for h in at.sidebar.header]
    assert FOOTER in warnings(at)
    assert any("cursando agora" in i.value for i in at.info)


def test_fill_history_places_courses_by_semester():
    at = fill_history(new_app())
    assert "1108190" in at.multiselect(key="hist_mand_2023.1").value  # 1st semester
    assert "1108356" in at.multiselect(key="hist_mand_2026.2").value  # 8th semester
    # No repetition: a course chosen in 2023.1 is not offered in other terms.
    assert all("1108190" not in o for o in at.multiselect(key="hist_mand_2023.2").options)


def test_fill_history_leaves_out_courses_after_history():
    at = new_app()
    at.selectbox(key="entry_term").select("2024.1").run()
    fill_history(at)
    assert any("Não foram marcadas" in w and "Trabalho de Conclusão de Curso II" in w for w in warnings(at))


def test_plan_options_and_offer_warning():
    at = fill_history(new_app())
    options = " ".join(at.multiselect(key="plan_mand_2027.1").options)
    assert "Métodos de Otimização" in options
    assert "Fundamentos de Banco de Dados" not in options  # needs lpcd
    at.multiselect(key="plan_mand_2027.1").set_value(["lpcd"]).run()
    assert not at.exception
    assert any(w.startswith("Atenção: você incluiu disciplinas fora do período") for w in warnings(at))
    assert "Fundamentos de Banco de Dados" in " ".join(at.multiselect(key="plan_mand_2027.2").options)


def test_cascade_removal_warning():
    at = fill_history(new_app())
    at.multiselect(key="plan_mand_2027.1").set_value(["lpcd"]).run()
    at.multiselect(key="plan_mand_2027.2").set_value(["fbdbd"]).run()
    at.multiselect(key="plan_mand_2027.1").set_value([]).run()
    assert not at.exception
    assert at.multiselect(key="plan_mand_2027.2").value == []
    assert any("Removidas automaticamente" in w and "Fundamentos de Banco de Dados" in w for w in warnings(at))


def test_complete_plan_gives_conclusion():
    at = fill_history(new_app())
    at.multiselect(key="plan_mand_2027.1").set_value(["moa", "pm"]).run()
    at.multiselect(key="plan_opt_2027.1").set_value(["cons"]).run()
    at.number_input(key="plan_generic:elective_2027.1").set_value(3).run()
    at.multiselect(key="plan_mand_2027.2").set_value(["lpcd"]).run()
    at.number_input(key="plan_generic:elective_2027.2").set_value(3).run()
    at.number_input(key="plan_generic:flexible_extension_2027.2").set_value(1).run()
    at.multiselect(key="plan_mand_2028.1").set_value(["fbdbd"]).run()
    at.number_input(key="plan_generic:flexible_extension_2028.1").set_value(1).run()
    at.number_input(key="plan_generic:flexible_2028.1").set_value(2).run()
    at.multiselect(key="plan_mand_2028.2").set_value(["ams"]).run()
    assert not at.exception
    assert metric(at, "Conclusão prevista") == ["2028.2"]
    assert metric(at, "Créditos no período")[:4] == ["24", "22", "18", "4"]


def test_changing_assumption_recomputes():
    at = fill_history(new_app())
    at.multiselect(key="plan_mand_2027.1").set_value(["moa"]).run()
    assert not any(w.startswith("Atenção") for w in warnings(at))
    at.multiselect(key="assumption_transition_every_term_ids").set_value([]).run()
    assert not at.exception
    assert any("premissas alteradas" in w for w in warnings(at))
    assert any("Métodos de Otimização e Aplicações (2027.1)" in w for w in warnings(at))
