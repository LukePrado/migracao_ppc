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


def test_real_data_warns_about_external_and_tbd():
    _, warnings = vd.validate(DATA_DIR)
    assert any("code:1107136" in w for w in warnings)
    assert any("'econ'" in w and "TBD" in w for w in warnings)
    assert any("eq13" in w for w in warnings)


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


def test_main_exits_1_on_cycle(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    with open(data / "prerequisites_2026.csv", "a", encoding="utf-8") as f:
        f.write("aevd;pae;1\n")
    assert vd.main([str(data)]) == 1


def test_main_exits_0_on_real_data():
    assert vd.main([str(DATA_DIR)]) == 0
