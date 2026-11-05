# CLAUDE.md — App de Migração do PPC (Estatística e Ciência de Dados, UFPB)

Este arquivo é o contexto do projeto para o Claude Code. Ele é a fonte de verdade
para dados curriculares, regras e tarefas. Responda sempre em português.

## Fluxo de trabalho no terminal 

```bash
cd ~/projetos/<repo>
source .venv/bin/activate
claude
```

No Claude Code, peça: `Execute a tarefa atual do CLAUDE.md.`
Depois de revisar o que foi feito:

```bash
python scripts/validate_data.py
pytest
git status        # confira que materials/ e .venv/ não aparecem
git add -A && git commit -m "<mensagem>"
git push
```

Ao concluir uma tarefa, marque-a como feita no Roteiro e atualize "Tarefa atual".

## Regras de trabalho (para o Claude Code)

- Antes de criar ou alterar arquivos, apresente o plano e os arquivos afetados.
- **Não invente dados curriculares.** Use somente as tabelas deste arquivo. Não
  corrija nem complete nada por conta própria.
- Valor incerto é escrito como `TBD` e registrado em `data/pending_issues.csv`.
- Código, nomes de arquivos, colunas, funções e variáveis em inglês. Textos
  exibidos ao aluno em português.
- Python com o venv `.venv`; dependências do app em `requirements.txt` e de
  desenvolvimento (testes) em `requirements-dev.txt` (`pip install -r requirements-dev.txt`).
- Depois de mudar `data/` ou código, rode `python scripts/validate_data.py` e `pytest`.
- Nunca leia, copie ou faça commit de `materials/` (documentos do PPC, fora do git)
  nem de `.env` (chaves de API). **Única exceção:** `materials/historico_exemplo.pdf`
  pode ser lido só para entender o layout do histórico do SIGAA; nenhum dado dele
  entra no repositório, nos testes ou nas respostas.
- Não implemente nada além da tarefa atual.
- Ao concluir uma tarefa, adicione uma entrada em docs/progress.md com data, o que foi
  feito, decisões tomadas e pendências. Nunca apague entradas anteriores.

## O projeto

App web para alunos de Estatística da UFPB decidirem se migram do PPC 2013 para o
novo PPC (Resolução CONSEPE 41/2026, curso de Estatística e Ciência de Dados). O
aluno envia o PDF do histórico do SIGAA (ou marca as disciplinas) e vê, para a
migração:

1. quantos créditos e horas faltam para concluir;
2. o percentual do que já cursou que é aproveitado;
3. a lista do que **não** é aproveitado (e por quê);
4. as obrigatórias do novo PPC que ainda precisa cursar.

**O app não faz previsão nem planejamento.** Isso é responsabilidade do aluno.
Especificação detalhada: `docs/escopo_final.md` (definida com a coordenação em
27/10/2026); as seções abaixo a resumem.

### Arquitetura

O núcleo é **determinístico**. A LLM só redige uma explicação do resultado já
calculado e nunca decide equivalências nem números.

1. Extração do histórico: `pdfplumber` + regex (layout do SIGAA é padronizado);
   preenchimento manual na mesma tabela como alternativa.
2. Motor de conversão: aplica as regras de conversão sobre os CSVs de `data/`.
3. Resumo: faltam, aproveitamento, não aproveitado, obrigatórias pendentes.
4. Parecer da LLM (opcional): recebe o resultado já calculado; se a API falhar, o
   aluno recebe só o resultado determinístico.

### Stack

Python, Streamlit, pdfplumber, pytest, SDK `openai` (Gemini como principal, Groq
como fallback, via endpoints compatíveis), Docker.
Chaves em variáveis de ambiente (`GEMINI_KEY`, `GROQ_KEY`, `GEMINI_MODEL`,
`GROQ_MODEL`); no Streamlit Community Cloud, em `st.secrets`.

### LGPD

- Processar o PDF em memória e descartar; nunca gravar o arquivo.
- Nunca extrair, exibir ou registrar nome, matrícula, CPF, filiação ou data de
  nascimento. Nada do PDF vai para log.
- Enviar à LLM só códigos e nomes de disciplinas, nunca dados do aluno.
- Cache, se houver, guarda só o hash do resultado da conversão e o texto do parecer.

### Estrutura do repositório

```
app/        código da aplicação
data/       CSVs curriculares (versionados)
docs/       escopo final e registro de progresso
scripts/    utilitários (validação etc.)
tests/      testes pytest
materials/  documentos do PPC (ignorado pelo git)
```

## Regras de conversão (decididas pela coordenação)

Aplicadas a cada disciplina aprovada da grade 2013, nesta ordem. Cada disciplina
tem um único destino.

1. **Mesmo código na grade 2026** (considerando os apelidos `active`): vira a
   disciplina de 2026. Se for optativa, entra na ênfase da disciplina de 2026
   (ou sem ênfase).
2. **Equivalência** (`equivalences.csv`, status `active`): vira a obrigatória de 2026.
3. **Sucessora** (`elective_successors.csv`): conta como optativa da ênfase da
   sucessora. Sucessora **não** ocupa destino: Econometria I e II contam as duas.
4. **Destino em `old_course_destinations.csv`**: optativas extintas e
   obrigatórias sem equivalência vão para Tópicos Especiais, para optativa
   (com ou sem ênfase) ou para nenhum destino (`none`).
5. **Tópicos Especiais de 2013 (I a IV)** e toda linha do histórico de tipo
   flexível (CF), mesmo com outro código: vão para Tópicos Especiais (flexível
   não extensionista).
6. **Destino já ocupado** (só equivalências e apelidos): se duas disciplinas de
   2013 levam à mesma disciplina de 2026 (ex.: Programação Estatística com Python
   e Introdução aos Softwares Estatísticos → Linguagem de Programação para
   Ciência de Dados), uma ocupa o destino e a outra vai para Tópicos Especiais.
   Ocupa o destino o primeiro código de `source_codes`; nos apelidos, o código
   de destino (`alias_of`).

