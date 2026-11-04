# Escopo final do app — especificação para o Claude Code

Definido com a coordenação em 27/10/2026 e refinado depois. Este documento
substitui as especificações das tarefas 3, 4 e 5 do `CLAUDE.md`.

## Objetivo

O aluno informa o histórico da grade 2013 e vê, para a migração ao novo PPC:

1. quantos créditos e horas faltam para concluir;
2. o percentual do que já cursou que é aproveitado;
3. a lista do que **não** é aproveitado (e por quê);
4. as obrigatórias do novo PPC que ainda precisa cursar.

**O app não faz previsão nem planejamento.** Isso é responsabilidade do aluno.

## O que sai do projeto

- `app/plan_check.py`, os blocos de plano da interface e seus testes.
- Regras de oferta e de limite por período (paridade, every_term_*,
  transition_every_term_ids, max_credits_*, first_planning_term).
- O código removido fica no histórico do git.

## Fluxo da tela

1. **Entrada do histórico**, de duas formas:
   - envio do PDF do histórico do SIGAA (parser preenche a tabela);
   - preenchimento manual na mesma tabela.
   A tabela é única, no estilo do histórico do SIGAA, agrupada pelo período do
   fluxograma de 2013 (obrigatórias) e depois "Optativas" e "Flexíveis", com
   linha de inclusão e botão de remover em cada linha. Mantém o atalho
   "marcar obrigatórias até o período N". Depois do envio do PDF, o aluno pode
   corrigir a tabela.
2. **Resumo em destaque** (o que a coordenação pediu): ver seção "Resumo".
3. **Tabela de conversão**, no estilo do histórico: ver seção "Tabela de conversão".
4. **Exportar para conversar com uma IA**: ver seção "Exportação".
5. Rodapé fixo: "Simulação baseada nas regras disponíveis; não substitui a
   orientação da coordenação."

## Regras de conversão (de cada disciplina aprovada da grade 2013)

Aplicar nesta ordem. Cada disciplina tem um único destino.

1. **Mesmo código na grade 2026** (considerando os apelidos de código): vira a
   disciplina de 2026. Se for optativa, entra na ênfase indicada na tabela de
   ênfases de 2026 (ou sem ênfase).
2. **Equivalência** (`equivalences.csv`): vira a obrigatória de 2026.
3. **Sucessora** (`elective_successors.csv`): conta como optativa da ênfase da
   sucessora.
4. **Destino definido em `old_course_destinations.csv`**: optativas que deixam
   de existir e obrigatórias sem equivalência (ver Dados).
5. **Tópicos Especiais de 2013 (I a IV)**: vão para Tópicos Especiais (flexível
   não extensionista).
6. **Destino já ocupado**: se duas disciplinas de 2013 levam à mesma disciplina
   de 2026 (ex.: Programação Estatística com Python e Introdução aos Softwares
   Estatísticos → Linguagem de Programação para Ciência de Dados), uma ocupa o
   destino e a outra vai para Tópicos Especiais.

**Horas aproveitadas e perdidas:**

- Disciplina que vira obrigatória, estágio ou TCC de 2026 aproveita no máximo a
  carga horária da disciplina de 2026; o excedente é perdido (ex.: Estágio
  Supervisionado I, 180 h → Estágio Supervisionado, 120 h: perde 60 h).
- **Tópicos Especiais**: tudo o que vai para Tópicos compartilha um limite único
  de `topics_max_hours` (120 h). O excedente é perdido.
- **Optativas**: limite de `electives_max_hours` (660 h). O excedente é perdido.
- **Estágio Supervisionado II**: não é contado automaticamente. Aparece em
  "possíveis aproveitamentos mediante pedido" (como horas de extensão).
- **Cálculo Numérico e Programação Matemática**: seguem o destino da regra 4 e
  aparecem também em "possíveis aproveitamentos mediante pedido" (como Métodos
  de Otimização e Aplicações).
