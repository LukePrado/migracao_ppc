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
- Python com o venv `.venv`; dependências em `requirements.txt`.
- Depois de mudar `data/` ou código, rode `python scripts/validate_data.py` e `pytest`.
- Nunca leia, copie ou faça commit de `materials/` (documentos do PPC, fora do git)
  nem de `.env` (chaves de API).
- Não implemente nada além da tarefa atual.

## O projeto

App web para alunos de Estatística da UFPB decidirem se migram do PPC 2013 para o
novo PPC (Resolução CONSEPE 41/2026, curso de Estatística e Ciência de Dados). O
aluno envia o PDF do histórico do SIGAA (ou marca as disciplinas) e vê:

1. o que é aproveitado, o que vira optativa e o que fica pendente;
2. um planejamento dos próximos semestres nos dois cenários (migrar e não migrar).

### Arquitetura

O núcleo é **determinístico**. A LLM só redige uma explicação do resultado já
calculado e nunca decide equivalências nem números.

1. Extração do histórico: `pdfplumber` + regex (layout do SIGAA é padronizado);
   formulário manual como fallback.
2. Motor de regras: aplica as regras de migração sobre os CSVs de `data/`.
3. Planejamento: grafo de pré-requisitos + ordenação topológica com limite de
   créditos por período.
4. Parecer da LLM (opcional): recebe o resultado em JSON; se a API falhar, o aluno
   recebe só o resultado determinístico.

### Stack

Python, FastAPI (ou Streamlit), pdfplumber, pytest, SDK `openai` (Gemini como
principal, Groq como fallback, via endpoints compatíveis), Docker.
Chaves em variáveis de ambiente (`GEMINI_KEY`, `GROQ_KEY`, `REDIS_URL`).

### LGPD

- Processar o PDF em memória e descartar; nunca gravar o arquivo.
- Enviar à LLM só códigos e nomes de disciplinas, nunca dados do aluno.
- Cache, se houver, guarda só o hash das disciplinas e o texto do parecer.

### Estrutura do repositório

```
app/        código da aplicação
data/       CSVs curriculares (versionados)
scripts/    utilitários (validação etc.)
tests/      testes pytest
materials/  documentos do PPC (ignorado pelo git)
```

## Regras de migração (decididas pela coordenação)

1. **Mesmo código nas duas grades:** aproveitamento direto.
2. **Consta em `equivalences.csv` com status `active`:** aproveita como a
   disciplina nova de destino.
3. **Disciplina de 2013 sem equivalência e fora das obrigatórias de 2026:** conta
   como optativa (créditos para o mínimo de 44 cr). Só conta para uma ênfase se
   estiver na lista daquela ênfase.
4. **Obrigatória de 2026 sem correspondente no histórico:** pendente.
5. **Equivalência com status `proposed`:** não é aplicada; o app apenas avisa o
   aluno afetado de que há uma proposta em análise.

Consequências: Fundamentos de Banco de Dados e Big Data e Métodos de Otimização e
Aplicações não têm correspondência em 2013. Pesquisa de Mercado (`1108156`) era
optativa em 2013 e é obrigatória em 2026: quem cursou aproveita pelo código.

## Parâmetros da grade 2026

- Total: 200 créditos (3.000 h); 1 crédito = 15 h; duração de 8 a 12 períodos.
- Obrigatórias 120 cr; estágio 8 cr; complementares (TCC I e II) 8 cr;
  optativas no mínimo 44 cr; flexíveis 20 cr.
- Ênfase: no mínimo 24 cr em optativas da mesma ênfase; senão, generalista.
- Matrícula por período: mínimo 17, máximo 25 créditos.
- Extensão: 300 h (Pesquisa de Mercado 60 h + flexíveis extensionistas 180 h +
  optativas extensionistas 60 h).

## Calendário e oferta (confirmado pela coordenação)

- O novo PPC entra em vigor em **2027.1** (a seção 8.3 do PPC diz 2026.1, mas a
  coordenação confirmou 2027.1). Ingressantes de 2027.1 em diante entram direto
  no novo PPC; veteranos escolhem migrar ou não.
- Os períodos letivos são `AAAA.1` e `AAAA.2`. O curso tem entrada anual no `.1`.
- Obrigatórias de semestre ímpar no fluxograma (1, 3, 5, 7) são ofertadas no `.1`;
  as de semestre par (2, 4, 6, 8) no `.2`. Vale para as duas grades, usando a
  coluna `semester`. É a regra geral: exceções pontuais podem existir.
- Optativas, flexíveis, estágios e TCC não têm periodicidade definida: o planejador
  assume oferta em todo período e mostra um aviso ao aluno.
- O primeiro período a planejar é o próximo período letivo (hoje, 2027.1).

## Parâmetros da grade 2013 (SIGAA, estrutura 232013)

- Total: 3.000 h (200 cr). Básicas profissionais 1.740 h (29 disciplinas);
  complementares obrigatórias 480 h (estágios I e II + TCC I e II);
  optativas no mínimo 540 h (36 cr); flexíveis 240 h (16 cr).
- Duração de 8 a 12 períodos. Por período: mínimo 180 h (12 cr), máximo 480 h (32 cr).

