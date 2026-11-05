"""Markdown file for the student to discuss the result with an AI assistant.

Pure function over the results already computed by the app: no API calls,
no files written and no personal data (no name, student id or birth date).
Courses always appear by name; SIGAA codes only in parentheses inside tables;
internal ids never appear.
"""

from app.conversion import (
    CONSULTORIA_ID,
    DESTINATION_ELECTIVE_PREFIX,
    DESTINATION_NO_EMPHASIS,
    DESTINATION_NONE,
    DESTINATION_TOPICS,
    EMPHASES,
    EMPHASIS_NAMES,
    FLEXIBLE_EXTENSION,
    TOPICS,
    UNRECOGNIZED,
)
from app.data_loader import TBD
from app.summary import (
    category_line,
    destination_text,
    format_hours,
    lost_line,
    split_pending,
)

NEW_CODE = "NEW"
EXTERNAL_PREFIX = "code:"
MANUAL_CODE_PREFIX = "MANUAL-"
FILE_NAME = "simulacao_migracao_ppc.md"
STATUS_LABELS = {"confirmed": "confirmada", "assumed": "suposta"}
DESTINATION_LABELS = {
    DESTINATION_TOPICS: "Tópicos Especiais (flexível)",
    DESTINATION_NONE: "Não aproveitada automaticamente",
    **{f"{DESTINATION_ELECTIVE_PREFIX}{e}": f"Optativa · {EMPHASIS_NAMES[e]}" for e in EMPHASES},
    f"{DESTINATION_ELECTIVE_PREFIX}{DESTINATION_NO_EMPHASIS}": "Optativa sem ênfase",
}

AI_INSTRUCTIONS = """\
- Responda em português.
- Explique ao aluno, em linguagem simples, o que ele aproveita, o que perde e o que falta, e
  ajude-o a pensar nas escolhas (por exemplo, quais optativas combinam com uma ênfase).
- Use apenas o que está neste arquivo: não invente disciplinas, regras ou equivalências.
- Os números deste arquivo foram calculados pelo app a partir das regras da coordenação. Não
  refaça as contas; se algo parecer divergir, prevalece o que está no arquivo, e o aluno deve
  confirmar com a coordenação.
- Sinalize sempre o que depende de decisão ou pedido à coordenação: premissas e destinos
  supostos e os possíveis aproveitamentos mediante pedido.
- Lembre o aluno de conferir qualquer conclusão no app e com a coordenação.
"""


# ---------- Formatting helpers ----------


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _label(name, code):
    """'Name (code)' for tables; courses from another program added by hand have no code."""
    if not code or code.startswith(MANUAL_CODE_PREFIX):
        return name
    return f"{name} ({'nova' if code == NEW_CODE else code})"


