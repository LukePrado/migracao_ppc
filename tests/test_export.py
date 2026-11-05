import re

import pytest

from app.conversion import HistoryEntry, convert
from app.data_loader import load_data
from app.export import FILE_NAME, build_export
from app.history_pdf import parse_history
from app.summary import build_summary
from tests.fixtures.make_history_pdf import FAKE_PERSONAL_DATA, build_history_pdf
from tests.test_summary import CASE_1, CASE_2

DATA = load_data()

SECTIONS = (
    "# Migração do PPC: resultado da simulação para conversar com uma IA",
    "## 1. Contexto e regras de conversão",
    "## 2. Premissas usadas",
    "## 3. Tabela de conversão",
    "## 4. Resumo",
    "## 5. Não aproveitado",
    "## 6. Possíveis aproveitamentos mediante pedido",
    "## 7. Obrigatórias do PPC 2026 que faltam",
    "## 8. Optativas disponíveis no PPC 2026",
    "## 9. Instruções para a IA",
)
INSTRUCTIONS = (
    "Responda em português.",
    "Explique ao aluno, em linguagem simples, o que ele aproveita, o que perde e o que falta",
    "não invente disciplinas, regras ou equivalências",
    "Os números deste arquivo foram calculados pelo app a partir das regras da coordenação. Não\n"
    "  refaça as contas; se algo parecer divergir, prevalece o que está no arquivo, e o aluno deve\n"
    "  confirmar com a coordenação.",
    "Sinalize sempre o que depende de decisão ou pedido à coordenação",
)
# Internal ids that are also ordinary Portuguese words.
PORTUGUESE_WORDS = {"na"}
MIXED = [
    "1108140",  # Demografia I: same code, elective
    "1108139",  # Controle Estatístico de Qualidade: successor
    "1108351", "1108352",  # Econometria I and II: same successor
    "1108353", "1108354",  # Estágio I (reduced) and II (request)
    "GDCOC0072",  # Cálculo Numérico: topics and request
    "1108211",  # alias of Introdução à Inferência Bayesiana
    "GDEST0105", "1108196",  # destination already taken
    HistoryEntry("9990002", "Disciplina de outro curso", 60, "OB"),  # unrecognized
    HistoryEntry("MANUAL-1", "Flexível de outro curso", 45, "CF"),  # added by hand
]


def export(history, overrides=None, destination_overrides=None, **kwargs):
    result = convert(history, overrides, destination_overrides, data=DATA)
    return build_export(result, build_summary(result), DATA, **kwargs)


def pdf_export():
    parsed = parse_history(build_history_pdf())
    return export(parsed.entries, in_progress_included=False)


SCENARIOS = {
    "caso real 1": export(CASE_1, current_period=4),
    "caso real 2": export(CASE_2),
    "misto": export(MIXED, current_period=3),
    "simulação": export(
        ["1108128", "1108197"], overrides={"topics_max_hours": 60},
        destination_overrides={"1108128": "elective:CD"},
    ),
    "histórico do PDF": pdf_export(),
    "vazio": export([]),
}


def outside_tables(text):
    return "\n".join(line for line in text.splitlines() if not line.startswith("|"))


@pytest.mark.parametrize("name", SCENARIOS)
def test_contains_all_sections_and_instructions(name):
    text = SCENARIOS[name]
    positions = [text.index(section) for section in SECTIONS]
    assert positions == sorted(positions)
    for instruction in INSTRUCTIONS:
        assert instruction in text, instruction
    assert "Não contém nome, matrícula nem outros dados pessoais" in text


@pytest.mark.parametrize("name", SCENARIOS)
def test_every_assumption_is_listed_with_its_status(name):
    text = SCENARIOS[name]
    for assumption in DATA.assumptions:
        line = next(l for l in text.splitlines() if l.startswith(f"| {assumption.description} |"))
        assert line.endswith("| confirmada |" if assumption.status == "confirmed" else "| suposta |") or (
            "alterada na simulação" in line
        )
    for row in DATA.old_course_destinations:
        assert f"({row.code}) |" in text


@pytest.mark.parametrize("name", SCENARIOS)
def test_no_internal_ids(name):
    text = SCENARIOS[name]
    ids = {c.id for c in DATA.curriculum_2026} | {c.id for c in DATA.curriculum_2013}
    ids |= {eq.rule_id for eq in DATA.equivalences}
    for internal_id in ids - PORTUGUESE_WORDS:
        assert not re.search(rf"(?<![\w-]){re.escape(internal_id)}(?![\w-])", text), internal_id
    assert "MANUAL-" not in text


@pytest.mark.parametrize("name", SCENARIOS)
def test_no_raw_values(name):
    text = SCENARIOS[name]
    for raw in ("None", "TBD", "true", "false", "elective", "topics", "mandatory", "assumed", "confirmed",
                "flexible_extension", "unrecognized", "EAM", "CD"):
        assert not re.search(rf"\b{raw}\b", text), raw