Disciplina do histórico fora da grade 2013 (e que não seja flexível): aparece como
"não reconhecida", fora das contas, com aviso para consultar a coordenação.

**Horas aproveitadas e perdidas:**

- Disciplina que vira obrigatória, estágio ou TCC de 2026 aproveita no máximo a
  carga horária da disciplina de 2026; o excedente é perdido (ex.: Estágio
  Supervisionado I, 180 h → Estágio Supervisionado, 120 h: perde 60 h).
- **Tópicos Especiais**: tudo o que vai para Tópicos compartilha um limite único
  de `topics_max_hours`. Preenchimento na ordem das regras (4, 5, 6) e, dentro de
  cada regra, na ordem do fluxograma de 2013; perda parcial é permitida (ex.:
  90 h com 60 h livres: aproveita 60 h, perde 30 h).
- **Optativas**: limite de `electives_max_hours`; o excedente é perdido. Perdem
  primeiro as sem ênfase, depois as da ênfase com menos horas. As horas por
  ênfase são contadas depois do corte.
- **Estágio Supervisionado II**: não é contado automaticamente (conta como
  perdido). Aparece em "possíveis aproveitamentos mediante pedido" (como horas
  de extensão).
- **Cálculo Numérico e Programação Matemática**: seguem o destino da regra 4 e
  aparecem também em "possíveis aproveitamentos mediante pedido" (como Métodos
  de Otimização e Aplicações).
- **Pesquisa de Mercado** cursada em 2013 vira a obrigatória de 2026 e conta
  60 h de extensão (premissa `old_pm_counts_as_extension`).
- Os possíveis aproveitamentos mediante pedido (`request_options.csv`) nunca
  entram nas contas.

## Parâmetros da grade 2026

- Total: 200 créditos (3.000 h); 1 crédito = 15 h; duração de 8 a 12 períodos.
- Obrigatórias 120 cr; estágio 8 cr; complementares (TCC I e II) 8 cr;
  optativas no mínimo 44 cr; flexíveis 20 cr (Tópicos Especiais 8 cr +
  flexíveis extensionistas 12 cr).
- Ênfase: no mínimo 360 h (24 cr) em optativas da mesma ênfase; senão, generalista.
- Extensão: 300 h (Pesquisa de Mercado 60 h + flexíveis extensionistas 180 h +
  optativas extensionistas 60 h).
- O novo PPC entra em vigor em **2027.1** (a seção 8.3 do PPC diz 2026.1, mas a
  coordenação confirmou 2027.1). Ingressantes de 2027.1 em diante entram direto
  no novo PPC; veteranos escolhem migrar ou não.

## Parâmetros da grade 2013 (SIGAA, estrutura 232013)

- Total: 3.000 h (200 cr). Básicas profissionais 1.740 h (29 disciplinas);
  complementares obrigatórias 480 h (estágios I e II + TCC I e II);
  optativas no mínimo 540 h (36 cr); flexíveis 240 h (16 cr).
- Duração de 8 a 12 períodos.

## Especificação de `data/`

| Arquivo | Colunas |
| --- | --- |
| `curriculum_2026.csv` | id;code;name;credits;hours;type;semester;emphasis;extension |
| `prerequisites_2026.csv` | course_id;prerequisite_id;group |
| `curriculum_2013.csv` | id;code;name;credits;hours;type;semester |
| `prerequisites_2013.csv` | course_id;prerequisite_id;group |
| `equivalences.csv` | rule_id;source_codes;match;target_id;status;note |
| `code_aliases.csv` | code;alias_of;status;note |
| `elective_successors.csv` | code;successor_id;note |
| `old_course_destinations.csv` | code;destination;status;note |
| `request_options.csv` | code;target;condition;note |
| `assumptions.csv` | key;value;status;description |
| `pending_issues.csv` | file;record;field;description |

Convenções:

- `id`: identificador curto e estável definido por nós; o grafo usa sempre `id`.
  Cada grade tem seu próprio espaço de ids (`prob3` de 2013 ≠ `prob3` de 2026).
- `code`: código SIGAA, ou `NEW` quando a disciplina ainda não tem código.
- `type`: `mandatory`, `elective`, `flexible`, `internship` ou `complementary`.
- `emphasis`: `EAM` (Estatística Aplicada e Modelagem), `CD` (Ciência de Dados) ou vazio.
- `extension`: `true` para componentes extensionistas, senão `false`.
- `semester`: período sugerido no fluxograma (só obrigatórias); vazio nas demais.
- Pré-requisitos em formato longo: uma linha por par. `group` expressa "OU": o
  pré-requisito está cumprido se **todas** as linhas de **algum** grupo estiverem
  cumpridas. Sem alternativas, use `group = 1` em todas as linhas. O motor de
  conversão não usa pré-requisitos; os arquivos são mantidos e validados.
- `prerequisite_id` é um `id` da mesma grade ou, para componentes fora da grade,
  `code:<código SIGAA>` (ex.: `code:1107136`).
- `source_codes`: códigos separados por `|`. `match`: `any_of` (basta um) ou
  `all_of` (exige todos). `status`: `active` (só `active` é aplicado).
- `code_aliases.csv`: códigos diferentes da mesma disciplina (código antigo e
  atual). Ao ler um histórico, um código em `code` conta como `alias_of`.
  `status`: `active` ou `proposed` (só `active` é aplicado).
- `elective_successors.csv`: optativa (ou obrigatória) de 2013 sem equivalência
  cuja sucessora existe na grade 2026. `code` é o código SIGAA de 2013 e
  `successor_id` é o `id` da sucessora em 2026 (regra 3).
- `old_course_destinations.csv`: destino das disciplinas de 2013 sem
  correspondente (regra 4). `destination`: `topics` (Tópicos Especiais),
  `elective:EAM`, `elective:CD`, `elective:none` ou `none` (não aproveitada
  automaticamente). `status`: `confirmed` ou `assumed` (os `assumed` podem ser
  alterados na barra lateral).