def _join(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " e " + names[-1]


def _bullets(lines):
    return "\n".join(f"- {line}" for line in lines)


def readable_assumption_value(key, value):
    """Plain words for an assumption value, never raw codes."""
    if value in ("true", "false"):
        return "Sim" if value == "true" else "Não"
    if key == "consultoria_emphasis":
        return EMPHASIS_NAMES.get(value, "sem ênfase")
    if key.endswith("_hours") and value.isdigit():
        return format_hours(int(value))
    return value


def _status(item):
    status = STATUS_LABELS.get(item.status, item.status)
    return status + (" (alterada na simulação)" if item.overridden else "")


# ---------- Sections ----------


def _section_context(result, assumptions, current_period, in_progress_included):
    def hours(key):
        return format_hours(int(assumptions[key].value))

    requirements = "; ".join(
        f"{t.name} {format_hours(t.required_hours)}" for t in result.totals
    )
    lines = [
        "## 1. Contexto e regras de conversão",
        "",
        "- Curso de Estatística da UFPB. O aluno está na grade de 2013 (PPC 2013) e simula a migração "
        "para o PPC 2026 do curso de Estatística e Ciência de Dados (Resolução CONSEPE 41/2026), que "
        f"entra em vigor em {assumptions['start_term'].value}.",
        "- O app não faz previsão nem planejamento: mostra o que é aproveitado, o que é perdido e o "
        "que falta. As escolhas são do aluno.",
        f"- Exigências do PPC 2026: {format_hours(result.total_required_hours)} no total "
        f"({requirements}). A extensão é cumprida dentro das outras categorias.",
        f"- Ênfase: no mínimo {hours('emphasis_min_hours')} em optativas da mesma ênfase (Estatística "
        "Aplicada e Modelagem ou Ciência de Dados); senão, a formação é generalista.",
    ]
    if current_period is not None:
        lines.append(f"- Período em que o aluno informou estar: {current_period}º.")
    if in_progress_included is not None:
        lines.append(
            "- Disciplinas em curso: "
            + ("incluídas como aprovadas nesta simulação." if in_progress_included
               else "não incluídas nesta simulação.")
        )
    lines += [
        "",
        "Cada disciplina aprovada na grade 2013 tem um único destino, pelas regras abaixo, nesta ordem:",
        "",
        "1. Mesmo código na grade 2026 (considerando códigos antigos da mesma disciplina): vira a "
        "disciplina de 2026; se for optativa, entra na ênfase dela.",
        "2. Equivalência definida no PPC 2026: vira a obrigatória de 2026.",
        "3. Disciplina com sucessora no PPC 2026: conta como optativa da ênfase da sucessora.",
        "4. Disciplinas extintas e obrigatórias sem equivalência: destino definido pela coordenação "
        "(Tópicos Especiais, optativa ou nenhum; ver a seção 2).",
        "5. Tópicos Especiais de 2013 e disciplinas flexíveis: vão para Tópicos Especiais.",
        "6. Destino já ocupado: se duas disciplinas levam à mesma disciplina de 2026, uma ocupa o "
        "destino e a outra vai para Tópicos Especiais.",
        "",
        "Horas aproveitadas e perdidas:",
        "",
        "- Quem vira obrigatória, estágio ou TCC de 2026 aproveita no máximo a carga horária da "
        "disciplina de 2026; o excedente é perdido.",
        f"- Tópicos Especiais: limite único de {hours('topics_max_hours')}; o excedente é perdido.",
        f"- Optativas: limite de {hours('electives_max_hours')}; o excedente é perdido (primeiro as sem "
        "ênfase, depois as da ênfase com menos horas).",
        "- Estágio Supervisionado II: não é contado automaticamente; pode ser aproveitado como "
        f"extensão mediante pedido, até {hours('internship2_recoverable_max_hours')}.",
        "- Possíveis aproveitamentos mediante pedido nunca entram nas contas.",
    ]
    if assumptions["old_pm_counts_as_extension"].value == "true":
        lines.append("- Pesquisa de Mercado cursada em 2013 conta também como horas de extensão.")
    lines.append("- Disciplinas fora da grade 2013 (e que não sejam flexíveis) ficam fora das contas.")
    return "\n".join(lines)


def _section_assumptions(result):
    assumption_rows = [
        (a.description, readable_assumption_value(a.key, a.value), _status(a)) for a in result.assumptions
    ]
    destination_rows = [
        (_label(d.name, d.code), DESTINATION_LABELS.get(d.destination, d.destination), _status(d))
        for d in result.destinations
    ]
    return "\n".join([
        "## 2. Premissas usadas",
        "",
        "Premissas e destinos **supostos** ainda não foram confirmados pela coordenação.",
        "",
        _table(("Premissa", "Valor", "Status"), assumption_rows),
        "",
        "Destino das disciplinas de 2013 sem correspondente no PPC 2026:",
        "",
        _table(("Disciplina (2013)", "Destino", "Status"), destination_rows),
    ])


def _section_conversion(result, data):
    lines = ["## 3. Tabela de conversão", ""]
    if not result.courses:
        lines.append("Nenhuma disciplina informada.")
        return "\n".join(lines)
    rows = [
        (
            _label(c.name, c.code),
            format_hours(c.hours),
            destination_text(c, data),
            format_hours(c.used_hours),
            format_hours(c.lost_hours),
            " ".join(part for part in (c.reason, c.note) if part) or "—",
        )
        for c in result.courses
    ]
    lines.append(_table(
        ("Disciplina (2013)", "CH", "Na grade 2026", "CH aproveitada", "CH perdida", "Observação"), rows
    ))
    return "\n".join(lines)


def _section_summary(result, summary):
    totals = {t.category: t for t in result.totals}
    lines = [
        "## 4. Resumo",
        "",
        f"- {summary.missing_text}",
        f"- {summary.used_text}" + (f" {summary.used_note}" if summary.used_note else ""),
        f"- Não aproveitado: {format_hours(summary.lost_hours)} (ver a seção 5).",
        "",
        "Por categoria do PPC 2026:",
        "",
        _bullets(category_line(c) for c in summary.categories),
        "",
        "Flexíveis do PPC 2026 (componentes sem lista fixa de disciplinas): faltam "
        f"{format_hours(totals[TOPICS].missing_hours)} de Tópicos Especiais e "
        f"{format_hours(totals[FLEXIBLE_EXTENSION].missing_hours)} de flexíveis extensionistas.",
        "",
        "Ênfase (horas em optativas):",
        "",
        _bullets(
            f"{e.name}: {format_hours(e.hours)} de {format_hours(e.min_hours)}"
            + (" (atingida)" if e.reached else "")
            for e in summary.emphases
        ),
        "",
        f"Comparação: {summary.stay_text}",
    ]
    if summary.warnings:
        lines += ["", "Avisos:", "", _bullets(summary.warnings)]
    return "\n".join(lines)


def _section_lost(result, summary):
    lines = ["## 5. Não aproveitado", "", summary.lost_text]
    if summary.recoverable_lines:
        lines += ["", _bullets(summary.recoverable_lines)]
    if summary.lost_items:
        lines += ["", "Disciplinas com horas perdidas:", "", _bullets(lost_line(i) for i in summary.lost_items)]
    unrecognized = [c for c in result.courses if c.category == UNRECOGNIZED]
    if unrecognized:
        lines += [
            "",
            "Não reconhecidas (fora da grade 2013; fora das contas; consultar a coordenação):",
            "",
            _bullets(f"{c.name} ({format_hours(c.hours)})" for c in unrecognized),
        ]
    return "\n".join(lines)


def _section_requests(summary):
    lines = [
        "## 6. Possíveis aproveitamentos mediante pedido",
        "",
        "Dependem de pedido à coordenação e não entram nas contas.",
        "",
    ]
    lines.append(_bullets(r.text for r in summary.requests) if summary.requests else "Nenhum.")
    return "\n".join(lines)


def _pending_lines(courses):
    return _bullets(f"{p.name} ({p.semester}º período)" for p in courses) if courses else "Nenhuma."


def _section_pending(result, current_period):
    lines = ["## 7. Obrigatórias do PPC 2026 que faltam", ""]
    if not result.pending:
        lines.append("Nenhuma: todas foram aproveitadas.")
        return "\n".join(lines)
    lines.append("Na ordem do fluxograma do PPC 2026 (inclui estágio e TCC).")
    if current_period is None:
        lines += ["", _pending_lines(result.pending)]
    else:
        behind, upcoming = split_pending(result.pending, current_period)
        lines += [
            "",
            f"Ficaram para trás (períodos anteriores ao {current_period}º):",
            "",
            _pending_lines(behind),
            "",
            "Próximos períodos:",
            "",
            _pending_lines(upcoming),
        ]
    return "\n".join(lines)


def _done_ids(result, data):
    """2026 courses already covered by the history (same code, equivalence or successor)."""
    successors = {s.code: s.successor_id for s in data.elective_successors}
    done = {c.target_id for c in result.courses if c.target_id}
    done |= {successors[c.code] for c in result.courses if c.code in successors}
    return done


def _prerequisite_text(course_id, groups, by_id, done):
    alternatives = []
    for group in groups.get(course_id, {}).values():
        parts = []
        for prereq in group:
            if prereq == TBD:
                parts.append("a definir pela coordenação")
            elif prereq.startswith(EXTERNAL_PREFIX):
                parts.append(f"disciplina de outro curso ({prereq[len(EXTERNAL_PREFIX):]})")
            else:
                name = by_id[prereq].name
                parts.append(f"{name} (já aproveitada)" if prereq in done else name)
        alternatives.append(_join(parts))
    if not alternatives:
        return "—"
    return alternatives[0] if len(alternatives) == 1 else " ou ".join(f"[{a}]" for a in alternatives)


def _section_electives(result, data):
    assumptions = {a.key: a for a in result.assumptions}
    by_id = {c.id: c for c in data.curriculum_2026}
    groups = {}
    for p in data.prerequisites_2026:
        groups.setdefault(p.course_id, {}).setdefault(p.group, []).append(p.prerequisite_id)
    done = _done_ids(result, data)

    def emphasis(course):
        value = assumptions["consultoria_emphasis"].value if course.id == CONSULTORIA_ID else course.emphasis
        return EMPHASIS_NAMES.get(value, "sem ênfase")

    electives = sorted(
        (c for c in data.curriculum_2026 if c.type == "elective" and c.id not in done),
        key=lambda c: (emphasis(c) == "sem ênfase", emphasis(c), c.name),
    )
    rows = [
        (
            _label(c.name, c.code),
            emphasis(c),
            "Sim" if c.extension else "Não",
            _prerequisite_text(c.id, groups, by_id, done),
        )
        for c in electives
    ]
    return "\n".join([
        "## 8. Optativas disponíveis no PPC 2026",
        "",
        "Todas com 60 h. Não inclui as que o aluno já aproveitou. Pré-requisitos marcados "
        "\"(já aproveitada)\" estão cumpridos pelo histórico.",
        "",
        _table(("Disciplina", "Ênfase", "Extensionista", "Pré-requisitos"), rows),
    ])


def _section_instructions():
    return "## 9. Instruções para a IA\n\n" + AI_INSTRUCTIONS.rstrip()


def build_export(result, summary, data, current_period=None, in_progress_included=None):
    """Return the Markdown file.

    result: ConversionResult; summary: build_summary(result); data: CurriculumData used in the
    conversion; current_period: period the student says they are in (1 to 8), or None;
    in_progress_included: whether the in-progress courses of the PDF count as approved, or None
    when the PDF had none.
    """
    assumptions = {a.key: a for a in result.assumptions}
    sections = [
        "# Migração do PPC: resultado da simulação para conversar com uma IA",
        "Gerado pelo simulador de migração do curso de Estatística da UFPB. Não contém nome, "
        "matrícula nem outros dados pessoais. É uma simulação baseada nas regras disponíveis e não "
        "substitui a orientação da coordenação.",
        _section_context(result, assumptions, current_period, in_progress_included),
        _section_assumptions(result),
        _section_conversion(result, data),
        _section_summary(result, summary),
        _section_lost(result, summary),
        _section_requests(summary),
        _section_pending(result, current_period),
        _section_electives(result, data),
        _section_instructions(),
    ]
    return "\n\n".join(sections) + "\n"
