"""Check the study plan built by the student in the migration scenario.

The student lists 2026 courses (or generic slots) per term, starting at
first_planning_term. This module checks prerequisites, usual offer terms,
credits per term and the 2026 requirements, and reports what is still missing
in both scenarios. It never builds a plan by itself.
"""

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field

from app.data_loader import TBD, load_data
from app.rules import (
    EMPHASES,
    MIN_EMPHASIS_CREDITS,
    STATUS_ELECTIVE,
    STATUS_FLEXIBLE,
    _as_int,
    evaluate,
    resolve_assumptions,
)

# Confirmed curriculum parameters (see CLAUDE.md); not assumptions.
MIN_CREDITS_2026 = 17
MAX_TERMS_SINCE_ENTRY = 12
EXTERNAL_PREFIX = "code:"
REQUIRED_TYPES = ("mandatory", "internship", "complementary")
OTHER_TYPES = ("elective", "flexible")

CATEGORY_LABELS = {
    "mandatory": "Obrigatórias",
    "internship": "Estágio",
    "complementary": "TCC",
    "elective": "Optativas",
    "emphasis_EAM": "Ênfase EAM (optativas)",
    "emphasis_CD": "Ênfase CD (optativas)",
    "flexible": "Flexíveis",
    "extension": "Extensão",
}

TERM_PATTERN = re.compile(r"^(\d{4})\.([12])$")


@dataclass(frozen=True)
class GenericItem:
    id: str
    name: str
    type: str
    credits: int
    hours: int
    extension: bool


GENERIC_ITEMS = {
    g.id: g
    for g in (
        GenericItem("generic:elective", "Optativa a definir", "elective", 4, 60, False),
        GenericItem("generic:flexible", "Flexível a definir", "flexible", 4, 60, False),
        GenericItem("generic:flexible_extension", "Flexível extensionista a definir", "flexible", 6, 90, True),
    )
}


# ---------- Terms ----------


def term_index(term):
    match = TERM_PATTERN.match(term)
    if not match:
        raise ValueError(f"Período inválido: '{term}' (use AAAA.1 ou AAAA.2)")
    return int(match.group(1)) * 2 + int(match.group(2)) - 1


def term_from_index(index):
    return f"{index // 2}.{index % 2 + 1}"


def terms_between(start, end):
    """Terms from start to end, inclusive (empty if end < start)."""
    return [term_from_index(i) for i in range(term_index(start), term_index(end) + 1)]


def history_terms(entry_term, first_planning_term):
    """Terms of the transcript: from entry up to the term before first_planning_term."""
    return terms_between(entry_term, term_from_index(term_index(first_planning_term) - 1))


def deadline_term(entry_term):
    return term_from_index(term_index(entry_term) + MAX_TERMS_SINCE_ENTRY - 1)


# ---------- Offer ----------


@dataclass(frozen=True)
class OfferRule:
    codes: frozenset
    types: frozenset
    ids: frozenset

    def is_offered(self, course, term):
        if course.code in self.codes or course.type in self.types or course.id in self.ids:
            return True
        if course.semester is None:
            return True
        # Odd flowchart semesters are offered in .1 terms, even ones in .2.
        return (course.semester % 2 == 1) == term.endswith(".1")


def _as_list(assumption):
    return [v for v in assumption.value.split("|") if v]


def offer_rule(assumptions):
    return OfferRule(
        codes=frozenset(_as_list(assumptions["every_term_codes"])),
        types=frozenset(_as_list(assumptions["every_term_types"])),
        ids=frozenset(_as_list(assumptions["transition_every_term_ids"])),
    )


# ---------- Context ----------


@dataclass
class PlanContext:
    """Everything derived from the transcript and the assumptions."""

    data: object
    assumptions: dict
    evaluation: object
    offer: OfferRule
    by_id: dict
    groups: dict
    used_ids: set
    to_define_ids: set
    external_codes: set

    @property
    def base_completed(self):
        # Courses "a definir" count as done for prerequisites (with a notice).
        return self.used_ids | self.to_define_ids


def build_context(history_codes, overrides=None, data=None):
    data = data or load_data()
    assumptions = resolve_assumptions(data.assumptions, overrides)
    evaluation = evaluate(history_codes, overrides=overrides, data=data)
    groups = defaultdict(lambda: defaultdict(list))
    for p in data.prerequisites_2026:
        groups[p.course_id][p.group].append(p.prerequisite_id)
    return PlanContext(
        data=data,
        assumptions=assumptions,
        evaluation=evaluation,
        offer=offer_rule(assumptions),
        by_id={c.id: c for c in data.curriculum_2026},
        groups={k: dict(v) for k, v in groups.items()},
        used_ids={r.id for r in evaluation.migrate.used},
        to_define_ids={t.course_id for t in evaluation.migrate.to_define},
        external_codes=set(evaluation.taken_codes) | set(evaluation.unknown_codes),
    )


