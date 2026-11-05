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

## 2026-10-26 — Exportar para conversar com uma IA

### O que foi feito

- `app/export.py` (novo): `build_export(ctx, check, plan, outcomes)` devolve
  um Markdown com 7 seções (contexto, premissas, histórico, situação nos dois
  cenários, plano atual, disciplinas pendentes e disponíveis, instruções
  para a IA). Função pura: não chama API nem grava arquivo.
- `app/streamlit_app.py`: botão "Exportar para conversar com uma IA" no fim
  do resultado (`st.download_button`, arquivo `migracao_ppc_resumo.md`), com
  legenda pedindo para revisar antes de compartilhar.
- Correções que também valem para a tela: avisos do motor de regras não
  citam mais o id da regra (ex.: "eq14") nem o `match`; o aviso de oferta do
  `plan_check` lista os tipos em português; itens "a definir" aparecem pelo
  nome da disciplina (na lista do que falta e no destaque da tela).
- Testes: `tests/test_export.py` (seções, todas as premissas com status,
  nenhum id interno, nenhum valor cru, sem período de ingresso, nomes nos
  valores das premissas, plano, pendentes, avisos, item a definir) em quatro
  cenários; teste do botão em `tests/test_streamlit_app.py`; testes do motor
  ajustados ao novo texto dos avisos. Total: 89 testes.
- Especificação da tarefa 4 no CLAUDE.md atualizada.

### Decisões tomadas (aprovadas pelo usuário)

1. A seção 6 inclui as optativas e flexíveis disponíveis (não cursadas) e as
   opções genéricas, para a IA ter o que sugerir.
2. Só o prazo máximo de conclusão; sem o período de ingresso.
3. Histórico como lista simples, sem os períodos cursados.
4. Disciplinas sempre pelo nome (também nos valores das premissas); código
   só entre parênteses nas tabelas; nenhum id interno.

### Decisões de implementação

- Valores das premissas legíveis: listas de disciplinas pelo nome, tipos em
  português, true/false como Sim/Não, `internship_match` como "exige Estágio
  I e II" / "basta um dos estágios". A chave da premissa aparece entre
  crases ao lado da descrição, para o aluno localizá-la na barra lateral.
- A descrição de `internship_match` em `assumptions.csv` contém "all_of" e
  "any_of"; o arquivo exportado reproduz a descrição como está nos dados.
- Pré-requisitos já cumpridos pelo histórico aparecem como "(já cumprido)";
  alternativas como "[A] ou [B]"; pré-requisito TBD como "a definir pela
  coordenação".

### Pendências

- A tarefa 5 (parser do PDF) ainda não tem especificação.
- As pendências de `data/pending_issues.csv` continuam abertas.

## 2026-11-04 — Escopo final: etapa 0 (CLAUDE.md) e etapa a (dados e validador)

### O que foi feito

- `CLAUDE.md` reescrito para o escopo final (`docs/escopo_final.md`): objetivo
  sem planejamento nem previsão; regras de conversão 1 a 6 e regras de horas;
  saíram calendário, oferta, limites por período e as especificações das
  tarefas 3 e 4; novas tabelas de dados (destinos, pedidos possíveis,
  premissas), pendências novas, Roteiro com as etapas a–g e especificações
  resumidas das etapas b–f. Exceção documentada para ler
  `materials/historico_exemplo.pdf` só para entender o layout.
- `data/`: eq13 só com o Estágio I (`any_of`); eq14 removida; apelidos
  `proposed` passaram a `active`; Econometria com pré-requisito `reg1`; novos
  `old_course_destinations.csv` (15 linhas) e `request_options.csv` (3 linhas);
  `assumptions.csv` com as 7 premissas do escopo; `pending_issues.csv` com as
  8 pendências novas (as resolvidas saíram).
- `app/data_loader.py`: tipos `OldCourseDestination` e `RequestOption`.
- `scripts/validate_data.py`: número de colunas por linha; horas = créditos × 15;
  horas fixas + mínimo de optativas = 3.000 h nas duas grades; flexíveis no
  total de créditos esperado; valores permitidos (`match`, `status`,
  `destination`); códigos e alvos de destinos e pedidos; premissas
  obrigatórias presentes; toda disciplina de 2013 com exatamente um destino
  pelas regras 1 a 5.
