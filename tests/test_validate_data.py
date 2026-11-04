import shutil
from pathlib import Path

import validate_data as vd

FIXTURES = Path(__file__).parent / "fixtures"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load(name):
    return vd.read_csv(FIXTURES / name)


def test_real_data_is_valid():
    errors, _ = vd.validate(DATA_DIR)
    assert errors == []


def test_real_data_warns_about_external_and_has_no_tbd():
    _, warnings = vd.validate(DATA_DIR)
    assert any("code:1107136" in w for w in warnings)
    assert not any("TBD" in w for w in warnings)


def test_cycle_is_detected():
    errors = vd.find_cycles(load("prerequisites_cycle.csv"), "teste")
    assert len(errors) == 1
    assert "ciclo" in errors[0]


def test_no_cycle_in_acyclic_graph():
    assert vd.find_cycles(load("prerequisites_missing.csv"), "teste") == []


def test_missing_prerequisite_is_error_and_external_is_warning():
    errors, warnings = vd.check_prerequisites(
        load("curriculum_small.csv"), load("prerequisites_missing.csv"), "teste"
    )
    assert len(errors) == 1
    assert "inexistente" in errors[0]
    assert len(warnings) == 1
    assert "code:9999999" in warnings[0]


def test_duplicate_id():
    rows = load("curriculum_small.csv") + [load("curriculum_small.csv")[0]]
    assert len(vd.check_unique_ids(rows, "teste")) == 1


def test_same_name_with_different_codes_is_allowed():
    rows = [
        {"name": "Libras", "code": "1403747"},
        {"name": "Libras", "code": "GDLS0024"},
    ]
    assert vd.check_duplicate_name_code(rows, "teste") == []
    assert len(vd.check_duplicate_name_code(rows + rows[:1], "teste")) == 1


def test_credit_totals():
    rows = load("curriculum_small.csv")
    assert vd.check_credit_totals(rows, {"mandatory": 12}, "teste") == []
    assert len(vd.check_credit_totals(rows, {"mandatory": 16, "internship": 0}, "teste")) == 1


def test_equivalence_target_must_exist():
    curriculum = load("curriculum_small.csv")
    equivalences = [
        {"rule_id": "eq1", "target_id": "a"},
        {"rule_id": "eq2", "target_id": "zz"},
    ]
    errors = vd.check_equivalence_targets(equivalences, curriculum)
    assert len(errors) == 1
    assert "zz" in errors[0]


def test_alias_target_must_exist():
    curriculum = load("curriculum_small.csv")
    aliases = [
        {"code": "9", "alias_of": "1000001"},
        {"code": "8", "alias_of": "7777777"},
    ]
    errors = vd.check_aliases(aliases, [curriculum])
    assert len(errors) == 1
    assert "7777777" in errors[0]


def test_successor_must_exist_in_both_curricula():
    curriculum = load("curriculum_small.csv")
    successors = [
        {"code": "1000001", "successor_id": "b"},
        {"code": "7777777", "successor_id": "zz"},
    ]
    errors = vd.check_successors(successors, curriculum, curriculum)
    assert len(errors) == 2


