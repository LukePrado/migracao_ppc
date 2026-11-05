"""Parser of the SIGAA history PDF (grade 2013).

Reads the PDF in memory and keeps only the course lines (code, name, hours,
SIGAA type and status), whether the curriculum number appears and the
"Integralizado" line of the TOTALIZAÇÃO table. Personal data (name, student id, CPF, parents, birth
date) is never extracted: every other line is ignored. Nothing is logged and
the file is never written.
"""

import io
import json
import re
from dataclasses import asdict, dataclass, field

import pdfplumber

from app.conversion import HistoryEntry

EXPECTED_CURRICULUM = "232013"

APPROVED = "APROVADO"
IN_PROGRESS = "MATRICULADO"
KNOWN_STATUSES = (APPROVED, "REPROVADO", "REP. FALTA", "TRANCADO", IN_PROGRESS, "PENDENTE")
SIGAA_TYPES = ("OB", "OP", "CO", "CF", "EC", "EQ")
# Columns of the TOTALIZAÇÃO table and the SIGAA type counted in each one.
TOTALIZATION_COLUMNS = ("OB", "CO", "OP", "CF")
# Equivalent (EQ) and extracurricular (EC) lines: outside the totalization check.
UNCHECKED_TYPES = ("EQ", "EC")

LINE_RE = re.compile(
    r"^(?P<code>(?=[A-Z]*\d)[A-Z0-9]{5,10})\s+"
    r"(?P<name>.+?)\s+"
    r"(?P<hours>\d{1,4})\s+"
    rf"(?P<type>{'|'.join(SIGAA_TYPES)})"
    r"(?:\s+\d{4}\.\d\s+\S+\s+\S+)?"  # year.term, class and grade (ignored)
    r"\s+(?P<status>[A-ZÀ-Ú][A-ZÀ-Ú. ]*)$"
)
INTEGRALIZED_RE = re.compile(r"^Integralizado\s+((?:\d+\s*){5})$")


@dataclass(frozen=True)
class HistoryLine:
    code: str
    name: str
    hours: int
    sigaa_type: str
    status: str


@dataclass
class ParsedHistory:
    entries: list[HistoryEntry]
    approved_hours_by_type: dict[str, int]
    in_progress: list[HistoryEntry]
    curriculum_found: bool
    integralized_hours: dict[str, int] | None
    totals_match: bool | None
    unknown_statuses: list[str]
    warnings: list[str] = field(default_factory=list)

    @property
    def approved_hours(self):
        return sum(self.approved_hours_by_type.values())

    def to_dict(self):
        return asdict(self)

    def to_json(self, **kwargs):
        return json.dumps(self.to_dict(), ensure_ascii=False, **kwargs)


def parse_line(text):
    """Return a HistoryLine for a course line, or None for any other line."""
    match = LINE_RE.match(text.strip())
    if match is None:
        return None
    return HistoryLine(
        code=match["code"],
        name=match["name"].strip(),
        hours=int(match["hours"]),
        sigaa_type=match["type"],
        status=" ".join(match["status"].split()),
    )


def _integralized(text):
    for line in text.splitlines():
        match = INTEGRALIZED_RE.match(line.strip())
        if match:
            values = [int(v) for v in match[1].split()]
            return dict(zip((*TOTALIZATION_COLUMNS, "total"), values))
    return None


def _page_texts(data):
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]
    except Exception:  # pdfplumber/pdfminer raise several error types
        raise ValueError("Não foi possível ler o PDF. Confira se é o histórico baixado do SIGAA.") from None


def _entry(line):
    return HistoryEntry(line.code, line.name, line.hours, line.sigaa_type)


def parse_history(data, include_in_progress=False):
    """Parse the bytes of a SIGAA history PDF.

    include_in_progress: also count MATRICULADO lines (supposing approval).
    """
    if hasattr(data, "read"):
        data = data.read()
    texts = _page_texts(data)

    lines = [line for text in texts for row in text.splitlines() if (line := parse_line(row))]
    approved, in_progress, unknown = {}, {}, []
    for line in lines:
        if line.status == APPROVED:
            approved.setdefault(line.code, line)
        elif line.status == IN_PROGRESS:
            in_progress.setdefault(line.code, line)
        elif line.status not in KNOWN_STATUSES:
            unknown.append(f"{line.name} ({line.code}): {line.status}")
    in_progress = {code: line for code, line in in_progress.items() if code not in approved}

    approved_hours = {t: 0 for t in SIGAA_TYPES}
    for line in approved.values():
        approved_hours[line.sigaa_type] += line.hours

    warnings = []
    if not lines:
        warnings.append(
            "Nenhuma disciplina foi encontrada no PDF. Confira se é o histórico do SIGAA "
            "ou preencha a tabela manualmente."
        )

    # The label and the value may be split by the text extraction: look for the value only.
    curriculum_found = any(EXPECTED_CURRICULUM in text for text in texts)
    if not curriculum_found:
        warnings.append(
            f"Não foi possível confirmar no PDF o currículo {EXPECTED_CURRICULUM}. O app vale só "
            "para a grade 2013."
        )

    integralized = next((v for text in texts if (v := _integralized(text))), None)
    totals_match = None
    if integralized is None:
        warnings.append("A tabela TOTALIZAÇÃO não foi encontrada; não foi possível conferir a leitura.")
    else:
        found = {t: approved_hours[t] for t in TOTALIZATION_COLUMNS}
        found["total"] = sum(found.values())
        totals_match = found == integralized
        if not totals_match:
            warnings.append(
                "As horas aprovadas lidas não batem com a TOTALIZAÇÃO do histórico: a leitura pode ter "
                "falhado. Confira a tabela abaixo."
            )

    unchecked = [f"{line.name} ({line.code}, {line.sigaa_type})" for line in approved.values()
                 if line.sigaa_type in UNCHECKED_TYPES]
    if unchecked:
        warnings.append(
            "Componentes equivalentes (EQ) ou extracurriculares (EC) não entram na conferência com a "
            "TOTALIZAÇÃO: " + "; ".join(unchecked) + ". Consulte a coordenação sobre o aproveitamento deles."
        )

    if unknown:
        warnings.append("Situações não reconhecidas (linhas não consideradas): " + "; ".join(unknown) + ".")

    entries = [_entry(line) for line in approved.values()]
    if include_in_progress:
        entries += [_entry(line) for line in in_progress.values()]

    return ParsedHistory(
        entries=entries,
        approved_hours_by_type=approved_hours,
        in_progress=[_entry(line) for line in in_progress.values()],
        curriculum_found=curriculum_found,
        integralized_hours=integralized,
        totals_match=totals_match,
        unknown_statuses=unknown,
        warnings=warnings,
    )