- **Pesquisa de Mercado** cursada em 2013 vira a obrigatória de 2026 e conta
  60 h de extensão.

## Dados

### Mudanças em arquivos existentes

- `equivalences.csv`: a regra do Estágio passa a ter como origem **só o
  Estágio Supervisionado I**, com `match` any_of e status active.
- `code_aliases.csv`: os três apelidos `proposed` (Introdução à Inferência
  Bayesiana, Funções de uma Variável Complexa e Libras) passam a `active`.
- `prerequisites_2026.csv`: o pré-requisito "Regressão" de Econometria é
  Regressão I (remover o TBD).
- `curriculum_2026.csv`: confirmar que a ênfase de cada optativa segue a tabela
  da seção 7.1.2 da Resolução 41/2026 (já está no `CLAUDE.md`).
- `pending_issues.csv`: remover o que foi resolvido; incluir as novas pendências
  (ver "Pendências").

### Novo arquivo `old_course_destinations.csv`

Colunas: `code;destination;status;note`.
`destination`: `topics` (Tópicos Especiais) ou `elective:EAM` / `elective:CD` /
`elective:none`. `status`: `confirmed` ou `assumed`.

| code | disciplina (2013) | destination | status | note |
| --- | --- | --- | --- | --- |
| 1108197 | Probabilidade III | topics | confirmed | obrigatória sem equivalência |
| GDCOC0072 | Cálculo Numérico | topics | confirmed | possível Métodos de Otimização mediante pedido |
| 1103153 | Matemática Elementar I | topics | assumed | optativa extinta |
| 1103142 | Introdução à Análise Real (90 h) | topics | assumed | optativa extinta |
| 1108128 | Análise de Dados Categorizados | topics | assumed | optativa extinta |
| 1108150 | Introdução à Teoria dos Grafos | topics | assumed | optativa extinta; perguntado se cabe Network Analysis |
| 1108162 | Programação Matemática | topics | assumed | optativa extinta; possível Métodos de Otimização mediante pedido |
| 1108198 | Fundamentos em Bancos de Dados Estatísticos | topics | assumed | optativa extinta (nunca ofertada) |
| 1108209 | Processos Estocásticos II | topics | assumed | optativa extinta |
| 1108212 | Análise Estatística de Dados Ecológicos | topics | assumed | optativa extinta |
| 1108213 | Introdução à Gestão de Projetos | topics | assumed | optativa extinta |
| 1108214 | Simulação | topics | assumed | optativa extinta; perguntado se cabe Modelagem e Simulação em CD |
| 1108215 | Ensaios Biológicos | topics | assumed | optativa extinta |
| 1108217 | Introdução à Análise de Dados Longitudinais | topics | assumed | optativa extinta |

Controle Estatístico de Qualidade (obrigatória de 2013) já está em
`elective_successors.csv` (→ Controle Estatístico de Processos, ênfase EAM).

### Premissas (`assumptions.csv`)

Remover as de planejamento e oferta. Manter ou criar:

| key | value | status | description |
| --- | --- | --- | --- |
| start_term | 2027.1 | confirmed | Início do novo PPC |
| migrant_extension_hours | 300 | confirmed | Horas de extensão exigidas de quem migra |
| old_pm_counts_as_extension | true | confirmed | Pesquisa de Mercado de 2013 conta 60 h de extensão |
| topics_max_hours | 120 | assumed | Limite único de horas para tudo o que vai para Tópicos Especiais |
| electives_max_hours | 660 | assumed | Optativas acima desse limite são perdidas |
| consultoria_emphasis | EAM | assumed | Ênfase de Consultoria Estatística (não consta na tabela de ênfases) |
| emphasis_min_hours | 360 | confirmed | Horas mínimas em optativas da mesma ênfase para o diploma com ênfase |

O destino de cada disciplina extinta fica em `old_course_destinations.csv`,
não em premissas. A barra lateral mostra as premissas `assumed` e permite
alterá-las; o destino das disciplinas extintas pode ser alterado numa seção
da barra lateral ("Disciplinas extintas: Tópicos ou optativa").

