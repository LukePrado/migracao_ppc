"""Migration rules engine.

Classifies the courses passed by a student of the 2013 curriculum in two
scenarios: migrating to the 2026 curriculum or staying in the 2013 one.
All curricular data comes from data/; unconfirmed rules come from
assumptions.csv and can be overridden per call.
"""

import json
from dataclasses import asdict, dataclass, field

from app.data_loader import TBD, load_data

STATUS_USED = "aproveitada"
STATUS_PENDING = "pendente"
STATUS_ELECTIVE = "optativa"
STATUS_FLEXIBLE = "flexível"
STATUS_TO_DEFINE = "a definir"

RULE_SAME_CODE = "mesmo código"
REQUIRED_TYPES = ("mandatory", "internship", "complementary")
EMPHASES = ("EAM", "CD")
HOURS_PER_CREDIT = 15

# Curriculum parameters confirmed in the PPCs (see CLAUDE.md); not assumptions.
REQUIRED_ELECTIVE_CREDITS_2026 = 44
REQUIRED_FLEXIBLE_CREDITS_2026 = 20
MIN_EMPHASIS_CREDITS = 24
REQUIRED_ELECTIVE_CREDITS_2013 = 36
REQUIRED_FLEXIBLE_CREDITS_2013 = 16

USED_ASSUMPTIONS = (
    "internship_match",
    "old_electives_count_for_emphasis",
    "migrant_extension_hours",
    "old_pm_counts_as_extension",
    "old_flexible_max_hours",
)


@dataclass
class AssumptionUsed:
    key: str
    value: str
    status: str
    description: str
    overridden: bool = False


@dataclass
class CourseResult:
    """A course of the target curriculum and its situation."""

    id: str
    code: str
    name: str
    type: str
    credits: int
    status: str
    source_codes: list[str] = field(default_factory=list)
    rule: str = ""
    note: str = ""


@dataclass
class TakenCourse:
    """A passed 2013 course counted as elective or flexible after migrating."""

    id: str
    code: str
    name: str
    credits: int
    hours: int
    status: str
    emphasis: str = ""
    note: str = ""


@dataclass
class ToDefine:
    record: str
    course_id: str
    description: str


@dataclass
class CreditTotal:
    category: str
    done: int
    required: int
    unit: str = "cr"


@dataclass
class MigrateResult:
    used: list[CourseResult]
    pending: list[CourseResult]
    electives: list[TakenCourse]
    flexibles: list[TakenCourse]
    to_define: list[ToDefine]
    notices: list[str]
    totals: list[CreditTotal]
    emphasis_credits: dict[str, int]
    emphases: list[str]


@dataclass
class StayResult:
    pending: list[CourseResult]
    totals: list[CreditTotal]


@dataclass
class Evaluation:
    migrate: MigrateResult
    stay: StayResult
    assumptions: list[AssumptionUsed]
    unknown_codes: list[str]
    notices: list[str]
    taken_codes: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def _to_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    return str(value)


def _as_bool(assumption):
    if assumption.value not in ("true", "false"):
        raise ValueError(f"Premissa '{assumption.key}' deveria ser true/false: '{assumption.value}'")
    return assumption.value == "true"


def _as_int(assumption):
    try:
        return int(assumption.value)
    except ValueError:
        raise ValueError(f"Premissa '{assumption.key}' deveria ser inteira: '{assumption.value}'") from None


def resolve_assumptions(assumptions, overrides=None):
    """Return {key: AssumptionUsed}, applying the overrides given by the caller."""
    overrides = overrides or {}
    by_key = {a.key: a for a in assumptions}
    unknown = sorted(set(overrides) - set(by_key))
    if unknown:
        raise ValueError(f"Premissas desconhecidas: {', '.join(unknown)}")
    return {
        key: AssumptionUsed(
            key=key,
            value=_to_text(overrides[key]) if key in overrides else a.value,
            status=a.status,
            description=a.description,
            overridden=key in overrides,
        )
        for key, a in by_key.items()
    }


def normalize_codes(codes, aliases):
    """Uppercase, strip and map codes through the active aliases."""
    active = {a.code: a.alias_of for a in aliases if a.status == "active"}
    normalized = set()
    for code in codes:
        code = code.strip().upper()
        if code:
            normalized.add(active.get(code, code))
    return normalized


