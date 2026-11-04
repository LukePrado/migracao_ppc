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
    "2026": {"mandatory": 120, "internship": 8, "complementary": 8, "flexible": 20},
    "2013": {"mandatory": 116, "internship": 24, "complementary": 8, "flexible": 16},
}
HOURS_PER_CREDIT = 15
TOTAL_HOURS = 3000
MIN_ELECTIVE_HOURS = {"2026": 660, "2013": 540}

ALLOWED_VALUES = {
    "equivalences": {"match": {"any_of", "all_of"}, "status": {"active", "proposed"}},
    "code_aliases": {"status": {"active", "proposed"}},
    "old_course_destinations": {
        "destination": {"topics", "none", "elective:EAM", "elective:CD", "elective:none"},
        "status": {"confirmed", "assumed"},
    },
    "assumptions": {"status": {"confirmed", "assumed"}},
}
REQUIRED_ASSUMPTIONS = (
    "start_term",
    "migrant_extension_hours",
    "old_pm_counts_as_extension",
    "topics_max_hours",
    "electives_max_hours",
    "consultoria_emphasis",
    "emphasis_min_hours",
)
EXTENSION_TARGET = "extension"


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=SEPARATOR))


def check_columns(data_dir):
    """Every row must have exactly the columns of the header."""
    errors = []
    for path in sorted(Path(data_dir).glob("*.csv")):
        for line_number, row in enumerate(read_csv(path), start=2):
            if None in row or None in row.values():
                errors.append(f"{path.name}: linha {line_number} com número de colunas diferente do cabeçalho")
    return errors


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


def check_successors(successors, curriculum_2013, curriculum_2026):
    codes_2013 = {row["code"] for row in curriculum_2013}
    ids_2026 = {row["id"] for row in curriculum_2026}
    errors = []
    for row in successors:
        if row["code"] not in codes_2013:
            errors.append(f"elective_successors: código '{row['code']}' não existe na grade 2013")
        if row["successor_id"] not in ids_2026:
            errors.append(f"elective_successors: successor_id '{row['successor_id']}' não existe na grade 2026")
    return errors


def check_hours(curriculum, min_elective_hours, label):
    """Hours must equal credits x 15, and the fixed part plus the minimum of
    electives must add up to the total of the curriculum."""
    errors = []
    fixed_hours = 0
    for row in curriculum:
        try:
            credits, hours = int(row["credits"]), int(row["hours"])
        except ValueError:
            continue  # reported by check_credit_totals
        if hours != credits * HOURS_PER_CREDIT:
            errors.append(f"{label}: '{row['id']}' tem {hours} h e {credits} cr (esperado {credits * HOURS_PER_CREDIT} h)")
        if row["type"] != "elective":
            fixed_hours += hours
    total = fixed_hours + min_elective_hours
    if total != TOTAL_HOURS:
        errors.append(
            f"{label}: horas fixas ({fixed_hours}) + optativas ({min_elective_hours}) = {total}, esperado {TOTAL_HOURS}"
        )
    return errors


def check_allowed_values(rows, allowed, label):
    return [
        f"{label}: valor inválido '{row[field]}' no campo '{field}' de '{list(row.values())[0]}'"
        for row in rows
        for field, values in allowed.items()
        if row[field] not in values
    ]


def check_destinations(destinations, curriculum_2013):
    codes_2013 = {row["code"] for row in curriculum_2013}
    errors = [
        f"old_course_destinations: código '{row['code']}' não existe na grade 2013"
        for row in destinations
        if row["code"] not in codes_2013
    ]
    counts = Counter(row["code"] for row in destinations)
    errors += [f"old_course_destinations: código '{code}' repetido" for code, n in counts.items() if n > 1]
    return errors