## Parser do PDF (`app/history_pdf.py`)

- `pdfplumber`, lendo o arquivo em memória (BytesIO). Nunca gravar o PDF.
- Linhas da tabela: código, nome, carga horária, tipo (OB, OP, CO, CF, EC, EQ),
  semestre/turma/nota (opcionais) e situação. Regex por linha; ignorar o resto.
- Contam as linhas com situação **APROVADO**. Uma disciplina aprovada uma vez
  conta uma vez, mesmo com reprovações anteriores.
- Caixa "Incluir disciplinas em curso (supondo aprovação)", **desmarcada** por
  padrão: inclui as linhas com situação MATRICULADO.
- Situações desconhecidas (diferentes de APROVADO, REPROVADO, REP. FALTA,
  TRANCADO, MATRICULADO, PENDENTE) geram aviso com a lista.
- Conferir "Currículo: 232013"; se for outro, avisar que o app vale só para a
  grade 2013.
- Conferir as horas aprovadas por tipo com a tabela "TOTALIZAÇÃO"
  (linha "Integralizado"); se não bater, avisar que a leitura pode ter falhado.
- **Dados pessoais**: nunca extrair, exibir ou registrar nome, matrícula, CPF,
  filiação ou data de nascimento. Nada do PDF vai para log.
- O exemplo real está em `materials/historico_exemplo.pdf` (só as páginas 2 e
  3; o PDF verdadeiro tem uma página 1 de dados pessoais). Use-o só para
  entender o layout. Os testes usam um **histórico fictício de três páginas**
  (com página 1 de dados inventados), gerado por script em `tests/fixtures/`.
  Nenhum dado do exemplo real entra no repositório.

## Resumo (em destaque, no topo do resultado)

Para o cenário "migrar":

- **Faltam**: horas e créditos para concluir (3.000 h / 200 cr menos o
  aproveitado), com a observação "equivale a N disciplinas de 60 h"
  (1 crédito = 15 h; disciplina padrão = 60 h = 4 créditos). Quando não for
  exato, "cerca de N".
- **Aproveitamento**: horas aproveitadas ÷ horas aprovadas na grade 2013, em %.
- **Não aproveitado**: total de horas perdidas e a lista (disciplina, horas
  perdidas, motivo: excedente de Tópicos, excedente de optativas, redução de
  carga horária do estágio, etc.).
- Tabela por categoria do novo PPC: exigido / aproveitado / falta
  (obrigatórias, estágio, TCC, optativas, Tópicos Especiais, flexíveis
  extensionistas, extensão).
- Obrigatórias do novo PPC que faltam cursar, pelo nome, na ordem do fluxograma.
- Ênfase: horas em Estatística Aplicada e Modelagem e em Ciência de Dados,
  frente ao mínimo de 360 h.
- **Possíveis aproveitamentos mediante pedido à coordenação** (Estágio II como
  extensão; Cálculo Numérico ou Programação Matemática como Métodos de
  Otimização), em destaque separado, sem entrar nas contas.
- Uma linha de comparação: quantas horas faltam se **não** migrar (pelas
  exigências da grade 2013).

Se houver perda de horas, mostrar um aviso bem visível com o total perdido.

## Tabela de conversão

No estilo do histórico do SIGAA, agrupada como a entrada (períodos do
fluxograma de 2013, depois optativas e flexíveis). Colunas: Código, Disciplina
(2013), CH, Na grade 2026 (disciplina ou categoria de destino), CH aproveitada,
CH perdida, Observação. Linhas com perda ficam destacadas.

## Exportação para IA (`app/export.py`)

Adaptar ao novo escopo, mantendo as regras atuais (sem dados pessoais,
disciplinas pelo nome, nenhum id interno). Seções: contexto e regras de
conversão, premissas usadas, tabela de conversão, resumo, não aproveitado,
possíveis aproveitamentos mediante pedido, obrigatórias que faltam, optativas
disponíveis no novo PPC (com ênfase) e instruções para a IA:

