"""Conversion engine: 2013 history -> 2026 curriculum.

Applies the conversion rules of CLAUDE.md to the courses passed by a student
of the 2013 curriculum, in this order:

1. same code in the 2026 curriculum (after the active code aliases);
2. active equivalence;
3. elective successor (counts as elective of the successor's emphasis);
4. destination in old_course_destinations.csv;
5. 2013 Special Topics and every flexible (CF) history line -> Special Topics;
6. destination already taken (equivalences and aliases only) -> Special Topics.

All curricular data comes from data/; unconfirmed rules come from
assumptions.csv and old_course_destinations.csv and can be overridden per call.
"""

import json
from dataclasses import asdict, dataclass, field

from app.data_loader import load_data

HOURS_PER_CREDIT = 15
EMPHASES = ("EAM", "CD")
EMPHASIS_NAMES = {"EAM": "Estatística Aplicada e Modelagem", "CD": "Ciência de Dados"}
REQUIRED_TYPES = ("mandatory", "internship", "complementary")
EXTENSION_TARGET = "extension"
CONSULTORIA_ID = "cons"
FLEXIBLE_SIGAA_TYPE = "CF"

# Curriculum parameters confirmed in the PPCs (see CLAUDE.md); not assumptions.
REQUIRED_ELECTIVE_HOURS_2026 = 660
REQUIRED_ELECTIVE_HOURS_2013 = 540
REQUIRED_FLEXIBLE_HOURS_2013 = 240

# Categories of the 2026 curriculum (the order is the display order).
MANDATORY = "mandatory"
INTERNSHIP = "internship"
COMPLEMENTARY = "complementary"
ELECTIVE = "elective"
TOPICS = "topics"
FLEXIBLE_EXTENSION = "flexible_extension"
EXTENSION = "extension"
# Destinations that are not categories.
NONE = "none"
UNRECOGNIZED = "unrecognized"

CATEGORY_NAMES = {
    MANDATORY: "Obrigatórias",
    INTERNSHIP: "Estágio",
    COMPLEMENTARY: "TCC",
    ELECTIVE: "Optativas",
    TOPICS: "Tópicos Especiais",
    FLEXIBLE_EXTENSION: "Flexíveis extensionistas",
    EXTENSION: "Extensão",
}
# Categories that add up to the total of the curriculum (extension overlaps them).
TOTAL_CATEGORIES = (MANDATORY, INTERNSHIP, COMPLEMENTARY, ELECTIVE, TOPICS, FLEXIBLE_EXTENSION)

STAY_CATEGORY_NAMES = {
    MANDATORY: "Obrigatórias",
    INTERNSHIP: "Estágios",
    COMPLEMENTARY: "TCC",
    ELECTIVE: "Optativas",
    "flexible": "Flexíveis",
}

RULE_SAME_CODE = "mesmo código"
RULE_EQUIVALENCE = "equivalência"
RULE_SUCCESSOR = "sucessora"
RULE_DESTINATION = "destino definido"
RULE_TOPICS = "Tópicos Especiais"
RULE_TAKEN = "destino já ocupado"
RULE_REQUEST = "pedido à coordenação"
RULE_NONE = "fora da grade 2013"

DESTINATION_TOPICS = "topics"
DESTINATION_NONE = "none"
DESTINATION_ELECTIVE_PREFIX = "elective:"
DESTINATION_NO_EMPHASIS = "none"


@dataclass(frozen=True)
class HistoryEntry:
    """A passed course as read from the history (PDF or manual table).

    hours and sigaa_type are only needed for courses outside the 2013
    curriculum (from the PDF).
    """

    code: str
    name: str = ""
    hours: int | None = None
    sigaa_type: str = ""


@dataclass
class AssumptionUsed:
    key: str
    value: str
    status: str
    description: str
    overridden: bool = False


@dataclass
class DestinationUsed:
    code: str
    name: str
    destination: str
    status: str
    overridden: bool = False


