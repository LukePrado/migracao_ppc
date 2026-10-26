"""Markdown summary for the student to discuss with an AI assistant.

Pure function over the results already computed by the app: no API calls,
no files written and no personal data (no name, id number or entry term).
Courses always appear by name; SIGAA codes only in parentheses inside tables.
"""

from app.data_loader import TBD
from app.plan_check import (
    GENERIC_ITEMS,
    MIN_CREDITS_2026,
    OTHER_TYPES,
)

NEW_CODE = "NEW"
EXTERNAL_PREFIX = "code:"
TYPE_LABELS = {
    "mandatory": "obrigatória",
    "elective": "optativa",
    "flexible": "flexível",
    "internship": "estágio",
    "complementary": "TCC",
}
STATUS_LABELS = {"confirmed": "confirmada", "assumed": "suposta"}
INTERNSHIP_MATCH_LABELS = {"all_of": "exige Estágio I e II", "any_of": "basta um dos estágios"}

AI_INSTRUCTIONS = """\
a) Explique ao aluno, em linguagem simples, o impacto de migrar ou não.
b) Se o aluno pedir, sugira um plano por período a partir de {first_term}, usando somente as
   disciplinas listadas, respeitando pré-requisitos, oferta e limites de créditos. Responda com
   uma tabela por período (código, disciplina, créditos).

Regras para a IA:
- Não invente disciplinas, regras ou equivalências: use apenas o que está neste arquivo.
- Sinalize sempre que algo depender de decisão da coordenação (premissas supostas, itens a
  definir, propostas em análise).
- Lembre o aluno de que o plano sugerido deve ser conferido no app antes de ser seguido.
"""


# ---------- Formatting helpers ----------


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _course_label(course):
    code = "novo" if course.code == NEW_CODE else course.code
    return f"{course.name} ({code})"


