"""Validate the curriculum CSVs in data/.

Usage: python scripts/validate_data.py [data_dir]

Lists every problem found and exits with code 1 if there is any.
Warnings (external prerequisites, TBD values) do not fail the validation.
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEPARATOR = ";"
TBD = "TBD"
EXTERNAL_PREFIX = "code:"

EXPECTED_CREDITS = {
    "2026": {"mandatory": 120, "internship": 8, "complementary": 8},
    "2013": {"mandatory": 116, "internship": 24, "complementary": 8},
}


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=SEPARATOR))


def check_unique_ids(curriculum, label):
    counts = Counter(row["id"] for row in curriculum)
    return [f"{label}: id duplicado '{id_}' ({n} vezes)" for id_, n in counts.items() if n > 1]


def check_prerequisites(curriculum, prerequisites, label):
    """Return (errors, warnings) for course_id/prerequisite_id references."""
    ids = {row["id"] for row in curriculum}
    errors, warnings = [], []
    for row in prerequisites:
        course, prereq = row["course_id"], row["prerequisite_id"]
        if course not in ids:
            errors.append(f"{label}: course_id '{course}' não existe na grade")
        if prereq.startswith(EXTERNAL_PREFIX):
            warnings.append(f"{label}: '{course}' tem pré-requisito externo à grade '{prereq}'")
        elif prereq == TBD:
            warnings.append(f"{label}: '{course}' tem pré-requisito TBD")
        elif prereq not in ids:
            errors.append(f"{label}: pré-requisito '{prereq}' de '{course}' não existe na grade")
    return errors, warnings


def find_cycles(prerequisites, label):
    """Return one error per cycle found in the prerequisite graph."""
    graph = defaultdict(list)
    for row in prerequisites:
        prereq = row["prerequisite_id"]
        if prereq == TBD or prereq.startswith(EXTERNAL_PREFIX):
            continue
        graph[row["course_id"]].append(prereq)

    white, gray, black = 0, 1, 2
    color = defaultdict(int)
    errors = []

    def visit(node, path):
        color[node] = gray
        path.append(node)
        for nxt in graph[node]:
            if color[nxt] == gray:
                cycle = path[path.index(nxt):] + [nxt]
                errors.append(f"{label}: ciclo de pré-requisitos: {' -> '.join(cycle)}")
            elif color[nxt] == white:
                visit(nxt, path)
        path.pop()
        color[node] = black

    for node in list(graph):
        if color[node] == white:
            visit(node, [])
    return errors


def check_credit_totals(curriculum, expected, label):
    errors = []
    totals = defaultdict(int)
    for row in curriculum:
        try:
            totals[row["type"]] += int(row["credits"])
        except ValueError:
            errors.append(f"{label}: créditos inválidos em '{row['id']}': '{row['credits']}'")
    for type_, value in expected.items():
        if totals[type_] != value:
            errors.append(f"{label}: créditos de '{type_}' = {totals[type_]}, esperado {value}")
    return errors


def check_equivalence_targets(equivalences, curriculum_2026):
    ids = {row["id"] for row in curriculum_2026}
    return [
        f"equivalences: target_id '{row['target_id']}' de '{row['rule_id']}' não existe na grade 2026"
        for row in equivalences
        if row["target_id"] not in ids
    ]


def check_aliases(aliases, curricula):
    codes = {row["code"] for curriculum in curricula for row in curriculum}
    return [
        f"code_aliases: alias_of '{row['alias_of']}' (de '{row['code']}') não existe em nenhuma grade"
        for row in aliases
        if row["alias_of"] not in codes
    ]


def check_duplicate_name_code(curriculum, label):
    counts = Counter((row["name"], row["code"]) for row in curriculum)
    return [
        f"{label}: par (nome, código) duplicado: ('{name}', '{code}')"
        for (name, code), n in counts.items()
        if n > 1
    ]


def check_tbd_values(rows, label):
    """Warn about every field written as TBD."""
    return [
        f"{label}: valor TBD em '{list(row.values())[0]}', campo '{field}'"
        for row in rows
        for field, value in row.items()
        if value == TBD and field != "prerequisite_id"
    ]


def validate(data_dir=DEFAULT_DATA_DIR):
    """Return (errors, warnings) for all CSVs in data_dir."""
    data_dir = Path(data_dir)
    errors, warnings = [], []

    curricula = {}
    for year in ("2026", "2013"):
        label = f"grade {year}"
        curriculum = read_csv(data_dir / f"curriculum_{year}.csv")
        prerequisites = read_csv(data_dir / f"prerequisites_{year}.csv")
        curricula[year] = curriculum

        errors += check_unique_ids(curriculum, label)
        prereq_errors, prereq_warnings = check_prerequisites(curriculum, prerequisites, label)
        errors += prereq_errors
        warnings += prereq_warnings
        errors += find_cycles(prerequisites, label)
        errors += check_credit_totals(curriculum, EXPECTED_CREDITS[year], label)
        errors += check_duplicate_name_code(curriculum, label)

    equivalences = read_csv(data_dir / "equivalences.csv")
    errors += check_equivalence_targets(equivalences, curricula["2026"])
    warnings += check_tbd_values(equivalences, "equivalences")

    aliases = read_csv(data_dir / "code_aliases.csv")
    errors += check_aliases(aliases, curricula.values())

    return errors, warnings


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    data_dir = Path(argv[0]) if argv else DEFAULT_DATA_DIR
    errors, warnings = validate(data_dir)
    for warning in warnings:
        print(f"AVISO: {warning}")
    for error in errors:
        print(f"ERRO: {error}")
    if errors:
        print(f"{len(errors)} problema(s) encontrado(s).")
        return 1
    print("Dados válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
