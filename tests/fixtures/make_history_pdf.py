"""Build a fictitious SIGAA history PDF (three pages) for the parser tests.

Every value here is invented: page 1 has fake personal data, page 2 the
course table and page 3 the TOTALIZAÇÃO table. No data of a real history.

Usage: python tests/fixtures/make_history_pdf.py <output.pdf>
"""

import sys

from fpdf import FPDF

FAKE_PERSONAL_DATA = (
    "Nome: ALUNA FICTICIA DE TESTE",
    "Matrícula: 20240000000",
    "CPF: 000.000.000-00",
    "Data de Nascimento: 01/01/2000",
    "Filiação: MAE FICTICIA DE TESTE / PAI FICTICIO DE TESTE",
)
HEADER = "Componente Curricular CH Tipo Ano/Sem Turma Nota Situação"

# (code, name, hours, type, "year.term class grade" or "", status)
DEFAULT_ROWS = (
    ("PERÍODO 1",),
    ("1103118", "CÁLCULO VETORIAL E GEOMETRIA ANALÍTICA", 60, "OB", "2023.1 01 3.0", "REPROVADO"),
    ("1103118", "CÁLCULO VETORIAL E GEOMETRIA ANALÍTICA", 60, "OB", "2023.2 02 7.5", "APROVADO"),
    ("1103177", "CÁLCULO DIFERENCIAL E INTEGRAL I", 60, "OB", "2023.1 03 8.0", "APROVADO"),
    ("1108189", "METODOLOGIA DO TRABALHO CIENTÍFICO", 60, "OB", "2023.1 01 9.0", "APROVADO"),
    ("1108190", "ANÁLISE EXPLORATÓRIA DE DADOS", 60, "OB", "2023.1 01 0.0", "REP. FALTA"),
    ("1108190", "ANÁLISE EXPLORATÓRIA DE DADOS", 60, "OB", "2024.1 01 7.0", "APROVADO"),
    ("1108191", "PROBABILIDADE I", 60, "OB", "2023.1 01 6.5", "APROVADO"),
    ("PERÍODO 2",),
    ("1103178", "CÁLCULO DIFERENCIAL E INTEGRAL II", 60, "OB", "2024.2 01 ---", "TRANCADO"),
    ("1103178", "CÁLCULO DIFERENCIAL E INTEGRAL II", 60, "OB", "2026.2 01 ---", "MATRICULADO"),
    ("1103179", "INTRODUÇÃO À ÁLGEBRA LINEAR", 60, "OB", "2024.2 02 7.0", "APROVADO"),
    ("1108192", "PESQUISA APLICADA À ESTATÍSTICA", 60, "OB", "2024.2 01 8.5", "APROVADO"),
    ("1108193", "PROBABILIDADE II", 60, "OB", "2026.2 01 ---", "MATRICULADO"),
    ("1108194", "PROGRAMAÇÃO APLICADA À ESTATÍSTICA", 60, "OB", "", "PENDENTE"),
    ("OPTATIVAS",),
    ("1108157", "PESQUISA OPERACIONAL", 60, "OP", "2025.1 01 7.8", "APROVADO"),
    ("1108130", "ANÁLISE DE SOBREVIVÊNCIA", 60, "OP", "2025.1 01 ---", "CANCELADO"),
    ("FLEXÍVEIS",),
    ("9990001", "TÓPICOS DE OUTRO CURSO", 60, "CF", "2025.2 01 9.0", "APROVADO"),
)
# Básicos profissionais (OB), complementares obrigatórios (CO), optativos (OP),
# flexíveis (CF) and total.
DEFAULT_INTEGRALIZED = (420, 0, 60, 60, 540)


def _line(pdf, text, bold=False):
    pdf.set_font("Helvetica", "B" if bold else "", 9)
    pdf.cell(text=text, new_x="LMARGIN", new_y="NEXT")


def _institution(pdf):
    _line(pdf, "UNIVERSIDADE FICTÍCIA DE TESTE")
    _line(pdf, "Histórico Escolar - Emitido em 01/01/2026")


def build_history_pdf(
    rows=DEFAULT_ROWS, integralized=DEFAULT_INTEGRALIZED, curriculum="232013", extra_page_lines=()
):
    """Return the bytes of a fictitious three-page history.

    extra_page_lines: lines added at the end of page 1 (e.g. a value split
    from its label by the text extraction).
    """
    pdf = FPDF()

    pdf.add_page()
    _institution(pdf)
    for text in FAKE_PERSONAL_DATA:
        _line(pdf, text)
    if curriculum:
        _line(pdf, f"Currículo: {curriculum}")
    for text in extra_page_lines:
        _line(pdf, text)

    pdf.add_page()
    _institution(pdf)
    _line(pdf, f"{FAKE_PERSONAL_DATA[0]} {FAKE_PERSONAL_DATA[1]}")
    for row in rows:
        if len(row) == 1:
            _line(pdf, row[0], bold=True)
            _line(pdf, HEADER)
            continue
        code, name, hours, type_, details, status = row
        _line(pdf, " ".join(str(v) for v in (code, name, hours, type_, details, status) if v != ""))
    _line(pdf, "Página 2 de 3")

    pdf.add_page()
    _institution(pdf)
    _line(pdf, "TOTALIZAÇÃO", bold=True)
    _line(pdf, "Componentes Curriculares Componentes Curriculares Complementares")
    _line(pdf, "Total")
    _line(pdf, "Básicos Profissionais Obrigatórios Optativos Flexíveis")
    _line(pdf, "Carga Horária")
    _line(pdf, "Exigido 1740 480 540 240 3000")
    if integralized:
        _line(pdf, "Integralizado " + " ".join(str(v) for v in integralized))
    _line(pdf, "LEGENDAS", bold=True)
    _line(pdf, "OB COMPONENTE CURRICULAR BÁSICO PROFISSIONAL")
    _line(pdf, "Página 3 de 3")
    return bytes(pdf.output())


if __name__ == "__main__":
    with open(sys.argv[1], "wb") as f:
        f.write(build_history_pdf())
