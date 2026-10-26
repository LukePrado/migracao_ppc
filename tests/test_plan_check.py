import json
from dataclasses import replace

import pytest

from app.data_loader import Prerequisite, load_data
from app.plan_check import (
    build_context,
    cascade_remove,
    check_plan,
    deadline_term,
    eligible_courses,
    history_outcomes,
    history_terms,
    offer_rule,
    term_from_index,
    term_index,
)

DATA = load_data()
BY_ID = {c.id: c for c in DATA.curriculum_2026}

FIRST_TERM = {"1103118", "1103177", "1108189", "1108190", "1108191"}
ALL_2013_REQUIRED = {
    c.code for c in DATA.curriculum_2013 if c.type in ("mandatory", "internship", "complementary")
}
EL, FL, FX = "generic:elective", "generic:flexible", "generic:flexible_extension"

# Completes every 2026 requirement for a student with all 2013 required courses.
COMPLETE_PLAN = {
    "2027.1": ["moa", "pm", "cons", EL, EL, EL],
    "2027.2": ["lpcd", EL, EL, EL, FX],
    "2028.1": ["fbdbd", FX, FL, FL],
    "2028.2": ["ams"],
}


def check(codes, plan, entry_term="2023.1", overrides=None, data=DATA):
    return check_plan(codes, entry_term, plan, overrides=overrides, data=data)


def row(result, category):
    return next(r for r in result.migrate.totals if r.category == category)


def test_terms():
    assert term_from_index(term_index("2026.2") + 1) == "2027.1"
    assert history_terms("2023.1", "2027.1")[0] == "2023.1"
    assert history_terms("2023.1", "2027.1")[-1] == "2026.2"
    assert len(history_terms("2023.1", "2027.1")) == 8
    assert history_terms("2027.1", "2027.1") == []
    assert deadline_term("2020.1") == "2025.2"
    with pytest.raises(ValueError):
        term_index("2027.3")


def test_offer_rule():
    ctx = build_context(FIRST_TERM, data=DATA)
    offer = ctx.offer
    assert offer.is_offered(BY_ID["calc2"], "2027.1")  # Dep. de Matemática: every term
    assert not offer.is_offered(BY_ID["inf2"], "2027.1")  # 4th semester: .2 only
    assert offer.is_offered(BY_ID["inf2"], "2027.2")
    assert offer.is_offered(BY_ID["fbdbd"], "2027.1")  # transition_every_term_ids
    assert offer.is_offered(BY_ID["est"], "2027.2")  # every_term_types
    assert offer.is_offered(BY_ID["dem1"], "2027.2")
    no_transition = offer_rule(build_context(FIRST_TERM, {"transition_every_term_ids": ""}, DATA).assumptions)
    assert not no_transition.is_offered(BY_ID["fbdbd"], "2027.1")


def test_complete_plan_gives_conclusion():
    result = check(ALL_2013_REQUIRED, COMPLETE_PLAN)
    assert result.prerequisite_issues == []
    assert result.offer_issues == []
    assert result.migrate.complete
    assert result.migrate.conclusion_term == "2028.2"
    assert result.migrate.missing == []
    assert row(result, "mandatory").done == 100
    assert row(result, "mandatory").planned == 20
    assert row(result, "elective").done + row(result, "elective").planned == 44
    assert row(result, "flexible").planned == 20
    assert row(result, "extension").planned == 300
    assert result.credit_notices == []  # 2028.2 has 4 cr but is the last term


def test_incomplete_plan_lists_what_is_missing():
    plan = {"2027.1": ["moa", "pm"], "2027.2": ["lpcd"]}
    result = check(ALL_2013_REQUIRED, plan)
    assert not result.migrate.complete
    assert result.migrate.conclusion_term is None
    assert {c.id for c in result.migrate.unplanned_required} == {"fbdbd", "ams"}
    assert any(m.startswith("Optativas: faltam 28 cr") for m in result.migrate.missing)
    assert any("Extensão" in m for m in result.migrate.missing)