def _match_sources(source_codes, taken, match):
    """Return the source codes used to satisfy a rule, or None if unsatisfied."""
    present = [c for c in source_codes if c in taken]
    if match == "any_of":
        return present[:1] or None
    if match == "all_of":
        return present if len(present) == len(source_codes) else None
    raise ValueError(f"match inválido: '{match}'")


def _course_result(course, status, source_codes=(), rule="", note=""):
    return CourseResult(
        id=course.id,
        code=course.code,
        name=course.name,
        type=course.type,
        credits=course.credits,
        status=status,
        source_codes=list(source_codes),
        rule=rule,
        note=note,
    )


def _names(codes, by_code):
    return ", ".join(f"{by_code[c].name} ({c})" if c in by_code else c for c in codes)


def _evaluate_migrate(taken, data, assumptions):
    by_id_2026 = {c.id: c for c in data.curriculum_2026}
    by_code_2013 = {c.code: c for c in data.curriculum_2013}
    pending_descriptions = {(p.file, p.record): p.description for p in data.pending_issues}
    successors = {s.code: s.successor_id for s in data.elective_successors}

    results = {}
    consumed = set()
    to_define, notices = [], []

    # Step 2a: same code in both curricula.
    for course in data.curriculum_2026:
        if course.code in taken:
            results[course.id] = _course_result(course, STATUS_USED, [course.code], RULE_SAME_CODE)
            consumed.add(course.code)

    # Steps 2b, 6 and 7: equivalence rules.
    for eq in data.equivalences:
        if not any(c in taken for c in eq.source_codes):
            continue
        target = by_id_2026.get(eq.target_id)
        if target is not None and target.id in results:
            continue
        match = eq.match
        if target is not None and target.type == "internship":
            match = assumptions["internship_match"].value

        if eq.status == "proposed":
            if TBD not in (match, *eq.source_codes) and target and _match_sources(eq.source_codes, taken, match):
                present = [c for c in eq.source_codes if c in taken]
                notices.append(
                    f"Você cursou {_names(present, by_code_2013)}: há uma proposta em análise pela "
                    f"coordenação ({eq.rule_id}) para aproveitá-la como {target.name}. "
                    "Por ora, a proposta não é aplicada."
                )
            continue
        if eq.status != "active":
            continue

        present = [c for c in eq.source_codes if c in taken]
        if TBD in (match, eq.target_id, *eq.source_codes):
            description = pending_descriptions.get(("equivalences.csv", eq.rule_id), eq.note)
            to_define.append(ToDefine(eq.rule_id, eq.target_id, description))
            if target is not None:
                results[target.id] = _course_result(target, STATUS_TO_DEFINE, present, eq.rule_id, description)
            consumed.update(present)
            continue

        used = _match_sources(eq.source_codes, taken, match)
        if used is None:
            missing = [c for c in eq.source_codes if c not in taken]
            notices.append(
                f"Você cursou {_names(present, by_code_2013)}, mas a equivalência {eq.rule_id} com "
                f"{target.name} exige também {_names(missing, by_code_2013)} (match {match}). "
                "A disciplina cursada é contada como optativa."
            )
            continue
        results[target.id] = _course_result(target, STATUS_USED, used, eq.rule_id, eq.note)
        consumed.update(used)

    # Step 3: required 2026 components not covered.
    for course in data.curriculum_2026:
        if course.type in REQUIRED_TYPES and course.id not in results:
            results[course.id] = _course_result(course, STATUS_PENDING)

    # Steps 4 and 5: remaining passed courses become electives or flexibles.
    count_successors = _as_bool(assumptions["old_electives_count_for_emphasis"])
    electives, flexibles = [], []
    for code in sorted(taken - consumed):
        old = by_code_2013.get(code)
        if old is None:
            continue
        if old.type == "flexible":
            flexibles.append(TakenCourse(old.id, old.code, old.name, old.credits, old.hours, STATUS_FLEXIBLE))
            continue
        emphasis, note = "", ""
        successor = by_id_2026.get(successors.get(code, ""))
        if successor is not None:
            note = f"Sucessora na grade 2026: {successor.name}."
            if count_successors:
                emphasis = successor.emphasis
        electives.append(
            TakenCourse(old.id, old.code, old.name, old.credits, old.hours, STATUS_ELECTIVE, emphasis, note)
        )

    max_flexible_hours = _as_int(assumptions["old_flexible_max_hours"])
    flexible_hours = sum(c.hours for c in flexibles)
    counted_flexible_hours = min(flexible_hours, max_flexible_hours)
    if flexible_hours > max_flexible_hours:
        notices.append(
            f"Os Tópicos Especiais cursados somam {flexible_hours} h, mas só {max_flexible_hours} h "
            "são aproveitadas como flexíveis."
        )

    used = [r for r in results.values() if r.status == STATUS_USED]
    pending = [r for r in results.values() if r.status == STATUS_PENDING]

    def used_credits(type_):
        return sum(r.credits for r in used if r.type == type_)

    def required_credits(type_):
        return sum(c.credits for c in data.curriculum_2026 if c.type == type_)

    emphasis_credits = {e: 0 for e in EMPHASES}
    for r in used:
        emphasis = by_id_2026[r.id].emphasis
        if r.type == "elective" and emphasis in emphasis_credits:
            emphasis_credits[emphasis] += r.credits
    for c in electives:
        if c.emphasis in emphasis_credits:
            emphasis_credits[c.emphasis] += c.credits

    extension_hours = 0
    if _as_bool(assumptions["old_pm_counts_as_extension"]):
        extension_hours = sum(by_id_2026[r.id].hours for r in used if by_id_2026[r.id].extension)

    totals = [CreditTotal(t, used_credits(t), required_credits(t)) for t in REQUIRED_TYPES]
    totals += [
        CreditTotal(
            "elective",
            used_credits("elective") + sum(c.credits for c in electives),
            REQUIRED_ELECTIVE_CREDITS_2026,
        ),
        CreditTotal("flexible", counted_flexible_hours // HOURS_PER_CREDIT, REQUIRED_FLEXIBLE_CREDITS_2026),
        CreditTotal("extension", extension_hours, _as_int(assumptions["migrant_extension_hours"]), "h"),
    ]

    return MigrateResult(
        used=used,
        pending=pending,
        electives=electives,
        flexibles=flexibles,
        to_define=to_define,
        notices=notices,
        totals=totals,
        emphasis_credits=emphasis_credits,
        emphases=[e for e in EMPHASES if emphasis_credits[e] >= MIN_EMPHASIS_CREDITS],
    )


def _evaluate_stay(taken, data):
    curriculum = data.curriculum_2013
    pending = [
        _course_result(c, STATUS_PENDING)
        for c in curriculum
        if c.type in REQUIRED_TYPES and c.code not in taken
    ]

    def credits(type_, only_taken):
        return sum(c.credits for c in curriculum if c.type == type_ and (not only_taken or c.code in taken))

    totals = [CreditTotal(t, credits(t, True), credits(t, False)) for t in REQUIRED_TYPES]
    totals += [
        CreditTotal("elective", credits("elective", True), REQUIRED_ELECTIVE_CREDITS_2013),
        CreditTotal("flexible", credits("flexible", True), REQUIRED_FLEXIBLE_CREDITS_2013),
    ]
    return StayResult(pending=pending, totals=totals)


def evaluate(codes, overrides=None, data=None):
    """Classify the passed SIGAA codes of a 2013 student in both scenarios.

    codes: iterable of SIGAA codes passed by the student.
    overrides: optional {assumption_key: value} replacing assumptions.csv values.
    data: optional CurriculumData (defaults to data/).
    """
    data = data or load_data()
    assumptions = resolve_assumptions(data.assumptions, overrides)
    raw_codes = {c.strip().upper() for c in codes if c.strip()}
    taken = normalize_codes(raw_codes, data.code_aliases)

    known = {c.code for c in data.curriculum_2013} | {c.code for c in data.curriculum_2026}
    known |= {c for eq in data.equivalences for c in eq.source_codes}
    unknown_codes = sorted(taken - known)
    taken -= set(unknown_codes)

    notices = [
        f"O código {code} não consta das grades 2013 e 2026 e não foi considerado."
        for code in unknown_codes
    ]
    notices += [
        f"{alias.note}: os códigos {alias.code} e {alias.alias_of} podem vir a valer como a mesma "
        "disciplina (proposta em análise pela coordenação). Por ora, são tratados separadamente."
        for alias in data.code_aliases
        if alias.status == "proposed" and alias.code in raw_codes
    ]

    return Evaluation(
        migrate=_evaluate_migrate(taken, data, assumptions),
        stay=_evaluate_stay(taken, data),
        assumptions=[assumptions[key] for key in USED_ASSUMPTIONS],
        unknown_codes=unknown_codes,
        notices=notices,
        taken_codes=sorted(taken),
    )