# ---------- Prerequisites ----------


def _prerequisite_done(ctx, prereq, completed):
    if prereq.startswith(EXTERNAL_PREFIX):
        return prereq[len(EXTERNAL_PREFIX):] in ctx.external_codes
    return prereq != TBD and prereq in completed


def missing_prerequisites(ctx, course_id, completed):
    """Return [] if prerequisites are met; else the missing items of each OR group."""
    course_groups = ctx.groups.get(course_id)
    if not course_groups:
        return []
    missing = []
    for group in course_groups.values():
        group_missing = [p for p in group if not _prerequisite_done(ctx, p, completed)]
        if not group_missing:
            return []
        missing.append(group_missing)
    return missing


def to_define_dependencies(ctx, course_id):
    """Prerequisites of the course whose situation is still 'a definir'."""
    return sorted(
        {p for group in ctx.groups.get(course_id, {}).values() for p in group if p in ctx.to_define_ids}
    )


def course_name(ctx, item_id):
    if item_id in GENERIC_ITEMS:
        return GENERIC_ITEMS[item_id].name
    course = ctx.by_id.get(item_id)
    return course.name if course else item_id


def _describe_missing(ctx, missing):
    alternatives = [", ".join(course_name(ctx, p) for p in group) for group in missing]
    return " ou ".join(f"({a})" if len(missing) > 1 else a for a in alternatives)


def _ordered_terms(plan):
    return sorted(plan, key=term_index)


def _course_ids(items):
    return [i for i in items if i not in GENERIC_ITEMS]


# ---------- Helpers for the interface ----------


def eligible_courses(ctx, plan, term, types):
    """2026 courses of the given types the student may add to `term`.

    Excludes courses already used from the transcript, 'a definir' or planned in
    another term; requires prerequisites completed in earlier terms. Courses
    already chosen for `term` stay in the list.
    """
    completed = set(ctx.base_completed)
    planned_elsewhere = set()
    for t in _ordered_terms(plan):
        ids = _course_ids(plan[t])
        if term_index(t) < term_index(term):
            completed.update(ids)
        if t != term:
            planned_elsewhere.update(ids)
    courses = [
        c
        for c in ctx.data.curriculum_2026
        if c.type in types
        and c.id not in ctx.base_completed
        and c.id not in planned_elsewhere
        and not missing_prerequisites(ctx, c.id, completed)
    ]
    return sorted(courses, key=lambda c: (c.semester or 99, OTHER_TYPES.index(c.type) if c.type in OTHER_TYPES else 0, c.emphasis or "~", c.name))


@dataclass
class RemovedItem:
    term: str
    id: str
    name: str
    reason: str


def cascade_remove(ctx, plan):
    """Drop plan items that are no longer valid, in term order (so removals cascade).

    Returns (cleaned_plan, removed). An item is dropped if it is already used
    from the transcript, already planned in an earlier term, or its
    prerequisites are not completed in earlier terms.
    """
    completed = set(ctx.base_completed)
    seen = set()
    cleaned, removed = {}, []
    for t in _ordered_terms(plan):
        kept = []
        for item in plan[t]:
            if item in GENERIC_ITEMS:
                kept.append(item)
                continue
            if item not in ctx.by_id:
                raise ValueError(f"Disciplina desconhecida no plano: '{item}'")
            reason = None
            if item in ctx.used_ids:
                reason = "já aproveitada pelo histórico"
            elif item in ctx.to_define_ids:
                reason = "situação a definir pela coordenação"
            elif item in seen:
                reason = "já incluída em período anterior"
            elif missing_prerequisites(ctx, item, completed):
                reason = "pré-requisitos não cumpridos em períodos anteriores"
            if reason:
                removed.append(RemovedItem(t, item, course_name(ctx, item), reason))
                continue
            kept.append(item)
            seen.add(item)
        cleaned[t] = kept
        completed.update(_course_ids(kept))
    return cleaned, removed


def history_outcomes(ctx):
    """Map each normalized transcript code to its outcome in the 2026 curriculum."""
    migrate = ctx.evaluation.migrate
    outcomes = {}
    for r in migrate.used:
        for code in r.source_codes:
            outcomes[code] = f"aproveitada como {r.name}"
    rules = {eq.rule_id: eq for eq in ctx.data.equivalences}
    taken = set(ctx.evaluation.taken_codes)
    for item in migrate.to_define:
        eq = rules.get(item.record)
        for code in eq.source_codes if eq else ():
            if code in taken:
                outcomes[code] = f"a definir pela coordenação ({course_name(ctx, item.course_id)})"
    for c in migrate.electives:
        suffix = f" (ênfase {c.emphasis})" if c.emphasis else ""
        outcomes[c.code] = f"vira {STATUS_ELECTIVE}{suffix}"
    for c in migrate.flexibles:
        outcomes[c.code] = f"vira {STATUS_FLEXIBLE}"
    for code in taken:
        outcomes.setdefault(code, "sem correspondência")
    return outcomes


