"""Streamlit prototype: SIGAA-like tables for the transcript and the student's plan.

Run with: streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.data_loader import load_data  # noqa: E402
from app.export import build_export  # noqa: E402
from app.plan_check import (  # noqa: E402
    GENERIC_ITEMS,
    OTHER_TYPES,
    REQUIRED_TYPES,
    build_context,
    cascade_remove,
    check_with_context,
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
NEW_CODE = "NEW"
OFF_OFFER_MARK = "⚠️"
TO_DEFINE_MARK = "ⓘ"
FOOTER = "Simulação baseada nas regras disponíveis; não substitui a orientação da coordenação."

# Relative widths: Código, Disciplina, Tipo, Créditos, extra column, remove button.
ROW_WIDTHS = [1.1, 4, 1.3, 0.8, 3.2, 1.2]


@st.cache_resource
def get_data():
    return load_data()


# ---------- Session state ----------


def hist_key(term):
    return f"hist_{term}"


def plan_key(term):
    return f"plan_{term}"


def ensure_key(key, default):
    if key not in st.session_state:
        st.session_state[key] = default


def add_item(list_key, select_key):
    """Selector callback: append the chosen item as a new row and reset the selector."""
    value = st.session_state.get(select_key)
    if value is not None:
        st.session_state[list_key] = [*st.session_state.get(list_key, []), value]
    st.session_state[select_key] = None


def remove_item(list_key, index):
    items = list(st.session_state.get(list_key, []))
    if 0 <= index < len(items):
        items.pop(index)
    st.session_state[list_key] = items


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


# ---------- Table layout ----------


def render_header(extra_label):
    cols = st.columns(ROW_WIDTHS)
    for col, label in zip(cols, ("Código", "Disciplina", "Tipo", "Créditos", extra_label, "")):
        col.markdown(f"**{label}**")


def render_row(code, name, type_, credits, extra, remove_key, list_key, index):
    cols = st.columns(ROW_WIDTHS, vertical_alignment="center")
    cols[0].markdown(code)
    cols[1].markdown(name)
    cols[2].markdown(TYPE_LABELS.get(type_, type_))
    cols[3].markdown(str(credits))
    cols[4].markdown(extra or "")
    cols[5].button("✕ Remover", key=remove_key, on_click=remove_item, args=(list_key, index), width="stretch")


def render_add_row(term, prefix, list_key, required_options, other_options, labels):
    cols = st.columns(2)
    for col, kind, options, placeholder in (
        (cols[0], "mand", required_options, "+ Obrigatória…"),
        (cols[1], "opt", other_options, "+ Optativa/flexível…"),
    ):
        select_key = f"add_{prefix}_{kind}_{term}"
        col.selectbox(
            placeholder,
            options,
            index=None,
            format_func=lambda v: labels[v],
            key=select_key,
            placeholder=placeholder,
            on_change=add_item,
            args=(list_key, select_key),
            label_visibility="collapsed",
        )


def display_code(code):
    return "novo" if code == NEW_CODE else code


# ---------- Transcript (2013) ----------


def history_courses(data):
    required = sorted((c for c in data.curriculum_2013 if c.type in REQUIRED_TYPES), key=lambda c: (c.semester, c.name))
    others = sorted((c for c in data.curriculum_2013 if c.type not in REQUIRED_TYPES), key=lambda c: (c.type, c.name))
    return required, others


def sanitize_history(terms, valid_codes):
    """Keep only valid codes and drop repeated courses (first term wins)."""
    seen = set()
    for term in terms:
        key = hist_key(term)
        ensure_key(key, [])
        kept = [c for c in st.session_state[key] if c in valid_codes and c not in seen]
        seen.update(kept)
        if kept != st.session_state[key]:
            st.session_state[key] = kept
    return sorted(seen)


def fill_until(required, first_term):
    """Place each 2013 required course up to semester N at entry + (semester - 1)."""
    entry = st.session_state["entry_term"]
    until = st.session_state["fill_until"]
    terms = history_terms(entry, first_term)
    left_out = []
    for course in required:
        if course.semester > until:
            continue
        for term in terms:
            key = hist_key(term)
            st.session_state[key] = [c for c in st.session_state.get(key, []) if c != course.code]
        target = term_from_index(term_index(entry) + course.semester - 1)
        if target in terms:
            st.session_state[hist_key(target)] = st.session_state[hist_key(target)] + [course.code]
        else:
            left_out.append(f"{course.name} ({course.semester}º período → {target})")
    st.session_state["fill_notice"] = left_out


def clear_history(first_term):
    for term in history_terms(st.session_state["entry_term"], first_term):
        st.session_state[hist_key(term)] = []
    st.session_state["fill_notice"] = []


def render_history(terms, data, ctx, first_term):
    st.subheader("1. Histórico na grade 2013")
    st.info("Inclua também as disciplinas que está cursando agora, supondo aprovação.")
    if not terms:
        st.caption("Não há períodos de histórico para este ingresso.")
        return

    required, others = history_courses(data)
    cols = st.columns([2, 1, 1], vertical_alignment="bottom")
    cols[0].selectbox(
        "Atalho: marcar obrigatórias até o período",
        sorted({c.semester for c in required}),
        format_func=lambda s: f"{s}º período",
        key="fill_until",
    )
    cols[1].button("Marcar", key="fill_button", on_click=fill_until, args=(required, first_term), width="stretch")
    cols[2].button("Limpar histórico", key="clear_button", on_click=clear_history, args=(first_term,), width="stretch")
    if st.session_state.get("fill_notice"):
        st.warning(
            "Não foram marcadas porque cairiam depois do último período do histórico: "
            + "; ".join(st.session_state["fill_notice"])
        )

    by_code = {c.code: c for c in data.curriculum_2013}
    outcomes = history_outcomes(ctx)
    chosen = {code for term in terms for code in st.session_state[hist_key(term)]}
    labels = {c.code: f"{c.semester}º sem. · {c.name} ({c.code})" for c in required}
    labels.update({c.code: f"{c.name} ({c.code}) · {TYPE_LABELS[c.type].lower()}" for c in others})
    required_options = [c.code for c in required if c.code not in chosen]
    other_options = [c.code for c in others if c.code not in chosen]

    for term in terms:
        list_key = hist_key(term)
        with st.container(border=True):
            st.markdown(f"#### {term} · grade 2013")
            render_header("Na grade 2026")
            for i, code in enumerate(st.session_state[list_key]):
                course = by_code[code]
                render_row(
                    course.code, course.name, course.type, course.credits,
                    outcomes.get(code, "—"), f"rm_hist_{term}_{i}", list_key, i,
                )
            render_add_row(term, "hist", list_key, required_options, other_options, labels)
            total = sum(by_code[c].credits for c in st.session_state[list_key])
            st.markdown(f"**Total: {total} créditos**")


# ---------- Plan (2026) ----------


def plan_terms(first_term):
    ensure_key("plan_term_count", 1)
    return [term_from_index(term_index(first_term) + i) for i in range(st.session_state["plan_term_count"])]


def add_term():
    st.session_state["plan_term_count"] += 1


def remove_last_term(term):
    st.session_state["plan_term_count"] = max(1, st.session_state["plan_term_count"] - 1)
    st.session_state.pop(plan_key(term), None)


def read_plan(terms, ctx):
    plan = {}
    for term in terms:
        ensure_key(plan_key(term), [])
        plan[term] = [i for i in st.session_state[plan_key(term)] if i in GENERIC_ITEMS or i in ctx.by_id]
    return plan


def plan_option_label(ctx, course, term):
    parts = [f"{course.semester}º sem." if course.semester else None, course.name]
    if course.type == "flexible":
        parts.append("flexível")
    if course.emphasis:
        parts.append(course.emphasis)
    if course.extension:
        parts.append("extensionista")
    label = " · ".join(p for p in parts if p)
    if not ctx.offer.is_offered(course, term):
        label += f" {OFF_OFFER_MARK} fora do período de oferta"
    return label


def item_notices(ctx, item):
    notices = []
    if item.off_offer:
        notices.append(f"{OFF_OFFER_MARK} fora do período de oferta")
    for dep in item.depends_on_to_define:
        notices.append(f"{TO_DEFINE_MARK} depende de {ctx.by_id[dep].name} (a definir pela coordenação)")
    if item.missing_prerequisites:
        notices.append("pré-requisito não cumprido")
    return " · ".join(notices)


def render_plan(terms, plan, ctx, check):
    st.subheader("2. Seu plano no cenário de migração (grade 2026)")
    st.caption(
        "Os seletores só mostram disciplinas ainda não cursadas nem planejadas, com pré-requisitos "
        f"cumpridos em períodos anteriores. {OFF_OFFER_MARK} indica oferta fora do período habitual."
    )
    term_checks = {t.term: t for t in check.terms}
    generic_labels = {g.id: f"{g.name} ({g.credits} cr)" for g in GENERIC_ITEMS.values()}

    for position, term in enumerate(terms):
        list_key = plan_key(term)
        items = plan[term]
        term_check = term_checks.get(term)
        with st.container(border=True):
            st.markdown(f"#### {term} · plano na grade 2026")
            render_header("Avisos")
            for i, item_id in enumerate(items):
                generic = GENERIC_ITEMS.get(item_id)
                source = generic or ctx.by_id[item_id]
                code = "—" if generic else display_code(source.code)
                notices = item_notices(ctx, term_check.items[i]) if term_check else ""
                render_row(code, source.name, source.type, source.credits, notices, f"rm_plan_{term}_{i}", list_key, i)

            required = [c for c in eligible_courses(ctx, plan, term, REQUIRED_TYPES) if c.id not in items]
            others = [c for c in eligible_courses(ctx, plan, term, OTHER_TYPES) if c.id not in items]
            labels = {**generic_labels, **{c.id: plan_option_label(ctx, c, term) for c in [*required, *others]}}
            render_add_row(
                term, "plan", list_key, [c.id for c in required], [*GENERIC_ITEMS, *(c.id for c in others)], labels
            )

            total = term_check.credits if term_check else 0
            st.markdown(f"**Total: {total} créditos**")
            for notice in term_check.notices if term_check else []:
                st.warning(notice)
            is_last = position == len(terms) - 1
            if is_last and len(terms) > 1 and not items:
                st.button("Remover período", key="remove_term", on_click=remove_last_term, args=(term,))

    st.button("+ Adicionar período", key="add_term", on_click=add_term)


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
        name = ctx.by_id[item.course_id].name if item.course_id in ctx.by_id else item.course_id
        st.warning(f"A definir pela coordenação ({name}): {item.description}")
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

    # Read the state, evaluate the transcript and clean the plan before drawing the tables.
    h_terms = history_terms(entry_term, first_term)
    history_codes = sanitize_history(h_terms, {c.code for c in data.curriculum_2013})
    ctx = build_context(history_codes, overrides=overrides, data=data)

    p_terms = plan_terms(first_term)
    plan, removed = cascade_remove(ctx, read_plan(p_terms, ctx))
    for term, items in plan.items():
        st.session_state[plan_key(term)] = items
    check = check_with_context(ctx, entry_term, plan)

    render_history(h_terms, data, ctx, first_term)
    render_plan(p_terms, plan, ctx, check)
    render_results(ctx, check, removed, overrides)

    st.download_button(
        "Exportar para conversar com uma IA",
        data=build_export(ctx, check, plan, history_outcomes(ctx)),
        file_name="migracao_ppc_resumo.md",
        mime="text/markdown",
        key="export",
    )
    st.caption(
        "Baixa um resumo em Markdown (sem nome, matrícula ou período de ingresso) para colar numa "
        "conversa com uma IA. Revise o arquivo antes de compartilhar."
    )

    st.divider()
    st.warning(FOOTER)


main()