def test_emphasis_is_informative_only():
    result = check(ALL_2013_REQUIRED, COMPLETE_PLAN)
    eam = row(result, "emphasis_EAM")
    assert eam.requirement is False and eam.missing > 0
    assert result.migrate.complete


def test_missing_prerequisite_is_reported():
    result = check(FIRST_TERM, {"2027.1": ["fbdbd"]})
    assert len(result.prerequisite_issues) == 1
    assert "Linguagem de Programação para Ciência de Dados" in result.prerequisite_issues[0]
    assert result.terms[0].items[0].missing_prerequisites == [["lpcd"]]


def test_prerequisite_in_same_term_is_not_enough():
    result = check(FIRST_TERM, {"2027.2": ["lpcd", "fbdbd"]})
    assert len(result.prerequisite_issues) == 1
    result = check(FIRST_TERM, {"2027.1": ["lpcd"], "2027.2": ["fbdbd"]})
    assert result.prerequisite_issues == []


def test_or_group_with_external_code():
    extra = Prerequisite("pae", "code:1107136", "2")
    data = replace(
        DATA,
        prerequisites_2026=tuple(p for p in DATA.prerequisites_2026 if p.course_id != "pae")
        + (Prerequisite("pae", "mtce", "1"), extra),
    )
    result = check({"1103177"}, {"2027.2": ["pae"]}, data=data)
    assert len(result.prerequisite_issues) == 1
    assert "ou" in result.prerequisite_issues[0]
    result = check({"1103177", "1107136"}, {"2027.2": ["pae"]}, data=data)
    assert result.prerequisite_issues == []


def test_off_offer_warning():
    result = check(FIRST_TERM, {"2027.1": ["lpcd", "prob2"]})
    assert result.offer_issues == [
        "Linguagem de Programação para Ciência de Dados (2027.1)",
        "Probabilidade 2 (2027.1)",
    ]
    assert result.offer_warning.startswith("Atenção: você incluiu disciplinas fora do período")
    assert result.terms[0].items[0].off_offer is True


def test_credit_limits_except_last_term_minimum():
    plan = {
        "2027.1": ["lpe", EL, EL, EL, EL, EL, EL, EL],  # 32 cr
        "2027.2": [EL, EL],  # 8 cr, not last
        "2028.1": [EL],  # 4 cr, last
    }
    result = check(FIRST_TERM, plan)
    assert result.credit_notices == [
        "2027.1: 32 créditos, acima do máximo de 25 por período.",
        "2027.2: 8 créditos, abaixo do mínimo de 17 por período.",
    ]


def test_empty_term_in_the_middle_is_below_minimum():
    result = check(FIRST_TERM, {"2027.1": ["lpe"] + [EL] * 4, "2027.2": [], "2028.1": [EL]})
    assert any(n.startswith("2027.2: 0 créditos") for n in result.credit_notices)
    assert [t.term for t in result.terms] == ["2027.1", "2027.2", "2028.1"]


def test_duplicate_and_already_used_courses():
    result = check(FIRST_TERM, {"2027.1": ["aevd", "lpe"], "2027.2": ["lpe"]})
    assert len(result.prerequisite_issues) == 2
    assert row(result, "mandatory").planned == 4


def test_deadline():
    result = check(ALL_2013_REQUIRED, COMPLETE_PLAN, entry_term="2017.1")
    assert result.deadline_term == "2022.2"
    assert result.exceeds_deadline
    assert any("prazo máximo" in n for n in result.notices)
    result = check(ALL_2013_REQUIRED, COMPLETE_PLAN, entry_term="2023.1")
    assert not result.exceeds_deadline