## Especificação de `data/`

| Arquivo | Colunas |
| --- | --- |
| `curriculum_2026.csv` | id;code;name;credits;hours;type;semester;emphasis;extension |
| `prerequisites_2026.csv` | course_id;prerequisite_id;group |
| `curriculum_2013.csv` | id;code;name;credits;hours;type;semester |
| `prerequisites_2013.csv` | course_id;prerequisite_id;group |
| `equivalences.csv` | rule_id;source_codes;match;target_id;status;note |
| `code_aliases.csv` | code;alias_of;status;note |
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
  cumpridas. Sem alternativas, use `group = 1` em todas as linhas.
- `prerequisite_id` é um `id` da mesma grade ou, para componentes fora da grade,
  `code:<código SIGAA>` (ex.: `code:1107136`).
- `source_codes`: códigos separados por `|`. `match`: `any_of` (basta um) ou
  `all_of` (exige todos). `status`: `active` ou `proposed`.
- `code_aliases.csv`: códigos diferentes da mesma disciplina (código antigo e
  atual). Ao ler um histórico, um código em `code` conta como `alias_of`.
  `status`: `active` ou `proposed` (só `active` é aplicado).
- `assumptions.csv`: regras ainda não confirmadas pela coordenação, como
  parâmetros. `status`: `confirmed` ou `assumed`. **Nenhuma dessas regras pode
  ficar fixa no código**: o código lê sempre deste arquivo.
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

Todas com 4 créditos e 60 h.

| id | code | name | emphasis | prerequisites |
| --- | --- | --- | --- | --- |
| amo2 | 1108216 | Amostragem II | EAM | amo1, reg1 |
| asob | 1108130 | Análise de Sobrevivência | EAM | inf2, reg1 |
| biom | 1108135 | Biometria | EAM | reg1 |
| cep | NEW | Controle Estatístico de Processos | EAM | inf1 |
| dem1 | 1108140 | Demografia I | EAM | aevd |
| dem2 | 1108141 | Demografia II | EAM | dem1 |
| econ | NEW | Econometria | EAM | TBD ("Regressão": I ou II?), st |
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

Fonte: Quadro 8 da Resolução 41/2026 e proposta em análise. Disciplinas com o
mesmo código nas duas grades não entram aqui (regra 1).

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
| eq13 | 1108353\|1108354 | all_of | est | active | Estágio I e II; `match` é TBD (all_of ou any_of) |
| eq14 | GDCOC0072\|1103176 | any_of | moa | proposed | Cálculo Numérico, código atual ou antigo (em análise pela coordenação) |

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
| 1108211 | 1108153 | proposed | Introdução à Inferência Bayesiana: dois códigos na grade 2013 |
| 1103128 | 1103259 | proposed | Funções de uma Variável Complexa: código 2013 e código 2026 |
| 1403747 | GDLS0024 | proposed | Libras: dois códigos na grade 2013 |

Os apelidos `proposed` aguardam confirmação da coordenação e não são aplicados.

## Dados: premissas (`assumptions.csv`)

| key | value | status | description |
| --- | --- | --- | --- |
| start_term | 2027.1 | confirmed | Início do novo PPC |
| first_planning_term | 2027.1 | confirmed | Primeiro período a planejar |
| every_term_types | elective\|flexible\|internship\|complementary | assumed | Tipos ofertados em todo período |
| transition_every_term_ids | fbdbd\|moa | assumed | Obrigatórias 2026 ofertadas em todo período na transição |
| old_electives_count_for_emphasis | false | assumed | Optativa antiga com sucessora conta para a ênfase |
| migrant_extension_hours | 300 | assumed | Horas de extensão exigidas de quem migra |
| old_pm_counts_as_extension | false | assumed | Pesquisa de Mercado cursada em 2013 conta como extensão |
| old_flexible_max_hours | 120 | assumed | Máximo de horas dos Tópicos Especiais I–IV (2013) aproveitadas como flexíveis não extensionistas |
| max_credits_2026 | 25 | confirmed | Máximo de créditos por período (2026) |
| max_credits_2013 | 32 | confirmed | Máximo de créditos por período (2013) |

## Pendências conhecidas

- Estágio: a equivalência exige I e II ou basta um?
- Econometria (2026): pré-requisito "Regressão" é Regressão I ou II?
- Apelidos `proposed` (Inferência Bayesiana, Funções de uma Variável Complexa,
  Libras): os códigos de cada par valem como a mesma disciplina?
- Optativas antigas com sucessora na grade nova (Econometria I/II → Econometria,
  Teoria das Matrizes → Matrizes e Aplicações, Introdução à Consultoria →
  Consultoria Estatística, Controle Estatístico de Qualidade → Controle
  Estatístico de Processos): contam para a ênfase ou só como optativa genérica?
- Implantação gradual: para quem migrar, as disciplinas novas (ex.: Fundamentos
  de Banco de Dados e Big Data, 4º período) serão ofertadas já em 2027.1, ou só
  quando a primeira turma do novo PPC chegar ao período delas?
