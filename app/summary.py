"""Summary of a conversion result: what the student sees first.

Pure functions over app.conversion.ConversionResult; all texts in Portuguese.
"""

import json
import math
from dataclasses import asdict, dataclass

from app.conversion import EMPHASIS_NAMES, EXTENSION_TARGET, HOURS_PER_CREDIT

STANDARD_COURSE_HOURS = 60


@dataclass
class CategoryRow:
    name: str
    required_hours: int
    used_hours: int
    missing_hours: int


@dataclass
class LostItem:
    code: str
    name: str
    lost_hours: int
    reason: str


@dataclass
class EmphasisRow:
    emphasis: str
    name: str
    hours: int
    min_hours: int
    reached: bool


@dataclass
class RequestRow:
    code: str
    name: str
    text: str


@dataclass
class Summary:
    missing_hours: int
    missing_credits: int
    missing_courses: int
    missing_text: str
    approved_hours: int
    used_hours: int
    used_percent: int
    used_text: str
    unrecognized_hours: int
    used_note: str
    lost_hours: int
    recoverable_hours: int
    lost_text: str
    recoverable_lines: list[str]
    lost_items: list[LostItem]
    categories: list[CategoryRow]
    pending: list[str]
    emphases: list[EmphasisRow]
    requests: list[RequestRow]
    stay_missing_hours: int
    stay_text: str
    warnings: list[str]

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def format_hours(hours):
    """3000 -> '3.000 h'."""
    return f"{hours:,} h".replace(",", ".")


def hours_and_credits(hours):
    credits = hours / HOURS_PER_CREDIT
    credits_text = f"{credits:g}".replace(".", ",")
    return f"{format_hours(hours)} ({credits_text} cr)"


def courses_text(hours):
    """'equivale a N disciplinas de 60 h', or 'cerca de N' when not exact."""
    count = math.ceil(hours / STANDARD_COURSE_HOURS)
    noun = "disciplina" if count == 1 else "disciplinas"
    prefix = "equivale a" if hours % STANDARD_COURSE_HOURS == 0 else "cerca de"
    return f"{prefix} {count} {noun} de {STANDARD_COURSE_HOURS} h"


def lost_text(lost_hours, recoverable_hours):
    """Main line; when hours can be recovered, one line per request follows."""
    if not lost_hours:
        return "Nenhuma hora perdida."
    if not recoverable_hours:
        return f"Perdido: {format_hours(lost_hours)}."
    return (
        f"Perdido: {format_hours(lost_hours)}, das quais até {format_hours(recoverable_hours)} "
        "podem ser recuperadas mediante pedido:"
    )


def request_text(request, hours):
    """'<course> como <target>: [até ]N h, <condition>.'"""
    prefix = "até " if request.target == EXTENSION_TARGET else ""
    return f"{request.name} como {request.target_name}: {prefix}{format_hours(hours)}, {request.condition}."


def build_summary(result):
    missing = max(result.total_required_hours - result.total_used_hours, 0)
    approved = result.approved_hours
    percent = round(100 * result.total_used_hours / approved) if approved else 0
    stay_missing = result.stay.missing_hours

    warnings = list(result.notices)
    if result.lost_hours:
        warnings.insert(
            0,
            f"Atenção: {format_hours(result.lost_hours)} do que você cursou não são aproveitadas "
            "na migração. Veja a lista do que não é aproveitado.",
        )
    if result.extra_extension_hours:
        warnings.append(
            f"Para completar as horas de extensão, você precisará de cerca de "
            f"{format_hours(result.extra_extension_hours)} de optativas extensionistas além das "
            f"{format_hours(result.total_required_hours)} do curso."
        )

    return Summary(
        missing_hours=missing,
        missing_credits=missing // HOURS_PER_CREDIT,
        missing_courses=math.ceil(missing / STANDARD_COURSE_HOURS),
        missing_text=f"Faltam {hours_and_credits(missing)}: {courses_text(missing)}."
        if missing
        else "Não falta nada: todas as exigências estão cumpridas.",
        approved_hours=approved,
        used_hours=result.total_used_hours,
        used_percent=percent,
        used_text=(
            f"Aproveitamento: {percent}% ({format_hours(result.total_used_hours)} de "
            f"{format_hours(approved)} aprovadas na grade 2013)."
        ),
        unrecognized_hours=result.unrecognized_hours,
        used_note=(
            f"Não entram no cálculo {format_hours(result.unrecognized_hours)} de disciplinas "
            "não reconhecidas na grade 2013."
            if result.unrecognized_hours
            else ""
        ),
        lost_hours=result.lost_hours,
        recoverable_hours=result.recoverable_hours,
        lost_text=lost_text(result.lost_hours, result.recoverable_hours),
        recoverable_lines=[
            request_text(r, r.recoverable_hours) for r in result.requests if r.recoverable_hours
        ],
        lost_items=[
            LostItem(c.code, c.name, c.lost_hours, c.reason) for c in result.courses if c.lost_hours
        ],
        categories=[
            CategoryRow(t.name, t.required_hours, t.used_hours, t.missing_hours) for t in result.totals
        ],
        pending=[p.name for p in result.pending],
        emphases=[
            EmphasisRow(e, name, result.emphasis_hours[e], result.emphasis_min_hours,
                        result.emphasis_hours[e] >= result.emphasis_min_hours)
            for e, name in EMPHASIS_NAMES.items()
        ],
        requests=[RequestRow(r.code, r.name, request_text(r, r.max_hours)) for r in result.requests],
        stay_missing_hours=stay_missing,
        stay_text=f"Se não migrar, faltam {hours_and_credits(stay_missing)} pela grade 2013.",
        warnings=warnings,
    )
