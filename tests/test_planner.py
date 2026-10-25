import json
from dataclasses import replace

import pytest

from app.data_loader import Prerequisite, load_data
from app.planner import (
    ELECTIVE_SLOT_NAME,
    KIND_COURSE,
    _prerequisite_groups,
    plan,
    term_from_index,
    term_index,
)
from app.rules import evaluate

DATA = load_data()

FIRST_TERM = {"1103118", "1103177", "1108189", "1108190", "1108191"}
ALL_2013_REQUIRED = {
    c.code for c in DATA.curriculum_2013 if c.type in ("mandatory", "internship", "complementary")
}
# 9 electives (36 cr) and the four Tópicos Especiais (16 cr) of 2013.
ELECTIVES_2013 = {"1108128", "1108130", "1108135", "1108141", "1108142", "1108146", "1108150", "1108153", "1108156"}
FLEXIBLES_2013 = {"1108195", "1108199", "1108200", "1108201"}


def run(codes, entry_term=None, overrides=None, data=DATA):
    evaluation = evaluate(codes, overrides=overrides, data=data)
    return evaluation, plan(evaluation, entry_term=entry_term, overrides=overrides, data=data)


def term_of(scenario_plan, course_id):
    for term in scenario_plan.terms:
        if any(c.id == course_id for c in term.courses):
            return term.term
    return None


def test_term_helpers():
    assert term_index("2027.1") + 1 == term_index("2027.2")
    assert term_from_index(term_index("2027.2") + 1) == "2028.1"
    with pytest.raises(ValueError):
        term_index("2027.3")


def test_student_without_pending_items():
    _, planning = run(ALL_2013_REQUIRED | ELECTIVES_2013 | FLEXIBLES_2013, entry_term="2023.1")
    stay = planning.stay
    assert stay.terms == []
    assert stay.remaining_terms == 0
    assert stay.conclusion_term is None
    assert stay.exceeds_deadline is False
    assert any("Não há pendências" in n for n in stay.notices)


def test_chain_lpcd_then_fbdbd():
    # Migrating: lpcd (even semester, .2 only) must come before fbdbd and ams.
    _, planning = run(ALL_2013_REQUIRED)
    migrate = planning.migrate
    assert term_of(migrate, "lpcd") == "2027.2"
    assert term_of(migrate, "fbdbd") == "2028.1"  # offered every term in the transition
    assert term_of(migrate, "ams") == "2028.2"
    assert migrate.conclusion_term == "2028.2"
    assert migrate.remaining_terms == 4


def test_transition_every_term_ids_effect():
    overrides = {"transition_every_term_ids": ""}
    _, planning = run(ALL_2013_REQUIRED, overrides=overrides)
    # Without the transition offer, moa and fbdbd follow parity (4th semester → .2).
    assert term_of(planning.migrate, "moa") == "2027.2"
    assert term_of(planning.migrate, "fbdbd") == "2028.2"

    _, planning = run(ALL_2013_REQUIRED)
    assert term_of(planning.migrate, "moa") == "2027.1"


def test_transition_ids_only_apply_to_migrate():
    _, planning = run(FIRST_TERM, overrides={"transition_every_term_ids": "dem1"})
    # dem1 is a 2013 mandatory of the 3rd semester: still only in .1 terms.
    assert term_of(planning.stay, "dem1").endswith(".1")


def assert_plan_is_consistent(scenario_plan, curriculum, prerequisites, done_ids, max_credits):
    by_id = {c.id: c for c in curriculum}
    groups = _prerequisite_groups(prerequisites)
    completed = set(done_ids)
    scheduled = []
    for term in scenario_plan.terms:
        assert term.credits <= max_credits
        assert term.credits == sum(c.credits for c in term.courses)
        courses = [c for c in term.courses if c.kind == KIND_COURSE]
        for course in courses:
            course_groups = groups[course.id]
            assert not course_groups or any(
                all(p in completed or p.startswith("code:") for p in g) for g in course_groups.values()
            ), (course.id, term.term)
            semester = by_id[course.id].semester
            if by_id[course.id].type == "mandatory" and course.id not in ("fbdbd", "moa"):
                assert (semester % 2 == 1) == term.term.endswith(".1"), (course.id, term.term)
        completed.update(c.id for c in courses)
        scheduled += [c.id for c in courses]
    return scheduled