@dataclass
class ConvertedCourse:
    """One passed 2013 course and what it becomes in the 2026 curriculum."""

    code: str
    name: str
    hours: int
    semester: int | None
    type_2013: str
    rule: str
    category: str
    destination: str
    target_id: str = ""
    emphasis: str = ""
    used_hours: int = 0
    lost_hours: int = 0
    reason: str = ""
    note: str = ""
    order: int = 0


@dataclass
class CategoryTotal:
    category: str
    name: str
    required_hours: int
    used_hours: int

    @property
    def missing_hours(self):
        return max(self.required_hours - self.used_hours, 0)


@dataclass
class RequestPossibility:
    code: str
    name: str
    target: str
    target_name: str
    max_hours: int
    condition: str
    note: str
    recoverable_hours: int = 0


@dataclass
class PendingCourse:
    id: str
    code: str
    name: str
    type: str
    hours: int
    semester: int | None


@dataclass
class StayResult:
    totals: list[CategoryTotal]
    pending: list[PendingCourse]

    @property
    def missing_hours(self):
        return sum(t.missing_hours for t in self.totals)


@dataclass
class ConversionResult:
    courses: list[ConvertedCourse]
    totals: list[CategoryTotal]
    emphasis_hours: dict[str, int]
    emphasis_min_hours: int
    pending: list[PendingCourse]
    requests: list[RequestPossibility]
    recoverable_hours: int
    extra_extension_hours: int
    stay: StayResult
    assumptions: list[AssumptionUsed]
    destinations: list[DestinationUsed]
    notices: list[str] = field(default_factory=list)

    @property
    def total_required_hours(self):
        return sum(t.required_hours for t in self.totals if t.category in TOTAL_CATEGORIES)

    @property
    def total_used_hours(self):
        return sum(t.used_hours for t in self.totals if t.category in TOTAL_CATEGORIES)

    @property
    def approved_hours(self):
        return sum(c.hours for c in self.courses if c.category != UNRECOGNIZED)

    @property
    def unrecognized_hours(self):
        return sum(c.hours for c in self.courses if c.category == UNRECOGNIZED)

    @property
    def lost_hours(self):
        return sum(c.lost_hours for c in self.courses)

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


# --- assumptions and destinations ------------------------------------------


def _to_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


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


def _as_int(assumption):
    try:
        return int(assumption.value)
    except ValueError:
        raise ValueError(f"Premissa '{assumption.key}' deveria ser inteira: '{assumption.value}'") from None


def _as_bool(assumption):
    if assumption.value not in ("true", "false"):
        raise ValueError(f"Premissa '{assumption.key}' deveria ser true/false: '{assumption.value}'")
    return assumption.value == "true"


def _valid_destination(value):
    if value in (DESTINATION_TOPICS, DESTINATION_NONE):
        return True
    if value.startswith(DESTINATION_ELECTIVE_PREFIX):
        return value[len(DESTINATION_ELECTIVE_PREFIX):] in (*EMPHASES, DESTINATION_NO_EMPHASIS)
    return False


def resolve_destinations(data, overrides=None):
    """Return {code: DestinationUsed}; only `assumed` destinations can be overridden."""
    overrides = overrides or {}
    names = {c.code: c.name for c in data.curriculum_2013}
    by_code = {d.code: d for d in data.old_course_destinations}
    for code, value in overrides.items():
        if code not in by_code:
            raise ValueError(f"Disciplina sem destino definido: '{code}'")
        if by_code[code].status != "assumed":
            raise ValueError(f"O destino de '{code}' está confirmado e não pode ser alterado")
        if not _valid_destination(value):
            raise ValueError(f"Destino inválido para '{code}': '{value}'")
    return {
        code: DestinationUsed(
            code=code,
            name=names.get(code, code),
            destination=overrides.get(code, d.destination),
            status=d.status,
            overridden=code in overrides,
        )
        for code, d in by_code.items()
    }


# --- helpers ----------------------------------------------------------------


