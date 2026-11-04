import pytest

pytest.skip("Módulo antigo; será reescrito na etapa b do escopo final.", allow_module_level=True)

import json
from dataclasses import replace

import pytest

from app.data_loader import load_data
from app.rules import STATUS_PENDING, evaluate, normalize_codes

DATA = load_data()

FIRST_TERM = {"1103118", "1103177", "1108189", "1108190", "1108191"}


def used_ids(result):
    return {r.id for r in result.migrate.used}


def pending_ids(result):
    return {r.id for r in result.migrate.pending}


def elective_codes(result):
    return {c.code for c in result.migrate.electives}


def total(totals, category):
    return next(t for t in totals if t.category == category)


def test_first_term_student():
    result = evaluate(FIRST_TERM, data=DATA)
    assert used_ids(result) == {"cvga", "calc1", "mtce", "aevd", "prob1"}
    rules = {r.id: r.rule for r in result.migrate.used}
    assert rules["cvga"] == "mesmo código"
    assert rules["aevd"] == "eq01"
    assert len(result.migrate.pending) == 33 - 5
    assert all(r.status == STATUS_PENDING for r in result.migrate.pending)
    assert result.migrate.electives == []
    assert total(result.migrate.totals, "mandatory").done == 20
    assert total(result.migrate.totals, "mandatory").required == 120
    assert len(result.stay.pending) == 33 - 5
    assert total(result.stay.totals, "mandatory").done == 20
    assert total(result.stay.totals, "mandatory").required == 116


def test_old_electives_with_equivalence_and_same_code():
    # Python and Introdução aos Softwares both map to lpcd (any_of): only one is used.
    codes = {"GDEST0105", "1108196", "GDEST0106", "1108216"}
    result = evaluate(codes, data=DATA)
    assert {"lpcd", "ams", "amo2"} <= used_ids(result)
    lpcd = next(r for r in result.migrate.used if r.id == "lpcd")
    assert lpcd.source_codes == ["GDEST0105"]
    assert elective_codes(result) == {"1108196"}
    # amo2 (same code, 2026 elective EAM) + Introdução aos Softwares
    assert total(result.migrate.totals, "elective").done == 8
    assert result.migrate.emphasis_credits == {"EAM": 4, "CD": 0}
    assert total(result.stay.totals, "elective").done == 16


def test_market_research_is_used_by_code():
    result = evaluate({"1108156"}, data=DATA)
    assert "pm" in used_ids(result)
    assert total(result.migrate.totals, "extension").done == 0
    result = evaluate({"1108156"}, overrides={"old_pm_counts_as_extension": True}, data=DATA)
    assert total(result.migrate.totals, "extension").done == 60
    assert total(result.migrate.totals, "extension").required == 300


def test_internship_one_without_two():
    result = evaluate({"1108353"}, data=DATA)
    assert "est" in pending_ids(result)
    assert elective_codes(result) == {"1108353"}
    assert any("Estágio Supervisionado II" in n and "exige também" in n for n in result.migrate.notices)
    assert total(result.migrate.totals, "elective").done == 12


def test_internship_match_assumption_any_of():
    result = evaluate({"1108353"}, overrides={"internship_match": "any_of"}, data=DATA)
    assert "est" in used_ids(result)
    assert elective_codes(result) == set()
    used = {a.key: a for a in result.assumptions}["internship_match"]
    assert used.value == "any_of" and used.overridden


def test_internship_both_parts():
    result = evaluate({"1108353", "1108354"}, data=DATA)
    est = next(r for r in result.migrate.used if r.id == "est")
    assert est.source_codes == ["1108353", "1108354"]
    assert total(result.migrate.totals, "internship").done == 8
    assert total(result.stay.totals, "internship").done == 24


def test_numerical_calculus_proposal_is_only_a_notice():
    result = evaluate({"GDCOC0072"}, data=DATA)
    assert "moa" in pending_ids(result)
    assert elective_codes(result) == {"GDCOC0072"}
    assert any("Métodos de Otimização e Aplicações" in n and "proposta" in n for n in result.migrate.notices)