def _join_names(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " e " + names[-1]


# ---------- Readable values ----------


def _names_by_code(ctx):
    names = {c.code: c.name for c in ctx.data.curriculum_2013}
    names.update({c.code: c.name for c in ctx.data.curriculum_2026 if c.code != NEW_CODE})
    return names


def _split(value):
    return [v for v in value.split("|") if v]


def readable_assumption_value(ctx, key, value):
    """Show an assumption value with course names and plain words, never internal ids."""
    if key == "every_term_codes":
        names = _names_by_code(ctx)
        return ", ".join(names.get(code, f"código {code}") for code in _split(value)) or "nenhuma"
    if key == "transition_every_term_ids":
        return ", ".join(ctx.by_id[i].name for i in _split(value) if i in ctx.by_id) or "nenhuma"
    if key == "every_term_types":
        return ", ".join(TYPE_LABELS.get(t, t) for t in _split(value)) or "nenhum"
    if key == "internship_match":
        return INTERNSHIP_MATCH_LABELS.get(value, value)
    if value in ("true", "false"):
        return "Sim" if value == "true" else "Não"
    return value


def _offer_text(ctx, course):
    offer = ctx.offer
    if course.code in offer.codes or course.type in offer.types or course.id in offer.ids:
        return "todo período"
    if course.semester is None:
        return "todo período"
    return "períodos .1" if course.semester % 2 == 1 else "períodos .2"


def _prerequisite_text(ctx, course_id):
    groups = ctx.groups.get(course_id)
    if not groups:
        return "—"
    done = ctx.base_completed
    alternatives = []
    for group in groups.values():
        parts = []
        for prereq in group:
            if prereq == TBD:
                parts.append("a definir pela coordenação")
            elif prereq.startswith(EXTERNAL_PREFIX):
                parts.append(f"disciplina de outro curso ({prereq[len(EXTERNAL_PREFIX):]})")
            else:
                name = ctx.by_id[prereq].name
                parts.append(f"{name} (já cumprido)" if prereq in done else name)
        alternatives.append(_join_names(parts))
    if len(alternatives) == 1:
        return alternatives[0]
    return " ou ".join(f"[{a}]" for a in alternatives)


def _planned_terms(plan):
    terms = {}
    for term, items in plan.items():
        for item in items:
            terms.setdefault(item, term)
    return terms


# ---------- Sections ----------


def _section_context(ctx, check):
    offer = ctx.offer
    names = _names_by_code(ctx)
    every_term_courses = _join_names(names.get(c, f"código {c}") for c in sorted(offer.codes, key=lambda c: names.get(c, c)))
    every_term_types = _join_names(TYPE_LABELS[t] for t in TYPE_LABELS if t in offer.types)
    transition = _join_names(ctx.by_id[i].name for i in sorted(offer.ids) if i in ctx.by_id)
    start = ctx.assumptions["start_term"].value
    max_credits = ctx.assumptions["max_credits_2026"].value
    required = {r.category: r for r in check.migrate.totals}

    lines = [
        "## 1. Contexto",
        "",
        "- Curso de Estatística da UFPB. O aluno está na grade de 2013 (PPC 2013) e pode migrar para "
        "a nova grade do curso de Estatística e Ciência de Dados (PPC 2026, Resolução CONSEPE "
        f"41/2026), que entra em vigor em {start}.",
        "- Oferta das obrigatórias: as de semestre ímpar no fluxograma são ofertadas nos períodos .1; "
        "as de semestre par, nos períodos .2.",
        f"- Ofertadas em todo período: {every_term_courses or 'nenhuma disciplina específica'}; "
        f"e os componentes do tipo {every_term_types or 'nenhum'}.",
    ]
    if transition:
        lines.append(f"- Na transição, também ofertadas em todo período: {transition}.")
    lines += [
        f"- Créditos por período: mínimo de {MIN_CREDITS_2026} (exceto no último período) e máximo "
        f"de {max_credits}.",
        "- Exigências da grade 2026: "
        + "; ".join(
            f"{r.label} {r.required} {r.unit}" for r in check.migrate.totals if r.requirement
        )
        + f". Para ter ênfase, são necessários {required['emphasis_EAM'].required} cr em optativas "
        "da mesma ênfase (Estatística Aplicada e Modelagem, EAM, ou Ciência de Dados, CD); senão, "
        "a formação é generalista.",
    ]
    if check.deadline_term:
        lines.append(f"- Prazo máximo de conclusão do aluno: {check.deadline_term}.")
    return "\n".join(lines)


def _section_assumptions(ctx):
    rows = []
    for a in ctx.assumptions.values():
        status = STATUS_LABELS.get(a.status, a.status)
        if a.overridden:
            status += " (alterada na simulação)"
        rows.append((f"{a.description} (`{a.key}`)", readable_assumption_value(ctx, a.key, a.value), status))
    return "\n".join(
        [
            "## 2. Premissas usadas",
            "",
            "Premissas **supostas** ainda não foram confirmadas pela coordenação.",
            "",
            _table(("Premissa", "Valor", "Status"), rows),
        ]
    )


def _section_history(ctx, outcomes):
    taken = set(ctx.evaluation.taken_codes)
    courses = [c for c in ctx.data.curriculum_2013 if c.code in taken]
    lines = ["## 3. Histórico (grade 2013) e o que vira na grade 2026", ""]
    if not courses:
        lines.append("Nenhuma disciplina informada.")
    else:
        lines.append(
            _table(
                ("Disciplina cursada (2013)", "Créditos", "Na grade 2026"),
                [(_course_label(c), c.credits, outcomes.get(c.code, "—")) for c in courses],
            )
        )
    notices = [*ctx.evaluation.notices, *ctx.evaluation.migrate.notices]
    notices += [
        f"A definir pela coordenação: {t.description}" for t in ctx.evaluation.migrate.to_define
    ]
    if notices:
        lines += ["", "Avisos:", ""] + [f"- {n}" for n in notices]
    return "\n".join(lines)


def _section_scenarios(ctx, check):
    migrate, stay = check.migrate, check.stay
    lines = ["## 4. Situação nos dois cenários", "", "### Migrar para o PPC 2026", ""]
    lines.append(
        _table(
            ("Categoria", "Exigido", "Cursado", "Planejado", "Falta"),
            [
                (
                    r.label + ("" if r.requirement else " (informativo)"),
                    f"{r.required} {r.unit}",
                    f"{r.done} {r.unit}",
                    f"{r.planned} {r.unit}",
                    f"{r.missing} {r.unit}",
                )
                for r in migrate.totals
            ],
        )
    )
    lines.append("")
    if migrate.complete and migrate.conclusion_term:
        lines.append(f"Conclusão prevista com o plano atual: {migrate.conclusion_term}.")
    else:
        lines += ["Ainda falta para concluir:", ""] + [f"- {m}" for m in migrate.missing]
    if check.exceeds_deadline:
        lines += ["", f"O plano atual ultrapassa o prazo máximo de conclusão ({check.deadline_term})."]

    lines += ["", "### Não migrar (PPC 2013)", ""]
    lines.append(
        _table(
            ("Categoria", "Exigido", "Cursado", "Planejado", "Falta"),
            [(t.label, f"{t.required} cr", f"{t.done} cr", "—", f"{t.missing} cr") for t in stay.totals],
        )
    )
    lines.append("")
    if stay.pending:
        lines += ["Obrigatórias, estágios e TCC pendentes na grade 2013:", ""]
        lines += [f"- {c.name} ({c.code}), {c.semester}º período" for c in stay.pending]
    else:
        lines.append("Nenhuma obrigatória pendente na grade 2013.")
    return "\n".join(lines)


def _item_notes(ctx, item):
    notes = []
    if item.off_offer:
        notes.append("fora do período de oferta")
    for dep in item.depends_on_to_define:
        notes.append(f"depende de {ctx.by_id[dep].name}, cuja situação está a definir pela coordenação")
    if item.missing_prerequisites:
        notes.append("pré-requisito não cumprido")
    return "; ".join(notes) or "—"


def _section_plan(ctx, check):
    lines = ["## 5. Plano atual do aluno (cenário de migração)", ""]
    terms = [t for t in check.terms if t.items or t.notices]
    if not any(t.items for t in check.terms):
        lines.append("Nenhum plano montado.")
        return "\n".join(lines)
    for term in terms:
        rows = []
        for item in term.items:
            if item.generic:
                label = item.name
            else:
                label = _course_label(ctx.by_id[item.id])
            rows.append((label, item.credits, _item_notes(ctx, item)))
        lines += [f"### {term.term}", "", _table(("Disciplina", "Créditos", "Avisos"), rows), ""]
        lines.append(f"Total: {term.credits} créditos.")
        if term.notices:
            lines += [""] + [f"- {n}" for n in term.notices]
        lines.append("")
    notices = [check.offer_warning] if check.offer_warning else []
    notices += [*check.to_define_notices, *check.notices]
    if notices:
        lines += ["Avisos:", ""] + [f"- {n}" for n in notices]
    return "\n".join(lines).rstrip()


def _section_pending(ctx, plan):
    planned = _planned_terms(plan)

    def in_plan(course_id):
        return f"Sim ({planned[course_id]})" if course_id in planned else "Não"

    pending_ids = {r.id for r in ctx.evaluation.migrate.pending}
    required = sorted(
        (c for c in ctx.data.curriculum_2026 if c.id in pending_ids),
        key=lambda c: (c.semester or 99, c.name),
    )
    others = sorted(
        (
            c
            for c in ctx.data.curriculum_2026
            if c.type in OTHER_TYPES and c.id not in ctx.base_completed
        ),
        key=lambda c: (OTHER_TYPES.index(c.type), c.emphasis or "~", c.name),
    )

    def kind(course):
        parts = [TYPE_LABELS[course.type]]
        if course.emphasis:
            parts.append(f"ênfase {course.emphasis}")
        if course.extension:
            parts.append("extensionista")
        return ", ".join(parts)

    lines = ["## 6. Disciplinas da grade 2026 ainda pendentes", "", "### Obrigatórias, estágio e TCC", ""]
    if required:
        lines.append(
            _table(
                ("Disciplina", "Créditos", "Semestre do fluxograma", "Pré-requisitos", "Oferta", "No plano atual"),
                [
                    (
                        _course_label(c) + (" — extensionista" if c.extension else ""),
                        c.credits,
                        f"{c.semester}º" if c.semester else "—",
                        _prerequisite_text(ctx, c.id),
                        _offer_text(ctx, c),
                        in_plan(c.id),
                    )
                    for c in required
                ],
            )
        )
    else:
        lines.append("Nenhuma: todas foram aproveitadas do histórico.")
    lines += ["", "### Optativas e flexíveis disponíveis", ""]
    lines.append(
        _table(
            ("Disciplina", "Tipo", "Créditos", "Pré-requisitos", "Oferta", "No plano atual"),
            [
                (_course_label(c), kind(c), c.credits, _prerequisite_text(ctx, c.id), _offer_text(ctx, c), in_plan(c.id))
                for c in others
            ],
        )
    )
    lines += [
        "",
        "### Opções genéricas (quando o aluno ainda não sabe qual disciplina cursar)",
        "",
    ]
    lines += [
        f"- {g.name}: {g.credits} cr, conta como {TYPE_LABELS[g.type]}"
        + (f" e {g.hours} h de extensão" if g.extension else "")
        + "; pode ser usada mais de uma vez."
        for g in GENERIC_ITEMS.values()
    ]
    return "\n".join(lines)


def _section_instructions(ctx):
    first_term = ctx.assumptions["first_planning_term"].value
    return "## 7. Instruções para a IA\n\n" + AI_INSTRUCTIONS.format(first_term=first_term).rstrip()


def build_export(ctx, check, plan, outcomes):
    """Return the Markdown summary.

    ctx: PlanContext (transcript and assumptions); check: PlanCheck of the plan;
    plan: {term: [item ids]}; outcomes: plan_check.history_outcomes(ctx).
    """
    sections = [
        "# Migração do PPC: resumo para conversar com uma IA",
        "Gerado pelo simulador de migração do curso de Estatística da UFPB. Não contém nome, "
        "matrícula nem outros dados pessoais. É uma simulação baseada nas regras disponíveis e não "
        "substitui a orientação da coordenação.",
        _section_context(ctx, check),
        _section_assumptions(ctx),
        _section_history(ctx, outcomes),
        _section_scenarios(ctx, check),
        _section_plan(ctx, check),
        _section_pending(ctx, plan),
        _section_instructions(ctx),
    ]
    return "\n\n".join(sections) + "\n"