def _entries(history):
    """HistoryEntry list without repeated codes (a passed course counts once)."""
    seen, entries = set(), []
    for item in history:
        entry = item if isinstance(item, HistoryEntry) else HistoryEntry(code=str(item))
        code = entry.code.strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        entries.append(HistoryEntry(code, entry.name, entry.hours, entry.sigaa_type.strip().upper()))
    return entries


def _emphasis_of(course, assumptions):
    if course.id == CONSULTORIA_ID:
        value = assumptions["consultoria_emphasis"].value
        return value if value in EMPHASES else ""
    return course.emphasis


def _emphasis_text(emphasis):
    return f"Optativa ({EMPHASIS_NAMES[emphasis]})" if emphasis else "Optativa (sem ênfase)"


def _fill(items, capacity, reason):
    """Use the hours of the items in order up to capacity; the rest is lost."""
    for item in items:
        item.used_hours = min(item.hours, max(capacity, 0))
        item.lost_hours = item.hours - item.used_hours
        capacity -= item.used_hours
        if item.lost_hours:
            item.reason = reason


# --- conversion -------------------------------------------------------------


class _Converter:
    def __init__(self, data, assumptions, destinations, granted_codes=frozenset()):
        self.data = data
        self.assumptions = assumptions
        self.destinations = destinations
        self.granted_codes = granted_codes
        self.aliases = {a.code: a.alias_of for a in data.code_aliases if a.status == "active"}
        self.by_code_2013 = {c.code: c for c in data.curriculum_2013}
        self.order_2013 = {c.code: i for i, c in enumerate(data.curriculum_2013)}
        self.by_id_2026 = {c.id: c for c in data.curriculum_2026}
        self.by_code_2026 = {c.code: c for c in data.curriculum_2026 if c.code != "NEW"}
        self.successors = {s.code: s for s in data.elective_successors}
        self.requests = {r.code: (i, r) for i, r in enumerate(data.request_options)}
        self.equivalences = {}
        for i, eq in enumerate(data.equivalences):
            if eq.status != "active":
                continue
            for j, code in enumerate(eq.source_codes):
                self.equivalences.setdefault(self.normalize(code), (i, j, eq))

    def normalize(self, code):
        return self.aliases.get(code, code)

    def course_2013(self, code):
        return self.by_code_2013.get(code) or self.by_code_2013.get(self.normalize(code))

    def run(self, history):
        entries = _entries(history)
        items, claims = [], []
        for position, entry in enumerate(entries):
            item, claim = self.classify(entry, position, entries)
            items.append(item)
            if claim is not None:
                claims.append(claim)
        self.resolve_claims(claims)
        self.allocate(items)
        return sorted(items, key=lambda i: i.order)

    def classify(self, entry, position, entries):
        """Return the ConvertedCourse of an entry and its claim on a 2026 course."""
        old = self.course_2013(entry.code)
        if old is None:
            return self.classify_outside(entry, position), None

        order = self.order_2013[old.code]
        item = ConvertedCourse(
            code=entry.code,
            name=old.name,
            hours=old.hours,
            semester=old.semester,
            type_2013=old.type,
            rule="",
            category="",
            destination="",
            order=order,
        )
        code = self.normalize(entry.code)

        target = self.by_code_2026.get(code)
        if target is not None:
            # The alias target (alias_of) has priority over the other code.
            return item, ((1, 0 if entry.code == code else 1, order), target, item, RULE_SAME_CODE)

        if code in self.equivalences:
            i, j, eq = self.equivalences[code]
            target = self.by_id_2026[eq.target_id]
            if eq.match == "all_of":
                taken = {self.normalize(e.code) for e in entries}
                missing = [c for c in eq.source_codes if self.normalize(c) not in taken]
                if missing:
                    names = ", ".join(self.by_code_2013[c].name if c in self.by_code_2013 else c for c in missing)
                    reason = f"O aproveitamento como {target.name} exige também {names}."
                    self.set_none(item, RULE_EQUIVALENCE, reason)
                    return item, None
            return item, ((2, i, j, order), target, item, RULE_EQUIVALENCE)

        if old.code in self.successors:
            successor = self.by_id_2026[self.successors[old.code].successor_id]
            self.set_elective(item, RULE_SUCCESSOR, _emphasis_of(successor, self.assumptions))
            item.note = f"Sucessora na grade 2026: {successor.name}."
            return item, None

        if old.code in self.granted_codes and old.code in self.requests:
            i, request = self.requests[old.code]
            if request.target == EXTENSION_TARGET:
                item.rule, item.category = RULE_REQUEST, FLEXIBLE_EXTENSION
                item.destination = "Horas de extensão (mediante pedido)"
                return item, None
            target = self.by_id_2026[request.target]
            return item, ((3, i, 0, order), target, item, RULE_REQUEST)

        self.classify_fallback(item, old)
        return item, None

    def classify_fallback(self, item, old):
        """Rules 4 and 5."""
        if old.code in self.destinations:
            destination = self.destinations[old.code].destination
            if destination == DESTINATION_TOPICS:
                self.set_topics(item, RULE_DESTINATION)
            elif destination == DESTINATION_NONE:
                self.set_none(item, RULE_DESTINATION, "Não é aproveitada automaticamente.")
            else:
                emphasis = destination[len(DESTINATION_ELECTIVE_PREFIX):]
                self.set_elective(item, RULE_DESTINATION, emphasis if emphasis in EMPHASES else "")
        elif old.type == "flexible":
            self.set_topics(item, RULE_TOPICS)
        else:
            self.set_none(item, RULE_DESTINATION, "Sem destino definido na grade 2026.")

    def classify_outside(self, entry, position):
        """A course outside the 2013 curriculum: flexible lines go to topics."""
        item = ConvertedCourse(
            code=entry.code,
            name=entry.name or entry.code,
            hours=entry.hours or 0,
            semester=None,
            type_2013="flexible" if entry.sigaa_type == FLEXIBLE_SIGAA_TYPE else "",
            rule="",
            category="",
            destination="",
            order=len(self.order_2013) + position,
        )
        if entry.sigaa_type == FLEXIBLE_SIGAA_TYPE and entry.hours:
            self.set_topics(item, RULE_TOPICS)
            return item
        item.rule, item.category = RULE_NONE, UNRECOGNIZED
        item.destination = "Não reconhecida"
        item.note = "Não consta da grade 2013 e não entra nas contas. Consulte a coordenação."
        return item

    def set_topics(self, item, rule):
        item.rule, item.category, item.destination = rule, TOPICS, "Tópicos Especiais (flexível)"

    def set_elective(self, item, rule, emphasis):
        item.rule, item.category, item.emphasis = rule, ELECTIVE, emphasis
        item.destination = _emphasis_text(emphasis)

    def set_none(self, item, rule, reason):
        item.rule, item.category, item.destination = rule, NONE, "Não aproveitada"
        item.reason = reason

    def resolve_claims(self, claims):
        """Rule 6: one course takes each 2026 course; the others go to topics."""
        winners = {}
        for _, target, item, rule in sorted(claims, key=lambda c: c[0]):
            if target.id not in winners:
                winners[target.id] = item
                item.rule, item.target_id = rule, target.id
                item.category = target.type if target.type in (*REQUIRED_TYPES, ELECTIVE) else TOPICS
                item.destination = target.name
                if target.type == ELECTIVE:
                    item.emphasis = _emphasis_of(target, self.assumptions)
            elif rule == RULE_REQUEST:
                self.classify_fallback(item, self.course_2013(item.code))
            else:
                self.set_topics(item, RULE_TAKEN)
                item.note = f"{target.name} já foi aproveitada por {winners[target.id].name}."

    def allocate(self, items):
        """Distribute the hours of each item between used and lost."""
        for item in items:
            if item.category in REQUIRED_TYPES:
                target = self.by_id_2026[item.target_id]
                item.used_hours = min(item.hours, target.hours)
                item.lost_hours = item.hours - item.used_hours
                if item.lost_hours:
                    item.reason = f"Redução de carga horária (o novo {target.name} tem {target.hours} h)."
            elif item.category in (NONE, UNRECOGNIZED):
                item.lost_hours = item.hours if item.category == NONE else 0

        rule_rank = {RULE_DESTINATION: 0, RULE_TOPICS: 1, RULE_TAKEN: 2}
        topics = sorted(
            (i for i in items if i.category == TOPICS),
            key=lambda i: (rule_rank.get(i.rule, 1), i.order),
        )
        limit = _as_int(self.assumptions["topics_max_hours"])
        _fill(topics, limit, f"Excedente de Tópicos Especiais (limite de {limit} h).")

        electives = [i for i in items if i.category == ELECTIVE]
        before_cut = {e: sum(i.hours for i in electives if i.emphasis == e) for e in EMPHASES}
        ranked = sorted(EMPHASES, key=lambda e: -before_cut[e])
        electives.sort(key=lambda i: (ranked.index(i.emphasis) if i.emphasis else len(ranked), i.order))
        limit = _as_int(self.assumptions["electives_max_hours"])
        _fill(electives, limit, f"Excedente de optativas (limite de {limit} h).")

        extension = [i for i in items if i.category == FLEXIBLE_EXTENSION]
        limit = min(
            _as_int(self.assumptions["internship2_recoverable_max_hours"]),
            self.required_hours(FLEXIBLE_EXTENSION),
        )
        _fill(extension, limit, f"Acima do máximo recuperável como extensão ({limit} h).")

    def required_hours(self, category):
        curriculum = self.data.curriculum_2026
        if category in REQUIRED_TYPES:
            return sum(c.hours for c in curriculum if c.type == category)
        if category == ELECTIVE:
            return REQUIRED_ELECTIVE_HOURS_2026
        if category == TOPICS:
            return sum(c.hours for c in curriculum if c.type == "flexible" and not c.extension)
        if category == FLEXIBLE_EXTENSION:
            return sum(c.hours for c in curriculum if c.type == "flexible" and c.extension)
        if category == EXTENSION:
            return _as_int(self.assumptions["migrant_extension_hours"])
        raise ValueError(category)

    def totals(self, items):
        used = {category: 0 for category in CATEGORY_NAMES}
        for item in items:
            if item.category in used:
                used[item.category] += item.used_hours
        used[EXTENSION] = self.extension_hours(items)
        totals = []
        for category, name in CATEGORY_NAMES.items():
            required = self.required_hours(category)
            totals.append(CategoryTotal(category, name, required, min(used[category], required)))
        return totals

    def extension_hours(self, items):
        hours = sum(i.used_hours for i in items if i.category == FLEXIBLE_EXTENSION)
        if _as_bool(self.assumptions["old_pm_counts_as_extension"]):
            hours += sum(
                i.used_hours for i in items if i.target_id and self.by_id_2026[i.target_id].extension
            )
        return hours

    def pending(self, items):
        used = {i.target_id for i in items if i.target_id}
        courses = [c for c in self.data.curriculum_2026 if c.type in REQUIRED_TYPES and c.id not in used]
        courses.sort(key=lambda c: c.semester or 0)
        return [PendingCourse(c.id, c.code, c.name, c.type, c.hours, c.semester) for c in courses]

    def request_possibilities(self, items):
        result = []
        for item in items:
            old = self.course_2013(item.code)
            if old is None or old.code not in self.requests:
                continue
            _, request = self.requests[old.code]
            if request.target == EXTENSION_TARGET:
                target_name = "extensão"
                max_hours = min(item.hours, _as_int(self.assumptions["internship2_recoverable_max_hours"]))
            else:
                target = self.by_id_2026[request.target]
                target_name, max_hours = target.name, target.hours
            result.append(
                RequestPossibility(
                    item.code, item.name, request.target, target_name, max_hours, request.condition, request.note
                )
            )
        return result

    def extra_extension_hours(self, pending, totals):
        """Extension hours that do not fit in the hours still missing.

        Extension can still come from pending mandatory extension courses,
        the missing flexible extension hours and the room left in electives.
        """
        by_category = {t.category: t for t in totals}
        room = sum(self.by_id_2026[p.id].hours for p in pending if self.by_id_2026[p.id].extension)
        room += by_category[FLEXIBLE_EXTENSION].missing_hours + by_category[ELECTIVE].missing_hours
        return max(by_category[EXTENSION].missing_hours - room, 0)