# ---------- Check ----------


@dataclass
class PlanItem:
    id: str
    name: str
    type: str
    credits: int
    generic: bool = False
    off_offer: bool = False
    missing_prerequisites: list = field(default_factory=list)
    depends_on_to_define: list = field(default_factory=list)
    duplicate: bool = False


@dataclass
class TermCheck:
    term: str
    credits: int
    items: list[PlanItem]
    notices: list[str]


@dataclass
class TotalRow:
    category: str
    label: str
    required: int
    done: int
    planned: int
    missing: int
    unit: str = "cr"
    requirement: bool = True


@dataclass
class CourseRef:
    id: str
    code: str
    name: str
    semester: int | None


@dataclass
class MigrateSummary:
    totals: list[TotalRow]
    unplanned_required: list[CourseRef]
    complete: bool
    conclusion_term: str | None
    missing: list[str]


@dataclass
class StayTotal:
    category: str
    label: str
    required: int
    done: int
    missing: int


@dataclass
class StaySummary:
    totals: list[StayTotal]
    pending: list[CourseRef]


@dataclass
class PlanCheck:
    terms: list[TermCheck]
    prerequisite_issues: list[str]
    offer_issues: list[str]
    offer_warning: str
    credit_notices: list[str]
    to_define_notices: list[str]
    migrate: MigrateSummary
    stay: StaySummary
    deadline_term: str | None
    exceeds_deadline: bool
    notices: list[str]
    assumptions: list

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def offer_warning_text(offer_issues):
    if not offer_issues:
        return ""
    return (
        "Atenção: você incluiu disciplinas fora do período em que costumam ser ofertadas: "
        f"{'; '.join(offer_issues)}. Confirme com a coordenação se haverá oferta antes de contar com elas."
    )


def _migrate_summary(ctx, planned_items, last_term):
    migrate = ctx.evaluation.migrate
    done = {t.category: t.done for t in migrate.totals}
    required = {t.category: t.required for t in migrate.totals}
    units = {t.category: t.unit for t in migrate.totals}

    planned = defaultdict(int)
    planned_emphasis = {e: 0 for e in EMPHASES}
    for item in planned_items:
        source = GENERIC_ITEMS.get(item.id) or ctx.by_id[item.id]
        planned[source.type] += source.credits
        if source.extension:
            planned["extension"] += source.hours
        emphasis = getattr(source, "emphasis", "")
        if source.type == "elective" and emphasis in planned_emphasis:
            planned_emphasis[emphasis] += source.credits

    def row(category, required_value, done_value, planned_value, unit="cr", requirement=True):
        return TotalRow(
            category=category,
            label=CATEGORY_LABELS[category],
            required=required_value,
            done=done_value,
            planned=planned_value,
            missing=max(0, required_value - done_value - planned_value),
            unit=unit,
            requirement=requirement,
        )

    totals = [row(c, required[c], done[c], planned[c]) for c in (*REQUIRED_TYPES, "elective")]
    totals += [
        row(f"emphasis_{e}", MIN_EMPHASIS_CREDITS, migrate.emphasis_credits[e], planned_emphasis[e], requirement=False)
        for e in EMPHASES
    ]
    totals += [
        row("flexible", required["flexible"], done["flexible"], planned["flexible"]),
        row("extension", required["extension"], done["extension"], planned["extension"], units["extension"]),
    ]

    planned_ids = {i.id for i in planned_items}
    unplanned = [
        CourseRef(r.id, r.code, r.name, ctx.by_id[r.id].semester)
        for r in migrate.pending
        if r.id not in planned_ids
    ]
    unplanned.sort(key=lambda c: (c.semester or 99, c.name))

    missing = [f"{r.label}: faltam {r.missing} {r.unit}" for r in totals if r.requirement and r.missing]
    if unplanned:
        missing.append("Obrigatórias, estágio ou TCC não planejados: " + ", ".join(c.name for c in unplanned))
    if migrate.to_define:
        missing.append("Itens a definir pela coordenação: " + ", ".join(t.record for t in migrate.to_define))
    complete = not missing
    return MigrateSummary(
        totals=totals,
        unplanned_required=unplanned,
        complete=complete,
        conclusion_term=last_term if complete else None,
        missing=missing,
    )


def _stay_summary(ctx):
    stay = ctx.evaluation.stay
    labels = {**CATEGORY_LABELS, "complementary": "TCC"}
    totals = [
        StayTotal(t.category, labels.get(t.category, t.category), t.required, t.done, max(0, t.required - t.done))
        for t in stay.totals
    ]
    by_id_2013 = {c.id: c for c in ctx.data.curriculum_2013}
    pending = [CourseRef(r.id, r.code, r.name, by_id_2013[r.id].semester) for r in stay.pending]
    return StaySummary(totals=totals, pending=pending)


