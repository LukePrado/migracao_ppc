"""Streamlit app: convert a 2013 history to the 2026 curriculum.

Run with: streamlit run app/streamlit_app.py

The page is split in four steps (history, summary, courses, AI). Streamlit
drops the state of a widget that is not rendered, so every choice that must
survive a change of step is also saved in st.session_state["saved"].
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
    FLEXIBLE_SIGAA_TYPE,
    UNRECOGNIZED,
    HistoryEntry,
    convert,
)
from app.data_loader import load_data  # noqa: E402
from app.export import FILE_NAME, build_export  # noqa: E402
from app.history_pdf import parse_history  # noqa: E402
from app.summary import (  # noqa: E402
    build_summary,
    category_line,
    courses_text,
    format_hours,
    lost_line,
    split_pending,
    used_line,
)

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

# Short labels for the step buttons (one line at 360 px) and titles for the progress bar.
STEPS = ("Histórico", "Resumo", "Disciplinas", "IA")
STEP_TITLES = ("Seu histórico", "Resumo", "Disciplinas", "Conversar com IA")
LAST_PERIOD = 8
CARD_WIDTH = 220
PAGE_STYLE = """<style>
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] h1 { font-size: 1.75rem; }
  .st-key-step_nav { gap: 0.25rem; flex-wrap: nowrap; }
  .st-key-step_nav button { padding: 0.25rem 0.5rem; min-height: 2.25rem; }
  .st-key-step_nav button p { font-size: 0.875rem; }
  div:has(> [class*="st-key-card_"]) { flex: 1 1 100% !important; width: 100% !important; }
}
</style>"""
AUTHORIZATION_TEXT = """O PDF do histórico contém dados pessoais, como nome, matrícula e CPF. Para fazer a simulação:

- o arquivo é enviado pela internet, de forma criptografada, para os servidores em nuvem onde este app
  está hospedado, que podem estar fora do Brasil, e é processado apenas na memória;
- o app lê somente as disciplinas e suas cargas horárias; nome, matrícula, CPF e outros dados pessoais
  são ignorados;
- nada é gravado: o arquivo é descartado após a leitura, e as disciplinas ficam disponíveis só enquanto
  esta página estiver aberta;
- nenhum dado pessoal é enviado a serviços de inteligência artificial. Se você pedir o parecer da IA na
  etapa 4, apenas a lista de disciplinas é enviada.