def _evaluate_stay(entries, data, aliases):
    """Hours missing to finish in the 2013 curriculum."""
    by_code = {c.code: c for c in data.curriculum_2013}
    passed, flexible_outside = {}, 0
    for entry in entries:
        course = by_code.get(entry.code) or by_code.get(aliases.get(entry.code, ""))
        if course is not None:
            passed[course.code] = course
        elif entry.sigaa_type == FLEXIBLE_SIGAA_TYPE and entry.hours:
            flexible_outside += entry.hours

    used = {t: sum(c.hours for c in passed.values() if c.type == t) for t in STAY_CATEGORY_NAMES}
    used["flexible"] += flexible_outside
    required = {t: sum(c.hours for c in data.curriculum_2013 if c.type == t) for t in REQUIRED_TYPES}
    required[ELECTIVE] = REQUIRED_ELECTIVE_HOURS_2013
    required["flexible"] = REQUIRED_FLEXIBLE_HOURS_2013

    pending = [
        PendingCourse(c.id, c.code, c.name, c.type, c.hours, c.semester)
        for c in data.curriculum_2013
        if c.type in REQUIRED_TYPES and c.code not in passed
    ]
    totals = [
        CategoryTotal(t, name, required[t], min(used[t], required[t]))
        for t, name in STAY_CATEGORY_NAMES.items()
    ]
    return StayResult(totals=totals, pending=pending)


