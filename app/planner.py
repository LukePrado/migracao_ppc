"""Term-by-term planning for both scenarios (migrate and stay).

Builds a plan from first_planning_term until nothing is pending, respecting
prerequisites (with OR groups), term parity of the offer and the credit limit
per term. Offer and limits come from assumptions.csv.
"""

import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from app.data_loader import TBD, load_data
from app.rules import _as_int, resolve_assumptions

# Confirmed curriculum parameters (see CLAUDE.md); not assumptions.
MAX_TERMS_SINCE_ENTRY = 12
MIN_CREDITS_2026 = 17
MIN_CREDITS_2013 = 12
SLOT_CREDITS = 4
EXTERNAL_PREFIX = "code:"

KIND_COURSE = "course"
KIND_ELECTIVE_SLOT = "elective_slot"
KIND_FLEXIBLE_SLOT = "flexible_slot"
ELECTIVE_SLOT_NAME = "Optativa a escolher"
FLEXIBLE_SLOT_NAME = "Flexível a escolher"

USED_ASSUMPTIONS = (
    "first_planning_term",
    "every_term_types",
    "transition_every_term_ids",
    "max_credits_2026",
    "max_credits_2013",
    "target_credits_2026",
    "target_credits_2013",
)

TERM_PATTERN = re.compile(r"^(\d{4})\.([12])$")


@dataclass
class PlannedCourse:
    id: str
    code: str
    name: str
    credits: int
    kind: str = KIND_COURSE


@dataclass
class Term:
    term: str
    courses: list[PlannedCourse]
    credits: int


@dataclass
class Plan:
    scenario: str
    terms: list[Term]
    remaining_terms: int
    conclusion_term: str | None
    deadline_term: str | None
    exceeds_deadline: bool
    unscheduled: list[str]
    notices: list[str]


@dataclass
class Planning:
    migrate: Plan
    stay: Plan
    assumptions: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def term_index(term):
    match = TERM_PATTERN.match(term)
    if not match:
        raise ValueError(f"Período inválido: '{term}' (use AAAA.1 ou AAAA.2)")
    return int(match.group(1)) * 2 + int(match.group(2)) - 1


def term_from_index(index):
    return f"{index // 2}.{index % 2 + 1}"


def _as_list(assumption):
    return [v for v in assumption.value.split("|") if v]


def _prerequisite_groups(prerequisites):
    groups = defaultdict(lambda: defaultdict(list))
    for p in prerequisites:
        groups[p.course_id][p.group].append(p.prerequisite_id)
    return groups


def _chain_lengths(pending_ids, groups):
    """Longest chain of pending dependents starting at each pending course."""
    dependents = defaultdict(set)
    for course_id in pending_ids:
        for group in groups[course_id].values():
            for prereq in group:
                if prereq in pending_ids:
                    dependents[prereq].add(course_id)
    lengths = {}

    def length(course_id):
        if course_id not in lengths:
            lengths[course_id] = 1 + max((length(d) for d in dependents[course_id]), default=0)
        return lengths[course_id]

    return {course_id: length(course_id) for course_id in pending_ids}


def _build_plan(
    scenario,
    pending,
    completed,
    external_codes,
    groups,
    is_offered,
    max_credits,
    target_credits,
    min_credits,
    first_term,
    slots,
    entry_term,
    notices,
):
    """Greedy term-by-term scheduler.

    pending: list of Course to schedule; completed: ids already done;
    slots: list of (kind, name) generic 4-credit slots, filled only up to
    target_credits; courses may go up to max_credits.
    """
    pending_ids = {c.id for c in pending}
    chains = _chain_lengths(pending_ids, groups)
    order = sorted(pending, key=lambda c: (-chains[c.id], c.semester or 99, c.id))
    completed = set(completed)
    remaining = list(order)
    slots = list(slots)
    terms = []
    index = term_index(first_term)
    idle_terms = 0

    def prerequisites_met(course):
        course_groups = groups[course.id]
        if not course_groups:
            return True
        return any(
            all(
                prereq[len(EXTERNAL_PREFIX):] in external_codes
                if prereq.startswith(EXTERNAL_PREFIX)
                else prereq != TBD and prereq in completed
                for prereq in group
            )
            for group in course_groups.values()
        )

    while remaining or slots:
        term = term_from_index(index)
        planned, credits = [], 0
        for course in list(remaining):
            if credits + course.credits > max_credits:
                continue
            if is_offered(course, term) and prerequisites_met(course):
                planned.append(PlannedCourse(course.id, course.code, course.name, course.credits))
                credits += course.credits
                remaining.remove(course)
        scheduled_courses = bool(planned)
        while slots and credits + SLOT_CREDITS <= min(target_credits, max_credits):
            kind, name = slots.pop(0)
            planned.append(PlannedCourse("", "", name, SLOT_CREDITS, kind))
            credits += SLOT_CREDITS

        if planned:
            terms.append(Term(term, planned, credits))
        completed.update(p.id for p in planned if p.kind == KIND_COURSE)

        # A full year without any course scheduled means the rest is blocked.
        idle_terms = 0 if scheduled_courses else idle_terms + 1
        if remaining and not slots and idle_terms >= 2:
            break
        index += 1

    for term in terms[:-1]:
        if term.credits < min_credits:
            notices.append(
                f"O período {term.term} fica com {term.credits} créditos, abaixo do mínimo de "
                f"{min_credits} por período."
            )

    unscheduled = [c.id for c in remaining]
    if unscheduled:
        names = ", ".join(c.name for c in remaining)
        notices.append(
            f"Não foi possível planejar: {names}. Os pré-requisitos não podem ser cumpridos com os dados atuais."
        )

    conclusion_term = terms[-1].term if terms else None
    deadline_term, exceeds = None, False
    if entry_term:
        deadline_index = term_index(entry_term) + MAX_TERMS_SINCE_ENTRY - 1
        deadline_term = term_from_index(deadline_index)
        if conclusion_term and term_index(conclusion_term) > deadline_index:
            exceeds = True
            notices.append(
                f"A conclusão prevista ({conclusion_term}) ultrapassa o prazo máximo de "
                f"{MAX_TERMS_SINCE_ENTRY} períodos desde o ingresso ({deadline_term})."
            )
    if not terms and not unscheduled:
        notices.append("Não há pendências neste cenário.")

    return Plan(
        scenario=scenario,
        terms=terms,
        remaining_terms=len(terms),
        conclusion_term=conclusion_term,
        deadline_term=deadline_term,
        exceeds_deadline=exceeds,
        unscheduled=unscheduled,
        notices=notices,
    )