- `request_options.csv`: possíveis aproveitamentos mediante pedido à coordenação.
  `code` é o código SIGAA de 2013; `target` é o `id` de 2026 ou `extension`
  (horas de extensão). `condition` é o texto da condição mostrado ao aluno.
  Nunca entram nas contas.
- `assumptions.csv`: regras e parâmetros lidos pelo código. `status`:
  `confirmed` ou `assumed`. **Nenhuma dessas regras pode ficar fixa no código**:
  o código lê sempre deste arquivo.
- Toda disciplina da grade 2013 tem exatamente um destino pelas regras 1 a 5
  (conferido pelo validador).
- Separador `;`, UTF-8, cabeçalho na primeira linha.

## Dados: grade 2026 — obrigatórias, estágio e TCC

Todas com 4 créditos e 60 h, exceto o estágio (8 cr, 120 h).
Fonte: Quadros 6 e 7 e ementas da Resolução 41/2026.

| id | code | name | sem | type | prerequisites |
| --- | --- | --- | --- | --- | --- |
| aevd | NEW | Análise Exploratória e Visualização de Dados | 1 | mandatory | — |
| calc1 | 1103177 | Cálculo Diferencial e Integral I | 1 | mandatory | — |
| cvga | 1103118 | Cálculo Vetorial e Geometria Analítica | 1 | mandatory | — |
| prob1 | NEW | Probabilidade 1 | 1 | mandatory | — |
| mtce | NEW | Metodologia do Trabalho Científico em Estatística | 1 | mandatory | — |
| pae | 1108192 | Pesquisa Aplicada à Estatística | 2 | mandatory | aevd |
| calc2 | 1103178 | Cálculo Diferencial e Integral II | 2 | mandatory | calc1, cvga |
| ial | 1103179 | Introdução à Álgebra Linear | 2 | mandatory | cvga |
| prob2 | NEW | Probabilidade 2 | 2 | mandatory | prob1, calc1 |
| lpcd | NEW | Linguagem de Programação para Ciência de Dados | 2 | mandatory | aevd |
| inf1 | 1108148 | Inferência Estatística I | 3 | mandatory | calc2, prob2 |
| calc3 | 1103232 | Cálculo Diferencial e Integral III | 3 | mandatory | calc2 |
| sedo | 1103180 | Séries e Equações Diferenciais Ordinárias | 3 | mandatory | calc2, ial |
| prob3 | NEW | Probabilidade 3 | 3 | mandatory | calc2, prob2 |
| lpe | NEW | Linguagem de Programação para Estatística | 3 | mandatory | aevd |
| inf2 | 1108149 | Inferência Estatística II | 4 | mandatory | inf1, prob3 |
| amo1 | 1108202 | Amostragem I | 4 | mandatory | aevd, inf1 |
| fbdbd | NEW | Fundamentos de Banco de Dados e Big Data | 4 | mandatory | aevd, lpcd |
| mes | NEW | Modelos Estocásticos e Simulação | 4 | mandatory | prob3, sedo |
| moa | NEW | Métodos de Otimização e Aplicações | 4 | mandatory | ial, inf1 |
| reg1 | 1108204 | Regressão I | 5 | mandatory | ial, inf2 |
| pe1 | 1108158 | Planejamento de Experimentos I | 5 | mandatory | amo1 |
| amv | NEW | Análise Multivariada | 5 | mandatory | ial, inf2 |
| pm | 1108156 | Pesquisa de Mercado (extension=true) | 5 | mandatory | pae, amo1 |
| ec | 1108143 | Estatística Computacional | 5 | mandatory | inf2, lpe |
| reg2 | 1108205 | Regressão II | 6 | mandatory | reg1 |
| st | 1108163 | Séries Temporais | 6 | mandatory | reg1 |
| amns | NEW | Aprendizagem de Máquina Não-Supervisionada | 6 | mandatory | amv |
| ams | NEW | Aprendizagem de Máquina Supervisionada | 6 | mandatory | reg1, lpcd |
| mnp | NEW | Métodos Não-Paramétricos | 6 | mandatory | ec |
| tcc1 | 1108355 | Trabalho de Conclusão de Curso I | 7 | complementary | mtce, reg1, amv |
| est | NEW | Estágio Supervisionado | 7 | internship | inf1 |
| tcc2 | 1108356 | Trabalho de Conclusão de Curso II | 8 | complementary | tcc1 |

Conferência: 30 obrigatórias × 4 = 120 cr. Códigos do TCC confirmados pelo SIGAA
(1108351/1108352 são Econometria I e II, não o TCC).

## Dados: grade 2026 — optativas

Todas com 4 créditos e 60 h. Ênfases conferidas com a seção 7.1.2 da
Resolução 41/2026. Consultoria Estatística não consta na tabela de ênfases: sua
ênfase vem da premissa `consultoria_emphasis`.