- Removidos `app/plan_check.py` e `tests/test_plan_check.py`. Testes de
  `rules`, `export` e `streamlit_app` com `skip` de módulo até as etapas b, e, d.
  Total: 25 testes passando, 3 módulos pulados.

### Decisões tomadas (aprovadas pelo usuário)

1. Pedidos possíveis em `request_options.csv` (`target` = id de 2026 ou
   `extension`); eq14 removida.
2. Estágio II com `destination = none` em `old_course_destinations.csv`; conta
   como perdido, e o resumo separa quanto pode ser recuperado por pedido.
3. Sucessoras não ocupam destino (Econometria I e II contam as duas); a regra 6
   vale só para equivalências e apelidos.
4. Disputa de destino: ganha o primeiro código de `source_codes` (nos apelidos,
   o `alias_of`). Tópicos enchem na ordem das regras 4, 5, 6 e do fluxograma,
   com perda parcial. Optativas acima do limite: perdem primeiro as sem
   ênfase, depois as da ênfase com menos horas.
5. Linhas CF do histórico vão para Tópicos (regra 5); outras fora da grade 2013
   são "não reconhecidas".
6. "Cerca de N disciplinas" arredondado para cima; sem período de ingresso;
   só destinos `assumed` editáveis; pré-requisitos mantidos só no validador.
7. Ênfases do CLAUDE.md conferidas pelo usuário com a seção 7.1.2: sem mudança.

### Decisões de implementação

- Notas dos CSVs não podem conter `;` (o validador agora acusa linhas com
  colunas a mais); usei vírgula.
- Acrescentei a etapa g (Dockerfile e deploy), que era a antiga tarefa 6.

### Pendências

- As 8 de `data/pending_issues.csv`.
- Para a etapa b: quantas horas do Estágio II contam como "recuperáveis
  mediante pedido" (180 h inteiras, ou limitadas pela extensão que falta?).

## 2026-11-04 — Escopo final: etapa b (motor de conversão e resumo)

### O que foi feito

- `app/conversion.py` (substitui `app/rules.py`, removido com
  `tests/test_rules.py`): `convert(history, overrides, destination_overrides)`
  aplica as regras 1 a 6 e as regras de horas. Entrada: códigos ou
  `HistoryEntry` (código, nome, horas, tipo SIGAA, para linhas de fora da grade
  2013 vindas do PDF). Saída `ConversionResult` (JSON): uma linha por
  disciplina (regra, destino, CH, aproveitada, perdida, motivo, observação),
  totais por categoria de 2026, horas por ênfase, obrigatórias pendentes na
  ordem do fluxograma, pedidos possíveis, horas recuperáveis, extensão além
  das 3.000 h, cenário "não migrar", premissas e destinos usados.
