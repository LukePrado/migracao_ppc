import re
from dataclasses import replace

import pytest

from app.data_loader import load_data
from app.export import build_export
from app.plan_check import (
    GENERIC_ITEMS,
    build_context,
    cascade_remove,
    check_with_context,
    history_outcomes,
)

DATA = load_data()

FIRST_TERM = {"1103118", "1103177", "1108189", "1108190", "1108191"}
ALL_2013_REQUIRED = {
    c.code for c in DATA.curriculum_2013 if c.type in ("mandatory", "internship", "complementary")
}
SECTIONS = (
    "## 1. Contexto",
    "## 2. Premissas usadas",
    "## 3. Histórico (grade 2013) e o que vira na grade 2026",
    "## 4. Situação nos dois cenários",
    "### Migrar para o PPC 2026",
    "### Não migrar (PPC 2013)",
    "## 5. Plano atual do aluno",
    "## 6. Disciplinas da grade 2026 ainda pendentes",
    "### Optativas e flexíveis disponíveis",
    "## 7. Instruções para a IA",
)
# Internal ids that are also ordinary Portuguese words.
PORTUGUESE_WORDS = {"na"}


def export(codes, plan, entry_term="2023.1", overrides=None, data=DATA):
    ctx = build_context(codes, overrides=overrides, data=data)
    plan, _ = cascade_remove(ctx, plan)
    check = check_with_context(ctx, entry_term, plan)
    return build_export(ctx, check, plan, history_outcomes(ctx))


def scenarios():
    tbd_data = replace(
        DATA,
        equivalences=tuple(replace(eq, match="TBD") if eq.rule_id == "eq09" else eq for eq in DATA.equivalences),
    )
    return {
        "veterano com plano": export(
            ALL_2013_REQUIRED | {"1108351", "1108195", "1103176"},
            {"2027.1": ["moa", "pm", "lpcd", "generic:elective"], "2027.2": ["fbdbd", "generic:flexible_extension"]},
            overrides={"transition_every_term_ids": ["fbdbd", "moa", "lpcd"]},
        ),
        "primeiro período fora da oferta": export(FIRST_TERM | {"1108353"}, {"2027.1": ["prob2", "lpcd"]}),
        "sem histórico": export(set(), {}),
        "item a definir": export({"1108206"}, {"2027.2": ["amns"]}, data=tbd_data),
    }


SCENARIOS = scenarios()


@pytest.mark.parametrize("name", SCENARIOS)
def test_contains_all_sections(name):
    text = SCENARIOS[name]
    for section in SECTIONS:
        assert section in text, section
    assert "Explique ao aluno, em linguagem simples, o impacto de migrar ou não." in text
    assert "sugira um plano por período a partir de 2027.1" in text
    assert "Não invente disciplinas, regras ou equivalências" in text
    assert "deve ser conferido no app" in text


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_assumption_is_listed(name):
    text = SCENARIOS[name]
    for assumption in DATA.assumptions:
        line = next((l for l in text.splitlines() if f"(`{assumption.key}`)" in l), None)
        assert line is not None, assumption.key
        assert ("confirmada" if assumption.status == "confirmed" else "suposta") in line


@pytest.mark.parametrize("name", SCENARIOS)
def test_no_internal_ids(name):
    text = SCENARIOS[name]
    ids = {c.id for c in DATA.curriculum_2026} | {c.id for c in DATA.curriculum_2013}
    ids |= {eq.rule_id for eq in DATA.equivalences} | set(GENERIC_ITEMS)
    for internal_id in ids - PORTUGUESE_WORDS:
        assert not re.search(rf"(?<![\w:-]){re.escape(internal_id)}(?![\w:-])", text), internal_id
    assert "fbdbd|moa" not in text


@pytest.mark.parametrize("name", SCENARIOS)
def test_no_raw_values(name):
    text = SCENARIOS[name]
    for raw in ("None", "TBD", "true", "false", "elective", "complementary"):
        assert not re.search(rf"\b{raw}\b", text), raw
    # all_of/any_of only appear inside the assumption description from assumptions.csv.
    line = next(l for l in text.splitlines() if "(`internship_match`)" in l)
    assert line.split(" | ")[1] == "exige Estágio I e II"


@pytest.mark.parametrize("name", SCENARIOS)
def test_no_personal_data(name):
    # Entry term 2023.1 must not appear; only the deadline derived from it.
    assert "2023.1" not in SCENARIOS[name]


def test_assumption_values_use_course_names():
    text = SCENARIOS["veterano com plano"]
    line = next(l for l in text.splitlines() if "(`transition_every_term_ids`)" in l)
    assert "Fundamentos de Banco de Dados e Big Data" in line
    assert "Linguagem de Programação para Ciência de Dados" in line
    assert "alterada na simulação" in line
    line = next(l for l in text.splitlines() if "(`every_term_codes`)" in l)
    assert "Cálculo Numérico" in line and "Introdução à Álgebra Linear" in line
    assert "Na transição, também ofertadas em todo período: Fundamentos de Banco de Dados" in text


def test_history_and_scenarios():
    text = SCENARIOS["veterano com plano"]
    assert "| Econometria I (1108351) | 4 | vira optativa |" in text
    assert "| Análise Multivariada I (1108206) | 4 | aproveitada como Análise Multivariada |" in text
    assert "| Obrigatórias | 120 cr | 100 cr | 16 cr | 4 cr |" in text
    assert "| Optativas | 36 cr | 4 cr | — | 32 cr |" in text
    assert "proposta em análise pela coordenação" in text
    assert "Prazo máximo de conclusão do aluno: 2028.2." in text


def test_plan_and_pending_courses():
    text = SCENARIOS["veterano com plano"]
    assert "### 2027.1" in text and "### 2027.2" in text
    assert "| Flexível extensionista a definir | 6 | — |" in text
    row = next(l for l in text.splitlines() if l.startswith("| Aprendizagem de Máquina Supervisionada (novo)"))
    assert "| 6º |" in row
    assert "Regressão I (já cumprido) e Linguagem de Programação para Ciência de Dados" in row
    assert "| períodos .2 | Não |" in row
    row = next(
        l for l in text.splitlines() if l.startswith("| Fundamentos de Banco de Dados e Big Data (novo)") and "4º" in l
    )
    assert "Sim (2027.2)" in row
    assert "Optativa a definir: 4 cr" in text


def test_plan_warnings_are_exported():
    text = SCENARIOS["primeiro período fora da oferta"]
    assert "| Probabilidade 2 (novo) | 4 | fora do período de oferta |" in text
    assert "Atenção: você incluiu disciplinas fora do período" in text
    assert "Estágio Supervisionado II" in text  # partial internship notice


def test_without_plan_or_history():
    text = SCENARIOS["sem histórico"]
    assert "Nenhuma disciplina informada." in text
    assert "Nenhum plano montado." in text


def test_to_define_dependency_is_flagged():
    text = SCENARIOS["item a definir"]
    assert "depende de Análise Multivariada, cuja situação está a definir pela coordenação" in text
    assert "A definir pela coordenação:" in text
