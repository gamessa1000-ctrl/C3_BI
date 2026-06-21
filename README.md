# COVID-19 ES Analytics: Migração de Arquitetura CSV para Data Warehouse (DuckDB)

**Autor:** Matheus Rhamet  
**Professor Orientador:** Otávio Lube  
**Disciplina:** Business Intelligence (BI) - Projeto C3 (Etapa Final Integradora)

---

## 1. Introdução Técnica
Este projeto consiste na migração de um sistema analítico legado (desenvolvido na C1), que consumia dados diretamente de arquivos brutos CSV de microdados do COVID-19 do Espírito Santo, para uma arquitetura moderna de **Data Warehouse (DW) colunar analítico com DuckDB**. 

A solução resolve as restrições físicas de processamento em memória e I/O de disco associadas ao arquivo original de **5.187.769 linhas (~1.95 GB)**. Através de um pipeline de ETL otimizado em Python, os dados foram estruturados em um modelo estrela (Star Schema) de alta performance, reduzindo drasticamente o tempo de resposta das visualizações do dashboard Streamlit e economizando memória RAM do servidor de aplicação.

---

## 2. Diagrama de Arquitetura de Dados

O fluxo de dados da arquitetura implementada está estruturado da seguinte forma:

```
[MICRODADOS.csv] (1.95 GB)
       │
       ▼ (Leitura em lotes de 500.000 linhas)
[etl_pipeline.py] (Pandas + SQLAlchemy) 
       │
       ├──► Limpeza, Tipagem (str) e Governança de Nulos (SK = -1)
       ├──► Enriquecimento & Aplicação de Regra SCD Tipo 2 (Município de Anchieta)
       ├──► Auditoria de Integridade e Reconciliação Volumétrica 1:1
       │
       ▼ (Carga Fata + Dimensões)
[dw_covid.db] (DuckDB Data Warehouse - Esquema Estrela)
       │
       ├──► dim_tempo (Role-Playing)
       ├──► dim_localidade (SCD Tipo 2)
       ├──► dim_paciente
       ├──► dim_exame
       ├──► dim_classificacao_evolucao
       ├──► dim_clinico (Junk Dimension)
       ├──► fato_notificacoes
       │
       ▼ (Consultas SQL Agregadas e Cacheadas via st.cache_data)
[app_dw.py] (Streamlit Dashboard Otimizado)
```

---

## 3. Estrutura do Repositório

* `etl_pipeline.py`: Script Python responsável pela extração, limpeza, enriquecimento, modelagem dimensional e carga (ETL) no banco de dados analítico.
* `app_dw.py`: Painel analítico Streamlit migrado e otimizado para ler dados agregados do DW.
* `app.py`: Painel analítico Streamlit legado (baseline) que realiza a leitura direta do CSV para propósitos de teste.
* `performance_benchmark.py`: Script de auditoria empírica para testes de tempo e memória.
* `etl_execution.log`: Log de execução detalhado do ETL.
* `README.md`: Documentação geral do repositório.

---

## 4. Guia de Configuração e Execução

Siga os passos abaixo para configurar o ambiente e executar os scripts do projeto em seu ambiente local.

### Passo 1: Clonar o Repositório e Acessar a Pasta
```bash
git clone <url-do-seu-repositorio>
cd c3_BI
```

### Passo 2: Criar e Ativar o Ambiente Virtual (venv)
No Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Passo 3: Instalar as Dependências
Com o ambiente virtual ativado, instale as bibliotecas necessárias para o projeto:
```bash
pip install pandas numpy duckdb streamlit matplotlib seaborn
```

### Passo 4: Executar o Pipeline de ETL
Este script criará o banco de dados analítico local `dw_covid.db` (DuckDB), criará o esquema estrela e inserirá o volume completo de dados:
```bash
python etl_pipeline.py
```
*Acompanhe o progresso da carga em tempo real no terminal ou abra o arquivo `etl_execution.log` para inspecionar os tempos e a reconciliação volumétrica 1:1.*

### Passo 5: Rodar os Testes de Benchmarking
Compare empiricamente a performance da versão CSV contra o DW executando:
```bash
python performance_benchmark.py
```
*O script salvará no diretório os gráficos comparativos `benchmark_time.png` e `benchmark_memory.png`.*

### Passo 6: Executar os Dashboards Streamlit
Para visualizar e interagir com as métricas do projeto:
* **Executar a versão DW (Otimizada):**
  ```bash
  streamlit run app_dw.py
  ```
* **Executar a versão CSV (Baseline):**
  ```bash
  streamlit run app.py
  ```