Se preferir, você pode preencher suas disciplinas manualmente, sem enviar o arquivo. Você autoriza o envio?"""

SOURCE_MANUAL = "manual"
SOURCE_PDF = "pdf"
SOURCE_IN_PROGRESS = "pdf_in_progress"
MANUAL_CODE_PREFIX = "MANUAL-"
MANUAL_FLEXIBLE_NAME = "Flexível de outro curso"
SIMULATION_PREFIXES = ("assumption_", "destination_")
EXPORT_TEXT = (
    "Quer explorar mais? Baixe o arquivo abaixo e anexe-o numa conversa com a IA de sua preferência. "
    "Ele não contém seus dados pessoais."
)
AI_LINKS = {"Claude": "https://claude.ai/new", "ChatGPT": "https://chatgpt.com", "Gemini": "https://gemini.google.com"}
# Session keys filled from the uploaded PDF (only course lines and counts; never the file).
PDF_KEYS = ("pdf_loaded", "pdf_file_id", "pdf_error_file_id", "pdf_in_progress", "pdf_report",
            "in_progress_choice")


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


def add_manual_flexible(state, name, hours):
    """A flexible course from another program: a CF line, so it goes to Special Topics."""
    used = {e["code"] for e in history(state)}
    number = 1
    while f"{MANUAL_CODE_PREFIX}{number}" in used:
        number += 1
    entry = entry_dict(f"{MANUAL_CODE_PREFIX}{number}", name.strip() or MANUAL_FLEXIBLE_NAME, int(hours),
                       FLEXIBLE_SIGAA_TYPE)
    state["history"] = [*history(state), entry]


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


def default_current_period(state, data):
    """The period after the most advanced 2013 period with a passed mandatory course (at most 8).

    The history already holds the in-progress courses when that option is on.
    """
    semesters = [
        course.semester for e in history(state)
        if (course := course_2013(data, e["code"])) is not None and course.type in REQUIRED_TYPES
    ]
    return min(max(semesters, default=0) + 1, LAST_PERIOD)


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
    if type_2013 == "flexible" or sigaa_type == FLEXIBLE_SIGAA_TYPE:
        return FLEXIBLES_GROUP
    return UNRECOGNIZED_GROUP


def options_by_group(data, chosen):
    options = {}
    for course in data.curriculum_2013:
        if course.code not in chosen:
            options.setdefault(group_of(course.type, course.semester), []).append(course)
    return options


def display_code(code):
    return "—" if code.startswith(MANUAL_CODE_PREFIX) else code


# ---------- Saved choices and simulated rules ----------


def saved(state):
    return state.setdefault("saved", {})


def restore(key, default):
    """Give a widget its saved value (or the default) when it is created again."""
    if key not in st.session_state:
        st.session_state[key] = saved(st.session_state).get(key, default)


def save(key):
    saved(st.session_state)[key] = st.session_state[key]


def as_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def simulated_rules(state, data):
    """Return (assumption overrides, destination overrides) from the saved simulation choices."""
    values = saved(state)
    overrides = {
        a.key: values[f"assumption_{a.key}"]
        for a in data.assumptions
        if a.status == "assumed" and f"assumption_{a.key}" in values
        and as_text(values[f"assumption_{a.key}"]) != a.value
    }
    destination_overrides = {
        row.code: values[f"destination_{row.code}"]
        for row in data.old_course_destinations
        if row.status == "assumed" and f"destination_{row.code}" in values
        and values[f"destination_{row.code}"] != row.destination
    }
    return overrides, destination_overrides


def default_assumption_value(assumption):
    if assumption.value in ("true", "false"):
        return assumption.value == "true"
    if assumption.value.isdigit():
        return int(assumption.value)
    return assumption.value


def assumption_widget(assumption):
    key = f"assumption_{assumption.key}"
    restore(key, default_assumption_value(assumption))
    common = {"key": key, "on_change": save, "args": (key,)}
    if assumption.value in ("true", "false"):
        return st.toggle(assumption.description, **common)
    if assumption.key == "consultoria_emphasis":
        return st.selectbox(assumption.description, list(EMPHASIS_OPTIONS), format_func=EMPHASIS_OPTIONS.get,
                            **common)
    if assumption.value.isdigit():
        return st.number_input(assumption.description, min_value=0, step=15, **common)
    return st.text_input(assumption.description, **common)


def on_restore():
    state = st.session_state
    state["saved"] = {k: v for k, v in saved(state).items() if not k.startswith(SIMULATION_PREFIXES)}
    for key in [k for k in state if k.startswith(SIMULATION_PREFIXES)]:
        del state[key]


def render_simulation(data):
    with st.expander("Simular regras ainda não confirmadas"):
        st.caption(
            "Estas regras são **supostas**: ainda não foram confirmadas pela coordenação. "
            "Altere-as para ver como o resultado muda."
        )
        st.button("Restaurar valores do arquivo", key="restore", on_click=on_restore)
        for assumption in data.assumptions:
            status = STATUS_LABELS.get(assumption.status, assumption.status)
            if assumption.status == "assumed":
                assumption_widget(assumption)
            else:
                st.caption(f"{assumption.description}: **{assumption.value}** ({status})")

        st.markdown("**Disciplinas extintas: Tópicos ou optativa**")
        st.caption("Destino na grade 2026 das disciplinas de 2013 sem correspondente.")
        names = {c.code: c.name for c in data.curriculum_2013}
        options = list(DESTINATION_LABELS)
        for row in data.old_course_destinations:
            name = names.get(row.code, row.code)
            if row.status != "assumed":
                label = DESTINATION_LABELS.get(row.destination, "Não aproveitada automaticamente")
                st.caption(f"{name}: **{label}** (confirmada)")
                continue
            key = f"destination_{row.code}"
            restore(key, row.destination)
            st.selectbox(f"{name} (suposta)", options, format_func=DESTINATION_LABELS.get, key=key,
                         on_change=save, args=(key,))


def warn_if_simulated(overrides, destination_overrides):
    if overrides or destination_overrides:
        st.warning("Resultado calculado com regras alteradas em \"Simular regras ainda não confirmadas\" (etapa 2).")


# ---------- Navigation ----------


def go_to(step):
    st.session_state["step"] = step
    st.session_state["scroll_count"] = st.session_state.get("scroll_count", 0) + 1
    st.session_state["scroll_pending"] = True


def scroll_to_top():
    """Once after a change of step: Streamlit keeps the scroll position between reruns."""
    if st.session_state.pop("scroll_pending", False):
        counter = st.session_state["scroll_count"]  # a new script each time, so it runs again
        st.html(
            f"<script>/* {counter} */ for (const s of ['[data-testid=\"stMain\"]', "
            "'[data-testid=\"stAppViewContainer\"]']) { document.querySelector(s)?.scrollTo(0, 0); } "
            "window.scrollTo(0, 0);</script>",
            unsafe_allow_javascript=True,
        )


def render_navigation(unlocked):
    step = st.session_state["step"]
    st.progress(step / len(STEPS), text=f"Etapa {step} de {len(STEPS)}: {STEP_TITLES[step - 1]}")
    with st.container(horizontal=True, gap="small", key="step_nav"):
        for number, name in enumerate(STEPS, start=1):
            st.button(
                f"{number} {name}", key=f"nav_{number}", on_click=go_to, args=(number,),
                type="primary" if number == step else "secondary",
                disabled=number > 1 and not unlocked,
            )
    if not unlocked:
        st.caption("Inclua ao menos uma disciplina para liberar as próximas etapas.")


def render_step_buttons(unlocked):
    step = st.session_state["step"]
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button("← Voltar", key="back", on_click=go_to, args=(step - 1,), disabled=step == 1)
        st.button("Próximo →", key="next", on_click=go_to, args=(step + 1,), type="primary",
                  disabled=step == len(STEPS) or not unlocked)


# ---------- 1. History input ----------


def on_add(select_key):
    course = st.session_state.get(select_key)
    if course is not None:
        add_course(st.session_state, course)
    st.session_state[select_key] = None


def on_add_flexible():
    add_manual_flexible(st.session_state, st.session_state["flex_name"], st.session_state["flex_hours"])
    st.session_state["flex_name"] = MANUAL_FLEXIBLE_NAME
    st.session_state["flex_hours"] = 60


def on_fill():
    fill_until(st.session_state, get_data(), st.session_state["fill_until"])


def on_clear():
    st.session_state["history"] = []


def remove_pdf(state):
    """Forget the uploaded file and empty the whole list (the upload permission is kept)."""
    for key in PDF_KEYS:
        state.pop(key, None)
    state["history"] = []
    state["uploader_id"] = state.get("uploader_id", 0) + 1  # a new, empty uploader


def set_in_progress(state, include):
    state["in_progress_choice"] = include
    sync_in_progress(state, include)


def in_progress_line(state):
    """'Disciplinas em curso: incluídas / não incluídas', or None when the PDF has none."""
    if not state.get("pdf_in_progress"):
        return None
    return "Disciplinas em curso: " + ("incluídas" if state.get("in_progress_choice") else "não incluídas")


def render_in_progress_choice(key_prefix):
    state = st.session_state
    line = in_progress_line(state)
    if line is None:
        return
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f"**{line}**")
        st.button("Alterar", key=f"{key_prefix}_in_progress_change", type="tertiary", on_click=set_in_progress,
                  args=(state, not state.get("in_progress_choice")))


def render_in_progress_question():
    state = st.session_state
    courses = state["pdf_in_progress"]
    names = "; ".join(e["name"] or e["code"] for e in courses)
    noun = "disciplina" if len(courses) == 1 else "disciplinas"
    with st.container(border=True):
        st.markdown(
            f"Encontramos {len(courses)} {noun} em curso: {names}. "
            "Deseja considerá-las como aprovadas na simulação?"
        )
        with st.container(horizontal=True, gap="small"):
            st.button("Sim, incluir", key="in_progress_yes", type="primary", on_click=set_in_progress,
                      args=(state, True))
            st.button("Não", key="in_progress_no", on_click=set_in_progress, args=(state, False))


@st.dialog("Antes de enviar seu histórico", width="medium")
def authorization_dialog():
    st.markdown(AUTHORIZATION_TEXT)
    with st.container(horizontal=True, gap="small"):
        st.button("Autorizo e quero enviar", key="pdf_authorize", type="primary", on_click=authorize)
        declined = st.button("Prefiro preencher manualmente", key="pdf_decline")
    if declined:
        st.rerun()
    if st.session_state["pdf_authorized"]:
        st.rerun()  # close the dialog and show the uploader


def authorize():
    st.session_state["pdf_authorized"] = True


def read_upload(uploaded):
    state = st.session_state
    if uploaded.file_id == state.get("pdf_error_file_id"):
        return
    try:
        parsed = parse_history(uploaded.getvalue(), include_in_progress=True)
    except ValueError as error:
        state["pdf_error_file_id"] = uploaded.file_id
        st.error(str(error))
        return
    apply_parsed(state, parsed, uploaded.file_id, include_in_progress=False)
    state["pdf_loaded"] = True  # not the file name: SIGAA's default name has the student id
    state["in_progress_choice"] = None if parsed.in_progress else False
    st.rerun()  # hide the uploader


def render_pdf_input():
    state = st.session_state
    if state.get("pdf_loaded"):
        with st.container(border=True):
            st.markdown("Arquivo carregado: histórico do SIGAA (PDF)")
            st.button("Remover arquivo e limpar lista", key="pdf_remove", on_click=remove_pdf, args=(state,))
        report = state.get("pdf_report")
        if report:
            st.success(
                f"Lista preenchida pelo PDF: {report['approved_count']} disciplinas aprovadas "
                f"({format_hours(report['approved_hours'])}) e {report['in_progress_count']} em curso. "
                "Confira e corrija a lista se precisar."
            )
            for warning in report["warnings"]:
                st.warning(warning)
        if state.get("pdf_in_progress") and state.get("in_progress_choice") is None:
            render_in_progress_question()
        else:
            render_in_progress_choice("history")
        return

    if state.get("pdf_authorized"):
        uploaded = st.file_uploader("Envie o PDF do histórico do SIGAA", type="pdf",
                                    key=f"pdf_{state.get('uploader_id', 0)}")
        if uploaded is not None:
            read_upload(uploaded)
    elif st.button("Enviar o PDF do histórico do SIGAA", key="pdf_start", type="primary", icon=":material/upload:"):
        authorization_dialog()
    st.caption("Se preferir, preencha a lista abaixo manualmente, sem enviar o arquivo.")


def history_items(data):
    """Rows of the history by group: (code, name, type label, hours)."""
    by_group = {}
    for entry in history(st.session_state):
        course = course_2013(data, entry["code"])
        if course is not None:
            group = group_of(course.type, course.semester)
            row = (entry["code"], course.name, TYPE_LABELS[course.type], course.hours)
        else:
            group = group_of("", None, entry["sigaa_type"])
            row = (entry["code"], entry["name"], SIGAA_TYPE_LABELS.get(entry["sigaa_type"], "—"), entry["hours"] or 0)
        by_group.setdefault(group, []).append(row)
    return by_group


def render_item(code, name, type_label, hours):
    with st.container(border=True, horizontal=True, vertical_alignment="center", gap="small"):
        with st.container(gap=None):
            st.markdown(f"**{name}**")
            st.caption(f"{display_code(code)} · {type_label} · {hours} h")
        st.button("✕", key=f"rm_{code}", help="Remover", type="tertiary", on_click=remove_entry,
                  args=(st.session_state, code))


def render_manual_flexible():
    st.session_state.setdefault("flex_name", MANUAL_FLEXIBLE_NAME)
    st.session_state.setdefault("flex_hours", 60)
    with st.container(border=True):
        st.caption("Flexível de outro curso (vai para Tópicos Especiais)")
        st.text_input("Nome da disciplina", key="flex_name")
        st.number_input("Carga horária (h)", min_value=15, step=15, key="flex_hours")
        st.button("+ Incluir flexível", key="flex_add", on_click=on_add_flexible)


def render_group_inputs(group, group_options):
    if group_options:
        select_key = f"add_{group}"
        st.selectbox(
            "Incluir", group_options, index=None, key=select_key,
            format_func=lambda c: f"{c.name} ({c.code})", placeholder="+ Incluir disciplina…",
            on_change=on_add, args=(select_key,), label_visibility="collapsed",
        )
    if group == FLEXIBLES_GROUP:
        render_manual_flexible()


def render_history(data):
    st.subheader("Seu histórico na grade 2013")
    render_pdf_input()

    semesters = sorted({c.semester for c in data.curriculum_2013 if c.type in REQUIRED_TYPES})
    st.selectbox("Atalho: marcar obrigatórias até o período", semesters,
                 format_func=period_group, key="fill_until")
    with st.container(horizontal=True, gap="small"):
        st.button("Marcar", key="fill_button", on_click=on_fill)
        st.button("Limpar lista", key="clear_button", on_click=on_clear)

    by_group = history_items(data)
    options = options_by_group(data, {e["code"] for e in history(st.session_state)})
    for group in group_names(data):
        rows, group_options = by_group.get(group, []), options.get(group, [])
        if not rows:
            # Empty groups stay collapsed so the page is short on a phone.
            if group != UNRECOGNIZED_GROUP:
                with st.expander(f"{group} · 0 h"):
                    render_group_inputs(group, group_options)
            continue
        st.markdown(f"##### {group} · {format_hours(sum(r[3] for r in rows))}")
        for row in sorted(rows, key=lambda r: r[1]):
            render_item(*row)
        render_group_inputs(group, group_options)


# ---------- 2. Summary ----------


def missing_caption(summary):
    """The 'Faltam' sentence without repeating the hours of the card."""
    if not summary.missing_hours:
        return summary.missing_text
    return f"{summary.missing_credits} cr: {courses_text(summary.missing_hours)}."


def used_caption(summary):
    text = (f"{format_hours(summary.used_hours)} de {format_hours(summary.approved_hours)} aprovadas "
            "na grade 2013.")
    return text + (f" {summary.used_note}" if summary.used_note else "")


def lost_caption(summary):
    if not summary.lost_hours:
        return "Nenhuma hora perdida."
    if summary.recoverable_hours:
        return (f"Até {format_hours(summary.recoverable_hours)} podem ser recuperadas mediante pedido "
                "(veja abaixo). Lista na etapa 3.")
    return "Lista na etapa 3."


def render_card(key, label, value, caption):
    with st.container(border=True, width=CARD_WIDTH, key=f"card_{key}"):
        st.metric(label, value)
        st.caption(caption)


def render_summary(summary, data, overrides, destination_overrides):
    st.subheader("Resumo da migração para o novo PPC")
    render_in_progress_choice("summary")
    warn_if_simulated(overrides, destination_overrides)
    for warning in summary.warnings:
        if warning.startswith("Atenção:"):
            st.error(warning)
        else:
            st.warning(warning)

    with st.container(horizontal=True, gap="small"):
        render_card("missing", "Faltam", format_hours(summary.missing_hours), missing_caption(summary))
        render_card("used", "Aproveitamento", f"{summary.used_percent}%", used_caption(summary))
        render_card("lost", "Não aproveitado", format_hours(summary.lost_hours), lost_caption(summary))

    st.markdown("**Por categoria do novo PPC**")
    st.markdown("\n".join(f"- {category_line(c)}" for c in summary.categories))
    st.caption("A extensão não soma às demais: ela é cumprida dentro das outras categorias.")
    with st.expander("Ver tabela completa"):
        st.dataframe(
            [{"Categoria": c.name, "Exigido": format_hours(c.required_hours),
              "Aproveitado": format_hours(c.used_hours), "Falta": format_hours(c.missing_hours)}
             for c in summary.categories],
            hide_index=True, width="stretch",
        )

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
    render_simulation(data)


# ---------- 3. Courses ----------


def conversion_rows(result):
    by_group = {}
    for c in result.courses:
        note = " ".join(part for part in (c.reason, c.note) if part)
        by_group.setdefault(group_of(c.type_2013, c.semester), []).append({
            "Código": display_code(c.code),
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


def pending_lines(courses):
    return "\n".join(f"- {p.name} ({p.semester}º período)" for p in courses)


def render_courses(result, summary, data, overrides, destination_overrides):
    st.subheader("Disciplinas")
    render_in_progress_choice("courses")
    warn_if_simulated(overrides, destination_overrides)

    st.markdown("#### Aproveitadas")
    used = [c for c in result.courses if c.used_hours]
    if used:
        st.markdown("\n".join(f"- {used_line(c, data)}" for c in used))
    else:
        st.caption("Nenhuma disciplina aproveitada.")

    st.markdown("#### Perdidas")
    st.markdown(f"**{summary.lost_text}**")
    if summary.recoverable_lines:
        st.markdown("\n".join(f"- {line}" for line in summary.recoverable_lines))
    if summary.lost_items:
        st.markdown("\n".join(f"- {lost_line(i)}" for i in summary.lost_items))
    unrecognized = [c for c in result.courses if c.category == UNRECOGNIZED]
    if unrecognized:
        st.markdown("**Não reconhecidas (fora das contas, consulte a coordenação)**")
        st.markdown("\n".join(f"- {c.name} ({c.hours} h)" for c in unrecognized))

    st.markdown("#### A cursar")
    restore("current_period", default_current_period(st.session_state, data))
    st.number_input("Em que período você está?", min_value=1, max_value=LAST_PERIOD, step=1,
                    key="current_period", on_change=save, args=("current_period",))
    if not result.pending:
        st.success("Nenhuma obrigatória do novo PPC a cursar: todas aproveitadas.")
    else:
        behind, upcoming = split_pending(result.pending, st.session_state["current_period"])
        st.markdown("**Ficaram para trás**")
        st.markdown(pending_lines(behind) if behind else "Nenhuma.")
        st.markdown("**Próximos períodos**")
        st.markdown(pending_lines(upcoming) if upcoming else "Nenhuma.")

    with st.expander("Ver tabela completa"):
        st.caption("Linhas destacadas têm horas não aproveitadas.")
        by_group = conversion_rows(result)
        for group in group_names(data):
            rows = by_group.get(group)
            if rows:
                st.markdown(f"**{group}**")
                st.dataframe(pd.DataFrame(rows).style.apply(highlight_losses, axis=1), hide_index=True,
                             width="stretch")


# ---------- 4. AI ----------


def export_text(state, result, summary, data):
    """The Markdown file of step 4, with the period and the in-progress choice of the student."""
    period = saved(state).get("current_period", default_current_period(state, data))
    in_progress = bool(state.get("in_progress_choice")) if state.get("pdf_in_progress") else None
    return build_export(result, summary, data, current_period=period, in_progress_included=in_progress)


def render_ai(result, summary, data):
    st.subheader("Conversar com IA")
    st.markdown(EXPORT_TEXT)
    st.download_button(
        "Baixar arquivo para a IA", export_text(st.session_state, result, summary, data), file_name=FILE_NAME,
        mime="text/markdown", key="export_download", type="primary", icon=":material/download:",
    )
    with st.container(horizontal=True, gap="small"):
        for name, url in AI_LINKS.items():
            st.link_button(name, url)
    st.caption("Anexe o arquivo baixado e pergunte o que quiser.")

    st.markdown("#### Parecer da IA")
    st.info("Em breve.")


# ---------- Page ----------


def main():
    st.set_page_config(page_title="Migração do PPC — Estatística UFPB")
    st.html(PAGE_STYLE)
    st.title("Migrar para o novo PPC: o que você aproveita?")
    st.caption("Estatística e Ciência de Dados (UFPB) · Resolução CONSEPE 41/2026")

    data = get_data()
    state = st.session_state
    state.setdefault("history", [])
    state.setdefault("step", 1)
    state.setdefault("pdf_authorized", False)
    unlocked = bool(state["history"])
    if not unlocked:
        state["step"] = 1
    render_navigation(unlocked)

    step = state["step"]
    if step == 1:
        render_history(data)
    else:
        overrides, destination_overrides = simulated_rules(state, data)
        result = convert(history_entries(state), overrides, destination_overrides, data=data)
        summary = build_summary(result)
        if step == 2:
            render_summary(summary, data, overrides, destination_overrides)
        elif step == 3:
            render_courses(result, summary, data, overrides, destination_overrides)
        else:
            render_ai(result, summary, data)

    st.divider()
    render_step_buttons(bool(state["history"]))
    st.warning(FOOTER)
    scroll_to_top()


if __name__ == "__main__":
    main()
