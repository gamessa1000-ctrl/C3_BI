import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import duckdb

# Configuração de Página Premium
st.set_page_config(
    page_title="COVID-19 ES Analytics - DW Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Customizada de Alta Fidelidade (Premium Dashboard UI)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif;
        background-color: #080c14;
        color: #e2e8f0;
    }
    
    [data-testid="stHeader"] {
        background: rgba(8, 12, 20, 0.85);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid #1e293b;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f8fafc !important;
        font-weight: 600 !important;
    }
    
    /* Custom Card Style */
    .dashboard-card {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
    }
    
    /* KPI Card Style */
    div[data-testid="metric-container"] {
        background-color: #0f172a;
        border: 1px solid #1e293b;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #3b82f6;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
        color: #3b82f6;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.95rem;
        font-weight: 500;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .stDataFrame {
        border: 1px solid #1e293b;
        border-radius: 12px;
        overflow: hidden;
    }
    
    /* Custom Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0b0f19;
        border-right: 1px solid #1e293b;
    }
    
    /* Title style banner */
    .title-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
        padding: 40px;
        border-radius: 20px;
        border: 1px solid #1e293b;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = 'dw_covid.db'

# --- BANNER DE TÍTULO PREMIUM ---
st.markdown("""
<div class="title-banner">
    <h1 style='margin: 0; font-size: 2.5rem; color: #ffffff;'>🦠 Painel Analítico COVID-19 Espírito Santo</h1>
    <p style='margin: 10px 0 0 0; font-size: 1.1rem; color: #94a3b8;'>
        Ambiente de Tomada de Decisão com Performance Colunar DuckDB • Desenvolvido por <b>Matheus Rhamet</b>
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar de controle
st.sidebar.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6sFsw_B-kM8bM8J2u98YjT6l2TzYj2K260w&s", width=80)
st.sidebar.markdown("<h3 style='margin-top: 10px; color:#ffffff;'>Filtros de Análise</h3>", unsafe_allow_html=True)
st.sidebar.write("Refine a base de 5.18M de linhas instantaneamente:")
municipio_filtro = st.sidebar.text_input("Filtrar por Município (ex: SERRA, VITORIA):", "").strip().upper()

# Função de execução de SQL com cache
@st.cache_data(show_spinner=False)
def run_query(sql, params=None):
    con = duckdb.connect(DB_PATH, read_only=True)
    if params:
        res = con.execute(sql, params).df()
    else:
        res = con.execute(sql).df()
    con.close()
    return res

# Define a cláusula WHERE baseada nos filtros
where_clause = ""
params = []
if municipio_filtro:
    where_clause = "AND l.municipio = ?"
    params = [municipio_filtro]

try:
    # --- BLOCO 1: INDICADORES CHAVE DE PERFORMANCE (KPIs) ---
    sql_kpis = f"""
    SELECT 
        COUNT(*) as total_cases,
        SUM(qtd_confirmados) as confirmados,
        SUM(qtd_obitos) as obitos,
        SUM(qtd_curados) as curados
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    WHERE 1=1 {where_clause}
    """
    df_kpis = run_query(sql_kpis, params)
    
    total_cases = int(df_kpis.loc[0, 'total_cases'])
    confirmados = int(df_kpis.loc[0, 'confirmados']) if pd.notnull(df_kpis.loc[0, 'confirmados']) else 0
    obitos = int(df_kpis.loc[0, 'obitos']) if pd.notnull(df_kpis.loc[0, 'obitos']) else 0
    curados = int(df_kpis.loc[0, 'curados']) if pd.notnull(df_kpis.loc[0, 'curados']) else 0
    letalidade = (obitos / confirmados * 100) if confirmados > 0 else 0.0
    
    # Exibição dos KPIs em 5 colunas limpas
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    kpi_col1.metric(label="Total Notificações", value=f"{total_cases:,}")
    kpi_col2.metric(label="Casos Confirmados", value=f"{confirmados:,}")
    kpi_col3.metric(label="Óbitos Confirmados", value=f"{obitos:,}")
    kpi_col4.metric(label="Pacientes Recuperados", value=f"{curados:,}")
    kpi_col5.metric(label="Taxa de Letalidade", value=f"{letalidade:.2f}%")
    
    st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)
    
    # --- BLOCO 2: EVOLUÇÃO TEMPORAL & COMORBIDADES (Grid 70% / 30%) ---
    row2_col1, row2_col2 = st.columns([7, 3])
    
    with row2_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 3: Evolução Temporal das Notificações")
        
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
        
        fig, ax = plt.subplots(figsize=(10, 4.2))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0b0f19')
        
        # Gráfico de linha suave e área preenchida para visual elegante
        ax.plot(evolucao_temp['AnoMes'], evolucao_temp['Notificacoes'], color='#38bdf8', linewidth=3, marker='o', markersize=4, label='Casos')
        ax.fill_between(evolucao_temp['AnoMes'], evolucao_temp['Notificacoes'], color='#38bdf8', alpha=0.12)
        
        # Organização dos eixos temporais (evita embaralhamento)
        all_months = evolucao_temp['AnoMes'].values
        if len(all_months) > 0:
            step = max(1, len(all_months) // 8) # Exibe até 8 ticks na tela
            ticks = all_months[::step]
            ax.set_xticks(ticks)
            ax.set_xticklabels(ticks, rotation=35, ha='right', color='#94a3b8', fontsize=9)
            
        ax.tick_params(colors='#94a3b8', axis='y')
        ax.grid(True, which='both', color='#1e293b', linestyle=':', linewidth=0.5)
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_ylabel("Quantidade de Casos", color='#94a3b8', fontsize=10)
        
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row2_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 5: Prevalência de Comorbidades")
        
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
        df_comorb = pd.DataFrame(comorb_data).sort_values('Casos', ascending=True)
        
        fig, ax = plt.subplots(figsize=(4, 4.3))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0b0f19')
        
        # Gráfico de barras horizontais organizado
        bars = ax.barh(df_comorb['Comorbidade'], df_comorb['Casos'], color='#34d399', height=0.6)
        
        # Adiciona rótulos com os valores ao lado das barras
        for bar in bars:
            width = bar.get_width()
            ax.annotate(f'{width:,}',
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0),
                        textcoords="offset points",
                        ha='left', va='center', color='#e2e8f0', fontsize=8, fontweight='bold')
                        
        ax.tick_params(colors='#94a3b8')
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_color('#1e293b')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xticklabels([]) # Remove ticks do X para deixar limpo
        ax.grid(False)
        
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 3: PERFIL DE PACIENTE (PIRÂMIDE ETÁRIA & INTERNAÇÕES) (Grid 50% / 50%) ---
    row3_col1, row3_col2 = st.columns(2)
    
    with row3_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 4: Pirâmide Etária dos Óbitos")
        
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
            
            fig, ax = plt.subplots(figsize=(6, 4.3))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0b0f19')
            
            ax.barh(categories, males, color='#60a5fa', label='Masculino', height=0.6)
            ax.barh(categories, females, color='#f472b6', label='Feminino', height=0.6)
            
            # Formata eixo X para escala absoluta sem sinal negativo
            abs_ticks = np.abs(ax.get_xticks())
            ax.set_xticks(ax.get_xticks())
            ax.set_xticklabels([f"{val:,.0f}" for val in abs_ticks])
            
            ax.tick_params(colors='#94a3b8')
            ax.grid(True, which='both', color='#1e293b', linestyle=':', linewidth=0.5)
            ax.spines['bottom'].set_color('#1e293b')
            ax.spines['left'].set_color('#1e293b')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.legend(facecolor='#0b0f19', edgecolor='#1e293b', labelcolor='#e2e8f0')
            
            st.pyplot(fig)
        else:
            st.warning("Sem dados de óbito disponíveis para o filtro selecionado.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row3_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 9: Taxa de Internação por Faixa Etária")
        
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
            
            fig, ax = plt.subplots(figsize=(6, 4.3))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0b0f19')
            
            # Gráfico elegante de barras horizontais ordenadas
            bars = ax.barh(df_interna['FaixaEtaria'], df_interna['Porcentagem Internados'], color='#f59e0b', height=0.6)
            
            # Mostra o valor percentual ao lado de cada barra
            for bar in bars:
                width = bar.get_width()
                ax.annotate(f'{width:.1f}%',
                            xy=(width, bar.get_y() + bar.get_height() / 2),
                            xytext=(5, 0),
                            textcoords="offset points",
                            ha='left', va='center', color='#e2e8f0', fontsize=8, fontweight='bold')
                            
            ax.tick_params(colors='#94a3b8')
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_color('#1e293b')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.set_xticklabels([])
            ax.grid(False)
            
            st.pyplot(fig)
        else:
            st.warning("Sem dados suficientes de internações.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 4: TABELAS CRUZADAS (CROSSTABS) (Grid 50% / 50%) ---
    row4_col1, row4_col2 = st.columns(2)
    
    with row4_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 6: Top 5 Municípios vs. Evolução do Caso")
        
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
            st.warning("Sem dados suficientes.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row4_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
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
        else:
            st.warning("Sem dados suficientes.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 5: MÉTODOS DE TESTES & PROFISSIONAIS DE SAÚDE (Grid 50% / 50%) ---
    row5_col1, row5_col2 = st.columns(2)
    
    with row5_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 8: Métodos de Testes Rápidos e Resultados")
        
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
        else:
            st.warning("Sem dados suficientes.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row5_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
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
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0b0f19')
            
            # Gráfico de Donut Moderno
            ax.pie(
                df_prof['qtd'].values,
                labels=df_prof['ProfissionalSaude'].values,
                colors=['#38bdf8', '#fb7185', '#64748b'],
                autopct='%1.1f%%',
                pctdistance=0.75,
                textprops={'color': '#f8fafc', 'fontsize': 9, 'weight': 'bold'},
                wedgeprops=dict(width=0.4, edgecolor='#0f172a', linewidth=2) # Cria o centro vazado (donut)
            )
            ax.set_title("Proporção - Profissionais de Saúde", color='#94a3b8', fontsize=11, pad=10)
            
            st.pyplot(fig)
        else:
            st.warning("Sem dados suficientes.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- FOOTER DO PAINEL ---
    st.markdown("""
    <div style='text-align: center; margin-top: 50px; padding: 20px; border-top: 1px solid #1e293b;'>
        <p style='color: #64748b; font-size: 0.85rem;'>
            Tecnologias: Streamlit • DuckDB Colunar • Matplotlib • Pandas • SQL | Trabalho Individual de Matheus Rhamet
        </p>
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro ao conectar ou consultar o DW: {e}")
    st.info("Verifique se o banco dw_covid.db foi populado pelo etl_pipeline.py.")
