# Análise técnica detalhada do repositório `caller-calle-extractor`

## 1) Objetivo funcional da ferramenta

A ferramenta foi concebida para **mineração de repositórios C** com foco em extração de relações **caller → callee** (grafo de chamadas), a partir do pipeline:

1. descobrir/listar repositórios GitHub,
2. baixar arquivos `.c` dos repositórios,
3. converter código C para XML via `srcml`,
4. extrair chamadas de função em cada função,
5. exportar os pares em CSV.

Há também uma linha de evolução para análise de **compilação condicional** (`#ifdef`, `#ifndef`, etc.), via extração de diretivas.

---

## 2) Mapa de módulos e responsabilidades

### Núcleo de orquestração
- `source/main.py`
  - Ponto de entrada.
  - Atualmente aciona apenas `download_repositories()`; as etapas de análise e exportação estão comentadas.

### Coleta de repositórios
- `source/github_repo_search.py`
  - Consulta a API Search do GitHub usando parâmetros montados em `params2`.
  - Persiste links em `repositories.txt` evitando duplicatas.
- `source/advanced_github_repository_search.py`
  - Interface gráfica Tkinter para construir filtros avançados.
  - Preenche `params2` (estado global) usado pela busca.
- `source/clone_repositories.py`
  - Lê `repositories.txt`.
  - Faz crawling recursivo pela API `/contents` do GitHub para baixar apenas arquivos `.c`.
  - Implementa checagem de rate limit e espera quando necessário.

### Análise estática de chamadas
- `source/program_snc.py`
  - Classe `SrcMLAnalyzer`.
  - Gera XML com `srcml` por arquivo `.c`.
  - Faz parsing XML (`xml.etree`) para localizar funções e chamadas, gravando em CSV (`Project`, `File`, `Caller`, `Callee`).
- `source/configurable_systems.py`
  - Variante do analisador para incluir contexto de compilação condicional no CSV.
  - Usa `lxml` e tenta usar `DirectiveExtractor`.
  - Está conceitualmente alinhado com a evolução para sistemas configuráveis, porém possui inconsistências de integração (ver seção 5).

### Diretivas de pré-processador (variabilidade)
- `source/directive_extractor.py`
  - Classe `DirectiveExtractor` baseada em `BeautifulSoup(xml)` para mapear diretivas e blocos associados.
  - Exporta JSON com lista de diretivas e instruções por condição.
- `source/test_directive_extractor.py`
  - Script de teste manual para validar o extractor.

### Infraestrutura utilitária
- `source/directory_manager.py`
  - Define caminhos-base e utilitários de path.
- `source/get_github_token.py`
  - Lê token GitHub de `github_token.txt`.
- `source/email_notifier.py`
  - Notificação por e-mail (SMTP) ao fim do download.
- `source/csv_display.py`
  - Preview de CSV via pandas.

---

## 3) Fluxo operacional atual (estado real)

No estado atual do `main.py`, o fluxo ativo é:

- baixar repositórios listados em `repositories.txt`;
- **não** executar automaticamente a extração de caller/callee (etapas comentadas).

Isso significa que o pipeline completo existe no código, mas a orquestração padrão ainda não está conectada fim a fim.

---

## 4) Modelo de dados observado

### Saída principal
- CSV de chamadas com colunas:
  - `Project`
  - `File`
  - `Caller`
  - `Callee`

### Saída de variabilidade (em evolução)
- JSON de diretivas (`*_directives_list.json`)
- JSON de instruções por condição (`*_instructions_code.json`)
- Variante de CSV planejada com coluna adicional `Conditional_Compilation`.

---

## 5) Diagnóstico técnico: riscos e gargalos para escalar

### 5.1 Acoplamento frágil e inconsistências internas
- `main.py` não conecta o pipeline completo por padrão.
- `configurable_systems.py` chama `DirectiveExtractor(tree)`, mas `DirectiveExtractor` foi implementado para receber `file_path` de arquivo XML. Há incompatibilidade de interface.
- `configurable_systems.py` tenta usar método `extract_conditionals(call)`, que não existe na implementação atual de `DirectiveExtractor`.

### 5.2 Escalabilidade de ingestão limitada
- Download via API `/contents` recursiva gera muitas chamadas HTTP e overhead em repositórios grandes.
- Ausência de concorrência controlada para IO de rede e escrita local.
- Ausência de cache/deduplicação por hash de arquivo ou commit SHA.

