"""Load the curriculum CSVs from data/ into typed records."""

import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEPARATOR = ";"
TBD = "TBD"


@dataclass(frozen=True)
class Course:
    id: str
    code: str
    name: str
    credits: int
    hours: int
    type: str
    semester: int | None
    emphasis: str = ""
    extension: bool = False


@dataclass(frozen=True)
class Prerequisite:
    course_id: str
    prerequisite_id: str
    group: str


@dataclass(frozen=True)
class Equivalence:
    rule_id: str
    source_codes: tuple[str, ...]
    match: str
    target_id: str
    status: str
    note: str


@dataclass(frozen=True)
class CodeAlias:
    code: str
    alias_of: str
    status: str
    note: str


@dataclass(frozen=True)
class ElectiveSuccessor:
    code: str
    successor_id: str
    note: str


@dataclass(frozen=True)
class OldCourseDestination:
    code: str
    destination: str
    status: str
    note: str


@dataclass(frozen=True)
class RequestOption:
    code: str
    target: str
    condition: str
    note: str


@dataclass(frozen=True)
class Assumption:
    key: str
    value: str
    status: str
    description: str


@dataclass(frozen=True)
class PendingIssue:
    file: str
    record: str
    field: str
    description: str


@dataclass(frozen=True)
class CurriculumData:
    curriculum_2026: tuple[Course, ...]
    curriculum_2013: tuple[Course, ...]
    prerequisites_2026: tuple[Prerequisite, ...]
    prerequisites_2013: tuple[Prerequisite, ...]
    equivalences: tuple[Equivalence, ...]
    code_aliases: tuple[CodeAlias, ...]
    elective_successors: tuple[ElectiveSuccessor, ...]
    old_course_destinations: tuple[OldCourseDestination, ...]
    request_options: tuple[RequestOption, ...]
    assumptions: tuple[Assumption, ...]
    pending_issues: tuple[PendingIssue, ...]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=SEPARATOR))


def _course(row):
    return Course(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        credits=int(row["credits"]),
        hours=int(row["hours"]),
        type=row["type"],
        semester=int(row["semester"]) if row["semester"] else None,
        emphasis=row.get("emphasis") or "",
        extension=(row.get("extension") or "false") == "true",
    )


def load_data(data_dir=DEFAULT_DATA_DIR):
    data_dir = Path(data_dir)

    def rows(name):
        return read_csv(data_dir / name)

    return CurriculumData(
        curriculum_2026=tuple(_course(r) for r in rows("curriculum_2026.csv")),
        curriculum_2013=tuple(_course(r) for r in rows("curriculum_2013.csv")),
        prerequisites_2026=tuple(Prerequisite(**r) for r in rows("prerequisites_2026.csv")),
        prerequisites_2013=tuple(Prerequisite(**r) for r in rows("prerequisites_2013.csv")),
        equivalences=tuple(
            Equivalence(
                rule_id=r["rule_id"],
                source_codes=tuple(r["source_codes"].split("|")),
                match=r["match"],
                target_id=r["target_id"],
                status=r["status"],
                note=r["note"],
            )
            for r in rows("equivalences.csv")
        ),
        code_aliases=tuple(CodeAlias(**r) for r in rows("code_aliases.csv")),
        elective_successors=tuple(ElectiveSuccessor(**r) for r in rows("elective_successors.csv")),
        old_course_destinations=tuple(
            OldCourseDestination(**r) for r in rows("old_course_destinations.csv")
        ),
        request_options=tuple(RequestOption(**r) for r in rows("request_options.csv")),
        assumptions=tuple(Assumption(**r) for r in rows("assumptions.csv")),
        pending_issues=tuple(PendingIssue(**r) for r in rows("pending_issues.csv")),
    )