def convert(history, overrides=None, destination_overrides=None, data=None):
    """Convert the passed courses of a 2013 student to the 2026 curriculum.

    history: iterable of SIGAA codes or HistoryEntry (passed courses).
    overrides: optional {assumption_key: value} replacing assumptions.csv values.
    destination_overrides: optional {code: destination} for `assumed` rows of
        old_course_destinations.csv.
    data: optional CurriculumData (defaults to data/).
    """
    data = data or load_data()
    assumptions = resolve_assumptions(data.assumptions, overrides)
    destinations = resolve_destinations(data, destination_overrides)
    history = list(history)

    converter = _Converter(data, assumptions, destinations)
    items = converter.run(history)
    totals = converter.totals(items)
    pending = converter.pending(items)

    # Recoverable hours: losses now minus losses with the requests granted.
    def lost_with(granted_codes):
        granted = _Converter(data, assumptions, destinations, frozenset(granted_codes))
        return sum(i.lost_hours for i in granted.run(history))

    lost = sum(i.lost_hours for i in items)
    requests = converter.request_possibilities(items)
    codes = {r.code: converter.course_2013(r.code).code for r in requests}
    for request in requests:
        request.recoverable_hours = max(lost - lost_with({codes[request.code]}), 0)
    recoverable = max(lost - lost_with(codes.values()), 0)

    electives = [i for i in items if i.category == ELECTIVE]
    emphasis_hours = {e: sum(i.used_hours for i in electives if i.emphasis == e) for e in EMPHASES}

    notices = [
        f"{i.name} ({i.code}) não consta da grade 2013 e não foi considerada. Consulte a coordenação."
        for i in items
        if i.category == UNRECOGNIZED
    ]

    return ConversionResult(
        courses=items,
        totals=totals,
        emphasis_hours=emphasis_hours,
        emphasis_min_hours=_as_int(assumptions["emphasis_min_hours"]),
        pending=pending,
        requests=requests,
        recoverable_hours=recoverable,
        extra_extension_hours=converter.extra_extension_hours(pending, totals),
        stay=_evaluate_stay(_entries(history), data, converter.aliases),
        assumptions=list(assumptions.values()),
        destinations=list(destinations.values()),
        notices=notices,
    )
