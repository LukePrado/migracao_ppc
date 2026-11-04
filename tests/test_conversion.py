import json

import pytest

from app.conversion import (
    ELECTIVE,
    NONE,
    TOPICS,
    UNRECOGNIZED,
    HistoryEntry,
    convert,
)
from app.data_loader import load_data

DATA = load_data()

EST1, EST2 = "1108353", "1108354"
PYTHON, SOFTWARES = "GDEST0105", "1108196"
PROB3_2013, NUMERICAL = "1108197", "GDCOC0072"
PROG_MAT = "1108162"
CATEGORICAL = "1108128"  # Análise de Dados Categorizados (optativa extinta)
REAL_ANALYSIS = "1103142"  # Introdução à Análise Real, 90 h
ECON1, ECON2 = "1108351", "1108352"
MARKET = "1108156"  # Pesquisa de Mercado
TOPICS_2013 = ("1108195", "1108199", "1108200", "1108201")


def run(history, **kwargs):
    return convert(history, data=DATA, **kwargs)


def course(result, code):
    return next(c for c in result.courses if c.code == code)


def total(result, category):
    return next(t for t in result.totals if t.category == category)


def test_empty_history():
    result = run([])
    assert result.courses == []
    assert result.total_required_hours == 3000
    assert result.total_used_hours == 0
    assert len(result.pending) == 33
    assert result.stay.missing_hours == 3000


def test_same_code_mandatory():
    c = course(run(["1103177"]), "1103177")
    assert (c.rule, c.target_id, c.used_hours, c.lost_hours) == ("mesmo código", "calc1", 60, 0)


def test_pending_follow_the_flowchart_order():
    pending = run(["1103177"]).pending
    assert "calc1" not in [p.id for p in pending]
    semesters = [p.semester for p in pending]
    assert semesters == sorted(semesters)


def test_internship_1_loses_60_hours():
    result = run([EST1])
    c = course(result, EST1)
    assert (c.target_id, c.used_hours, c.lost_hours) == ("est", 120, 60)
    assert "Redução de carga horária" in c.reason
    assert total(result, "internship").used_hours == 120


def test_internship_2_is_lost_and_recoverable_by_request():
    result = run([EST2])
    c = course(result, EST2)
    assert (c.category, c.used_hours, c.lost_hours) == (NONE, 0, 180)
    assert result.recoverable_hours == 180
    assert [(r.code, r.target, r.max_hours, r.recoverable_hours) for r in result.requests] == [
        (EST2, "extension", 180, 180)
    ]
    assert result.total_used_hours == 0  # requests never enter the totals


def test_internship_2_recoverable_follows_assumption():
    result = run([EST2], overrides={"internship2_recoverable_max_hours": 60})
    assert result.recoverable_hours == 60
    assert result.requests[0].max_hours == 60


def test_python_and_softwares_one_goes_to_topics():
    for history in ([PYTHON, SOFTWARES], [SOFTWARES, PYTHON]):
        result = run(history)
        python, softwares = course(result, PYTHON), course(result, SOFTWARES)
        assert python.target_id == "lpcd"  # first code of source_codes
        assert (softwares.rule, softwares.category) == ("destino já ocupado", TOPICS)
        assert softwares.used_hours == 60


def test_topics_share_a_single_limit():
    result = run([PROB3_2013, NUMERICAL, PYTHON, SOFTWARES])
    topics = [c for c in result.courses if c.category == TOPICS]
    assert sum(c.hours for c in topics) == 180
    assert sum(c.used_hours for c in topics) == 120
    assert total(result, TOPICS).used_hours == 120
    assert result.lost_hours == 60
    # rule 4 fills first; the course of rule 6 loses
    assert course(result, SOFTWARES).lost_hours == 60
    assert "Excedente de Tópicos" in course(result, SOFTWARES).reason


def test_numerical_calculus_request_frees_topics():
    result = run([PROB3_2013, NUMERICAL, PYTHON, SOFTWARES])
    assert [r.target_name for r in result.requests] == ["Métodos de Otimização e Aplicações"]
    assert result.requests[0].recoverable_hours == 60
    assert result.recoverable_hours == 60