- explicar ao aluno, em linguagem simples, o que ele aproveita, o que perde e o
  que falta, e ajudá-lo a pensar nas escolhas;
- não inventar disciplinas, regras ou equivalências;
- sinalizar o que depende de decisão ou pedido à coordenação.

Ao lado do botão de download, links para abrir uma IA (Claude:
https://claude.ai/new, ChatGPT: https://chatgpt.com, Gemini:
https://gemini.google.com) com a orientação: "Anexe o arquivo baixado e
pergunte o que quiser."

## Parecer da IA (última etapa)

Só depois que conversão, parser, resumo e exportação estiverem prontos.

- Botão "Gerar parecer" abaixo do resumo; a chamada só acontece no clique.
- Prompt: o mesmo conteúdo do arquivo exportado (sem dados pessoais), com a
  instrução de explicar em linguagem simples o que é aproveitado, o que é
  perdido e por quê, e o que falta. **Não repetir números**: os valores ficam
  no resumo. Não inventar disciplinas, regras ou equivalências; sinalizar o que
  depende da coordenação.
- Provedores com fallback (Gemini como principal, Groq como reserva), via SDK
  `openai` e endpoints compatíveis. Chaves em variáveis de ambiente
  (`GEMINI_KEY`, `GROQ_KEY`, `GEMINI_MODEL`, `GROQ_MODEL`); no Streamlit
  Community Cloud, em `st.secrets`. Nunca no código.
- Cache em memória pelo hash do resultado da conversão (perfis iguais recebem
  o mesmo parecer sem nova chamada).
- Se todos os provedores falharem: "Não foi possível gerar o parecer agora.
  O resultado acima continua válido."
- Validação simples: toda disciplina citada no parecer deve existir nos dados;
  se não existir, descartar o parecer e mostrar a mensagem de falha.
- Textos fixos da tela:

  > **Atenção:** este parecer foi gerado por um LLM (IA). Como estudante de
  > Estatística, você sabe que esses modelos são probabilísticos e podem
  > produzir informações incorretas, as chamadas alucinações. Use-o como
  > apoio, não como verdade absoluta: os números que valem são os do resumo
  > acima, e as decisões finais são da coordenação.

  > **Quer explorar mais?** Baixe o arquivo abaixo e anexe-o numa conversa com
  > a IA de sua preferência. Ele não contém seus dados pessoais.

- Testes com a chamada à API simulada (mock): sucesso, falha de todos os
  provedores, cache e parecer descartado por citar disciplina inexistente.

## Testes mínimos

- Parser: histórico fictício com reprovação seguida de aprovação, trancamento,
  matriculadas (com e sem a caixa marcada), situação desconhecida e
  totalização que bate e que não bate.
- Conversão: Estágio I (perde 60 h); Estágio II (só aparece como pedido);
  Python e Introdução aos Softwares juntas (uma vai para Tópicos);
  Probabilidade III + Cálculo Numérico + Python excedente = 180 h em Tópicos
  (60 h perdidas); optativa extinta; sucessora; apelido de código; optativas
  acima de 660 h; Pesquisa de Mercado contando extensão.
- Resumo: percentual, faltam, "equivale a N disciplinas de 60 h".
- Exportação: seções, nenhum dado pessoal, nenhum id interno.

## Pendências (aguardando a coordenação)

- Destino das optativas extintas (Tópicos ou optativa, e qual ênfase) e se
  Teoria dos Grafos e Simulação podem ser aproveitadas como Network Analysis e
  Modelagem e Simulação em Ciência de Dados.
- Qual disciplina pode ser aproveitada para Métodos de Otimização, e se é
  automático ou por pedido.
- Se o limite de 120 h dos Tópicos é único e compartilhado.
- Optativas acima de 660 h: perdidas?
- Quantas horas do Estágio II podem virar extensão.
- Ênfase de Consultoria Estatística.