| id | code | name | emphasis | prerequisites |
| --- | --- | --- | --- | --- |
| amo2 | 1108216 | Amostragem II | EAM | amo1, reg1 |
| asob | 1108130 | Análise de Sobrevivência | EAM | inf2, reg1 |
| biom | 1108135 | Biometria | EAM | reg1 |
| cep | NEW | Controle Estatístico de Processos | EAM | inf1 |
| dem1 | 1108140 | Demografia I | EAM | aevd |
| dem2 | 1108141 | Demografia II | EAM | dem1 |
| econ | NEW | Econometria | EAM | reg1, st |
| geo | 1108146 | Geoestatística e Estatística Espacial | EAM | inf2 |
| pe2 | 1108159 | Planejamento de Experimentos II | EAM | pe1 |
| mat | NEW | Matrizes e Aplicações | EAM | ial, calc2 |
| tea | NEW | Tópicos em Estatística Aplicada | EAM | inf1, lpe |
| epdi | 1108142 | Estatística Aplicada ao Processamento Digital de Imagens | CD | inf1, lpe |
| fvd | NEW | Ferramentas de Visualização de Dados | CD | lpe, fbdbd |
| iacd | NEW | Inteligência Artificial para Ciência de Dados | CD | lpcd |
| iib | 1108153 | Introdução à Inferência Bayesiana | CD | prob2 |
| mscd | NEW | Modelagem e Simulação em Ciência de Dados | CD | mes, st |
| na | NEW | Network Analysis | CD | lpcd |
| paia | NEW | Programação Avançada em Inteligência Artificial | CD | lpcd, lpe |
| pln | NEW | Processamento de Linguagem Natural | CD | ams |
| pcd | NEW | Projeto de Ciência de Dados | CD | ams, amns |
| md | NEW | Mineração de Dados | CD | ams, amns |
| rndl | NEW | Redes Neurais e Deep Learning | CD | ams |
| tcd | NEW | Tópicos em Ciência de Dados | CD | lpcd |
| cons | NEW | Consultoria Estatística (extension=true) | — | lpe, reg1 |
| fuvc | 1103259 | Funções de uma Variável Complexa | — | calc3 |
| libras | GDLS0024 | Libras | — | — |
| po | 1108157 | Pesquisa Operacional | — | ial |
| prob4 | NEW | Probabilidade 4 | — | prob3, calc3, sedo |
| uce1 | NEW | UCE I – Programas e Projetos (extension=true) | — | — |
| uce2 | NEW | UCE II – Cursos, Oficinas e Eventos (extension=true) | — | — |

## Dados: grade 2026 — flexíveis

| id | code | name | credits | hours | extension |
| --- | --- | --- | --- | --- | --- |
| te1 | NEW | Tópicos Especiais em Estatística e Ciência de Dados I | 4 | 60 | false |
| te2 | NEW | Tópicos Especiais em Estatística e Ciência de Dados II | 4 | 60 | false |
| tee1 | NEW | Tópicos Especiais Extensionistas em Estatística e Ciência de Dados I | 6 | 90 | true |
| tee2 | NEW | Tópicos Especiais Extensionistas em Estatística e Ciência de Dados II | 6 | 90 | true |

## Dados: equivalências

Fonte: Quadro 8 da Resolução 41/2026 e escopo final. Disciplinas com o mesmo
código nas duas grades não entram aqui (regra 1).

| rule_id | source_codes | match | target_id | status | note |
| --- | --- | --- | --- | --- | --- |
| eq01 | 1108190 | any_of | aevd | active | Análise Exploratória de Dados |
| eq02 | 1108189 | any_of | mtce | active | Metodologia do Trabalho Científico |
| eq03 | 1108191 | any_of | prob1 | active | Probabilidade I |
| eq04 | 1108193 | any_of | prob2 | active | Probabilidade II |
| eq05 | 1108194 | any_of | lpe | active | Programação Aplicada à Estatística |
| eq06 | GDEST0105\|1108196 | any_of | lpcd | active | Prog. Estatística com Python ou Introdução aos Softwares Estatísticos |
| eq07 | 1108203 | any_of | prob3 | active | Probabilidade IV (a IV antiga vira a 3 nova) |
| eq08 | 1108208 | any_of | mes | active | Processos Estocásticos I |
| eq09 | 1108206 | any_of | amv | active | Análise Multivariada I |
| eq10 | 1108207 | any_of | amns | active | Análise Multivariada II |
| eq11 | 1108145 | any_of | mnp | active | Estatística Não-Paramétrica |
| eq12 | GDEST0106 | any_of | ams | active | Aprendizagem de Máquina |
| eq13 | 1108353 | any_of | est | active | Estágio Supervisionado I (o II não é equivalência, ver `request_options.csv`) |

A antiga eq14 (Cálculo Numérico → Métodos de Otimização, `proposed`) saiu: o
Cálculo Numérico vai para Tópicos (regra 4) e aparece como pedido possível.

## Dados: grade 2013 — obrigatórias, estágio e TCC

Fonte: estrutura curricular 232013 do SIGAA (fonte oficial; o PDF fica em
`materials/`). Todas com 4 cr e 60 h, exceto os estágios (12 cr, 180 h cada).
Cálculo Numérico tem 60 h (36 h aula + 24 h laboratório).

