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

## 2026-10-25 — Tarefa 2: Motor de regras

### O que foi feito

- `app/data_loader.py`: carrega os CSVs de `data/` em dataclasses tipadas
  (`Course`, `Equivalence`, `CodeAlias`, `Assumption` etc.) e devolve um
  `CurriculumData`.
- `app/rules.py`: `evaluate(codes, overrides=None, data=None)` aplica os
  passos 1 a 7 da especificação e devolve um `Evaluation` (cenários `migrate`
  e `stay`, premissas usadas, códigos desconhecidos e avisos gerais),
  serializável com `to_dict()` / `to_json()`. Premissas são lidas de
  `assumptions.csv` e podem ser sobrescritas em `overrides`.
- `data/elective_successors.csv` (novo): sucessoras das optativas antigas,
  transcritas das "Pendências conhecidas" do CLAUDE.md; usado só pela premissa
  `old_electives_count_for_emphasis`. O validador confere que o código existe
  em 2013 e a sucessora em 2026. A especificação de `data/` foi atualizada.
- `tests/test_rules.py`: 18 testes (aluno do 1º período, optativas com
  equivalência, Estágio I sem o II, Cálculo Numérico com a proposta, apelido
  1103176, Tópicos Especiais, ênfase, premissas sobrescritas, TBD, JSON).

### Decisões tomadas

1. A equivalência do estágio é identificada pelo tipo do destino
   (`internship`), não pelo `rule_id` eq13, e usa o `match` da premissa
   `internship_match`.
2. Regra `any_of` com mais de um código cursado: só o primeiro código da
   lista é consumido; os demais seguem para optativa (ex.: Python e
   Introdução aos Softwares → um vira lpcd, o outro optativa).
3. Equivalência `all_of` parcial (ex.: Estágio I sem o II): a disciplina
   cursada vira optativa (com seus créditos de 2013, 12 cr) e o aluno recebe
   um aviso.
4. Tópicos Especiais acima de `old_flexible_max_hours` não são contados
   (nem como optativa); o aluno recebe um aviso.
5. Extensão: só componentes aproveitados com `extension = true` (hoje, só
   Pesquisa de Mercado) e apenas se `old_pm_counts_as_extension = true`.
6. Com `old_electives_count_for_emphasis = true`, cada disciplina antiga
   conta seus próprios créditos para a ênfase da sucessora (Econometria I e
   II somam 8 cr, embora a sucessora seja uma só).
7. Apelidos `proposed` não são aplicados, mas geram aviso geral (mesma lógica
   da regra 5 para equivalências).
8. Códigos fora das duas grades vão para `unknown_codes`, com aviso, e não
   contam em nenhum cenário.
9. Parâmetros confirmados das grades (44/20 cr de optativas/flexíveis em
   2026, 36/16 em 2013, 24 cr para ênfase, 15 h por crédito) são constantes
   em `app/rules.py`; os totais de obrigatórias, estágio e complementares
   são somados dos CSVs.
10. Valores de status seguem a especificação, em português (`aproveitada`,
    `pendente`, `optativa`, `flexível`, `a definir`).

### Pendências

- As de `data/pending_issues.csv` continuam abertas.
- Confirmar com a coordenação as decisões 2, 3, 4 e 6 acima.
- Econometria (`econ;TBD`) afeta só o planejamento (tarefa 3), não a
  classificação.

## 2026-10-25 — Tarefa 3: Planejamento

### O que foi feito

- `app/planner.py`: `plan(evaluation, entry_term=None, overrides=None, data=None)`
  devolve um `Planning` com os planos `migrate` e `stay` (períodos com as
  disciplinas, créditos por período, períodos restantes, conclusão prevista,
  prazo máximo, disciplinas não planejáveis e avisos) e as premissas usadas.
  Serializável com `to_dict()` / `to_json()`.
- Algoritmo guloso período a período, a partir de `first_planning_term`:
  oferta por paridade do `semester`, tipos de `every_term_types` e ids de
  `transition_every_term_ids` (só em migrar) em todo período; pré-requisitos
  cumpridos em períodos anteriores, com grupos "OU"; limite de
  `max_credits_2026` / `max_credits_2013`; prioridade por maior cadeia de
  dependentes pendentes, depois menor `semester` (e `id`, para desempate
  estável); vagas genéricas de 4 cr depois das disciplinas do período.
