import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import duckdb

# Configuração de Página Premium
st.set_page_config(
    page_title="COVID-19 ES Dashboard - DW Optimized",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Customizada para Design Premium
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif;
        background-color: #0b0f19;
        color: #f1f5f9;
    }
    
    [data-testid="stHeader"] {
        background: rgba(11, 15, 25, 0.85);
        backdrop-filter: blur(12px);
    }
    
    h1, h2, h3, h4 {
        color: #60a5fa !important;
        font-weight: 700 !important;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #10b981;
    }
    
    div[data-testid="metric-container"] {
        background-color: #131a2e;
        border: 1px solid #1e293b;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        transition: transform 0.2s ease-in-out;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #10b981;
    }
    
    .exercise-box {
        background-color: #0f172a;
        padding: 25px;
        border-radius: 16px;
        border: 1px solid #1e293b;
        margin-bottom: 25px;
    }
    
    .stDataFrame {
        border: 1px solid #1e293b;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = 'dw_covid.db'

st.title("⚡ Monitoramento COVID-19 Espírito Santo (DW Optimized)")
st.write("Esta versão consome dados agregados diretamente do **Data Warehouse (DuckDB)** por meio de consultas SQL otimizadas.")

# Sidebar de controle
st.sidebar.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6sFsw_B-kM8bM8J2u98YjT6l2TzYj2K260w&s", width=80)
st.sidebar.header("Filtros do Painel")
municipio_filtro = st.sidebar.text_input("Filtrar por Município (ex: SERRA, VITORIA):", "").strip().upper()

# Função de execução de SQL com cache para evitar recarregar dados
@st.cache_data(show_spinner="Executando consulta SQL no DW...")
def run_query(sql, params=None):
    con = duckdb.connect(DB_PATH, read_only=True)
    if params:
        res = con.execute(sql, params).df()
    else:
        res = con.execute(sql).df()
    con.close()
    return res

# Trata a cláusula WHERE para filtros dinâmicos de localidade
where_clause = ""
params = []
if municipio_filtro:
    where_clause = "AND l.municipio = ?"
    params = [municipio_filtro]

try:
    # Criação do layout em colunas para os Metadados Gerais (Exercício 1 e 2)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 1: Metadados do Dataset (Volume Geral)")
        # Consulta rápida de contagem
        sql_count = f"""
        SELECT COUNT(*) as total_rows 
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        WHERE 1=1 {where_clause}
        """
        df_count = run_query(sql_count, params)
        total_rows = df_count.loc[0, 'total_rows']
        
        st.metric("Total de Linhas (Registros)", f"{total_rows:,}")
        st.metric("Total de Colunas", "45")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 2: Contagem de Nulos / Ausentes")
        # Consulta de nulos agregada no banco
        sql_nulls = f"""
        SELECT 
            SUM(CASE WHEN f.fk_tempo_cadastro = -1 THEN 1 ELSE 0 END) as DataCadastro,
            SUM(CASE WHEN f.fk_tempo_diagnostico = -1 THEN 1 ELSE 0 END) as DataDiagnostico,
            SUM(CASE WHEN f.fk_tempo_encerramento = -1 THEN 1 ELSE 0 END) as DataEncerramento,
            SUM(CASE WHEN f.fk_tempo_obito = -1 THEN 1 ELSE 0 END) as DataObito,
            SUM(CASE WHEN ce.evolucao = 'NÃO INFORMADO' THEN 1 ELSE 0 END) as Evolucao
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
        WHERE 1=1 {where_clause}
        """
        df_nulls_raw = run_query(sql_nulls, params)
        null_data = {
            'Coluna': ['DataCadastro', 'DataDiagnostico', 'DataEncerramento', 'DataObito', 'Evolucao'],
            'Valores Ausentes': [
                int(df_nulls_raw.loc[0, 'DataCadastro']),
                int(df_nulls_raw.loc[0, 'DataDiagnostico']),
                int(df_nulls_raw.loc[0, 'DataEncerramento']),
                int(df_nulls_raw.loc[0, 'DataObito']),
                int(df_nulls_raw.loc[0, 'Evolucao'])
            ]
        }
        df_nulls = pd.DataFrame(null_data)
        st.dataframe(df_nulls, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Exercício 3: Evolução Temporal das Notificações
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 3: Evolução Temporal das Notificações (Por Mês)")
    sql_temporal = f"""
    SELECT t.ano_mes as AnoMes, COUNT(*) as Notificacoes
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_tempo t ON f.fk_tempo_notificacao = t.sk_tempo
    WHERE t.sk_tempo != -1 {where_clause}
    GROUP BY t.ano_mes
    ORDER BY t.ano_mes
    """
    evolucao_temp = run_query(sql_temporal, params)
    
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor('#0b0f19')
    ax.set_facecolor('#0f172a')
    
    ax.bar(evolucao_temp['AnoMes'], evolucao_temp['Notificacoes'], color='#3b82f6')
    ax.set_xticklabels(evolucao_temp['AnoMes'], rotation=45, ha='right', color='#94a3b8')
    ax.tick_params(colors='#94a3b8')
    ax.spines['bottom'].set_color('#1e293b')
    ax.spines['left'].set_color('#1e293b')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title("Casos Notificados ao Longo do Tempo (via DW)", color='#60a5fa', fontsize=12)
    
    st.pyplot(fig)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 4: Pirâmide Etária dos Óbitos por COVID-19
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 4: Pirâmide Etária de Óbitos por COVID-19")
    sql_pyramid = f"""
    SELECT p.faixa_etaria as FaixaEtaria, p.sexo as Sexo, COUNT(*) as obitos
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
    JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
    WHERE ce.evolucao = 'ÓBITO PELO COVID-19' 
      AND p.sexo IN ('M', 'F') {where_clause}
    GROUP BY p.faixa_etaria, p.sexo
    """
    df_pyramid_raw = run_query(sql_pyramid, params)
    
    if len(df_pyramid_raw) > 0:
        pyramid_data = df_pyramid_raw.pivot(index='FaixaEtaria', columns='Sexo', values='obitos').fillna(0).reset_index()
        pyramid_data['ordem'] = pyramid_data['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
        pyramid_data = pyramid_data.sort_values('ordem')
        
        if 'M' not in pyramid_data.columns: pyramid_data['M'] = 0
        if 'F' not in pyramid_data.columns: pyramid_data['F'] = 0
        
        males = -pyramid_data['M'].values
        females = pyramid_data['F'].values
        categories = pyramid_data['FaixaEtaria'].values
        
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor('#0b0f19')
        ax.set_facecolor('#0f172a')
        
        ax.barh(categories, males, color='#3b82f6', label='Masculino')
        ax.barh(categories, females, color='#ec4899', label='Feminino')
        
        abs_ticks = np.abs(ax.get_xticks())
        ax.set_xticklabels([f"{val:,.0f}" for val in abs_ticks])
        ax.tick_params(colors='#94a3b8')
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(facecolor='#0f172a', edgecolor='#1e293b', labelcolor='#f1f5f9')
        ax.set_title("Distribuição de Óbitos por Sexo e Faixa Etária (via DW)", color='#60a5fa', fontsize=12)
        
        st.pyplot(fig)
    else:
        st.warning("Sem dados de óbito disponíveis para o filtro selecionado.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 5: Distribuição por Comorbidades
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 5: Distribuição por Comorbidades")
    sql_comorb = f"""
    SELECT 
        SUM(CASE WHEN cl.comorbidade_pulmao = 'SIM' THEN 1 ELSE 0 END) as Pulmao,
        SUM(CASE WHEN cl.comorbidade_cardio = 'SIM' THEN 1 ELSE 0 END) as Cardio,
        SUM(CASE WHEN cl.comorbidade_renal = 'SIM' THEN 1 ELSE 0 END) as Renal,
        SUM(CASE WHEN cl.comorbidade_diabetes = 'SIM' THEN 1 ELSE 0 END) as Diabetes,
        SUM(CASE WHEN cl.comorbidade_tabagismo = 'SIM' THEN 1 ELSE 0 END) as Tabagismo,
        SUM(CASE WHEN cl.comorbidade_obesidade = 'SIM' THEN 1 ELSE 0 END) as Obesidade
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_clinico cl ON f.fk_clinico = cl.sk_clinico
    WHERE 1=1 {where_clause}
    """
    df_comorb_raw = run_query(sql_comorb, params)
    comorb_data = {
        'Comorbidade': ['Pulmão', 'Cardio', 'Renal', 'Diabetes', 'Tabagismo', 'Obesidade'],
        'Casos': [
            int(df_comorb_raw.loc[0, 'Pulmao']),
            int(df_comorb_raw.loc[0, 'Cardio']),
            int(df_comorb_raw.loc[0, 'Renal']),
            int(df_comorb_raw.loc[0, 'Diabetes']),
            int(df_comorb_raw.loc[0, 'Tabagismo']),
            int(df_comorb_raw.loc[0, 'Obesidade'])
        ]
    }
    df_comorb = pd.DataFrame(comorb_data).sort_values('Casos', ascending=False)
    
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor('#0b0f19')
    ax.set_facecolor('#0f172a')
    ax.bar(df_comorb['Comorbidade'], df_comorb['Casos'], color='#10b981')
    ax.tick_params(colors='#94a3b8')
    ax.spines['bottom'].set_color('#1e293b')
    ax.spines['left'].set_color('#1e293b')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title("Prevalência de Comorbidades Declaradas (via DW)", color='#60a5fa', fontsize=12)
    st.pyplot(fig)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 6: Crosstab: Top 5 Municípios vs. Evolução
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 6: Crosstab - Top 5 Municípios com Mais Casos vs. Evolução do Caso")
    
    if not municipio_filtro:
        # Busca os top 5 municípios em termos de casos
        sql_top_cities = """
        SELECT l.municipio, COUNT(*) as casos
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        WHERE l.municipio != 'NÃO INFORMADO'
        GROUP BY l.municipio
        ORDER BY casos DESC
        LIMIT 5
        """
        df_top_cities = run_query(sql_top_cities)
        top_cities = df_top_cities['municipio'].tolist()
        
        # Consulta crosstab apenas para os top 5
        sql_ct = f"""
        SELECT l.municipio as Municipio, ce.evolucao as Evolucao, COUNT(*) as qtd
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
        WHERE l.municipio IN ({','.join(["?"] * len(top_cities))})
        GROUP BY l.municipio, ce.evolucao
        """
        df_ct = run_query(sql_ct, top_cities)
    else:
        # Se filtrado, exibe crosstab do município selecionado
        sql_ct = """
        SELECT l.municipio as Municipio, ce.evolucao as Evolucao, COUNT(*) as qtd
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
        WHERE l.municipio = ?
        GROUP BY l.municipio, ce.evolucao
        """
        df_ct = run_query(sql_ct, [municipio_filtro])
        
    if len(df_ct) > 0:
        ct = df_ct.pivot(index='Municipio', columns='Evolucao', values='qtd').fillna(0).astype(int)
        st.dataframe(ct, use_container_width=True)
    else:
        st.warning("Sem dados suficientes para gerar a tabela cruzada.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Colunas para Exercícios 7 e 8
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 7: Perfil de Casos por Sexo e Raça/Cor")
        sql_sex_raca = f"""
        SELECT p.raca_cor as RacaCor, p.sexo as Sexo, COUNT(*) as qtd
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
        WHERE 1=1 {where_clause}
        GROUP BY p.raca_cor, p.sexo
        """
        df_sex_raca = run_query(sql_sex_raca, params)
        if len(df_sex_raca) > 0:
            ct_sex_raca = df_sex_raca.pivot(index='RacaCor', columns='Sexo', values='qtd').fillna(0).astype(int)
            st.dataframe(ct_sex_raca, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col4:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 8: Análise de Métodos de Teste e Resultados")
        sql_tests = f"""
        SELECT e.tipo_teste_rapido as TipoTeste, e.resultado_teste_rapido as ResultadoTeste, COUNT(*) as qtd
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_exame e ON f.fk_exame = e.sk_exame
        WHERE e.tipo_teste_rapido != 'NÃO INFORMADO' {where_clause}
        GROUP BY e.tipo_teste_rapido, e.resultado_teste_rapido
        """
        df_tests = run_query(sql_tests, params)
        if len(df_tests) > 0:
            ct_tests = df_tests.pivot(index='TipoTeste', columns='ResultadoTeste', values='qtd').fillna(0).astype(int)
            st.dataframe(ct_tests, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Colunas para Exercícios 9 e 10
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 9: Proporção de Internações por Faixa Etária")
        sql_interna = f"""
        SELECT p.faixa_etaria as FaixaEtaria, 
               SUM(CASE WHEN cl.ficou_internado = 'SIM' THEN 1 ELSE 0 END) as internados,
               COUNT(*) as total_casos
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
        JOIN dim_clinico cl ON f.fk_clinico = cl.sk_clinico
        WHERE cl.ficou_internado != 'NÃO INFORMADO' {where_clause}
        GROUP BY p.faixa_etaria
        """
        df_interna = run_query(sql_interna, params)
        
        if len(df_interna) > 0:
            df_interna['Porcentagem Internados'] = (df_interna['internados'] / df_interna['total_casos']) * 100
            df_interna['ordem'] = df_interna['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
            df_interna = df_interna.sort_values('ordem')
            
            fig, ax = plt.subplots(figsize=(6, 4))
            fig.patch.set_facecolor('#0b0f19')
            ax.set_facecolor('#0f172a')
            ax.barh(df_interna['FaixaEtaria'], df_interna['Porcentagem Internados'], color='#f59e0b')
            ax.tick_params(colors='#94a3b8')
            ax.spines['bottom'].set_color('#1e293b')
            ax.spines['left'].set_color('#1e293b')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.set_xlabel("Taxa de Internação (%)", color='#94a3b8')
            st.pyplot(fig)
        else:
            st.warning("Sem dados suficientes de internações.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col6:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 10: Notificações de Profissionais de Saúde")
        sql_prof = f"""
        SELECT p.profissional_saude as ProfissionalSaude, COUNT(*) as qtd
        FROM fato_notificacoes f
        JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
        JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
        WHERE 1=1 {where_clause}
        GROUP BY p.profissional_saude
        """
        df_prof = run_query(sql_prof, params)
        
        if len(df_prof) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            fig.patch.set_facecolor('#0b0f19')
            ax.set_facecolor('#0f172a')
            
            ax.pie(
                df_prof['qtd'].values,
                labels=df_prof['ProfissionalSaude'].values,
                colors=['#3b82f6', '#f43f5e', '#64748b'],
                autopct='%1.1f%%',
                textprops={'color': '#f1f5f9'}
            )
            ax.set_title("Casos - Profissionais de Saúde (via DW)", color='#60a5fa')
            st.pyplot(fig)
        else:
            st.warning("Sem dados disponíveis.")
        st.markdown('</div>', unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro ao conectar ou consultar o DW: {e}")
    st.info("Verifique se você rodou o pipeline de ETL (`etl_pipeline.py`) para criar e popular o banco de dados `dw_covid.db`.")