@pytest.mark.parametrize("name", SCENARIOS)
def test_codes_only_in_parentheses_inside_tables(name):
    text = SCENARIOS[name]
    codes = {c.code for c in DATA.curriculum_2013} | {c.code for c in DATA.curriculum_2026} - {"NEW"}
    for code in codes:
        for line in text.splitlines():
            if code in line:
                assert line.startswith("|") and f"({code})" in line, (code, line)
    # Courses outside the 2013 curriculum keep their SIGAA code in parentheses only.
    assert all(c not in outside_tables(text) for c in codes)


def test_no_personal_data():
    text = SCENARIOS["histórico do PDF"]
    for item in FAKE_PERSONAL_DATA:
        label, value = item.split(": ", 1)
        for piece in value.split(" / "):
            assert piece not in text, label
    assert "20240000000" not in text
    assert "Disciplinas em curso: não incluídas nesta simulação." in text


def test_real_case_summary_and_pending():
    text = SCENARIOS["caso real 1"]
    assert "- Faltam 2.100 h (140 cr): equivale a 35 disciplinas de 60 h." in text
    assert "Aproveitamento: 100% (900 h de 900 h aprovadas na grade 2013)." in text
    assert "Nenhuma hora perdida." in text
    assert "Período em que o aluno informou estar: 4º." in text
    behind = text[text.index("Ficaram para trás (períodos anteriores ao 4º):"):text.index("Próximos períodos:")]
    assert behind.split("\n\n")[1] == "- Probabilidade 3 (3º período)"
    assert "- Fundamentos de Banco de Dados e Big Data (4º período)" in text[text.index("Próximos períodos:"):]


def test_real_case_with_loss_and_request():
    text = SCENARIOS["caso real 2"]
    assert "Perdido: 60 h, das quais até 60 h podem ser recuperadas mediante pedido:" in text
    assert "- Introdução aos Softwares Estatísticos: 60 h perdidas, excedente de Tópicos Especiais" in text
    assert ("- Cálculo Numérico como Métodos de Otimização e Aplicações: 60 h, se a coordenação aceitar o "
            "pedido.") in text
    assert "Ficaram para trás" not in text  # no period informed: a single list
    assert "Disciplinas em curso" not in text


def test_conversion_table_and_lists():
    text = SCENARIOS["misto"]
    assert ("| Demografia I (1108140) | 60 h | Demografia I (optativa · Estatística Aplicada e Modelagem) "
            "| 60 h | 0 h | — |") in text
    assert "| Controle Estatístico de Qualidade (1108139) | 60 h | Controle Estatístico de Processos (optativa" in text
    assert "| Flexível de outro curso | 45 h | Tópicos Especiais (flexível) | 45 h | 0 h | — |" in text
    assert "- Estágio Supervisionado II: 180 h perdidas, não é aproveitada automaticamente." in text
    assert "- Disciplina de outro curso (60 h)" in text
    assert "Flexíveis do PPC 2026 (componentes sem lista fixa de disciplinas): faltam 0 h de Tópicos" in text
    assert "Estágio Supervisionado II como extensão: até 180 h, quantidade a definir pela coordenação." in text


def test_available_electives():
    text = SCENARIOS["misto"]
    electives = text[text.index("## 8."):text.index("## 9.")]
    rows = [line.split(" | ")[0] for line in electives.splitlines() if line.startswith("| ")]
    for taken in ("| Demografia I (1108140)", "| Econometria (nova)", "| Controle Estatístico de Processos (nova)",
                  "| Introdução à Inferência Bayesiana (1108153)"):
        assert taken not in rows, taken
    assert "| Demografia II (1108141) | Estatística Aplicada e Modelagem | Não | Demografia I (já aproveitada) |" in electives
    assert "| Consultoria Estatística (nova) | Estatística Aplicada e Modelagem | Sim |" in electives
    assert "| Pesquisa Operacional (1108157) | sem ênfase | Não | Introdução à Álgebra Linear |" in electives


def test_simulated_rules_are_flagged():
    text = SCENARIOS["simulação"]
    assert "| Limite único de horas para tudo o que vai para Tópicos Especiais | 60 h | suposta (alterada na simulação) |" in text
    assert ("| Análise de Dados Categorizados (1108128) | Optativa · Ciência de Dados | suposta (alterada na "
            "simulação) |") in text
    assert "| Análise de Dados Categorizados (1108128) | 60 h | Optativa · Ciência de Dados |" in text


def test_empty_history():
    text = SCENARIOS["vazio"]
    assert "Nenhuma disciplina informada." in text
    assert "- Faltam 3.000 h (200 cr): equivale a 50 disciplinas de 60 h." in text


def test_file_name():
    assert FILE_NAME == "simulacao_migracao_ppc.md"