def test_to_define_counts_as_done_with_notice():
    equivalences = tuple(replace(eq, match="TBD") if eq.rule_id == "eq09" else eq for eq in DATA.equivalences)
    data = replace(DATA, equivalences=equivalences)
    result = check({"1108206"}, {"2027.2": ["amns"]}, data=data)
    assert result.prerequisite_issues == []
    assert result.to_define_notices == [
        "Aprendizagem de Máquina Não-Supervisionada depende de Análise Multivariada, cuja situação está a "
        "definir pela coordenação."
    ]
    assert not result.migrate.complete


def test_eligible_courses():
    ctx = build_context(FIRST_TERM, data=DATA)
    plan = {"2027.1": ["lpcd"], "2027.2": []}
    required = ("mandatory", "internship", "complementary")
    first = [c.id for c in eligible_courses(ctx, plan, "2027.1", required)]
    assert "aevd" not in first  # already used
    assert "prob2" in first and "lpcd" in first
    assert "fbdbd" not in first  # lpcd is only in this same term
    semesters = [BY_ID[i].semester for i in first]
    assert semesters == sorted(semesters)
    second = [c.id for c in eligible_courses(ctx, plan, "2027.2", required)]
    assert "fbdbd" in second and "lpcd" not in second
    others = [c.id for c in eligible_courses(ctx, plan, "2027.2", ("elective", "flexible"))]
    assert "dem1" in others and "tee1" in others
    assert "pln" not in others  # needs ams


def test_cascade_removal_after_history_change():
    plan = {"2027.1": ["lpcd", EL], "2027.2": ["fbdbd"], "2028.1": ["tcd", "dem1"]}
    ctx = build_context(FIRST_TERM, data=DATA)
    cleaned, removed = cascade_remove(ctx, plan)
    assert removed == [] and cleaned == plan
    # Without Análise Exploratória de Dados, aevd is no longer done:
    # lpcd → fbdbd → (tcd needs lpcd) and dem1 (needs aevd) all go.
    ctx = build_context(FIRST_TERM - {"1108190"}, data=DATA)
    cleaned, removed = cascade_remove(ctx, plan)
    assert cleaned == {"2027.1": [EL], "2027.2": [], "2028.1": []}
    assert [r.id for r in removed] == ["lpcd", "fbdbd", "tcd", "dem1"]


def test_cascade_removes_course_now_used_by_history():
    ctx = build_context(FIRST_TERM, data=DATA)
    cleaned, removed = cascade_remove(ctx, {"2027.1": ["aevd", "lpe"]})
    assert cleaned == {"2027.1": ["lpe"]}
    assert removed[0].reason == "já aproveitada pelo histórico"


def test_history_outcomes():
    ctx = build_context({"GDEST0105", "1108196", "1108195", "1108190", "1108197"}, data=DATA)
    outcomes = history_outcomes(ctx)
    assert outcomes["GDEST0105"] == "aproveitada como Linguagem de Programação para Ciência de Dados"
    assert outcomes["1108196"] == "vira optativa"
    assert outcomes["1108195"] == "vira flexível"
    assert outcomes["1108190"] == "aproveitada como Análise Exploratória e Visualização de Dados"
    assert outcomes["1108197"] == "vira optativa"


def test_stay_summary_comes_from_rules():
    result = check(FIRST_TERM, {})
    assert len(result.stay.pending) == 33 - 5
    mandatory = next(t for t in result.stay.totals if t.category == "mandatory")
    assert (mandatory.required, mandatory.done, mandatory.missing) == (116, 20, 96)


def test_plan_before_first_planning_term_is_invalid():
    with pytest.raises(ValueError):
        check(FIRST_TERM, {"2026.2": ["lpe"]})


def test_result_is_json_serializable():
    payload = json.loads(check(ALL_2013_REQUIRED, COMPLETE_PLAN).to_json())
    assert payload["migrate"]["conclusion_term"] == "2028.2"
    assert any(a["key"] == "every_term_codes" for a in payload["assumptions"])