- `app/rules.py`: `Evaluation` ganhou `taken_codes` (códigos cursados
  normalizados), usado pelo planejador.
- `tests/test_planner.py`: 12 testes (aluno sem pendências, cadeia
  lpcd → fbdbd, efeito de `transition_every_term_ids`, consistência de um
  aluno do 1º período nos dois cenários, vagas genéricas, prazo, pré-requisito
  impossível, pré-requisito externo, JSON).

### Decisões tomadas

1. Vagas genéricas: "Optativa a escolher" e "Flexível a escolher", ambas de
   4 cr; número de vagas = créditos faltantes / 4, arredondado para cima.
   Optativas antes de flexíveis.
2. Pré-requisito externo (`code:...`) conta como cumprido se o código estiver
   no histórico do aluno (inclusive entre os códigos desconhecidos).
   Pré-requisito `TBD` nunca é cumprido (hoje só afeta Econometria, que não é
   planejada individualmente).
3. Disciplinas "a definir" não são planejadas e não bloqueiam quem depende
   delas; o aluno recebe um aviso.
4. Se dois períodos seguidos passam sem nenhuma disciplina planejável e não há
   mais vagas genéricas, o planejamento para e lista as disciplinas
   bloqueadas (proteção contra laço infinito).
5. Prazo: 12 períodos contados a partir do período de ingresso, inclusive
   (ingresso 2020.1 → prazo 2025.2). Não considera trancamentos.
6. Extensão: o planejador não escolhe componentes extensionistas; só avisa
   quantas horas faltam.
7. Estágio e TCC de 2013/2026 seguem `every_term_types`; se esses tipos
   forem retirados da premissa, passam a seguir a paridade do `semester`.

### Pendências

- O planejador não respeita o mínimo de créditos por período (17 em 2026,
  12 em 2013): o último período pode ficar abaixo do mínimo. A especificação
  não pede isso; confirmar se deve.
- Como as vagas genéricas preenchem a sobra de cada período, alunos do início
  do curso recebem várias optativas já nos primeiros períodos. Confirmar se
  é o comportamento desejado.
- As pendências de `data/pending_issues.csv` continuam abertas.

## 2026-10-25 — Ajustes no planejador (antes da tarefa 4)

### O que foi feito

- `assumptions.csv`: novas premissas `target_credits_2026 = 24` e
  `target_credits_2013 = 24` (assumed). As vagas genéricas de optativa e
  flexível só preenchem um período até a carga-alvo; obrigatórias, estágio e
  TCC continuam podendo ir até `max_credits_*`. A descrição contém `;`, por
  isso está entre aspas no CSV. A tabela de premissas do CLAUDE.md foi
  atualizada.
- `app/planner.py`: aplica a carga-alvo às vagas genéricas e gera aviso
  quando um período que não é o último fica abaixo do mínimo de créditos
  (17 em 2026, 12 em 2013, constantes do PPC). Nada é bloqueado.
- `tests/test_planner.py`: 4 testes novos (carga-alvo, disciplinas acima da
  carga-alvo até o máximo, aviso de mínimo, transição ampliada).

### Resultado do exemplo

Aluno que concluiu todas as obrigatórias, estágios e TCCs de 2013, com
`transition_every_term_ids = fbdbd|moa|lpcd|ams`:

- Migrar: conclusão em **2028.1** (3 períodos): 2027.1 lpcd, moa, pm + 3
  optativas; 2027.2 fbdbd, ams + 4 optativas; 2028.1 5 flexíveis (20 cr).
- Não migrar: conclusão em **2028.1** (3 períodos: 9 optativas e 4 flexíveis
  em vagas genéricas, limitadas a 24 cr por período).

Com a premissa padrão (`fbdbd|moa`), migrar termina em 2028.2, com aviso de
2028.1 abaixo do mínimo (16 cr).

### Decisões tomadas

1. Os mínimos de 17 e 12 cr por período são parâmetros confirmados das
   grades e ficaram como constantes em `app/planner.py`, como os demais
   parâmetros do PPC.
2. A carga-alvo vale só para as vagas genéricas; ela não limita
   disciplinas específicas.

### Pendências

- Com a carga-alvo de 24 cr, quem não migra também passou a levar 3
  períodos no exemplo (antes, com 32 cr, eram 2).
