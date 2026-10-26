"""Streamlit prototype: manual course selection, both scenarios side by side.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.data_loader import load_data  # noqa: E402
from app.planner import plan, term_from_index, term_index  # noqa: E402
from app.rules import STATUS_PENDING, STATUS_TO_DEFINE, STATUS_USED, evaluate  # noqa: E402

TYPE_LABELS = {
    "mandatory": "Obrigatória",
    "elective": "Optativa",
    "flexible": "Flexível",
    "internship": "Estágio",
    "complementary": "Complementar (TCC)",
}
CATEGORY_LABELS = {
    "mandatory": "Obrigatórias",
    "internship": "Estágio",
    "complementary": "Complementares (TCC)",
    "elective": "Optativas",
    "flexible": "Flexíveis",
    "extension": "Extensão",
}
ASSUMPTION_STATUS_LABELS = {"confirmed": "confirmada", "assumed": "suposta"}
REQUIRED_TYPES = ("mandatory", "internship", "complementary")
FIRST_ENTRY_TERM = "2013.1"
LAST_ENTRY_TERM = "2026.2"
DEFAULT_ENTRY_TERM = "2023.1"


@st.cache_resource
def get_data():
    return load_data()


def course_label(course):
    return f"{course.name} ({course.code})"


# ---------- Sidebar: assumptions ----------


def assumption_widget(assumption, data):
    """Render an editable widget for an assumed assumption; return its value."""
    key = f"assumption_{assumption.key}"
    label = assumption.description
    value = assumption.value
    if value in ("true", "false"):
        return st.toggle(label, value=value == "true", key=key)
    if assumption.key == "internship_match":
        options = ["all_of", "any_of"]
        labels = {"all_of": "Exige Estágio I e II", "any_of": "Basta um dos estágios"}
        return st.radio(label, options, index=options.index(value), format_func=labels.get, key=key)
    if assumption.key == "every_term_types":
        return st.multiselect(
            label, list(TYPE_LABELS), default=value.split("|"), format_func=TYPE_LABELS.get, key=key
        )
    if assumption.key == "transition_every_term_ids":
        names = {c.id: c.name for c in data.curriculum_2026 if c.type in REQUIRED_TYPES}
        default = [v for v in value.split("|") if v in names]
        return st.multiselect(label, list(names), default=default, format_func=names.get, key=key)
    if value.isdigit():
        return st.number_input(label, min_value=0, value=int(value), step=1, key=key)
    return st.text_input(label, value=value, key=key)


def as_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "|".join(value)
    return str(value)


def render_assumptions(data):
    """Render the assumptions sidebar and return the overrides that differ from the CSV."""
    overrides = {}
    with st.sidebar:
        st.header("Premissas")
        st.caption(
            "Premissas **supostas** ainda não foram confirmadas pela coordenação e podem ser "
            "alteradas aqui; o resultado é recalculado na hora."
        )
        if st.button("Restaurar valores do arquivo"):
            for a in data.assumptions:
                st.session_state.pop(f"assumption_{a.key}", None)
            st.rerun()
        for assumption in data.assumptions:
            status = ASSUMPTION_STATUS_LABELS.get(assumption.status, assumption.status)
            st.markdown(f"**`{assumption.key}`** · {status}")
            if assumption.status == "assumed":
                value = assumption_widget(assumption, data)
                if as_text(value) != assumption.value:
                    overrides[assumption.key] = value
            else:
                st.caption(f"{assumption.description}: **{assumption.value}**")
            st.divider()
    return overrides


# ---------- Input: transcript ----------


def entry_terms():
    return [
        term_from_index(i) for i in range(term_index(FIRST_ENTRY_TERM), term_index(LAST_ENTRY_TERM) + 1)
    ]


def fill_until(semester, courses):
    """Check every course up to the given semester (None: the semester picked in the selectbox)."""
    if semester is None:
        semester = st.session_state["fill_until"]
    for course in courses:
        st.session_state[f"taken_{course.code}"] = course.semester <= semester


def render_transcript_input(data):
    """Render the course selection; return (entry_term, codes)."""
    st.subheader("1. Seu histórico na grade 2013")
    terms = entry_terms()
    entry_term = st.selectbox(
        "Período de ingresso", terms, index=terms.index(DEFAULT_ENTRY_TERM), key="entry_term"
    )

    required = [c for c in data.curriculum_2013 if c.type in REQUIRED_TYPES]
    semesters = sorted({c.semester for c in required})

    fill_cols = st.columns([2, 1, 1])
    fill_cols[0].selectbox(
        "Atalho: marcar todas as obrigatórias até o período",
        semesters,
        format_func=lambda s: f"{s}º período",
        key="fill_until",
    )
    fill_cols[1].button("Marcar", on_click=fill_until, args=(None, required), width="stretch")
    fill_cols[2].button("Limpar", on_click=fill_until, args=(0, required), width="stretch")

    st.markdown("**Obrigatórias, estágios e TCC** (marque as cursadas com aprovação)")
    codes = []
    columns = st.columns(4)
    for i, semester in enumerate(semesters):
        with columns[i % 4]:
            st.markdown(f"*{semester}º período*")
            for course in (c for c in required if c.semester == semester):
                if st.checkbox(course.name, key=f"taken_{course.code}", help=course.code):
                    codes.append(course.code)

    others = [c for c in data.curriculum_2013 if c.type not in REQUIRED_TYPES]
    selected = st.multiselect(
        "**Optativas e flexíveis** cursadas com aprovação",
        others,
        format_func=lambda c: f"{course_label(c)} · {TYPE_LABELS[c.type].lower()}",
        key="electives",
    )
    codes += [c.code for c in selected]
    return entry_term, codes


# ---------- Output ----------


def totals_rows(totals):
    return [
        {
            "Categoria": CATEGORY_LABELS.get(t.category, t.category),
            "Feito": f"{t.done} {t.unit}",
            "Exigido": f"{t.required} {t.unit}",
            "Falta": f"{max(0, t.required - t.done)} {t.unit}",
        }
        for t in totals
    ]


def plan_rows(scenario_plan):
    rows = []
    for term in scenario_plan.terms:
        names = " · ".join(c.name for c in term.courses)
        rows.append({"Período": term.term, "Créditos": term.credits, "Disciplinas": names})
    return rows


def render_conclusion(scenario_plan):
    cols = st.columns(2)
    cols[0].metric("Conclusão prevista", scenario_plan.conclusion_term or "—")
    cols[1].metric("Períodos restantes", scenario_plan.remaining_terms)
    if scenario_plan.exceeds_deadline:
        st.error(f"Ultrapassa o prazo máximo de conclusão ({scenario_plan.deadline_term}).")
    elif scenario_plan.deadline_term:
        st.caption(f"Prazo máximo de conclusão: {scenario_plan.deadline_term}.")


def render_plan(scenario_plan):
    st.markdown("**Planejamento por período**")
    rows = plan_rows(scenario_plan)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    if scenario_plan.unscheduled:
        st.error("Disciplinas que não puderam ser planejadas: " + ", ".join(scenario_plan.unscheduled))
    for notice in scenario_plan.notices:
        st.info(notice)


def render_migrate(evaluation, planning):
    result = evaluation.migrate
    st.header("Migrar para o PPC 2026")
    render_conclusion(planning.migrate)

    if result.to_define:
        st.markdown("**A definir pela coordenação**")
        for item in result.to_define:
            st.warning(f"**{item.record}** ({item.course_id}): {item.description}")
    for notice in result.notices:
        st.warning(notice)

    st.markdown("**Créditos**")
    st.dataframe(totals_rows(result.totals), hide_index=True, width="stretch")
    emphasis = ", ".join(result.emphases) if result.emphases else "generalista"
    credits = ", ".join(f"{e}: {c} cr" for e, c in result.emphasis_credits.items())
    st.caption(f"Ênfase: **{emphasis}** (créditos em optativas por ênfase: {credits}; mínimo de 24 cr).")

    st.markdown("**Situação das disciplinas da grade 2026**")
    rows = [
        {
            "Disciplina": r.name,
            "Tipo": TYPE_LABELS.get(r.type, r.type),
            "Situação": r.status,
            "Cursada como": ", ".join(r.source_codes),
            "Regra": r.rule,
        }
        for r in [*result.used, *result.pending]
    ] + [
        {
            "Disciplina": next((c.name for c in get_data().curriculum_2026 if c.id == t.course_id), t.course_id),
            "Tipo": "",
            "Situação": STATUS_TO_DEFINE,
            "Cursada como": "",
            "Regra": t.record,
        }
        for t in result.to_define
    ]
    order = {STATUS_USED: 0, STATUS_TO_DEFINE: 1, STATUS_PENDING: 2}
    rows.sort(key=lambda r: order.get(r["Situação"], 3))
    st.dataframe(rows, hide_index=True, width="stretch")

    taken = [*result.electives, *result.flexibles]
    if taken:
        st.markdown("**Disciplinas de 2013 aproveitadas como optativa ou flexível**")
        st.dataframe(
            [
                {
                    "Disciplina": c.name,
                    "Código": c.code,
                    "Conta como": c.status,
                    "Créditos": c.credits,
                    "Ênfase": c.emphasis,
                    "Observação": c.note,
                }
                for c in taken
            ],
            hide_index=True,
            width="stretch",
        )

    render_plan(planning.migrate)


def render_stay(evaluation, planning):
    result = evaluation.stay
    st.header("Não migrar (PPC 2013)")
    render_conclusion(planning.stay)

    st.markdown("**Créditos**")
    st.dataframe(totals_rows(result.totals), hide_index=True, width="stretch")

    st.markdown("**Obrigatórias, estágios e TCC pendentes**")
    if result.pending:
        st.dataframe(
            [
                {"Disciplina": r.name, "Código": r.code, "Tipo": TYPE_LABELS.get(r.type, r.type), "Situação": r.status}
                for r in result.pending
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.success("Nenhuma obrigatória pendente.")

    render_plan(planning.stay)


def main():
    st.set_page_config(page_title="Migração do PPC — Estatística UFPB", layout="wide")
    st.title("Migrar ou não migrar para o novo PPC?")
    st.caption(
        "Estatística e Ciência de Dados (UFPB) · Resolução CONSEPE 41/2026. Protótipo: o resultado é "
        "calculado pelas regras de migração definidas pela coordenação e por premissas ainda em análise."
    )

    data = get_data()
    overrides = render_assumptions(data)
    entry_term, codes = render_transcript_input(data)

    evaluation = evaluate(codes, overrides=overrides, data=data)
    planning = plan(evaluation, entry_term=entry_term, overrides=overrides, data=data)

    st.subheader("2. Resultado")
    if overrides:
        changed = ", ".join(f"`{k}`" for k in overrides)
        st.warning(f"Resultado calculado com premissas alteradas na barra lateral: {changed}.")
    for notice in evaluation.notices:
        st.info(notice)

    left, right = st.columns(2)
    with left:
        render_migrate(evaluation, planning)
    with right:
        render_stay(evaluation, planning)


main()