| id | code | name | sem | type | prerequisites |
| --- | --- | --- | --- | --- | --- |
| cvga | 1103118 | Cálculo Vetorial e Geometria Analítica | 1 | mandatory | — |
| calc1 | 1103177 | Cálculo Diferencial e Integral I | 1 | mandatory | — |
| mtc | 1108189 | Metodologia do Trabalho Científico | 1 | mandatory | — |
| aed | 1108190 | Análise Exploratória de Dados | 1 | mandatory | — |
| prob1 | 1108191 | Probabilidade I | 1 | mandatory | — |
| calc2 | 1103178 | Cálculo Diferencial e Integral II | 2 | mandatory | calc1, cvga |
| ial | 1103179 | Introdução à Álgebra Linear | 2 | mandatory | cvga |
| pae | 1108192 | Pesquisa Aplicada à Estatística | 2 | mandatory | aed |
| prob2 | 1108193 | Probabilidade II | 2 | mandatory | prob1, calc1 |
| prog | 1108194 | Programação Aplicada à Estatística | 2 | mandatory | — |
| sedo | 1103180 | Séries e Equações Diferenciais Ordinárias | 3 | mandatory | calc2, ial |
| calc3 | 1103232 | Cálculo Diferencial e Integral III | 3 | mandatory | calc2 |
| dem1 | 1108140 | Demografia I | 3 | mandatory | aed |
| inf1 | 1108148 | Inferência Estatística I | 3 | mandatory | calc1, prob2 |
| prob3 | 1108197 | Probabilidade III | 3 | mandatory | prob2, calc2 |
| inf2 | 1108149 | Inferência Estatística II | 4 | mandatory | inf1, prob3 |
| amo1 | 1108202 | Amostragem I | 4 | mandatory | inf1 |
| prob4 | 1108203 | Probabilidade IV | 4 | mandatory | sedo, calc3, prob3 |
| cn | GDCOC0072 | Cálculo Numérico | 4 | mandatory | grupo 1: sedo, prog — OU grupo 2: code:1107136 (Introdução à Programação, Dep. de Informática) |
| ceq | 1108139 | Controle Estatístico de Qualidade | 5 | mandatory | inf2 |
| ec | 1108143 | Estatística Computacional | 5 | mandatory | inf2, cn (o SIGAA lista 1103176, código antigo de Cálculo Numérico) |
| reg1 | 1108204 | Regressão I | 5 | mandatory | inf2 |
| amv1 | 1108206 | Análise Multivariada I | 5 | mandatory | inf2 |
| pest1 | 1108208 | Processos Estocásticos I | 5 | mandatory | prob4 |
| enp | 1108145 | Estatística Não-Paramétrica | 6 | mandatory | inf2 |
| plex1 | 1108158 | Planejamento de Experimentos I | 6 | mandatory | reg1 |
| st | 1108163 | Séries Temporais | 6 | mandatory | inf2 |
| reg2 | 1108205 | Regressão II | 6 | mandatory | reg1 |
| amv2 | 1108207 | Análise Multivariada II | 6 | mandatory | amv1 |
| est1 | 1108353 | Estágio Supervisionado I | 7 | internship | inf1 |
| est2 | 1108354 | Estágio Supervisionado II | 7 | internship | est1 |
| tcc1 | 1108355 | Trabalho de Conclusão de Curso I | 8 | complementary | reg2, amv2 |
| tcc2 | 1108356 | Trabalho de Conclusão de Curso II | 8 | complementary | tcc1 |

Conferência: 29 obrigatórias = 1.740 h; estágios + TCC = 480 h.

## Dados: grade 2013 — optativas e flexíveis

Todas com 4 cr e 60 h, exceto Introdução à Análise Real (6 cr, 90 h).
`semester` fica vazio. Flexíveis com `type = flexible`, as demais `elective`.

| id | code | name | prerequisites |
| --- | --- | --- | --- |
| fuvc | 1103128 | Funções de uma Variável Complexa | calc3 |
| me1 | 1103153 | Matemática Elementar I | — |
| iar | 1103142 | Introdução à Análise Real (90 h) | me1, sedo |
| adc | 1108128 | Análise de Dados Categorizados | reg2 |
| asob | 1108130 | Análise de Sobrevivência | inf2, reg1 |
| biom | 1108135 | Biometria | inf2 |
| dem2 | 1108141 | Demografia II | dem1 |
| epdi | 1108142 | Estatística Aplicada ao Processamento Digital de Imagens | inf2 |
| geo | 1108146 | Geoestatística e Estatística Espacial | inf2 |
| itg | 1108150 | Introdução à Teoria dos Grafos | po |
| iib | 1108153 | Introdução à Inferência Bayesiana | — |
| pm | 1108156 | Pesquisa de Mercado | inf2 |
| po | 1108157 | Pesquisa Operacional | ial |
| pe2 | 1108159 | Planejamento de Experimentos II | plex1 |
| pmat | 1108162 | Programação Matemática | po |
| tma | 1108165 | Teoria das Matrizes e Aplicações | calc2, ial |
| ise | 1108196 | Introdução aos Softwares Estatísticos | pae |
| fbde | 1108198 | Fundamentos em Bancos de Dados Estatísticos | — |
| pest2 | 1108209 | Processos Estocásticos II | pest1 |
| iib2 | 1108211 | Introdução à Inferência Bayesiana | inf2 |
| aede | 1108212 | Análise Estatística de Dados Ecológicos | amv2 |
| igp | 1108213 | Introdução à Gestão de Projetos | — |
| sim | 1108214 | Simulação | ec |
| ebio | 1108215 | Ensaios Biológicos | reg2 |
| amo2 | 1108216 | Amostragem II | amo1, reg1 |
| iadl | 1108217 | Introdução à Análise de Dados Longitudinais | amo1, reg1 |
| ice | 1108350 | Introdução à Consultoria Estatística | — |
| econ1 | 1108351 | Econometria I | reg1 |
| econ2 | 1108352 | Econometria II | econ1 |
| pyt | GDEST0105 | Programação Estatística com Python | ise |
| aml | GDEST0106 | Aprendizagem de Máquina | reg1 |
| libras1 | 1403747 | Libras – Língua Brasileira de Sinais | — |
| libras2 | GDLS0024 | Libras | — |
| te1 | 1108195 | Tópicos Especiais em Estatística I (flexível) | — |
| te2 | 1108199 | Tópicos Especiais em Estatística II (flexível) | — |
| te3 | 1108200 | Tópicos Especiais em Estatística III (flexível) | — |
| te4 | 1108201 | Tópicos Especiais em Estatística IV (flexível) | — |

Atenção: o mesmo nome com dois códigos (Introdução à Inferência Bayesiana
1108153/1108211; Libras 1403747/GDLS0024) é intencional, porque o SIGAA lista os
dois. A regra "nenhum nome duplicado" do validador deve considerar nome **e**
código, não só o nome.

## Dados: apelidos de código

| code | alias_of | status | note |
| --- | --- | --- | --- |
| 1103176 | GDCOC0072 | active | Cálculo Numérico: código antigo (Dep. de Matemática) e atual |
| 1108211 | 1108153 | active | Introdução à Inferência Bayesiana: dois códigos na grade 2013 |
| 1103128 | 1103259 | active | Funções de uma Variável Complexa: código 2013 e código 2026 |
| 1403747 | GDLS0024 | active | Libras: dois códigos na grade 2013 |

## Dados: sucessoras de optativas antigas (`elective_successors.csv`)