- As pendências de `data/pending_issues.csv` continuam abertas.

## 2026-10-25 — Tarefa 4: Protótipo em Streamlit

### O que foi feito

- `app/streamlit_app.py` (rodar com `streamlit run app/streamlit_app.py`),
  todo em português, sem LLM e sem PDF:
  - entrada: período de ingresso (2013.1 a 2026.2), obrigatórias, estágios e
    TCC de 2013 em caixas de seleção agrupadas por período, e uma lista de
    optativas e flexíveis de 2013; atalho "marcar todas as obrigatórias até o
    período N" e botão "Limpar";
  - resultado em duas colunas, "Migrar" e "Não migrar": conclusão prevista,
    períodos restantes, prazo máximo, tabela de créditos, ênfase, situação de
    cada disciplina, disciplinas antigas contadas como optativa/flexível,
    pendentes e planejamento por período;
  - destaques: itens "a definir pela coordenação" e avisos do motor em
    amarelo; avisos do planejamento em azul; prazo ultrapassado e disciplinas
    não planejáveis em vermelho;
  - barra lateral "Premissas": todas as premissas com o status (confirmada ou
    suposta); as supostas são editáveis e o resultado é recalculado na hora;
    botão para restaurar os valores do arquivo. Quando há premissa alterada,
    o resultado mostra um aviso.
- `requirements.txt`: `streamlit`.
- `tests/test_streamlit_app.py`: 4 testes com `streamlit.testing.v1.AppTest`
  (página renderiza, marcar disciplinas recalcula, alterar premissa recalcula,
  aviso do Estágio I sem o II aparece).

### Decisões tomadas

1. A interface só chama `rules.evaluate` e `planner.plan`; nenhuma regra
   curricular nova. Só as premissas alteradas na tela são enviadas como
   `overrides`.
2. O tipo de controle de cada premissa é escolhido pelo valor (true/false →
   chave; número → campo numérico) e, para três premissas, pela chave
   (`internship_match` → opções all_of/any_of; `every_term_types` e
   `transition_every_term_ids` → seleção múltipla). Premissas novas sem
   controle específico aparecem como campo de texto.
3. `internship_match` na tela só aceita `all_of` ou `any_of` (não `TBD`).
4. Não há campo para códigos avulsos (ex.: 1103176, código antigo de Cálculo
   Numérico, ou 1107136, de outro departamento): a especificação pede só a
   lista da grade 2013. Isso fica para o parser do PDF (tarefa 5).

### Pendências

- A tarefa 5 (parser do PDF) ainda não tem especificação no CLAUDE.md.
- As pendências de `data/pending_issues.csv` continuam abertas.

## 2026-10-26 — Mudança de escopo: tarefas 3 e 4 refeitas (plano montado pelo aluno)

### O que foi feito

- CLAUDE.md: Roteiro, especificações das tarefas 3 e 4, regra de oferta
  ("Calendário e oferta"), descrição da arquitetura e tabela de premissas
  atualizados para o novo escopo; o planejamento automático saiu.
- `data/assumptions.csv`: nova premissa `every_term_codes` (confirmed:
  Dep. de Matemática e Cálculo Numérico em todo período); removidas
  `target_credits_2026` e `target_credits_2013` (só serviam ao planejador).
- Removidos `app/planner.py` e `tests/test_planner.py` (ficam no histórico do
  git, commit 3dc58de).
- `app/plan_check.py` (novo): `check_plan(history_codes, entry_term, plan,
  overrides, data)` verifica o plano do aluno na grade 2026 (pré-requisitos
  em períodos anteriores com grupos "OU", oferta fora do período habitual,
  créditos por período com mínimo 17 e máximo 25, totais cursado + planejado
  vs. exigido, ênfase, extensão, conclusão prevista ou o que falta, prazo de
  12 períodos) e resume o cenário "não migrar" pelo motor de regras. Também
  expõe funções usadas pela interface: `eligible_courses`, `cascade_remove`,
  `history_outcomes`, `OfferRule`, funções de período.
- `app/streamlit_app.py` (reescrito): ingresso; histórico por período
  (2013 → coluna 2026 preenchida pelo motor), sem repetição e com o atalho
  "marcar obrigatórias até o período N"; plano por período a partir de
  2027.1 com listas filtradas por pré-requisito, opções genéricas em
  contadores; remoção em cascata com aviso; créditos e avisos ao lado de cada
  bloco; aviso de oferta no topo e na disciplina; resumo "Migrar" e
  "Não migrar"; barra lateral de premissas; rodapé fixo.