### 5.3 Escalabilidade de análise limitada
- Processamento arquivo-a-arquivo, predominantemente sequencial.
- Conversão `srcml` por subprocesso para cada arquivo sem pool de workers.
- XML temporário salvo no diretório do projeto, elevando IO e footprint em grandes volumes.

### 5.4 Confiabilidade operacional
- Em muitos pontos, erros chamam `sys.exit(1)`, interrompendo batch inteiro em vez de isolar falhas por arquivo/projeto.
- Logs estruturados inexistentes (somente `print`), dificultando observabilidade.
- Dependências e configuração operacionais (SMTP/token/srcml) sem camada robusta de validação de ambiente.

### 5.5 Reprodutibilidade e governança de dados
- Ausência de versionamento do dataset extraído (metadados por execução, commit SHA, timestamp, versão do parser).
- Sem checkpoints de progresso para retomar jobs longos após falha.

---

## 6) Estratégia recomendada para evoluir para sistemas grandes/complexos

## Fase A — estabilização arquitetural (curto prazo)
1. **Refatorar para pipeline explícito**: `discover -> fetch -> parse -> extract -> persist`.
2. **Definir contratos de módulo** com dataclasses/tipos claros (entrada/saída por estágio).
3. **Unificar analisadores** (`program_snc` e `configurable_systems`) em uma engine com feature flags.
4. **Trocar `print` por logging estruturado** (json logs + níveis).
5. **Tratamento de erro resiliente**: falha por arquivo não derruba execução global.

## Fase B — performance e escala (médio prazo)
1. **Paralelismo controlado**:
   - ThreadPool/async para download.
   - ProcessPool para parsing `srcml`/XML.
2. **Processamento incremental**:
   - registrar `repo`, `commit`, `path`, `sha256`, `status`.
   - pular arquivos já processados sem mudança.
3. **Formato de saída analítico**:
   - migrar CSV para Parquet (particionado por projeto/data).
4. **Orquestração por lotes**:
   - filas (ex.: Celery/RQ) ou jobs distribuídos.
5. **Limitar memória e IO** com streaming e limpeza de artefatos temporários.

## Fase C — qualidade analítica (médio/longo prazo)
1. **Melhorar precisão do call graph**:
   - distinguir chamadas de função vs macro/ponteiros.
   - capturar contexto de escopo/arquivo/assinatura.
2. **Variabilidade real para SPL**:
   - associar cada aresta caller→callee a expressão proposicional de presença.
   - normalizar condições (`#if/#elif/#else`) para forma canônica.
3. **Validação de qualidade**:
   - suíte de testes com repositórios-ouro (fixtures).
   - métricas de cobertura, precisão e taxa de erro por estágio.

---

## 7) Backlog priorizado (prático)

### Prioridade P0
- Corrigir incompatibilidade `configurable_systems` ↔ `directive_extractor`.
- Reativar pipeline fim-a-fim em `main.py` com argumentos de linha de comando.
- Implementar logging estruturado + relatório final de execução.

### Prioridade P1
- Paralelizar download e parsing.
- Persistir metadados de execução (run_id, tempos, erros, versão).
- Suportar modo incremental por hash/commit.

### Prioridade P2
- Migrar saída para Parquet + catálogo de dados.
- Adicionar testes automatizados (unit + integração com fixtures C).
- Criar benchmark em repositórios grandes para medir throughput e custo.

---

## 8) KPIs recomendados para acompanhar escalabilidade

- **Throughput de ingestão**: arquivos C/minuto.
- **Throughput de análise**: funções/minuto e chamadas/minuto.
- **Taxa de falha**: % de arquivos com erro por estágio.
- **Custo por milhão de linhas C**: tempo, CPU e armazenamento.
- **Reprocessamento evitado**: % de arquivos pulados no modo incremental.
- **Latência ponta a ponta por repositório**.

---

## 9) Conclusão objetiva

O repositório já contém os blocos essenciais para mineração de caller/callee em C, mas ainda em formato de protótipo com acoplamento e lacunas de robustez. A evolução para sistemas grandes requer, primeiro, **consolidar arquitetura e contratos**, depois **adotar processamento incremental/paralelo**, e por fim elevar **qualidade analítica e observabilidade**.

Com esse plano, a ferramenta deixa de ser um script pipeline local e passa a operar como plataforma de mineração estática em escala.