def test_requests_for_the_same_course_do_not_add_up():
    result = run([PROB3_2013, NUMERICAL, PROG_MAT])  # 180 h in topics, 60 h lost
    assert [r.recoverable_hours for r in result.requests] == [60, 60]
    assert result.recoverable_hours == 60  # only one can become Métodos de Otimização


def test_partial_loss_in_topics():
    result = run([PROB3_2013, NUMERICAL, REAL_ANALYSIS], overrides={"topics_max_hours": 150})
    c = course(result, REAL_ANALYSIS)
    assert (c.used_hours, c.lost_hours) == (30, 60)


def test_topics_2013_go_to_topics():
    result = run(TOPICS_2013[:3])
    assert {c.rule for c in result.courses} == {"Tópicos Especiais"}
    assert total(result, TOPICS).used_hours == 120
    assert result.lost_hours == 60


def test_extinct_elective_goes_to_topics_or_to_elective():
    c = course(run([CATEGORICAL]), CATEGORICAL)
    assert (c.rule, c.category, c.used_hours) == ("destino definido", TOPICS, 60)

    result = run([CATEGORICAL], destination_overrides={CATEGORICAL: "elective:CD"})
    c = course(result, CATEGORICAL)
    assert (c.category, c.emphasis) == (ELECTIVE, "CD")
    assert result.emphasis_hours["CD"] == 60


def test_confirmed_destination_cannot_be_overridden():
    with pytest.raises(ValueError):
        run([PROB3_2013], destination_overrides={PROB3_2013: "elective:EAM"})
    with pytest.raises(ValueError):
        run([CATEGORICAL], destination_overrides={CATEGORICAL: "elective:XX"})


def test_successors_count_both_and_do_not_take_the_destination():
    result = run([ECON1, ECON2])
    for code in (ECON1, ECON2):
        c = course(result, code)
        assert (c.rule, c.category, c.emphasis, c.used_hours) == ("sucessora", ELECTIVE, "EAM", 60)
    assert result.emphasis_hours["EAM"] == 120
    assert result.lost_hours == 0


def test_consultoria_emphasis_comes_from_assumption():
    assert course(run(["1108350"]), "1108350").emphasis == "EAM"
    result = run(["1108350"], overrides={"consultoria_emphasis": "CD"})
    assert course(result, "1108350").emphasis == "CD"


def test_active_aliases():
    result = run(["1103176", "1103128", "1108211"])
    assert course(result, "1103176").name == "Cálculo Numérico"
    assert course(result, "1103176").category == TOPICS
    assert course(result, "1103128").target_id == "fuvc"
    assert (course(result, "1108211").target_id, course(result, "1108211").emphasis) == ("iib", "CD")


def test_alias_target_takes_the_destination():
    result = run(["1108211", "1108153"])
    assert course(result, "1108153").target_id == "iib"
    assert course(result, "1108211").rule == "destino já ocupado"


ELECTIVES_12 = [
    "1108130", "1108135", "1108141", "1108146", "1108159", "1108216",  # EAM
    "1108142", "1108153",  # CD
    "1108157", "GDLS0024", "1103128", "1108140",  # sem ênfase (x3) e Demografia I (EAM)
]


def test_electives_above_limit_are_lost():
    result = run(ELECTIVES_12)
    electives = [c for c in result.courses if c.category == ELECTIVE]
    assert sum(c.hours for c in electives) == 720
    assert total(result, ELECTIVE).used_hours == 660
    assert result.lost_hours == 60
    lost = [c for c in electives if c.lost_hours]
    assert len(lost) == 1 and lost[0].emphasis == ""  # without emphasis is lost first
    assert "Excedente de optativas" in lost[0].reason