| code | successor_id | note |
| --- | --- | --- |
| 1108351 | econ | Econometria I → Econometria |
| 1108352 | econ | Econometria II → Econometria |
| 1108165 | mat | Teoria das Matrizes e Aplicações → Matrizes e Aplicações |
| 1108350 | cons | Introdução à Consultoria Estatística → Consultoria Estatística |
| 1108139 | cep | Controle Estatístico de Qualidade → Controle Estatístico de Processos |

## Dados: destinos das disciplinas sem correspondente (`old_course_destinations.csv`)

| code | disciplina (2013) | destination | status | note |
| --- | --- | --- | --- | --- |
| 1108197 | Probabilidade III | topics | confirmed | obrigatória sem equivalência |
| GDCOC0072 | Cálculo Numérico | topics | confirmed | possível Métodos de Otimização mediante pedido |
| 1108354 | Estágio Supervisionado II | none | confirmed | não contado automaticamente; possível extensão mediante pedido |
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

O arquivo não tem a coluna "disciplina (2013)" (o nome vem de `curriculum_2013.csv`).

## Dados: possíveis aproveitamentos mediante pedido (`request_options.csv`)

| code | target | condition | note |
| --- | --- | --- | --- |
| 1108354 | extension | quantidade a definir pela coordenação | Estágio Supervisionado II como horas de extensão (flexível extensionista, Resolução 04/2026, Art. 11) |
| GDCOC0072 | moa | se a coordenação aceitar o pedido | Cálculo Numérico como Métodos de Otimização e Aplicações |
| 1108162 | moa | se a coordenação aceitar o pedido | Programação Matemática como Métodos de Otimização e Aplicações |

## Dados: premissas (`assumptions.csv`)

| key | value | status | description |
| --- | --- | --- | --- |
| start_term | 2027.1 | confirmed | Início do novo PPC |
| migrant_extension_hours | 300 | confirmed | Horas de extensão exigidas de quem migra |
| old_pm_counts_as_extension | true | confirmed | Pesquisa de Mercado de 2013 conta 60 h de extensão |
| topics_max_hours | 120 | assumed | Limite único de horas para tudo o que vai para Tópicos Especiais |
| electives_max_hours | 660 | assumed | Optativas acima desse limite são perdidas |
| consultoria_emphasis | EAM | assumed | Ênfase de Consultoria Estatística (não consta na tabela de ênfases) |
| emphasis_min_hours | 360 | confirmed | Horas mínimas em optativas da mesma ênfase para o diploma com ênfase |
| internship2_recoverable_max_hours | 180 | assumed | Máximo de horas do Estágio II que podem ser recuperadas como extensão mediante pedido; as resoluções indicam entre 60 h (Res. 02/2026) e 180 h (Res. 04/2026) |

A barra lateral mostra as premissas `assumed` e permite alterá-las; os destinos
`assumed` de `old_course_destinations.csv` podem ser alterados numa seção
própria ("Disciplinas extintas: Tópicos ou optativa").

## Pendências conhecidas (aguardando a coordenação)

- Destino das optativas extintas (Tópicos ou optativa, e qual ênfase) e se
  Teoria dos Grafos e Simulação podem ser aproveitadas como Network Analysis e
  Modelagem e Simulação em Ciência de Dados.
- Qual disciplina pode ser aproveitada para Métodos de Otimização, e se é
  automático ou por pedido.
- Se o limite de 120 h dos Tópicos é único e compartilhado.
- Optativas acima de 660 h: perdidas?
- Quantas horas do Estágio II podem virar extensão.
- Ênfase de Consultoria Estatística.

## Roteiro

Meta: app de conversão do histórico definido no escopo final
(`docs/escopo_final.md`). Cada etapa para para revisão do usuário.

- [x] 1. Dados de `data/` + validador + testes
- [x] 2. Motor de regras (classificação do histórico) com testes
- [x] 3. ~~Verificação do plano montado pelo aluno~~ (saiu do escopo; o código
  fica no histórico do git)
- [x] 4. ~~Interface com histórico por período e plano~~ (substituída pela etapa d)
- [x] 0. Atualização do CLAUDE.md para o escopo final
- [x] a. Dados e validador do escopo final
- [x] b. Motor de conversão e resumo, com testes
- [x] c. Parser do PDF do histórico do SIGAA, com histórico fictício
- [x] d. Interface (Streamlit)
- [x] d2. Reformulação de UX: etapas, celular, lista de disciplinas
- [ ] e. Exportação para conversar com uma IA
- [ ] f. Parecer da IA com fallback entre provedores e cache (só depois de a–e aprovadas)
- [ ] g. Dockerfile e deploy em serviço gratuito

## Tarefa atual: e — Exportação para IA

Ver "Especificação da etapa e" abaixo. Começar só depois da revisão da etapa d2.

## Especificação da etapa b — Motor de conversão e resumo

`app/conversion.py` (substitui `app/rules.py`) e `app/summary.py`.

- Entrada: códigos aprovados da grade 2013 (e, do parser, linhas flexíveis e não
  reconhecidas), premissas de `assumptions.csv` e destinos de
  `old_course_destinations.csv`, ambos sobrescrevíveis na chamada.
- Aplica as regras de conversão 1 a 6 e as regras de horas (ver acima).
- Saída (dataclasses serializáveis em JSON):
  - uma linha por disciplina de 2013: destino em 2026 (disciplina ou
    categoria), CH, CH aproveitada, CH perdida, motivo;
  - por categoria do novo PPC: exigido / aproveitado / falta (obrigatórias,
    estágio, TCC, optativas, Tópicos Especiais, flexíveis extensionistas,
    extensão);
  - horas em optativas de cada ênfase frente a `emphasis_min_hours`;
  - possíveis aproveitamentos mediante pedido (das disciplinas cursadas);
  - cenário "não migrar": horas que faltam pelas exigências de 2013;
  - premissas usadas, com valor e status.
