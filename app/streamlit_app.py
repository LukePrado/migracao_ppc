"""Streamlit prototype: transcript per term and a plan built by the student.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.data_loader import load_data  # noqa: E402
from app.plan_check import (  # noqa: E402
    GENERIC_ITEMS,
    MIN_CREDITS_2026,
    OTHER_TYPES,
    REQUIRED_TYPES,
    build_context,
    cascade_remove,
    check_with_context,
    deadline_term,
    eligible_courses,
    history_outcomes,
    history_terms,
    term_from_index,
    term_index,
    terms_between,
)

TYPE_LABELS = {
    "mandatory": "Obrigatória",
    "elective": "Optativa",
    "flexible": "Flexível",
    "internship": "Estágio",
    "complementary": "TCC",
}
ASSUMPTION_STATUS_LABELS = {"confirmed": "confirmada", "assumed": "suposta"}
FIRST_ENTRY_TERM = "2013.1"
DEFAULT_ENTRY_TERM = "2023.1"
MAX_PLAN_TERMS = 12
OFF_OFFER_MARK = "⚠️"
TO_DEFINE_MARK = "ⓘ"
FOOTER = "Simulação baseada nas regras disponíveis; não substitui a orientação da coordenação."


@st.cache_resource
def get_data():
    return load_data()


# ---------- Session state keys ----------


def hist_key(kind, term):
    return f"hist_{kind}_{term}"


def plan_key(kind, term):
    return f"plan_{kind}_{term}"


def ensure_key(key, default):
    if key not in st.session_state:
        st.session_state[key] = default


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


# ---------- Transcript (2013) ----------


def history_course_groups(data):
    required = [c for c in data.curriculum_2013 if c.type in REQUIRED_TYPES]
    required.sort(key=lambda c: (c.semester, c.name))
    others = [c for c in data.curriculum_2013 if c.type not in REQUIRED_TYPES]
    others.sort(key=lambda c: (c.type, c.name))
    return {"mand": required, "opt": others}


def sanitize_history(terms, groups):
    """Keep only valid codes and drop repeated courses (first term wins)."""
    seen = set()
    for kind, courses in groups.items():
        valid = {c.code for c in courses}
        for term in terms:
            key = hist_key(kind, term)
            ensure_key(key, [])
            kept = [c for c in st.session_state[key] if c in valid and c not in seen]
            seen.update(kept)
            if kept != st.session_state[key]:
                st.session_state[key] = kept
    return sorted(seen)


def fill_until(groups, first_term):
    """Place each 2013 required course up to semester N at entry + (semester - 1)."""
    entry = st.session_state["entry_term"]
    until = st.session_state["fill_until"]
    terms = history_terms(entry, first_term)
    left_out = []
    for course in groups["mand"]:
        if course.semester > until:
            continue
        for term in terms:
            key = hist_key("mand", term)
            st.session_state[key] = [c for c in st.session_state.get(key, []) if c != course.code]
        target = term_from_index(term_index(entry) + course.semester - 1)
        if target in terms:
            key = hist_key("mand", target)
            st.session_state[key] = st.session_state[key] + [course.code]
        else:
            left_out.append(f"{course.name} ({course.semester}º período → {target})")
    st.session_state["fill_notice"] = left_out


def clear_history(groups, first_term):
    terms = history_terms(st.session_state["entry_term"], first_term)
    for kind in groups:
        for term in terms:
            st.session_state[hist_key(kind, term)] = []
    st.session_state["fill_notice"] = []


def render_history(terms, groups, ctx, first_term):
    st.subheader("1. Histórico na grade 2013")
    st.info("Inclua também as disciplinas que está cursando agora, supondo aprovação.")
    if not terms:
        st.caption("Não há períodos de histórico para este ingresso.")
        return

    cols = st.columns([2, 1, 1])
    cols[0].selectbox(
        "Atalho: marcar obrigatórias até o período",
        sorted({c.semester for c in groups["mand"]}),
        format_func=lambda s: f"{s}º período",
        key="fill_until",
    )
    cols[1].button("Marcar", on_click=fill_until, args=(groups, first_term), width="stretch")
    cols[2].button("Limpar histórico", on_click=clear_history, args=(groups, first_term), width="stretch")
    if st.session_state.get("fill_notice"):
        st.warning(
            "Não foram marcadas porque cairiam depois do último período do histórico: "
            + "; ".join(st.session_state["fill_notice"])
        )

    by_code = {c.code: c for kind in groups for c in groups[kind]}
    outcomes = history_outcomes(ctx)
    labels = {"mand": "Obrigatórias", "opt": "Optativas e flexíveis"}
    for term in terms:
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{term}** · grade 2013")
                for kind, courses in groups.items():
                    chosen_elsewhere = {
                        code for t in terms if t != term for code in st.session_state[hist_key(kind, t)]
                    }
                    options = [c.code for c in courses if c.code not in chosen_elsewhere]
                    st.multiselect(
                        labels[kind],
                        options,
                        format_func=lambda code: f"{by_code[code].name} ({code})",
                        key=hist_key(kind, term),
                        placeholder="Escolha as disciplinas",
                    )
            with right:
                st.markdown("Na grade 2026")
                codes = [*st.session_state[hist_key("mand", term)], *st.session_state[hist_key("opt", term)]]
                if codes:
                    st.dataframe(
                        [
                            {"Disciplina (2013)": by_code[c].name, "Na grade 2026": outcomes.get(c, "—")}
                            for c in codes
                        ],
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.caption("Nenhuma disciplina neste período.")


# ---------- Plan (2026) ----------


def read_plan(terms):
    plan = {}
    for term in terms:
        for kind in ("mand", "opt"):
            ensure_key(plan_key(kind, term), [])
        items = [*st.session_state[plan_key("mand", term)], *st.session_state[plan_key("opt", term)]]
        for generic_id in GENERIC_ITEMS:
            key = plan_key(generic_id, term)
            ensure_key(key, 0)
            items += [generic_id] * int(st.session_state[key])
        plan[term] = items
    return plan


def write_plan(plan, ctx):
    """Store the cleaned specific courses back into the widget state."""
    for term, items in plan.items():
        for kind, types in (("mand", REQUIRED_TYPES), ("opt", OTHER_TYPES)):
            key = plan_key(kind, term)
            kept = [i for i in items if i not in GENERIC_ITEMS and ctx.by_id[i].type in types]
            if kept != st.session_state[key]:
                st.session_state[key] = kept


def option_label(ctx, course, term, show_semester):
    parts = [course.name]
    if show_semester and course.semester:
        parts.append(f"{course.semester}º sem.")
    if course.type == "flexible":
        parts.append("flexível")
    if course.emphasis:
        parts.append(course.emphasis)
    if course.extension:
        parts.append("extensionista")
    label = " · ".join(parts)
    if not ctx.offer.is_offered(course, term):
        label += f" {OFF_OFFER_MARK} fora do período habitual"
    return label


def render_plan(terms, plan, ctx, check):
    st.subheader("2. Seu plano no cenário de migração (grade 2026)")
    st.caption(
        "Só aparecem disciplinas ainda não cursadas nem planejadas, com pré-requisitos cumpridos "
        f"em períodos anteriores. {OFF_OFFER_MARK} indica oferta fora do período habitual."
    )
    term_checks = {t.term: t for t in check.terms}
    max_credits = int(ctx.assumptions["max_credits_2026"].value)
    for term in terms:
        with st.container(border=True):
            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"**{term}** · grade 2026")
                for kind, types, label, show_semester in (
                    ("mand", REQUIRED_TYPES, "Obrigatórias, estágio e TCC", True),
                    ("opt", OTHER_TYPES, "Optativas e flexíveis", False),
                ):
                    courses = {c.id: c for c in eligible_courses(ctx, plan, term, types)}
                    key = plan_key(kind, term)
                    st.session_state[key] = [i for i in st.session_state[key] if i in courses]
                    st.multiselect(
                        label,
                        list(courses),
                        format_func=lambda i, cs=courses, t=term, s=show_semester: option_label(ctx, cs[i], t, s),
                        key=key,
                        placeholder="Escolha as disciplinas",
                    )
                generic_cols = st.columns(len(GENERIC_ITEMS))
                for col, generic in zip(generic_cols, GENERIC_ITEMS.values()):
                    col.number_input(
                        f"{generic.name} ({generic.credits} cr)",
                        min_value=0,
                        max_value=10,
                        step=1,
                        key=plan_key(generic.id, term),
                    )
            with right:
                term_check = term_checks.get(term)
                credits = term_check.credits if term_check else 0
                st.metric("Créditos no período", credits, help=f"Mínimo {MIN_CREDITS_2026}, máximo {max_credits}")
                for notice in term_check.notices if term_check else []:
                    st.warning(notice)
                for item in term_check.items if term_check else []:
                    marks = ""
                    if item.off_offer:
                        marks += f" {OFF_OFFER_MARK} fora do período habitual"
                    if item.depends_on_to_define:
                        names = ", ".join(ctx.by_id[d].name for d in item.depends_on_to_define)
                        marks += f" {TO_DEFINE_MARK} depende de {names} (a definir pela coordenação)"
                    st.markdown(f"- {item.name} ({item.credits} cr){marks}")


# ---------- Results ----------


def render_results(ctx, check, removed, overrides):
    st.subheader("3. Resultado")
    if overrides:
        changed = ", ".join(f"`{k}`" for k in overrides)
        st.warning(f"Resultado calculado com premissas alteradas na barra lateral: {changed}.")
    if check.offer_warning:
        st.warning(check.offer_warning)
    if removed:
        st.warning(
            "Removidas automaticamente do plano: "
            + "; ".join(f"{r.name} ({r.term}): {r.reason}" for r in removed)
        )
    for issue in check.prerequisite_issues:
        st.error(issue)
    for item in ctx.evaluation.migrate.to_define:
        st.warning(f"A definir pela coordenação ({item.record}): {item.description}")
    for notice in check.to_define_notices:
        st.warning(notice)
    for notice in [*ctx.evaluation.notices, *ctx.evaluation.migrate.notices]:
        st.info(notice)
    for notice in check.notices:
        st.info(notice)

    left, right = st.columns(2)
    with left:
        st.header("Migrar para o PPC 2026")
        migrate = check.migrate
        st.metric("Conclusão prevista", migrate.conclusion_term or "—")
        if check.exceeds_deadline:
            st.error(f"O plano ultrapassa o prazo máximo de conclusão ({check.deadline_term}).")
        elif check.deadline_term:
            st.caption(f"Prazo máximo de conclusão: {check.deadline_term}.")
        if not migrate.complete:
            st.warning("Ainda falta para concluir:\n\n" + "\n".join(f"- {m}" for m in migrate.missing))
        st.dataframe(
            [
                {
                    "Categoria": r.label + ("" if r.requirement else " (informativo)"),
                    "Exigido": f"{r.required} {r.unit}",
                    "Cursado": f"{r.done} {r.unit}",
                    "Planejado": f"{r.planned} {r.unit}",
                    "Falta": f"{r.missing} {r.unit}",
                }
                for r in migrate.totals
            ],
            hide_index=True,
            width="stretch",
        )
        emphases = ", ".join(ctx.evaluation.migrate.emphases) or "nenhuma ainda (generalista)"
        st.caption(f"Ênfase pelo histórico: {emphases}. A ênfase exige 24 cr em optativas da mesma ênfase.")
        st.markdown("**Obrigatórias, estágio e TCC ainda não planejados**")
        if migrate.unplanned_required:
            st.markdown("\n".join(f"- {c.name} ({c.semester}º sem.)" for c in migrate.unplanned_required))
        else:
            st.success("Todas planejadas ou cursadas.")
    with right:
        st.header("Não migrar (PPC 2013)")
        stay = check.stay
        st.dataframe(
            [
                {"Categoria": t.label, "Exigido": f"{t.required} cr", "Cursado": f"{t.done} cr", "Falta": f"{t.missing} cr"}
                for t in stay.totals
            ],
            hide_index=True,
            width="stretch",
        )
        st.markdown("**Obrigatórias, estágios e TCC pendentes**")
        if stay.pending:
            st.markdown("\n".join(f"- {c.name} ({c.semester}º período)" for c in stay.pending))
        else:
            st.success("Nenhuma obrigatória pendente.")


# ---------- Page ----------


def main():
    st.set_page_config(page_title="Migração do PPC — Estatística UFPB", layout="wide")
    st.title("Migrar ou não migrar para o novo PPC?")
    st.caption("Estatística e Ciência de Dados (UFPB) · Resolução CONSEPE 41/2026 · protótipo")

    data = get_data()
    overrides = render_assumptions(data)
    first_term = next(a.value for a in data.assumptions if a.key == "first_planning_term")

    entry_terms = terms_between(FIRST_ENTRY_TERM, term_from_index(term_index(first_term) - 1))
    ensure_key("entry_term", DEFAULT_ENTRY_TERM)
    entry_term = st.selectbox("Período de ingresso", entry_terms, key="entry_term")

    # Read the state, evaluate the transcript and clean the plan before drawing widgets.
    groups = history_course_groups(data)
    h_terms = history_terms(entry_term, first_term)
    history_codes = sanitize_history(h_terms, groups)
    ctx = build_context(history_codes, overrides=overrides, data=data)

    remaining = term_index(deadline_term(entry_term)) - term_index(first_term) + 1
    ensure_key("plan_terms", min(MAX_PLAN_TERMS, max(4, remaining)))
    p_terms = [term_from_index(term_index(first_term) + i) for i in range(int(st.session_state["plan_terms"]))]
    plan, removed = cascade_remove(ctx, read_plan(p_terms))
    write_plan(plan, ctx)
    check = check_with_context(ctx, entry_term, plan)

    render_history(h_terms, groups, ctx, first_term)
    st.number_input("Quantidade de períodos no plano", min_value=1, max_value=MAX_PLAN_TERMS, key="plan_terms")
    render_plan(p_terms, plan, ctx, check)
    render_results(ctx, check, removed, overrides)

    st.divider()
    st.warning(FOOTER)


main()