def test_first_term_student_plan_is_consistent():
    evaluation, planning = run(FIRST_TERM, entry_term="2026.1")
    scheduled = assert_plan_is_consistent(
        planning.migrate, DATA.curriculum_2026, DATA.prerequisites_2026,
        {r.id for r in evaluation.migrate.used}, 25,
    )
    assert sorted(scheduled) == sorted(r.id for r in evaluation.migrate.pending)
    assert planning.migrate.unscheduled == []

    done_2013 = {c.id for c in DATA.curriculum_2013 if c.code in FIRST_TERM}
    scheduled = assert_plan_is_consistent(
        planning.stay, DATA.curriculum_2013, DATA.prerequisites_2013, done_2013, 32,
    )
    assert sorted(scheduled) == sorted(r.id for r in evaluation.stay.pending)


def test_generic_slots_fill_missing_electives_after_courses():
    evaluation, planning = run(FIRST_TERM)
    slots = [c for t in planning.migrate.terms for c in t.courses if c.kind != KIND_COURSE]
    assert sum(c.credits for c in slots) == 44 + 20
    assert sum(1 for c in slots if c.name == ELECTIVE_SLOT_NAME) == 11
    for term in planning.migrate.terms:
        kinds = [c.kind for c in term.courses]
        assert kinds == sorted(kinds, key=lambda k: k != KIND_COURSE)


def test_deadline_warning():
    _, planning = run(FIRST_TERM, entry_term="2020.1")
    assert planning.migrate.deadline_term == "2025.2"
    assert planning.migrate.exceeds_deadline is True
    assert any("prazo máximo" in n for n in planning.migrate.notices)
    _, planning = run(FIRST_TERM, entry_term="2026.1")
    assert planning.migrate.exceeds_deadline is False


def test_unsatisfiable_prerequisite_is_reported():
    extra = Prerequisite("lpcd", "code:0000000", "1")
    data = replace(DATA, prerequisites_2026=DATA.prerequisites_2026 + (extra,))
    _, planning = run(FIRST_TERM, data=data)
    assert {"lpcd", "fbdbd", "ams"} <= set(planning.migrate.unscheduled)
    assert any("Não foi possível planejar" in n for n in planning.migrate.notices)


def test_external_prerequisite_from_transcript():
    # cn (2013) is satisfied by group 2 (code:1107136) without sedo and prog.
    evaluation, planning = run(FIRST_TERM | {"1107136"})
    assert "1107136" in evaluation.unknown_codes
    assert term_of(planning.stay, "cn") == "2027.2"
    assert term_index(term_of(planning.stay, "sedo")) > term_index("2027.2")

    _, planning = run(FIRST_TERM)
    assert term_index(term_of(planning.stay, "cn")) > term_index(term_of(planning.stay, "sedo"))


def test_planning_is_json_serializable():
    _, planning = run(FIRST_TERM, entry_term="2026.1")
    payload = json.loads(planning.to_json())
    assert set(payload) == {"migrate", "stay", "assumptions"}
    assert {a["key"] for a in payload["assumptions"]} >= {"first_planning_term", "max_credits_2026"}


def test_target_credits_limit_generic_slots_only():
    _, planning = run(ALL_2013_REQUIRED)
    for term in planning.stay.terms:
        assert term.credits <= 24
    _, planning = run(ALL_2013_REQUIRED, overrides={"target_credits_2013": 32})
    assert planning.stay.terms[0].credits == 32
    assert planning.stay.conclusion_term == "2027.2"


def test_courses_may_exceed_target_up_to_max():
    # First-term student staying in 2013: 2027.2 has five 2nd-semester courses (20 cr);
    # with target 8, slots stop at 8 but courses still go up to the 32 cr maximum.
    _, planning = run(FIRST_TERM, overrides={"target_credits_2013": 8})
    term = next(t for t in planning.stay.terms if t.term == "2027.2")
    courses = [c for c in term.courses if c.kind == KIND_COURSE]
    assert sum(c.credits for c in courses) == 20
    assert term.credits == 20


def test_warning_below_minimum_credits_except_last_term():
    _, planning = run(ALL_2013_REQUIRED)
    notices = [n for n in planning.migrate.notices if "abaixo do mínimo" in n]
    assert notices == ["O período 2028.1 fica com 16 créditos, abaixo do mínimo de 17 por período."]
    # The last stay term has 4 cr but is the last one: no warning.
    assert planning.stay.terms[-1].credits == 4
    assert not any("abaixo do mínimo" in n for n in planning.stay.notices)


def test_transition_with_lpcd_and_ams_shortens_migration():
    overrides = {"transition_every_term_ids": "fbdbd|moa|lpcd|ams"}
    _, planning = run(ALL_2013_REQUIRED, overrides=overrides)
    assert term_of(planning.migrate, "lpcd") == "2027.1"
    assert term_of(planning.migrate, "fbdbd") == "2027.2"
    assert term_of(planning.migrate, "ams") == "2027.2"
    assert planning.migrate.conclusion_term == "2028.1"
    assert planning.stay.conclusion_term == "2028.1"