- Resumo:
  - **Faltam**: 3.000 h / 200 cr menos o aproveitado, com "equivale a N
    disciplinas de 60 h" (arredondado para cima; "cerca de N" quando não for
    exato). A extensão aparece só na sua linha, com aviso se faltar optativa
    extensionista além das 3.000 h;
  - **Aproveitamento**: horas aproveitadas ÷ horas aprovadas na grade 2013, em %;
  - **Não aproveitado**: "Perdido: X h, das quais até Y h podem ser
    recuperadas mediante pedido:", seguido de uma linha por pedido
    ("<disciplina> como <destino>: [até ]N h, <condition>."), e a lista
    (disciplina, horas perdidas, motivo). Y = perdas do cenário base menos
    perdas com todos os pedidos concedidos; N de cada linha = o mesmo com só
    aquele pedido concedido. O Estágio II recuperado conta como flexível
    extensionista e como extensão, até `internship2_recoverable_max_hours`.
    Ao lado do percentual, nota com as horas não reconhecidas fora do cálculo;
  - obrigatórias do novo PPC que faltam, pelo nome, na ordem do fluxograma.
- Testes (casos mínimos de `docs/escopo_final.md`): Estágio I (perde 60 h);
  Estágio II (perdido, recuperável por pedido); Python e Introdução aos Softwares
  juntas (uma vai para Tópicos); Probabilidade III + Cálculo Numérico + Python
  excedente = 180 h em Tópicos (60 h perdidas); optativa extinta; sucessora
  (Econometria I e II contam as duas); apelido de código; optativas acima de
  660 h; Pesquisa de Mercado contando extensão; percentual, faltam e "equivale
  a N disciplinas de 60 h".

## Especificação da etapa c — Parser do PDF (`app/history_pdf.py`)

- `pdfplumber`, lendo o arquivo em memória (BytesIO). Nunca gravar o PDF.
- Linhas da tabela: código, nome, carga horária, tipo (OB, OP, CO, CF, EC, EQ),
  semestre/turma/nota (opcionais) e situação. Regex por linha; ignorar o resto.
- Contam as linhas com situação **APROVADO** ou **DISPENSADO** (a legenda do
  CRA no histórico cita Aprovado, Dispensado, Reprovado e Falta); aprovada uma
  vez conta uma vez, mesmo com reprovações anteriores.
- Opção "Incluir disciplinas em curso (supondo aprovação)", **desmarcada** por
  padrão: inclui as linhas MATRICULADO.
- CANCELADO é ignorado sem aviso (como TRANCADO). Situações diferentes de
  APROVADO, DISPENSADO, REPROVADO, REP. FALTA, TRANCADO, CANCELADO,
  MATRICULADO e PENDENTE geram aviso com a lista.
- Conferir o currículo: verificar se `232013` aparece em qualquer lugar do PDF
  (a extração pode separar o rótulo "Currículo:" do valor); se não aparecer,
  avisar que o app vale só para a grade 2013.
- Conferir as horas aprovadas por tipo com a tabela "TOTALIZAÇÃO" (linha
  "Integralizado", colunas: Básicos Profissionais = OB, Complementares
  Obrigatórios = CO, Optativos = OP, Flexíveis = CF, Total); se não bater,
  avisar que a leitura pode ter falhado.
- Layout da linha: `<código> <nome> <CH> <tipo> [<ano.período> <turma> <nota>]
  <situação>`; linhas PENDENTE vêm sem ano, turma e nota.
- Linhas de tipo CF vão para Tópicos Especiais (regra 5); códigos fora da grade
  2013 de outro tipo são "não reconhecidos".
- Linhas EQ (equivalente) e EC (extracurricular) aprovadas ficam fora da
  conferência com a TOTALIZAÇÃO e geram um aviso que as lista e orienta a
  consultar a coordenação.
- Dados pessoais: nunca extrair, exibir ou registrar.
- Testes com um **histórico fictício de três páginas** (página 1 de dados
  inventados), gerado por script em `tests/fixtures/`: reprovação seguida de
  aprovação, trancamento, matriculadas (com e sem a opção), situação
  desconhecida, totalização que bate e que não bate.

## Especificação da etapa d — Interface (`app/streamlit_app.py`)

Todo o texto em português. Rodar com `streamlit run app/streamlit_app.py`.

1. **Entrada do histórico**: envio do PDF (o parser preenche a tabela) ou
   preenchimento manual na mesma tabela. Tabela única no estilo do histórico do
   SIGAA, agrupada pelo período do fluxograma de 2013 (obrigatórias) e depois
   "Optativas" e "Flexíveis", com linha de inclusão e botão de remover em cada
   linha. Atalho "marcar obrigatórias até o período N". Depois do PDF, o aluno
   pode corrigir a tabela. Sem período de ingresso.
2. **Resumo em destaque**: ver etapa b. Aviso bem visível com o total perdido,
   se houver. Possíveis aproveitamentos mediante pedido em destaque separado.
   Linha de comparação com o cenário "não migrar".
3. **Tabela de conversão**, agrupada como a entrada. Colunas: Código,
   Disciplina (2013), CH, Na grade 2026, CH aproveitada, CH perdida,
   Observação. Linhas com perda destacadas.
4. **Barra lateral**: premissas `assumed` editáveis (com o status de cada
   uma) e a seção "Disciplinas extintas: Tópicos ou optativa" (só os destinos
   `assumed` são editáveis; os `confirmed` aparecem fixos).
5. Rodapé fixo: "Simulação baseada nas regras disponíveis; não substitui a
   orientação da coordenação."

## Especificação da etapa d2 — Reformulação de UX

Substitui os itens 1, 3 e 4 da etapa d (o resumo e o rodapé continuam).

1. **Navegação em etapas**, com barra de progresso clicável no topo:
   1) Seu histórico, 2) Resumo, 3) Disciplinas, 4) Conversar com IA. As
   etapas 2 a 4 ficam liberadas quando o histórico tem ao menos uma
   disciplina (se ficar vazio, volta à 1). Botões "Voltar" e "Próximo" no fim
   de cada etapa. Estado em `st.session_state`; as escolhas que precisam
   sobreviver à troca de etapa (incluir em curso, regras simuladas, período
   atual) ficam também em `st.session_state["saved"]`.