def _missing_slots(totals):
    by_category = {t.category: t for t in totals}
    slots = []
    for category, kind, name in (
        ("elective", KIND_ELECTIVE_SLOT, ELECTIVE_SLOT_NAME),
        ("flexible", KIND_FLEXIBLE_SLOT, FLEXIBLE_SLOT_NAME),
    ):
        total = by_category[category]
        missing = max(0, total.required - total.done)
        slots += [(kind, name)] * math.ceil(missing / SLOT_CREDITS)
    return slots


def _offer_rule(every_term_types, every_term_ids):
    def is_offered(course, term):
        if course.type in every_term_types or course.id in every_term_ids:
            return True
        if course.semester is None:
            return True
        # Odd flowchart semesters are offered in .1 terms, even ones in .2.
        return (course.semester % 2 == 1) == term.endswith(".1")

    return is_offered


def _offer_notice(every_term_types, every_term_ids, by_id):
    notice = (
        "Optativas, flexíveis, estágio e TCC não têm periodicidade definida: o planejamento assume "
        f"oferta em todo período para os tipos {', '.join(every_term_types)}."
    )
    if every_term_ids:
        names = ", ".join(by_id[i].name for i in every_term_ids if i in by_id)
        notice += f" Na transição, assume também oferta em todo período de: {names}."
    return notice


def plan(evaluation, entry_term=None, overrides=None, data=None):
    """Plan the remaining terms of both scenarios of an Evaluation.

    entry_term: term of entry in the course (AAAA.1/AAAA.2), for the deadline check.
    overrides: same assumption overrides given to rules.evaluate.
    """
    data = data or load_data()
    assumptions = resolve_assumptions(data.assumptions, overrides)
    first_term = assumptions["first_planning_term"].value
    term_index(first_term)
    if entry_term:
        term_index(entry_term)
    every_term_types = _as_list(assumptions["every_term_types"])
    transition_ids = _as_list(assumptions["transition_every_term_ids"])
    external_codes = set(evaluation.taken_codes) | set(evaluation.unknown_codes)

    # Migrate scenario (2026 curriculum).
    by_id_2026 = {c.id: c for c in data.curriculum_2026}
    migrate_notices = [_offer_notice(every_term_types, transition_ids, by_id_2026)]
    completed_2026 = {r.id for r in evaluation.migrate.used}
    for item in evaluation.migrate.to_define:
        completed_2026.add(item.course_id)
        if item.course_id in by_id_2026:
            migrate_notices.append(
                f"{by_id_2026[item.course_id].name} não foi planejada: a definir pela coordenação."
            )
    extension = next((t for t in evaluation.migrate.totals if t.category == "extension"), None)
    if extension and extension.done < extension.required:
        migrate_notices.append(
            f"Faltam {extension.required - extension.done} h de extensão: escolha componentes "
            "extensionistas entre as optativas e flexíveis a cursar."
        )
    migrate_plan = _build_plan(
        scenario="migrate",
        pending=[by_id_2026[r.id] for r in evaluation.migrate.pending],
        completed=completed_2026,
        external_codes=external_codes,
        groups=_prerequisite_groups(data.prerequisites_2026),
        is_offered=_offer_rule(every_term_types, transition_ids),
        max_credits=_as_int(assumptions["max_credits_2026"]),
        target_credits=_as_int(assumptions["target_credits_2026"]),
        min_credits=MIN_CREDITS_2026,
        first_term=first_term,
        slots=_missing_slots(evaluation.migrate.totals),
        entry_term=entry_term,
        notices=migrate_notices,
    )

    # Stay scenario (2013 curriculum).
    by_id_2013 = {c.id: c for c in data.curriculum_2013}
    taken = set(evaluation.taken_codes)
    stay_plan = _build_plan(
        scenario="stay",
        pending=[by_id_2013[r.id] for r in evaluation.stay.pending],
        completed={c.id for c in data.curriculum_2013 if c.code in taken},
        external_codes=external_codes,
        groups=_prerequisite_groups(data.prerequisites_2013),
        is_offered=_offer_rule(every_term_types, []),
        max_credits=_as_int(assumptions["max_credits_2013"]),
        target_credits=_as_int(assumptions["target_credits_2013"]),
        min_credits=MIN_CREDITS_2013,
        first_term=first_term,
        slots=_missing_slots(evaluation.stay.totals),
        entry_term=entry_term,
        notices=[_offer_notice(every_term_types, [], by_id_2013)],
    )

    return Planning(
        migrate=migrate_plan,
        stay=stay_plan,
        assumptions=[assumptions[key] for key in USED_ASSUMPTIONS],
    )