def check_request_options(options, curriculum_2013, curriculum_2026):
    codes_2013 = {row["code"] for row in curriculum_2013}
    targets = {row["id"] for row in curriculum_2026} | {EXTENSION_TARGET}
    errors = []
    for row in options:
        if row["code"] not in codes_2013:
            errors.append(f"request_options: código '{row['code']}' não existe na grade 2013")
        if row["target"] not in targets:
            errors.append(f"request_options: target '{row['target']}' não é id da grade 2026 nem '{EXTENSION_TARGET}'")
    return errors


def check_assumption_keys(assumptions):
    keys = {row["key"] for row in assumptions}
    return [f"assumptions: premissa '{key}' ausente" for key in REQUIRED_ASSUMPTIONS if key not in keys]


def conversion_rules_matched(row, codes_2026, equivalence_codes, successor_codes, destination_codes, alias_of):
    """Names of the conversion rules 1 to 5 that apply to a 2013 course."""
    code = alias_of.get(row["code"], row["code"])
    matched = []
    if code in codes_2026:
        matched.append("mesmo código")
    if code in equivalence_codes:
        matched.append("equivalência")
    if row["code"] in successor_codes:
        matched.append("sucessora")
    if row["code"] in destination_codes:
        matched.append("destino definido")
    if row["type"] == "flexible":
        matched.append("Tópicos Especiais")
    return matched


def check_single_destination(curriculum_2013, curriculum_2026, equivalences, aliases, successors, destinations):
    """Every 2013 course must have exactly one destination by rules 1 to 5."""
    alias_of = {row["code"]: row["alias_of"] for row in aliases if row["status"] == "active"}

    def normalize(code):
        return alias_of.get(code, code)

    codes_2026 = {normalize(row["code"]) for row in curriculum_2026 if row["code"] != "NEW"}
    equivalence_codes = {
        normalize(code)
        for row in equivalences
        if row["status"] == "active"
        for code in row["source_codes"].split("|")
    }
    successor_codes = {row["code"] for row in successors}
    destination_codes = {row["code"] for row in destinations}

    errors = []
    for row in curriculum_2013:
        matched = conversion_rules_matched(
            row, codes_2026, equivalence_codes, successor_codes, destination_codes, alias_of
        )
        if not matched:
            errors.append(f"grade 2013: '{row['id']}' ({row['code']}) não tem destino na grade 2026")
        elif len(matched) > 1:
            errors.append(f"grade 2013: '{row['id']}' ({row['code']}) tem mais de um destino: {', '.join(matched)}")
    return errors


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
    errors += check_columns(data_dir)

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
        errors += check_hours(curriculum, MIN_ELECTIVE_HOURS[year], label)
        errors += check_duplicate_name_code(curriculum, label)

    equivalences = read_csv(data_dir / "equivalences.csv")
    errors += check_equivalence_targets(equivalences, curricula["2026"])
    warnings += check_tbd_values(equivalences, "equivalences")

    aliases = read_csv(data_dir / "code_aliases.csv")
    errors += check_aliases(aliases, curricula.values())

    successors = read_csv(data_dir / "elective_successors.csv")
    errors += check_successors(successors, curricula["2013"], curricula["2026"])

    destinations = read_csv(data_dir / "old_course_destinations.csv")
    errors += check_destinations(destinations, curricula["2013"])

    options = read_csv(data_dir / "request_options.csv")
    errors += check_request_options(options, curricula["2013"], curricula["2026"])

    assumptions = read_csv(data_dir / "assumptions.csv")
    errors += check_assumption_keys(assumptions)
    warnings += check_tbd_values(assumptions, "assumptions")

    tables = {
        "equivalences": equivalences,
        "code_aliases": aliases,
        "old_course_destinations": destinations,
        "assumptions": assumptions,
    }
    for label, rows in tables.items():
        errors += check_allowed_values(rows, ALLOWED_VALUES[label], label)

    errors += check_single_destination(
        curricula["2013"], curricula["2026"], equivalences, aliases, successors, destinations
    )

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