- Testes: `tests/test_plan_check.py` (21) e `tests/test_streamlit_app.py`
  (7, com `AppTest`). Total: 59 testes passando.

### Decisões tomadas (aprovadas pelo usuário)

1. Opções genéricas ("Optativa a definir" 4 cr, "Flexível a definir" 4 cr,
   "Flexível extensionista a definir" 6 cr / 90 h de extensão) são contadores
   numéricos em cada período; as disciplinas específicas ficam em campos de
   seleção.
2. Estágio e TCC ficam no campo "Obrigatórias, estágio e TCC".
3. O aviso de mínimo de créditos não vale para o último período planejado
   (períodos vazios no meio do plano geram aviso).
4. `target_credits_*` removidas; `max_credits_2013` mantida.
5. Atalho do histórico: período = ingresso + (semestre − 1); as que cairiam
   depois de 2026.2 não são marcadas e aparecem num aviso.
6. Disciplina "a definir" conta como cumprida para pré-requisito, com aviso
   na dependente ("depende de X, cuja situação está a definir pela
   coordenação").

### Decisões de implementação

- Quantidade de períodos do plano: campo na tela (1 a 12); o padrão é o
  número de períodos até o prazo máximo, com mínimo de 4.
- A ênfase aparece no resumo como linha informativa; não impede a conclusão
  (sem 24 cr, o aluno é generalista).
- A conclusão também exige que não haja itens "a definir" no histórico.
- Disciplinas antigas que viram optativa sem correspondência específica
  aparecem como "vira optativa"; "sem correspondência" fica como caso de
  segurança.

### Pendências

- A tarefa 5 (parser do PDF) ainda não tem especificação.
- As pendências de `data/pending_issues.csv` continuam abertas.

## 2026-10-26 — Tarefa 4: tabelas no estilo do histórico do SIGAA

### O que foi feito

- Especificação da tarefa 4 no CLAUDE.md atualizada (tabelas, linha de
  inclusão, remoção, rodapé, períodos do plano).
- `app/streamlit_app.py`: histórico e plano passam a ter o mesmo formato de
  tabela por período, com colunas Código, Disciplina, Tipo e Créditos, mais
  "Na grade 2026" (histórico) ou "Avisos" (plano), e um botão "✕ Remover" em
  cada linha. A última linha tem os seletores "+ Obrigatória…" e
  "+ Optativa/flexível…"; ao escolher, a disciplina vira uma linha e o
  seletor volta a ficar vazio. As opções genéricas são itens do seletor de
  optativa/flexível (os contadores saíram) e podem se repetir. Rodapé com o
  total de créditos; avisos de mínimo e máximo só no plano. O plano começa
  com 2027.1; "+ Adicionar período" acrescenta o seguinte e o último período
  pode ser removido quando vazio (o campo numérico saiu).
- O estado de cada tabela é uma lista ordenada de itens em
  `st.session_state` (`hist_<período>`, `plan_<período>`); a remoção em
  cascata continua no início de cada execução.
- `tests/test_streamlit_app.py` reescrito (9 testes) e novo teste em
  `tests/test_plan_check.py` para a regra de oferta de obrigatória de
  semestre par (sem aviso em AAAA.2, com aviso em AAAA.1). Total: 62 testes.

### Decisões tomadas (aprovadas pelo usuário)

1. Histórico sem avisos de mínimo e máximo, só o total de créditos.
2. Estágio e TCC aparecem como tipos próprios.
3. Disciplina sem código SIGAA mostra "novo"; opção genérica mostra "—".
4. Períodos do plano controlados pelos botões "+ Adicionar período" e
   "Remover período" (só no último, quando vazio).

### Observação

- A regra de oferta já estava correta: Probabilidade 2 (2º semestre) em
  2027.2 não gera aviso. O "fora do período" no exemplo do plano apresentado
  ao usuário era um erro do desenho ilustrativo, não do código.

### Pendências

- A tarefa 5 (parser do PDF) ainda não tem especificação.
- As pendências de `data/pending_issues.csv` continuam abertas.