- Estágio e TCC: são ofertados em todo período? (Na grade 2013, TCC I e II estão
  ambos no 8º semestre, e o II exige o I.)
- Cálculo Numérico → Métodos de Otimização: decisão em análise (eq14).

## Roteiro

Meta: **protótipo funcional para a reunião com a coordenação** (tarefas 1 a 4).

- [x] 1. Dados de `data/` + validador + testes
- [ ] 2. Motor de regras (classificação do histórico) com testes
- [ ] 3. Planejamento por período, nos dois cenários, com testes
- [ ] 4. Protótipo em Streamlit com seleção manual de disciplinas
- [ ] 5. Parser do PDF do histórico do SIGAA
- [ ] 6. Dockerfile e deploy em serviço gratuito
- [ ] 7. Parecer da LLM com fallback entre provedores e cache

## Tarefa atual: 2 — Motor de regras

Siga a "Especificação da tarefa 2" abaixo.

## Especificação da tarefa 2 — Motor de regras

Módulo `app/rules.py` (carregamento dos CSVs em `app/data_loader.py`).

Entrada: conjunto de códigos SIGAA cursados com aprovação (aluno da grade 2013)
e as premissas (lidas de `assumptions.csv`, com possibilidade de sobrescrever
valores na chamada, para a interface poder alternar premissas).

Passos:
1. Normalizar códigos pelos apelidos `active` de `code_aliases.csv`.
2. Para cada disciplina de 2026: mesmo código cursado → `aproveitada`; regra
   `active` de `equivalences.csv` satisfeita (`any_of`/`all_of`) → `aproveitada`.
3. Obrigatórias, estágio e TCC de 2026 não aproveitados → `pendente`.
4. Disciplinas cursadas que não foram usadas nos passos 2 e 3 → `optativa`
   (créditos para o mínimo de optativas). Contam para ênfase só se o código for
   de uma optativa de 2026 com ênfase (ou conforme `old_electives_count_for_emphasis`).
5. Tópicos Especiais I–IV de 2013 → horas flexíveis não extensionistas, até
   `old_flexible_max_hours`.
6. Equivalência `proposed` satisfeita → aviso ("proposta em análise").
7. Registro com TBD envolvido → status `a definir`, com a descrição da pendência.

Saída (dataclasses serializáveis em JSON), para os dois cenários:
- **Migrar:** listas de aproveitadas, pendentes, optativas, avisos e itens a definir;
  totais de créditos feitos e exigidos por categoria (obrigatórias, estágio,
  complementares, optativas, flexíveis, extensão).
- **Não migrar:** obrigatórias de 2013 pendentes e créditos de optativas e
  flexíveis faltantes, pelas exigências de 2013.
- Lista das premissas usadas, com valor e status.

Testes: casos pequenos e explícitos para cada passo (aluno do 1º período, aluno
com optativas de 2013 que têm equivalência, Estágio I sem o II, Cálculo Numérico
com a proposta, apelido 1103176).

## Especificação da tarefa 3 — Planejamento

Módulo `app/planner.py`. Para cada cenário, a partir de `first_planning_term`,
monta período a período até não restar nada pendente:
- Oferta: obrigatórias seguem a paridade (`semester` ímpar → `.1`, par → `.2`);
  tipos em `every_term_types` e ids em `transition_every_term_ids` (só no
  cenário migrar) são ofertados em todo período.
- Uma disciplina entra no período se os pré-requisitos estiverem cumpridos em
  períodos anteriores (respeitando `group`) e houver crédito disponível
  (`max_credits_2026` ou `max_credits_2013`).
- Prioridade: maior cadeia de dependentes pendentes (caminho crítico); depois,
  menor `semester`.
- Optativas e flexíveis faltantes entram como vagas genéricas de 4 créditos
  ("Optativa a escolher"), depois das obrigatórias de cada período.
- Saída: lista de períodos (`AAAA.1`/`AAAA.2`) com as disciplinas, número de
  períodos restantes e o período previsto de conclusão. Avisar se ultrapassar o
  prazo máximo (12 períodos desde o ingresso, informado pelo usuário).

Testes: um aluno sem pendências, um com a cadeia Linguagem de Programação para
CD → Fundamentos de BD, e um que mostre o efeito de `transition_every_term_ids`.

## Especificação da tarefa 4 — Protótipo em Streamlit

`app/streamlit_app.py`, todo o texto em português. Sem LLM e sem PDF.
- Entrada: período de ingresso e as disciplinas cursadas, marcadas em caixas de
  seleção agrupadas por semestre (obrigatórias de 2013) e uma lista de optativas
  e flexíveis de 2013.
- Resultado em duas colunas, "Migrar" e "Não migrar": situação de cada disciplina,
  totais de créditos, planejamento por período e conclusão prevista.
- Destaque para "a definir pela coordenação" e avisos.
- Barra lateral **"Premissas"**: cada linha `assumed` de `assumptions.csv` pode ser
  alterada na tela, e o resultado é recalculado na hora. Mostrar o status
  (confirmada ou suposta) de cada premissa.
- Rodar com `streamlit run app/streamlit_app.py`. Adicionar `streamlit` ao
  `requirements.txt`.
