# Progresso

## 2026-10-25 — Tarefa 1: Dados de `data/` + validador + testes

### O que foi feito

- `data/`: os oito CSVs (`curriculum_2026`, `prerequisites_2026`,
  `curriculum_2013`, `prerequisites_2013`, `equivalences`, `code_aliases`,
  `assumptions`, `pending_issues`), transcritos somente das tabelas do
  CLAUDE.md, com pré-requisitos em formato longo. Totais conferidos:
  2026 = 120 / 8 / 8 cr (obrigatórias / estágio / complementares);
  2013 = 116 / 24 / 8 cr.
- `scripts/validate_data.py`: ids únicos, pré-requisitos existentes (`code:...`
  e `TBD` geram aviso), ausência de ciclos, totais de créditos, `target_id` das
  equivalências, `alias_of` dos apelidos e pares (nome, código) duplicados.
  Lista todos os problemas e sai com código 1 se houver algum.
- `tests/`: testes pytest com fixtures em `tests/fixtures/` (ciclo,
  pré-requisito inexistente, grade pequena) e testes sobre os dados reais.
- `requirements.txt` com `pytest`.

### Decisões tomadas

1. Valores incertos ficaram como `TBD`: o pré-requisito "Regressão" de
   Econometria (`econ;TBD;1`) e o `match` da eq13. O validador trata `TBD`
   e o pré-requisito externo `code:1107136` (Cálculo Numérico) como aviso,
   não como erro.
2. A nota da eq13 tinha `;`, que quebraria o separador do CSV; foi reescrita
   sem ele.
3. `semester` de estágio e TCC foi preenchido com o período das tabelas
   (7 e 8), nas duas grades; o `type` distingue esses componentes das
   obrigatórias.
4. `pending_issues.csv` traz, além dos dois TBD, as demais pendências
   conhecidas do CLAUDE.md, cada uma ligada ao registro afetado.

### Ajustes posteriores (antes da tarefa 2)

- O `match` da eq13 virou a premissa `internship_match` (`all_of`, assumed)
  em `assumptions.csv`; em `equivalences.csv` a eq13 ficou com `all_of` e uma
  nota apontando para a premissa. A especificação da tarefa 2 foi atualizada
  para o motor usar essa premissa. A pendência continua em `pending_issues.csv`.

### Pendências

- Todas as listadas em `data/pending_issues.csv` (Econometria, Estágio, apelidos
  `proposed`, ênfase das optativas antigas, implantação gradual, oferta de
  estágio/TCC, eq14).