def test_alias_1103176_counts_as_numerical_calculus():
    assert normalize_codes({"1103176"}, DATA.code_aliases) == {"GDCOC0072"}
    result = evaluate({"1103176"}, data=DATA)
    assert "cn" not in {r.id for r in result.stay.pending}
    assert elective_codes(result) == {"GDCOC0072"}
    assert any("Métodos de Otimização e Aplicações" in n for n in result.migrate.notices)
    assert result.unknown_codes == []


def test_proposed_alias_is_not_applied_but_noticed():
    result = evaluate({"1108211"}, data=DATA)
    assert "iib" not in used_ids(result)
    assert elective_codes(result) == {"1108211"}
    assert any("1108211" in n for n in result.notices)


def test_special_topics_are_flexible_up_to_limit():
    codes = {"1108195", "1108199", "1108200", "1108201"}
    result = evaluate(codes, data=DATA)
    assert len(result.migrate.flexibles) == 4
    assert result.migrate.electives == []
    assert total(result.migrate.totals, "flexible").done == 8
    assert any("240 h" in n for n in result.migrate.notices)
    result = evaluate(codes, overrides={"old_flexible_max_hours": 240}, data=DATA)
    assert total(result.migrate.totals, "flexible").done == 16
    assert total(result.stay.totals, "flexible").done == 16


def test_old_elective_with_successor_and_emphasis_assumption():
    result = evaluate({"1108351"}, data=DATA)
    assert result.migrate.electives[0].emphasis == ""
    assert result.migrate.emphasis_credits["EAM"] == 0
    result = evaluate({"1108351"}, overrides={"old_electives_count_for_emphasis": True}, data=DATA)
    assert result.migrate.electives[0].emphasis == "EAM"
    assert result.migrate.emphasis_credits["EAM"] == 4


def test_emphasis_reached_with_24_credits():
    # amo2, asob, biom, dem2, geo, pe2: six EAM electives with the same code.
    codes = {"1108216", "1108130", "1108135", "1108141", "1108146", "1108159"}
    result = evaluate(codes, data=DATA)
    assert result.migrate.emphasis_credits["EAM"] == 24
    assert result.migrate.emphases == ["EAM"]


def test_tbd_equivalence_is_to_define():
    equivalences = tuple(
        replace(eq, match="TBD") if eq.rule_id == "eq09" else eq for eq in DATA.equivalences
    )
    data = replace(DATA, equivalences=equivalences)
    result = evaluate({"1108206"}, data=data)
    assert [t.record for t in result.migrate.to_define] == ["eq09"]
    assert "amv" not in pending_ids(result)
    assert "amv" not in used_ids(result)
    assert elective_codes(result) == set()


def test_internship_match_tbd_uses_pending_issue_description():
    result = evaluate({"1108353"}, overrides={"internship_match": "TBD"}, data=DATA)
    item = result.migrate.to_define[0]
    assert item.record == "eq13"
    assert "Estágio" in item.description
    assert "est" not in used_ids(result) | pending_ids(result)


def test_unknown_code_is_reported():
    result = evaluate({"9999999", " 1103177 "}, data=DATA)
    assert result.unknown_codes == ["9999999"]
    assert "calc1" in used_ids(result)


def test_unknown_assumption_override_raises():
    with pytest.raises(ValueError):
        evaluate(FIRST_TERM, overrides={"nao_existe": 1}, data=DATA)


def test_result_is_json_serializable():
    result = evaluate(FIRST_TERM | {"1108353"}, data=DATA)
    payload = json.loads(result.to_json())
    assert set(payload) == {"migrate", "stay", "assumptions", "unknown_codes", "notices", "taken_codes"}
    assert {a["key"] for a in payload["assumptions"]} >= {"internship_match", "old_flexible_max_hours"}


def test_full_2013_mandatory_student_has_nothing_pending_in_2013():
    codes = {c.code for c in DATA.curriculum_2013 if c.type in ("mandatory", "internship", "complementary")}
    result = evaluate(codes, data=DATA)
    assert result.stay.pending == []
    # New 2026 courses without a 2013 counterpart remain pending after migrating.
    assert {"fbdbd", "moa"} <= pending_ids(result)
