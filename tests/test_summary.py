from app.conversion import HistoryEntry, convert
from app.data_loader import load_data
from app.summary import build_summary, courses_text, format_hours, lost_text

DATA = load_data()


def summary(history, **kwargs):
    return build_summary(convert(history, data=DATA, **kwargs))


def test_format_hours():
    assert format_hours(3000) == "3.000 h"
    assert format_hours(60) == "60 h"


def test_courses_text_exact_and_approximate():
    assert courses_text(2880) == "equivale a 48 disciplinas de 60 h"
    assert courses_text(2910) == "cerca de 49 disciplinas de 60 h"
    assert courses_text(60) == "equivale a 1 disciplina de 60 h"


def test_empty_history():
    s = summary([])
    assert s.missing_hours == 3000
    assert s.missing_credits == 200
    assert s.missing_text == "Faltam 3.000 h (200 cr): equivale a 50 disciplinas de 60 h."
    assert s.used_percent == 0
    assert s.lost_text == "Nenhuma hora perdida."
    assert s.stay_text == "Se não migrar, faltam 3.000 h (200 cr) pela grade 2013."
    assert s.pending[0] == "Análise Exploratória e Visualização de Dados"
    assert len(s.pending) == 33


def test_percent_and_missing():
    s = summary(["1108353"])  # Estágio I: 180 h aprovadas, 120 h aproveitadas
    assert s.used_percent == 67
    assert s.missing_hours == 2880
    assert s.missing_text.endswith("equivale a 48 disciplinas de 60 h.")
    assert "67%" in s.used_text and "120 h de 180 h" in s.used_text


def test_missing_not_exact():
    s = summary(["1103142"])  # Introdução à Análise Real, 90 h em Tópicos
    assert s.missing_hours == 2910
    assert s.missing_text == "Faltam 2.910 h (194 cr): cerca de 49 disciplinas de 60 h."


def test_lost_with_recoverable_hours():
    s = summary(["1108353", "1108354"])
    assert s.lost_hours == 240
    assert s.recoverable_hours == 180
    assert s.lost_text == "Perdido: 240 h, das quais até 180 h podem ser recuperadas mediante pedido:"
    assert s.recoverable_lines == [
        "Estágio Supervisionado II como extensão: até 180 h, quantidade a definir pela coordenação."
    ]
    assert [(i.name, i.lost_hours) for i in s.lost_items] == [
        ("Estágio Supervisionado I", 60),
        ("Estágio Supervisionado II", 180),
    ]
    assert s.warnings[0].startswith("Atenção: 240 h")
    assert s.requests[0].text == (
        "Estágio Supervisionado II como extensão: até 180 h, quantidade a definir pela coordenação."
    )


def test_lost_without_recoverable_hours():
    assert lost_text(60, 0) == "Perdido: 60 h."


def test_categories_and_emphases():
    s = summary(["1108351", "1108352", "1108156"])
    names = [c.name for c in s.categories]
    assert names == [
        "Obrigatórias", "Estágio", "TCC", "Optativas", "Tópicos Especiais",
        "Flexíveis extensionistas", "Extensão",
    ]
    extension = s.categories[-1]
    assert (extension.required_hours, extension.used_hours, extension.missing_hours) == (300, 60, 240)
    eam = s.emphases[0]
    assert (eam.name, eam.hours, eam.min_hours, eam.reached) == ("Estatística Aplicada e Modelagem", 120, 360, False)


def test_unrecognized_course_warning():
    s = summary([HistoryEntry("8888888", "Disciplina desconhecida", 60, "OB")])
    assert any("8888888" in w for w in s.warnings)
    assert s.approved_hours == 0
    assert s.used_percent == 0
    assert s.unrecognized_hours == 60
    assert s.used_note == "Não entram no cálculo 60 h de disciplinas não reconhecidas na grade 2013."


def test_no_note_without_unrecognized_courses():
    assert summary(["1108353"]).used_note == ""


# Real cases checked by the user (stage b review).
CASE_1 = [
    "1103118", "1103177", "1108189", "1108190", "1108191", "1103178", "1103179", "1108192",
    "1108193", "1108194", "1108196", "1103180", "1103232", "1108148", "1108197",
]
CASE_2 = CASE_1 + ["GDEST0105", "1108149", "1108202", "1108203", "GDCOC0072"]


def test_real_case_first_periods():
    s = summary(CASE_1)
    assert (s.approved_hours, s.used_hours, s.used_percent) == (900, 900, 100)
    assert (s.missing_hours, s.missing_credits, s.missing_courses) == (2100, 140, 35)
    assert s.missing_text == "Faltam 2.100 h (140 cr): equivale a 35 disciplinas de 60 h."
    assert (s.lost_hours, s.recoverable_hours) == (0, 0)
    assert s.lost_text == "Nenhuma hora perdida."
    assert s.recoverable_lines == []


def test_real_case_with_topics_above_limit():
    s = summary(CASE_2)
    assert (s.approved_hours, s.used_hours, s.used_percent) == (1200, 1140, 95)
    assert (s.missing_hours, s.missing_credits, s.missing_courses) == (1860, 124, 31)
    assert s.lost_hours == 60
    assert [(i.name, i.lost_hours) for i in s.lost_items] == [("Introdução aos Softwares Estatísticos", 60)]
    assert "Excedente de Tópicos Especiais" in s.lost_items[0].reason
    assert s.recoverable_hours == 60
    assert s.lost_text == "Perdido: 60 h, das quais até 60 h podem ser recuperadas mediante pedido:"
    assert s.recoverable_lines == [
        "Cálculo Numérico como Métodos de Otimização e Aplicações: 60 h, se a coordenação aceitar o pedido."
    ]
    assert [r.text for r in s.requests] == s.recoverable_lines


def test_summary_is_json_serializable():
    assert '"missing_hours": 2880' in summary(["1108353"]).to_json()