- `app/summary.py`: `build_summary(result)` com faltam (h, cr e "equivale a /
  cerca de N disciplinas de 60 h"), aproveitamento em %, "Perdido: X h, das
  quais até Y h podem ser recuperadas mediante pedido (quantidade a definir
  pela coordenação)", lista do não aproveitado, tabela por categoria, ênfases,
  pedidos, linha do "não migrar" e avisos.
- Premissa nova `internship2_recoverable_max_hours = 180` (assumed), exigida
  pelo validador; pendência do Estágio II passou a apontar para ela.
- Testes: `tests/test_conversion.py` (29) e `tests/test_summary.py` (10).
  Total: 63 passando, 2 módulos pulados (export e streamlit_app).

### Decisões tomadas (aprovadas pelo usuário)

- Estágio II conta como perdido; até `internship2_recoverable_max_hours` é
  mostrado como recuperável mediante pedido.

### Decisões de implementação

- Horas recuperáveis = perdas do cenário base − perdas com todos os pedidos
  concedidos (conversão rodada duas vezes). Assim entram também as horas de
  Tópicos liberadas quando Cálculo Numérico vira Métodos de Otimização. No
  cenário com pedidos, o Estágio II conta como flexível extensionista (até a
  premissa e até as 180 h da categoria) e uma disciplina com pedido para uma
  disciplina de 2026 ocupa o destino só se ele estiver livre.
- Ordem das linhas e do preenchimento: ordem de `curriculum_2013.csv`
  (fluxograma: obrigatórias por período, optativas, flexíveis); disciplinas
  de fora da grade 2013 no fim, na ordem de entrada.
- Disciplina que vira optativa de 2026 pelo mesmo código (ex.: Demografia I)
  entra no limite de optativas com a ênfase da disciplina de 2026.
- Percentual: horas aproveitadas ÷ horas aprovadas reconhecidas (as "não
  reconhecidas" ficam fora do denominador), arredondado ao inteiro.
- Extensão além das 3.000 h: horas de extensão que faltam menos o que ainda
  cabe (obrigatórias extensionistas pendentes, flexíveis extensionistas que
  faltam e espaço restante em optativas).
- Cenário "não migrar": horas por tipo da grade 2013 (cada categoria limitada
  ao exigido); linhas CF de fora da grade contam como flexíveis.
- Destinos `confirmed` não podem ser sobrescritos (ValueError).
- `all_of` continua suportado (nenhuma regra atual usa), com teste.

### Pendências

- O exemplo do escopo ("Probabilidade III + Cálculo Numérico + Python
  excedente") chama de excedente o Python, mas pela decisão 5 quem ocupa
  Linguagem de Programação para Ciência de Dados é o Python (primeiro código
  de `source_codes`) e o excedente é Introdução aos Softwares Estatísticos.
- O Estágio II recuperado como extensão foi tratado como flexível
  extensionista (reduz o "Faltam"); confirmar.

## 2026-11-04 — Etapa b: ajustes da revisão

- Aprovado: Python ocupa Linguagem de Programação para Ciência de Dados e o
  excedente é Introdução aos Softwares; Estágio II recuperado como flexível
  extensionista (Resolução 04/2026, Art. 11), contando também na linha de
  Extensão (teste novo).
- Não reconhecidas continuam fora do percentual; o resumo ganhou
  `used_note` ("Não entram no cálculo X h de disciplinas não reconhecidas na
  grade 2013.") e `unrecognized_hours`.
- Conferência com dois casos reais do usuário (15 e 20 disciplinas): todos os
  números bateram sem correção; viraram testes em `tests/test_summary.py`.
  Total: 67 testes passando, 2 módulos pulados.

## 2026-11-04 — Etapa b: frase dos pedidos; etapa c: parser do PDF

### O que foi feito

- Resumo: linha principal "Perdido: X h, das quais até Y h podem ser
  recuperadas mediante pedido:" seguida de uma linha por pedido
  ("<disciplina> como <destino>: [até ]N h, <condição>."). Nova coluna
  `condition` em `request_options.csv`. O motor calcula as horas recuperáveis
  de cada pedido (só aquele concedido) além do total Y (todos concedidos);
  pedidos para o mesmo destino não se somam (teste).
- `app/history_pdf.py`: `parse_history(bytes ou arquivo, include_in_progress)`
  com pdfplumber em memória. Regex por linha; só APROVADO conta (uma vez);
  MATRICULADO só com a opção (e ignorado se já aprovado); situações
  desconhecidas geram aviso; conferência do currículo (rótulo `Currículo:`) e
  da linha "Integralizado" da TOTALIZAÇÃO; saída com `HistoryEntry` pronta
  para `convert`. Nada além das linhas de disciplina, do currículo e da
  totalização é guardado.
- `tests/fixtures/make_history_pdf.py`: histórico fictício de três páginas
  (página 1 com dados pessoais inventados), gerado em memória com fpdf2.
- `tests/test_history_pdf.py` (26 testes). Total: 94 passando, 2 módulos
  pulados. `requirements.txt`: pdfplumber e fpdf2.
- Conferência em `materials/historico_exemplo.pdf` (só totais): OB 840 h,
  OP 60 h (900 h), 5 disciplinas em curso, TOTALIZAÇÃO bateu.

### Decisões de implementação

- O layout foi lido com o texto mascarado (só palavras dos nomes das
  disciplinas e termos do SIGAA ficaram visíveis); nada do exemplo entrou no
  repositório.
- Colunas da TOTALIZAÇÃO mapeadas para OB, CO, OP e CF; EC e EQ não entram
  na conferência.
- Nome, horas e tipo SIGAA vêm do PDF; para disciplinas da grade 2013 o motor
  usa as horas da grade.

### Pendências

- O exemplo não tem a página 1, então o rótulo do currículo não foi visto no
  layout real; com o exemplo, o parser avisa "Não foi possível conferir o
  currículo".
- Linhas EQ (componente equivalente) e EC (extracurricular): como contam na
  TOTALIZAÇÃO? Sem exemplo, ficam fora da conferência.
- Nomes longos que quebrem em duas linhas no PDF não foram vistos no exemplo;
  a linha quebrada seria ignorada e a conferência da TOTALIZAÇÃO acusaria.

## 2026-11-04 — Etapa c: ajustes da revisão; etapa d: interface

### O que foi feito

- Parser: o currículo é conferido pela presença de `232013` em qualquer lugar
  do PDF (`curriculum_found`), porque a extração pode separar rótulo e valor;
  linhas EQ e EC aprovadas geram aviso com a lista e a orientação de consultar
  a coordenação (continuam fora da conferência). Fixture com
  `extra_page_lines`; testes novos.
- `app/streamlit_app.py` reescrito para o escopo final:
  - entrada pelo PDF (preenche a tabela) e opção "Incluir disciplinas em curso
    (supondo aprovação)", desmarcada, que acrescenta ou retira só as linhas
    em curso, preservando as correções;
  - tabela única agrupada por período do fluxograma de 2013, Optativas,
    Flexíveis e "Não reconhecidas na grade 2013" (só se houver), com inclusão,
    remoção e total de horas por grupo; atalho "marcar obrigatórias até o
    período N" e "Limpar tabela";
  - resumo: faltam, aproveitamento (com a nota das não reconhecidas),
    não aproveitado com as linhas de pedido e a lista, tabela por categoria,
    obrigatórias pendentes, ênfases, pedidos possíveis em destaque, linha do
    "não migrar" e avisos (perda em vermelho);
  - tabela de conversão agrupada como a entrada, linhas com perda destacadas;
  - barra lateral: premissas supostas editáveis (confirmadas fixas) e
    "Disciplinas extintas: Tópicos ou optativa" (só as supostas editáveis);
  - rodapé fixo. Sem exportação (etapa e).
- `tests/test_streamlit_app.py` reescrito (19 testes: AppTest e funções de
  estado). Total: 115 passando, 1 módulo pulado (export).

### Decisões de implementação

- O AppTest não simula envio de arquivo: o preenchimento pelo PDF fica em
  funções puras (`apply_parsed`, `sync_in_progress`) testadas diretamente.
- Enviar um novo PDF substitui a tabela inteira; o mesmo arquivo não é
  relido a cada interação (controle por `file_id`).
- Do PDF só ficam na sessão as linhas de disciplina e um relatório (contagens,
  horas, avisos); o arquivo não é gravado.
- `main()` só roda com `__name__ == "__main__"` (como o Streamlit executa),
  para os testes poderem importar as funções.

### Pendências

- Não há inclusão manual de disciplina de fora da grade 2013 (ex.: flexível
  de outro curso); hoje ela só entra pelo PDF.

## 2026-11-05 — Etapa d2: reformulação de UX

### O que foi feito

- `app/streamlit_app.py` reorganizado em quatro etapas (Seu histórico,
  Resumo, Disciplinas, Conversar com IA), com barra de progresso e botões
  clicáveis no topo e "Voltar"/"Próximo" no fim. As etapas 2 a 4 só liberam
  com ao menos uma disciplina; histórico vazio volta à etapa 1.
- Entrada: cada disciplina é um item com borda (nome; "Código · Tipo · CH";
  botão ✕), em contêiner horizontal, sem `st.columns`. Opção "Flexível de
  outro curso" com nome e horas editáveis (linha CF, código `MANUAL-n`
  exibido como "—"). "Limpar tabela" virou "Limpar lista".
- Resumo: métricas em contêiner horizontal (2 + 1 em 360 px); lista do
  perdido e obrigatórias pendentes foram para a etapa 3; a barra lateral saiu
  e as regras supostas estão no expander "Simular regras ainda não
  confirmadas".
- Disciplinas: Aproveitadas, Perdidas (com pedidos e a sublista "Não
  reconhecidas") e A cursar ("Ficaram para trás" / "Próximos períodos"),
  campo "Em que período você está?" e expander "Ver tabela completa".
- Etapa 4: título e "Em breve".
- `requirements.txt` (streamlit, pdfplumber, pandas) e `requirements-dev.txt`
  (`-r requirements.txt`, pytest, fpdf2); README com instalação.
- `tests/test_streamlit_app.py`: 27 testes. Total: 123 passando, 1 módulo
  pulado (export).
- Capturas em 360 px de largura (Chromium headless via Playwright, num venv
  temporário fora do repositório) de todas as etapas.

### Decisões

- Período atual padrão = período mais avançado com obrigatória (ou estágio/
  TCC) aprovada + 1, no máximo 8; as em curso contam quando a opção está
  marcada (decisão do usuário).
- O Streamlit apaga o estado de widget não exibido; as escolhas que precisam
  sobreviver à troca de etapa ficam em `st.session_state["saved"]` e são
  devolvidas ao widget quando ele reaparece.
- Disciplina aproveitada em parte aparece em Aproveitadas e em Perdidas.

### Pendências

- A etapa e deve omitir o código `MANUAL-n` das flexíveis manuais.

## 2026-11-05 — Etapa d2: ajustes da revisão

### O que foi feito

- Envio do PDF: botão "Enviar o PDF do histórico do SIGAA" abre o diálogo de
  autorização (texto do usuário); o envio só aparece depois de "Autorizo e
  quero enviar" (`pdf_authorized` na sessão). Depois do envio: "Arquivo
  carregado: <nome>" e "Remover arquivo e limpar lista" (zera a lista e cria
  um novo `file_uploader`, com outra chave).
- A caixa "Incluir disciplinas em curso" saiu: pergunta com "Sim, incluir" /
  "Não" quando o PDF tem linhas MATRICULADO; linha "Disciplinas em curso:
  incluídas / não incluídas" com "Alterar" nas etapas 1 a 3.
- Trocar de etapa volta ao topo (script único por troca, com
  `st.html(..., unsafe_allow_javascript=True)`); interações comuns não mexem
  na rolagem.
- Barra com rótulos curtos e CSS compacto no celular (cabe em uma linha em
  360 px); título menor no celular.
- Resumo: cartões com legenda (sem repetir o número), largura total no
  celular e lado a lado na tela grande; categorias em linhas, tabela no
  expander; pedidos só no quadro azul.
- Disciplinas: "Aproveitadas" em linhas "2013 → 2026 (CH)", com "N de M h"
  quando o aproveitamento é parcial.
- Grupos de período vazios recolhidos em expanders.
- Testes: 32 em `tests/test_streamlit_app.py` (autorização, arquivo
  carregado, remover arquivo, pergunta das em curso, grupos recolhidos,
  volta ao topo). Total: 128 passando, 1 módulo pulado.
- Capturas em 360 px e 1280 px de todas as etapas, com o histórico fictício
  dos testes enviado pelo navegador.

### Decisões

- Os botões do diálogo usam callback: assim a autorização vale também no
  AppTest, que não reexecuta o diálogo sozinho.
- O nome do arquivo fica só na sessão e só é mostrado ao próprio aluno.

### Pendências

- O nome do arquivo pode conter dados pessoais (resolvido nos ajustes finais).

## 2026-11-05 — Etapa d2: ajustes finais

### O que foi feito

- O nome do arquivo não é mais guardado nem exibido: "Arquivo carregado:
  histórico do SIGAA (PDF)" (o nome padrão do SIGAA traz a matrícula).
- "Aproveitadas": destino optativo mostra a natureza ("optativa · <ênfase>"
  ou "optativa sem ênfase"), inclusive nas sucessoras; optativa da regra 4
  sem disciplina específica aparece como "Optativa sem ênfase (60 h)".
- "Perdidas" em itens: "<disciplina>: N h perdidas, <motivo>"; não
  reconhecidas em itens. Motivo da redução de carga horária reescrito em
  `app/conversion.py`: "Redução de carga horária (o novo <disciplina> tem
  N h)."
- Parser: DISPENSADO conta como aprovado; CANCELADO é ignorado sem aviso.
  Fixture: Demografia I DISPENSADO (TOTALIZAÇÃO 600 h) e uma situação
  desconhecida inventada (INDEFERIDO) no lugar do CANCELADO.
- Total: 130 testes passando, 1 módulo pulado (export).

### Decisões

- Nas optativas, a CH entra no mesmo parêntese da natureza
  ("(optativa · … · 60 h)"), para todas as linhas mostrarem a CH.