2. **Celular** (conferido em 360 px): sem `st.columns` para linhas de tabela.
   Na entrada, cada disciplina é um item com borda discreta: nome em
   destaque, "Código · Tipo · CH" em texto menor e botão de remover. Tabelas
   só de leitura com `st.dataframe`.
3. **Etapa 1**: a entrada da etapa d, mais a opção "Flexível de outro curso"
   no grupo Flexíveis (nome e horas editáveis; entra como linha CF e vai para
   Tópicos; código interno `MANUAL-n`, exibido como "—").
4. **Etapa 2**: o resumo da etapa d, sem a lista do perdido nem as
   obrigatórias que faltam (vão para a etapa 3), e uma seção recolhida
   "Simular regras ainda não confirmadas" com as premissas e os destinos
   supostos (no lugar da barra lateral).
5. **Etapa 3 (Disciplinas)**, em três listas:
   - Aproveitadas: disciplina de 2013 → onde entra no novo PPC;
   - Perdidas: horas perdidas, motivo, linhas do que pode ser recuperado
     mediante pedido e a sublista "Não reconhecidas (fora das contas,
     consulte a coordenação)", que não soma ao total perdido;
   - A cursar: obrigatórias do novo PPC que faltam, em "Ficaram para trás"
     (períodos anteriores ao período atual) e "Próximos períodos", na ordem
     do fluxograma. Campo "Em que período você está?" (1 a 8), pré-preenchido
     com o período mais avançado do fluxograma de 2013 com obrigatória
     aprovada + 1 (máximo 8; com "incluir em curso" marcado, as em curso
     contam como aprovadas), editável.
   Disciplina aproveitada em parte aparece nas duas primeiras listas, cada
   uma com suas horas. A tabela de conversão completa fica no expander "Ver
   tabela completa", com as linhas com perda destacadas.
6. **Etapa 4**: só o título e "Em breve" (preparada para as etapas e e f).
7. **Ajustes da revisão**:
   - rótulos curtos na barra ("1 Histórico", "2 Resumo", "3 Disciplinas",
     "4 IA"), numa linha em 360 px; título menor no celular; trocar de etapa
     volta ao topo da página;
   - antes do envio, um `st.dialog` "Antes de enviar seu histórico" com o
     texto de autorização e os botões "Autorizo e quero enviar" e "Prefiro
     preencher manualmente"; o envio só aparece depois da autorização
     (guardada na sessão);
   - depois do envio, o `session_state` guarda só que há um arquivo
     carregado ("Arquivo carregado: histórico do SIGAA (PDF)"; o nome do
     arquivo não é guardado nem exibido, porque o nome padrão do SIGAA traz a
     matrícula), com o botão "Remover arquivo e limpar lista", que zera a
     lista inteira (não depende do estado do `st.file_uploader`);
   - disciplinas em curso: em vez da caixa, se o PDF tiver linhas
     MATRICULADO, a pergunta "Encontramos N disciplinas em curso: <lista>.
     Deseja considerá-las como aprovadas na simulação?" ("Sim, incluir" /
     "Não"); nas etapas 1 a 3, a linha "Disciplinas em curso: incluídas / não
     incluídas" com "Alterar";
   - grupos de período sem disciplinas ficam recolhidos;
   - resumo sem repetições: a frase do "Faltam" é a legenda do cartão; os
     pedidos possíveis aparecem só no quadro azul; categorias em linhas
     ("Obrigatórias: 1.500 de 1.800 h · faltam 300 h"), com a tabela no
     expander "Ver tabela completa";
   - "Aproveitadas" em linhas "disciplina de 2013 → destino em 2026 (CH)";
     destino optativo mostra a natureza: "Demografia I → Demografia I
     (optativa · Estatística Aplicada e Modelagem · 60 h)", "(optativa ·
     Ciência de Dados · …)" ou "(optativa sem ênfase · …)"; o mesmo vale para
     as sucessoras (Controle Estatístico de Qualidade → Controle Estatístico
     de Processos);
   - "Perdidas" em linhas "Estágio Supervisionado I: 60 h perdidas, redução
     de carga horária (o novo Estágio Supervisionado tem 120 h)."; as não
     reconhecidas também em linhas.

## Especificação da etapa e — Exportação para IA (`app/export.py`)

Função pura (sem chamar API, sem gravar arquivo) que gera Markdown. Sem dados
pessoais, disciplinas pelo nome (código só entre parênteses nas tabelas),
nenhum id interno. Seções: contexto e regras de conversão, premissas usadas,
tabela de conversão, resumo, não aproveitado, possíveis aproveitamentos mediante
pedido, obrigatórias que faltam, optativas disponíveis no novo PPC (com ênfase)
e instruções para a IA:

- explicar ao aluno, em linguagem simples, o que ele aproveita, o que perde e o
  que falta, e ajudá-lo a pensar nas escolhas;
- não inventar disciplinas, regras ou equivalências;
- sinalizar o que depende de decisão ou pedido à coordenação.

Na tela (etapa 4 da navegação): botão de download e, ao lado, links para abrir uma IA (Claude:
https://claude.ai/new, ChatGPT: https://chatgpt.com, Gemini:
https://gemini.google.com) com a orientação "Anexe o arquivo baixado e pergunte
o que quiser." Testes: seções, nenhum dado pessoal, nenhum id interno.

## Especificação da etapa f — Parecer da IA

Ver a seção "Parecer da IA" de `docs/escopo_final.md` (botão "Gerar parecer",
prompt igual ao arquivo exportado sem repetir números, Gemini → Groq via SDK
`openai`, cache em memória pelo hash do resultado, mensagem de falha, validação
das disciplinas citadas, textos fixos da tela e testes com mock).