def check_with_context(ctx, entry_term, plan):
    first_term = ctx.assumptions["first_planning_term"].value
    for t in plan:
        if term_index(t) < term_index(first_term):
            raise ValueError(f"O plano começa em {first_term}; período inválido: {t}")
    max_credits = _as_int(ctx.assumptions["max_credits_2026"])

    ordered = _ordered_terms(plan)
    nonempty = [t for t in ordered if plan[t]]
    last_term = nonempty[-1] if nonempty else None

    completed = set(ctx.base_completed)
    seen = set()
    terms, planned_items = [], []
    prerequisite_issues, offer_issues, credit_notices, to_define_notices = [], [], [], []

    for t in ordered:
        if last_term is None or term_index(t) > term_index(last_term):
            break
        items = []
        for item_id in plan[t]:
            generic = GENERIC_ITEMS.get(item_id)
            if generic:
                item = PlanItem(generic.id, generic.name, generic.type, generic.credits, generic=True)
                items.append(item)
                planned_items.append(item)
                continue
            course = ctx.by_id.get(item_id)
            if course is None:
                raise ValueError(f"Disciplina desconhecida no plano: '{item_id}'")
            item = PlanItem(course.id, course.name, course.type, course.credits)
            item.duplicate = course.id in seen or course.id in ctx.base_completed
            item.missing_prerequisites = missing_prerequisites(ctx, course.id, completed)
            item.off_offer = not ctx.offer.is_offered(course, t)
            item.depends_on_to_define = to_define_dependencies(ctx, course.id)
            if item.duplicate:
                prerequisite_issues.append(f"{t}: {course.name} já foi cursada, aproveitada ou planejada antes.")
            if item.missing_prerequisites:
                prerequisite_issues.append(
                    f"{t}: {course.name} sem pré-requisitos cumpridos em períodos anteriores "
                    f"(falta: {_describe_missing(ctx, item.missing_prerequisites)})."
                )
            if item.off_offer:
                offer_issues.append(f"{course.name} ({t})")
            for dep in item.depends_on_to_define:
                to_define_notices.append(
                    f"{course.name} depende de {course_name(ctx, dep)}, cuja situação está a definir pela coordenação."
                )
            items.append(item)
            if not item.duplicate:
                planned_items.append(item)
                seen.add(course.id)

        credits = sum(i.credits for i in items)
        notices = []
        if credits > max_credits:
            notices.append(f"{t}: {credits} créditos, acima do máximo de {max_credits} por período.")
        elif credits < MIN_CREDITS_2026 and t != last_term:
            notices.append(f"{t}: {credits} créditos, abaixo do mínimo de {MIN_CREDITS_2026} por período.")
        credit_notices += notices
        terms.append(TermCheck(t, credits, items, notices))
        completed.update(i.id for i in items if not i.generic)

    migrate = _migrate_summary(ctx, planned_items, last_term)

    notices = []
    deadline, exceeds = None, False
    if entry_term:
        deadline = deadline_term(entry_term)
        if last_term and term_index(last_term) > term_index(deadline):
            exceeds = True
            notices.append(
                f"O plano vai até {last_term} e ultrapassa o prazo máximo de {MAX_TERMS_SINCE_ENTRY} "
                f"períodos desde o ingresso ({deadline})."
            )
    every_term_types = sorted(ctx.offer.types)
    if any(i.type in ctx.offer.types for i in planned_items):
        notices.append(
            "Optativas, flexíveis, estágio e TCC não têm periodicidade definida: o app assume "
            f"oferta em todo período para os tipos {', '.join(every_term_types)}."
        )

    return PlanCheck(
        terms=terms,
        prerequisite_issues=prerequisite_issues,
        offer_issues=offer_issues,
        offer_warning=offer_warning_text(offer_issues),
        credit_notices=credit_notices,
        to_define_notices=to_define_notices,
        migrate=migrate,
        stay=_stay_summary(ctx),
        deadline_term=deadline,
        exceeds_deadline=exceeds,
        notices=notices,
        assumptions=[asdict(a) for a in ctx.assumptions.values()],
    )


def check_plan(history_codes, entry_term, plan, overrides=None, data=None):
    """Check the student's plan.

    history_codes: SIGAA codes passed in the 2013 curriculum.
    entry_term: term of entry (AAAA.1/AAAA.2), for the deadline check.
    plan: {term: [2026 course id or generic item id, ...]} from first_planning_term on.
    """
    if entry_term:
        term_index(entry_term)
    ctx = build_context(history_codes, overrides=overrides, data=data)
    return check_with_context(ctx, entry_term, plan)
