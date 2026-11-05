"""Streamlit app: convert a 2013 history to the 2026 curriculum.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.conversion import (  # noqa: E402
    DESTINATION_ELECTIVE_PREFIX,
    DESTINATION_NO_EMPHASIS,
    DESTINATION_TOPICS,
    EMPHASES,
    EMPHASIS_NAMES,
    HistoryEntry,
    convert,
)
from app.data_loader import load_data  # noqa: E402
from app.history_pdf import parse_history  # noqa: E402
from app.summary import build_summary, format_hours  # noqa: E402

REQUIRED_TYPES = ("mandatory", "internship", "complementary")
TYPE_LABELS = {
    "mandatory": "Obrigatória",
    "elective": "Optativa",
    "flexible": "Flexível",
    "internship": "Estágio",
    "complementary": "TCC",
}
SIGAA_TYPE_LABELS = {"OB": "Obrigatória", "OP": "Optativa", "CO": "Obrigatória", "CF": "Flexível",
                     "EC": "Extracurricular", "EQ": "Equivalente"}
STATUS_LABELS = {"confirmed": "confirmada", "assumed": "suposta"}
ELECTIVES_GROUP = "Optativas"
FLEXIBLES_GROUP = "Flexíveis"
UNRECOGNIZED_GROUP = "Não reconhecidas na grade 2013"
DESTINATION_LABELS = {
    DESTINATION_TOPICS: "Tópicos Especiais (flexível)",
    **{f"{DESTINATION_ELECTIVE_PREFIX}{e}": f"Optativa ({EMPHASIS_NAMES[e]})" for e in EMPHASES},
    f"{DESTINATION_ELECTIVE_PREFIX}{DESTINATION_NO_EMPHASIS}": "Optativa (sem ênfase)",
}
EMPHASIS_OPTIONS = {**{e: EMPHASIS_NAMES[e] for e in EMPHASES}, DESTINATION_NO_EMPHASIS: "Sem ênfase"}
FOOTER = "Simulação baseada nas regras disponíveis; não substitui a orientação da coordenação."
LOSS_ROW_STYLE = "background-color: rgba(255, 75, 75, 0.15)"

# Relative widths: Código, Disciplina, Tipo, CH, remove button.
ROW_WIDTHS = [1.2, 5, 1.4, 0.8, 1.3]

SOURCE_MANUAL = "manual"
SOURCE_PDF = "pdf"
SOURCE_IN_PROGRESS = "pdf_in_progress"


@st.cache_resource
def get_data():
    return load_data()


# ---------- History state (pure functions over a dict-like state) ----------


def entry_dict(code, name, hours, sigaa_type="", source=SOURCE_MANUAL):
    return {"code": code, "name": name, "hours": hours, "sigaa_type": sigaa_type, "source": source}


def history(state):
    return state.setdefault("history", [])


def add_course(state, course):
    if course.code not in {e["code"] for e in history(state)}:
        state["history"] = [*history(state), entry_dict(course.code, course.name, course.hours)]


def remove_entry(state, code):
    state["history"] = [e for e in history(state) if e["code"] != code]


def fill_until(state, data, until):
    """Add the 2013 mandatory courses (with internship and TCC) up to period N."""
    for course in data.curriculum_2013:
        if course.type in REQUIRED_TYPES and course.semester <= until:
            add_course(state, course)


def apply_parsed(state, parsed, file_id, include_in_progress):
    """Fill the table from a parsed PDF (replacing it) and keep the in-progress lines aside."""
    def dicts(entries, source):
        return [entry_dict(e.code, e.name, e.hours, e.sigaa_type, source) for e in entries]

    approved = dicts([e for e in parsed.entries if e.code not in {i.code for i in parsed.in_progress}], SOURCE_PDF)
    state["pdf_file_id"] = file_id
    state["pdf_in_progress"] = dicts(parsed.in_progress, SOURCE_IN_PROGRESS)
    state["pdf_report"] = {
        "approved_count": len(approved),
        "approved_hours": parsed.approved_hours,
        "in_progress_count": len(parsed.in_progress),
        "totals_match": parsed.totals_match,
        "warnings": list(parsed.warnings),
    }
    state["history"] = approved
    sync_in_progress(state, include_in_progress)


def sync_in_progress(state, include):
    """Add or remove the in-progress lines of the PDF, keeping the other rows."""
    rows = [e for e in history(state) if e["source"] != SOURCE_IN_PROGRESS]
    if include:
        codes = {e["code"] for e in rows}
        rows += [e for e in state.get("pdf_in_progress", []) if e["code"] not in codes]
    state["history"] = rows


def history_entries(state):
    return [HistoryEntry(e["code"], e["name"], e["hours"], e["sigaa_type"]) for e in history(state)]


# ---------- Groups (2013 flowchart periods, then electives and flexibles) ----------


def course_2013(data, code):
    by_code = {c.code: c for c in data.curriculum_2013}
    aliases = {a.code: a.alias_of for a in data.code_aliases if a.status == "active"}
    return by_code.get(code) or by_code.get(aliases.get(code, ""))


def period_group(semester):
    return f"{semester}º período"


def group_names(data):
    semesters = sorted({c.semester for c in data.curriculum_2013 if c.type in REQUIRED_TYPES})
    return [period_group(s) for s in semesters] + [ELECTIVES_GROUP, FLEXIBLES_GROUP, UNRECOGNIZED_GROUP]


def group_of(type_2013, semester, sigaa_type=""):
    if type_2013 in REQUIRED_TYPES:
        return period_group(semester)
    if type_2013 == "elective":
        return ELECTIVES_GROUP
    if type_2013 == "flexible" or sigaa_type == "CF":
        return FLEXIBLES_GROUP
    return UNRECOGNIZED_GROUP


def options_by_group(data, chosen):
    options = {}
    for course in data.curriculum_2013:
        if course.code not in chosen:
            options.setdefault(group_of(course.type, course.semester), []).append(course)
    return options


# ---------- Sidebar ----------


def as_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def assumption_widget(assumption):
    key = f"assumption_{assumption.key}"
    if assumption.value in ("true", "false"):
        return st.toggle(assumption.description, value=assumption.value == "true", key=key)
    if assumption.key == "consultoria_emphasis":
        options = list(EMPHASIS_OPTIONS)
        index = options.index(assumption.value) if assumption.value in options else len(options) - 1
        return st.selectbox(assumption.description, options, index=index, format_func=EMPHASIS_OPTIONS.get, key=key)
    if assumption.value.isdigit():
        return st.number_input(assumption.description, min_value=0, value=int(assumption.value), step=15, key=key)
    return st.text_input(assumption.description, value=assumption.value, key=key)


def render_sidebar(data):
    """Return (assumption overrides, destination overrides)."""
    overrides, destination_overrides = {}, {}
    names = {c.code: c.name for c in data.curriculum_2013}
    with st.sidebar:
        st.header("Premissas")
        st.caption(
            "Premissas **supostas** ainda não foram confirmadas pela coordenação e podem ser "
            "alteradas aqui; o resultado é recalculado na hora."
        )
        if st.button("Restaurar valores do arquivo", key="restore"):
            for key in [k for k in st.session_state if k.startswith(("assumption_", "destination_"))]:
                del st.session_state[key]
            st.rerun()
        for assumption in data.assumptions:
            status = STATUS_LABELS.get(assumption.status, assumption.status)
            if assumption.status == "assumed":
                st.markdown(f"**{status.capitalize()}** · `{assumption.key}`")
                value = assumption_widget(assumption)
                if as_text(value) != assumption.value:
                    overrides[assumption.key] = value
            else:
                st.caption(f"{assumption.description}: **{assumption.value}** ({status})")

        st.header("Disciplinas extintas: Tópicos ou optativa")
        st.caption("Destino na grade 2026 das disciplinas de 2013 sem correspondente.")
        options = list(DESTINATION_LABELS)
        for row in data.old_course_destinations:
            name = names.get(row.code, row.code)
            if row.status != "assumed":
                label = DESTINATION_LABELS.get(row.destination, "Não aproveitada automaticamente")
                st.caption(f"{name}: **{label}** (confirmada)")
                continue
            value = st.selectbox(
                f"{name} (suposta)", options, index=options.index(row.destination),
                format_func=DESTINATION_LABELS.get, key=f"destination_{row.code}",
            )
            if value != row.destination:
                destination_overrides[row.code] = value
    return overrides, destination_overrides


# ---------- 1. History input ----------


def on_add(select_key):
    course = st.session_state.get(select_key)
    if course is not None:
        add_course(st.session_state, course)
    st.session_state[select_key] = None


def on_fill():
    fill_until(st.session_state, get_data(), st.session_state["fill_until"])


def on_clear():
    st.session_state["history"] = []


def on_toggle_in_progress():
    sync_in_progress(st.session_state, st.session_state["include_in_progress"])


def render_pdf_input():
    cols = st.columns([3, 2], vertical_alignment="center")
    uploaded = cols[0].file_uploader("Envie o PDF do histórico do SIGAA", type="pdf", key="pdf")
    cols[1].checkbox(
        "Incluir disciplinas em curso (supondo aprovação)", key="include_in_progress",
        on_change=on_toggle_in_progress,
    )
    st.caption(
        "O PDF é lido na memória e descartado: não é gravado, e nome, matrícula e outros dados "
        "pessoais não são lidos. Se preferir, preencha a tabela abaixo manualmente."
    )
    if uploaded is not None and uploaded.file_id != st.session_state.get("pdf_file_id"):
        try:
            parsed = parse_history(uploaded.getvalue(), include_in_progress=True)
        except ValueError as error:
            st.session_state["pdf_file_id"] = uploaded.file_id
            st.session_state.pop("pdf_report", None)
            st.error(str(error))
            return
        apply_parsed(st.session_state, parsed, uploaded.file_id, st.session_state["include_in_progress"])

    report = st.session_state.get("pdf_report")
    if report:
        st.success(
            f"Tabela preenchida pelo PDF: {report['approved_count']} disciplinas aprovadas "
            f"({format_hours(report['approved_hours'])}) e {report['in_progress_count']} em curso. "
            "Confira e corrija a tabela se precisar."
        )
        for warning in report["warnings"]:
            st.warning(warning)


def render_history(data):
    st.subheader("1. Seu histórico na grade 2013")
    ensure_defaults()
    render_pdf_input()

    semesters = sorted({c.semester for c in data.curriculum_2013 if c.type in REQUIRED_TYPES})
    cols = st.columns([2, 1, 1], vertical_alignment="bottom")
    cols[0].selectbox(
        "Atalho: marcar obrigatórias até o período", semesters,
        format_func=lambda s: f"{s}º período", key="fill_until",
    )
    cols[1].button("Marcar", key="fill_button", on_click=on_fill, width="stretch")
    cols[2].button("Limpar tabela", key="clear_button", on_click=on_clear, width="stretch")

    rows = history(st.session_state)
    by_group = {}
    for entry in rows:
        course = course_2013(data, entry["code"])
        if course is not None:
            group = group_of(course.type, course.semester)
            row = (entry["code"], course.name, TYPE_LABELS[course.type], course.hours)
        else:
            group = group_of("", None, entry["sigaa_type"])
            row = (entry["code"], entry["name"], SIGAA_TYPE_LABELS.get(entry["sigaa_type"], "—"), entry["hours"] or 0)
        by_group.setdefault(group, []).append(row)
    options = options_by_group(data, {e["code"] for e in rows})

    for group in group_names(data):
        group_rows, group_options = by_group.get(group, []), options.get(group, [])
        if group == UNRECOGNIZED_GROUP and not group_rows:
            continue
        with st.container(border=True):
            st.markdown(f"#### {group}")
            header = st.columns(ROW_WIDTHS)
            for col, label in zip(header, ("Código", "Disciplina", "Tipo", "CH", "")):
                col.markdown(f"**{label}**")
            for code, name, type_label, hours in sorted(group_rows, key=lambda r: r[1]):
                cols = st.columns(ROW_WIDTHS, vertical_alignment="center")
                cols[0].markdown(code)
                cols[1].markdown(name)
                cols[2].markdown(type_label)
                cols[3].markdown(f"{hours} h")
                cols[4].button(
                    "✕ Remover", key=f"rm_{code}", on_click=remove_entry,
                    args=(st.session_state, code), width="stretch",
                )
            if group_options:
                select_key = f"add_{group}"
                st.selectbox(
                    "Incluir", group_options, index=None, key=select_key,
                    format_func=lambda c: f"{c.name} ({c.code})", placeholder="+ Incluir disciplina…",
                    on_change=on_add, args=(select_key,), label_visibility="collapsed",
                )
            total = sum(r[3] for r in group_rows)
            st.markdown(f"**Total: {format_hours(total)}**")


def ensure_defaults():
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("include_in_progress", False)


# ---------- 2. Summary ----------


def render_summary(result, summary, overrides, destination_overrides):
    st.subheader("2. Resumo da migração para o novo PPC")
    if overrides or destination_overrides:
        st.warning("Resultado calculado com premissas ou destinos alterados na barra lateral.")
    for warning in summary.warnings:
        if warning.startswith("Atenção:"):
            st.error(warning)
        else:
            st.warning(warning)

    cols = st.columns(3)
    cols[0].metric("Faltam", format_hours(summary.missing_hours))
    cols[0].caption(summary.missing_text)
    cols[1].metric("Aproveitamento", f"{summary.used_percent}%")
    cols[1].caption(summary.used_text + (f" {summary.used_note}" if summary.used_note else ""))
    cols[2].metric("Não aproveitado", format_hours(summary.lost_hours))
    cols[2].caption(summary.lost_text)

    if summary.lost_hours:
        st.markdown(f"**{summary.lost_text}**")
        if summary.recoverable_lines:
            st.markdown("\n".join(f"- {line}" for line in summary.recoverable_lines))
        st.dataframe(
            [{"Disciplina": i.name, "Horas perdidas": format_hours(i.lost_hours), "Motivo": i.reason}
             for i in summary.lost_items],
            hide_index=True, width="stretch",
        )

    st.markdown("**Por categoria do novo PPC**")
    st.dataframe(
        [{"Categoria": c.name, "Exigido": format_hours(c.required_hours),
          "Aproveitado": format_hours(c.used_hours), "Falta": format_hours(c.missing_hours)}
         for c in summary.categories],
        hide_index=True, width="stretch",
    )
    st.caption("A extensão não soma às demais: ela é cumprida dentro das outras categorias.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Obrigatórias do novo PPC que faltam cursar**")
        if result.pending:
            st.markdown("\n".join(f"- {p.name} ({p.semester}º período)" for p in result.pending))
        else:
            st.success("Nenhuma: todas aproveitadas.")
    with right:
        st.markdown("**Ênfase**")
        for e in summary.emphases:
            mark = "✅" if e.reached else "—"
            st.markdown(f"{mark} {e.name}: {format_hours(e.hours)} de {format_hours(e.min_hours)} em optativas")

    if summary.requests:
        st.info(
            "**Possíveis aproveitamentos mediante pedido à coordenação** (não entram nas contas):\n\n"
            + "\n".join(f"- {r.text}" for r in summary.requests)
        )
    st.markdown(f"**Comparação:** {summary.stay_text}")


# ---------- 3. Conversion table ----------


def conversion_rows(result):
    by_group = {}
    for c in result.courses:
        note = " ".join(part for part in (c.reason, c.note) if part)
        by_group.setdefault(group_of(c.type_2013, c.semester), []).append({
            "Código": c.code,
            "Disciplina (2013)": c.name,
            "CH": c.hours,
            "Na grade 2026": c.destination,
            "CH aproveitada": c.used_hours,
            "CH perdida": c.lost_hours,
            "Observação": note,
        })
    return by_group


def highlight_losses(row):
    return [LOSS_ROW_STYLE if row["CH perdida"] else ""] * len(row)


def render_conversion(result, data):
    st.subheader("3. Tabela de conversão")
    st.caption("Linhas destacadas têm horas não aproveitadas.")
    by_group = conversion_rows(result)
    for group in group_names(data):
        rows = by_group.get(group)
        if not rows:
            continue
        st.markdown(f"#### {group}")
        st.dataframe(pd.DataFrame(rows).style.apply(highlight_losses, axis=1), hide_index=True, width="stretch")


# ---------- Page ----------


def main():
    st.set_page_config(page_title="Migração do PPC — Estatística UFPB", layout="wide")
    st.title("Migrar para o novo PPC: o que você aproveita?")
    st.caption("Estatística e Ciência de Dados (UFPB) · Resolução CONSEPE 41/2026")

    data = get_data()
    overrides, destination_overrides = render_sidebar(data)
    render_history(data)

    entries = history_entries(st.session_state)
    if entries:
        result = convert(entries, overrides, destination_overrides, data=data)
        summary = build_summary(result)
        render_summary(result, summary, overrides, destination_overrides)
        render_conversion(result, data)
    else:
        st.info("Envie o PDF do histórico ou inclua as disciplinas aprovadas para ver o resultado.")

    st.divider()
    st.warning(FOOTER)


if __name__ == "__main__":
    main()
