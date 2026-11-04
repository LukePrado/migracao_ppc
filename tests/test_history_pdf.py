import io

import pytest

pytest.importorskip("fpdf")

from app.conversion import convert  # noqa: E402
from app.data_loader import load_data  # noqa: E402
from app.history_pdf import parse_history, parse_line  # noqa: E402
from tests.fixtures.make_history_pdf import (  # noqa: E402
    DEFAULT_ROWS,
    FAKE_PERSONAL_DATA,
    build_history_pdf,
)


@pytest.fixture(scope="module")
def parsed():
    return parse_history(build_history_pdf())


def codes(entries):
    return [e.code for e in entries]


def test_approved_lines_count_once(parsed):
    assert codes(parsed.entries).count("1103118") == 1  # failed, then passed
    assert codes(parsed.entries).count("1108190") == 1  # REP. FALTA, then passed
    assert len(parsed.entries) == 9


def test_approved_hours_by_type(parsed):
    assert {t: h for t, h in parsed.approved_hours_by_type.items() if h} == {"OB": 420, "OP": 60, "CF": 60}
    assert parsed.approved_hours == 540


def test_locked_failed_and_pending_lines_are_not_counted(parsed):
    assert "1108194" not in codes(parsed.entries)  # PENDENTE
    assert "1108130" not in codes(parsed.entries)  # unknown status


def test_in_progress_lines_are_left_out_by_default(parsed):
    assert codes(parsed.in_progress) == ["1103178", "1108193"]  # TRANCADO, then MATRICULADO
    assert "1103178" not in codes(parsed.entries)


def test_in_progress_lines_included_on_request():
    result = parse_history(build_history_pdf(), include_in_progress=True)
    assert len(result.entries) == 11
    assert {"1103178", "1108193"} <= set(codes(result.entries))
    assert result.approved_hours == 540  # still only the approved ones


def test_in_progress_already_approved_is_ignored():
    rows = DEFAULT_ROWS + (("1103177", "CÁLCULO DIFERENCIAL E INTEGRAL I", 60, "OB", "2026.2 01 ---", "MATRICULADO"),)
    result = parse_history(build_history_pdf(rows))
    assert "1103177" not in codes(result.in_progress)


def test_unknown_status_warns(parsed):
    assert parsed.unknown_statuses == ["ANÁLISE DE SOBREVIVÊNCIA (1108130): CANCELADO"]
    assert any("CANCELADO" in w for w in parsed.warnings)


def test_totalization_matches(parsed):
    assert parsed.integralized_hours == {"OB": 420, "CO": 0, "OP": 60, "CF": 60, "total": 540}
    assert parsed.totals_match is True
    assert parsed.curriculum == "232013"
    assert parsed.warnings == [w for w in parsed.warnings if "CANCELADO" in w]


def test_totalization_does_not_match():
    result = parse_history(build_history_pdf(integralized=(480, 0, 60, 60, 600)))
    assert result.totals_match is False
    assert any("não batem com a TOTALIZAÇÃO" in w for w in result.warnings)


def test_totalization_missing():
    result = parse_history(build_history_pdf(integralized=None))
    assert result.totals_match is None
    assert any("TOTALIZAÇÃO não foi encontrada" in w for w in result.warnings)


def test_other_curriculum_warns():
    result = parse_history(build_history_pdf(curriculum="242026"))
    assert any("currículo 242026" in w for w in result.warnings)


def test_missing_curriculum_warns():
    result = parse_history(build_history_pdf(curriculum=""))
    assert result.curriculum is None
    assert any("Não foi possível conferir o currículo" in w for w in result.warnings)


def test_personal_data_is_never_extracted(parsed):
    text = parsed.to_json()
    for item in FAKE_PERSONAL_DATA:
        value = item.split(": ", 1)[1]
        for piece in value.split(" / "):
            assert piece not in text
    assert "20240000000" not in text


def test_accepts_file_like_object():
    assert len(parse_history(io.BytesIO(build_history_pdf())).entries) == 9


def test_invalid_pdf_raises_value_error():
    with pytest.raises(ValueError, match="Não foi possível ler o PDF"):
        parse_history(b"isto nao e um pdf")


def test_pdf_without_courses_warns():
    result = parse_history(build_history_pdf(rows=()))
    assert result.entries == []
    assert any("Nenhuma disciplina" in w for w in result.warnings)


@pytest.mark.parametrize(
    "line, expected",
    [
        ("1103118 CÁLCULO VETORIAL E GEOMETRIA ANALÍTICA 60 OB 2025.1 08 8.8 APROVADO",
         ("1103118", "CÁLCULO VETORIAL E GEOMETRIA ANALÍTICA", 60, "OB", "APROVADO")),
        ("1108191 PROBABILIDADE I 60 OB 2024.1 01 0.0 REP. FALTA",
         ("1108191", "PROBABILIDADE I", 60, "OB", "REP. FALTA")),
        ("1108353 ESTÁGIO SUPERVISIONADO I 180 CO PENDENTE",
         ("1108353", "ESTÁGIO SUPERVISIONADO I", 180, "CO", "PENDENTE")),
        ("GDEST0105 PROGRAMAÇÃO ESTATÍSTICA COM PYTHON 60 OP 2026.2 01 --- MATRICULADO",
         ("GDEST0105", "PROGRAMAÇÃO ESTATÍSTICA COM PYTHON", 60, "OP", "MATRICULADO")),
    ],
)
def test_parse_line(line, expected):
    parsed = parse_line(line)
    assert (parsed.code, parsed.name, parsed.hours, parsed.sigaa_type, parsed.status) == expected


@pytest.mark.parametrize(
    "line",
    ["Componente Curricular CH Tipo Ano/Sem Turma Nota Situação", "PERÍODO 3", "Página 2 de 3",
     "Integralizado 840 0 60 0 900", "Nome: ALUNA FICTICIA DE TESTE Matrícula: 20240000000"],
)
def test_other_lines_are_ignored(line):
    assert parse_line(line) is None


def test_parsed_history_feeds_the_conversion(parsed):
    result = convert(parsed.entries, data=load_data())
    flexible = next(c for c in result.courses if c.code == "9990001")
    assert (flexible.category, flexible.used_hours) == ("topics", 60)
    assert result.approved_hours == 540