def test_main_exits_1_on_cycle(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    with open(data / "prerequisites_2026.csv", "a", encoding="utf-8") as f:
        f.write("aevd;pae;1\n")
    assert vd.main([str(data)]) == 1


def test_main_exits_0_on_real_data():
    assert vd.main([str(DATA_DIR)]) == 0


def course(id_, code, type_="elective", credits="4", hours="60"):
    return {"id": id_, "code": code, "name": id_, "credits": credits, "hours": hours, "type": type_}


def test_hours_must_match_credits_and_total():
    rows = [course("a", "1", "mandatory", "196", "2940"), course("b", "2", "flexible", "4", "60")]
    assert vd.check_hours(rows, 0, "teste") == []
    assert len(vd.check_hours(rows, 60, "teste")) == 1
    rows.append(course("c", "3", "elective", "4", "90"))
    errors = vd.check_hours(rows, 0, "teste")
    assert len(errors) == 1
    assert "'c'" in errors[0]


def test_allowed_values():
    rows = [
        {"code": "1", "destination": "topics", "status": "assumed"},
        {"code": "2", "destination": "elective:XX", "status": "confirmed"},
        {"code": "3", "destination": "none", "status": "talvez"},
    ]
    errors = vd.check_allowed_values(rows, vd.ALLOWED_VALUES["old_course_destinations"], "teste")
    assert len(errors) == 2
    assert any("elective:XX" in e for e in errors)
    assert any("talvez" in e for e in errors)


def test_destination_code_must_exist_and_be_unique():
    curriculum = load("curriculum_small.csv")
    destinations = [
        {"code": "1000001", "destination": "topics"},
        {"code": "1000001", "destination": "none"},
        {"code": "7777777", "destination": "topics"},
    ]
    errors = vd.check_destinations(destinations, curriculum)
    assert len(errors) == 2


def test_request_option_target_must_be_2026_id_or_extension():
    curriculum = load("curriculum_small.csv")
    options = [
        {"code": "1000001", "target": "a"},
        {"code": "1000002", "target": "extension"},
        {"code": "7777777", "target": "zz"},
    ]
    errors = vd.check_request_options(options, curriculum, curriculum)
    assert len(errors) == 2


def test_missing_assumption_is_error():
    rows = [{"key": key} for key in vd.REQUIRED_ASSUMPTIONS if key != "topics_max_hours"]
    errors = vd.check_assumption_keys(rows)
    assert errors == ["assumptions: premissa 'topics_max_hours' ausente"]


def single_destination_errors(curriculum_2013, **overrides):
    tables = {
        "curriculum_2026": [course("x", "1000001", "mandatory"), course("y", "NEW", "mandatory")],
        "equivalences": [{"source_codes": "1000002|1000009", "status": "active"}],
        "aliases": [{"code": "1000008", "alias_of": "1000001", "status": "active"}],
        "successors": [{"code": "1000003"}],
        "destinations": [{"code": "1000004"}],
    }
    tables.update(overrides)
    return vd.check_single_destination(curriculum_2013, **tables)


def test_each_rule_gives_a_destination():
    curriculum_2013 = [
        course("same", "1000001"),
        course("alias", "1000008"),
        course("equiv", "1000009"),
        course("succ", "1000003"),
        course("dest", "1000004"),
        course("flex", "1000005", "flexible"),
    ]
    assert single_destination_errors(curriculum_2013) == []


def test_course_without_destination_is_error():
    errors = single_destination_errors([course("orphan", "1000006"), course("new", "NEW")])
    assert len(errors) == 2
    assert all("não tem destino" in e for e in errors)


def test_course_with_two_destinations_is_error():
    errors = single_destination_errors(
        [course("both", "1000001")], destinations=[{"code": "1000001"}]
    )
    assert len(errors) == 1
    assert "mesmo código, destino definido" in errors[0]


def test_inactive_equivalence_and_alias_do_not_count():
    errors = single_destination_errors(
        [course("equiv", "1000002"), course("alias", "1000008")],
        equivalences=[{"source_codes": "1000002", "status": "proposed"}],
        aliases=[{"code": "1000008", "alias_of": "1000001", "status": "proposed"}],
    )
    assert len(errors) == 2


def test_main_exits_1_when_2013_course_loses_destination(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    path = data / "old_course_destinations.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(line for line in lines if not line.startswith("1108197;")) + "\n", encoding="utf-8")
    assert vd.main([str(data)]) == 1


def test_row_with_extra_column_is_error(tmp_path):
    (tmp_path / "x.csv").write_text("a;b\n1;2\n1;2;3\n4\n", encoding="utf-8")
    errors = vd.check_columns(tmp_path)
    assert len(errors) == 2
    assert "linha 3" in errors[0]
    assert "linha 4" in errors[1]


def test_real_data_loads():
    from app.data_loader import load_data

    data = load_data(DATA_DIR)
    assert len(data.old_course_destinations) == 15
    assert len(data.request_options) == 3