def test_electives_lose_the_smaller_emphasis_after_the_ones_without():
    history = ["1108130", "1108135", "1108153", "1108157"]  # EAM, EAM, CD, sem ênfase
    result = run(history, overrides={"electives_max_hours": 120})
    assert [c.code for c in result.courses if c.lost_hours] == ["1108153", "1108157"]
    assert result.emphasis_hours == {"EAM": 120, "CD": 0}


def test_market_research_counts_extension():
    result = run([MARKET])
    c = course(result, MARKET)
    assert (c.target_id, c.category) == ("pm", "mandatory")
    assert total(result, "extension").used_hours == 60
    result = run([MARKET], overrides={"old_pm_counts_as_extension": False})
    assert total(result, "extension").used_hours == 0


def test_extension_beyond_the_total_when_electives_are_full():
    result = run(ELECTIVES_12[:11])  # 660 h of non-extension electives
    assert total(result, ELECTIVE).missing_hours == 0
    # 300 h needed; room: Pesquisa de Mercado 60 h + flexible extension 180 h
    assert result.extra_extension_hours == 60
    assert run([]).extra_extension_hours == 0


def test_repeated_code_counts_once():
    result = run([EST1, EST1, " 1108353 "])
    assert len(result.courses) == 1


def test_courses_outside_the_2013_curriculum():
    history = [
        HistoryEntry("9999999", "Disciplina de outro curso", 60, "CF"),
        HistoryEntry("8888888", "Disciplina desconhecida", 60, "OB"),
    ]
    result = run(history)
    flexible, unknown = course(result, "9999999"), course(result, "8888888")
    assert (flexible.category, flexible.used_hours) == (TOPICS, 60)
    assert (unknown.category, unknown.used_hours, unknown.lost_hours) == (UNRECOGNIZED, 0, 0)
    assert result.approved_hours == 60
    assert any("8888888" in n for n in result.notices)
    assert total(result.stay, "flexible").used_hours == 60


def test_stay_scenario():
    result = run([EST1, EST2, ELECTIVES_12[0], TOPICS_2013[0]])
    assert result.stay.missing_hours == 3000 - 360 - 60 - 60
    assert EST1 not in [p.code for p in result.stay.pending]


def test_order_follows_the_2013_flowchart():
    result = run([TOPICS_2013[0], "1108157", EST1, "1103177"])
    assert [c.code for c in result.courses] == ["1103177", EST1, "1108157", TOPICS_2013[0]]


def test_result_is_json_serializable():
    result = run([EST1, EST2, PYTHON, SOFTWARES, ECON1])
    data = json.loads(result.to_json())
    assert data["recoverable_hours"] == 180
    assert {a["key"] for a in data["assumptions"]} >= {"topics_max_hours", "internship2_recoverable_max_hours"}


def test_unknown_assumption_override_is_error():
    with pytest.raises(ValueError):
        run([], overrides={"nao_existe": 1})


def test_all_of_equivalence_requires_every_source():
    from dataclasses import replace

    equivalences = tuple(
        replace(eq, source_codes=(EST1, "1108355"), match="all_of") if eq.rule_id == "eq13" else eq
        for eq in DATA.equivalences
    )
    data = replace(DATA, equivalences=equivalences)
    c = course(convert([EST1], data=data), EST1)
    assert (c.category, c.lost_hours) == (NONE, 180)
    assert "exige também Trabalho de Conclusão de Curso I" in c.reason
    assert course(convert([EST1, "1108355"], data=data), EST1).target_id == "est"


def test_recovered_internship_2_counts_as_flexible_extension_and_extension():
    from app.conversion import FLEXIBLE_EXTENSION, _Converter, resolve_assumptions, resolve_destinations

    converter = _Converter(
        DATA, resolve_assumptions(DATA.assumptions), resolve_destinations(DATA), frozenset({EST2})
    )
    items = converter.run([EST2])
    c = next(i for i in items if i.code == EST2)
    assert (c.category, c.used_hours, c.lost_hours) == (FLEXIBLE_EXTENSION, 180, 0)
    totals = {t.category: t.used_hours for t in converter.totals(items)}
    assert totals[FLEXIBLE_EXTENSION] == 180
    assert totals["extension"] == 180
