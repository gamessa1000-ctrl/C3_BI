import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Configuração de Página Premium
st.set_page_config(
    page_title="COVID-19 ES Dashboard - CSV Baseline",
    page_icon="🦠",
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
        background: linear-gradient(135deg, #1e3b8b 0%, #0f172a 100%);
        padding: 40px;
        border-radius: 20px;
        border: 1px solid #1e293b;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

CSV_PATH = 'MICRODADOS.csv'

# --- BANNER DE TÍTULO PREMIUM ---
st.markdown("""
<div class="title-banner">
    <h1 style='margin: 0; font-size: 2.5rem; color: #ffffff;'>🦠 Painel Analítico COVID-19 Espírito Santo (CSV)</h1>
    <p style='margin: 10px 0 0 0; font-size: 1.1rem; color: #94a3b8;'>
        Ambiente de Tomada de Decisão com Pandas in-memory • Desenvolvido por <b>Matheus Rhamet</b>
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar de controle
st.sidebar.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6sFsw_B-kM8bM8J2u98YjT6l2TzYj2K260w&s", width=80)
st.sidebar.markdown("<h3 style='margin-top: 10px; color:#ffffff;'>Filtros de Análise</h3>", unsafe_allow_html=True)
st.sidebar.write("Filtragem de linhas na memória RAM:")
municipio_filtro = st.sidebar.text_input("Filtrar por Município (ex: SERRA, VITORIA):", "").strip().upper()

# Função de Carregamento com Cache do Pandas
@st.cache_data(show_spinner="Carregando e processando arquivo CSV (isso pode demorar de 30s a 1min)...")
def load_data():
    df = pd.read_csv(CSV_PATH, sep=';', encoding='latin-1', dtype=str)
    df = df.fillna('Não Informado')
    return df

try:
    df_raw = load_data()
    
    if municipio_filtro:
        df = df_raw[df_raw['Municipio'].str.upper() == municipio_filtro].copy()
    else:
        df = df_raw
        
    # --- BLOCO 1: INDICADORES CHAVE DE PERFORMANCE (KPIs) ---
    total_cases = len(df)
    confirmados = (df['Classificacao'].str.upper() == 'CONFIRMADOS').sum()
    obitos = (df['Evolucao'].str.upper() == 'ÓBITO PELO COVID-19').sum()
    curados = (df['Evolucao'].str.upper() == 'CURA').sum()
    letalidade = (obitos / confirmados * 100) if confirmados > 0 else 0.0
    
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
        
        df_dates = df[df['DataNotificacao'] != 'Não Informado'].copy()
        df_dates['AnoMes'] = df_dates['DataNotificacao'].str[:7]
        evolucao_temp = df_dates['AnoMes'].value_counts().sort_index().reset_index()
        evolucao_temp.columns = ['AnoMes', 'Notificacoes']
        
        fig, ax = plt.subplots(figsize=(10, 4.2))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0b0f19')
        
        ax.plot(evolucao_temp['AnoMes'], evolucao_temp['Notificacoes'], color='#38bdf8', linewidth=3, marker='o', markersize=4)
        ax.fill_between(evolucao_temp['AnoMes'], evolucao_temp['Notificacoes'], color='#38bdf8', alpha=0.12)
        
        all_months = evolucao_temp['AnoMes'].values
        if len(all_months) > 0:
            step = max(1, len(all_months) // 8)
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
        
        comorbidades_cols = [
            'ComorbidadePulmao', 'ComorbidadeCardio', 'ComorbidadeRenal',
            'ComorbidadeDiabetes', 'ComorbidadeTabagismo', 'ComorbidadeObesidade'
        ]
        comorb_counts = {col.replace('Comorbidade', ''): (df[col].str.upper() == 'SIM').sum() for col in comorbidades_cols}
        df_comorb = pd.DataFrame(list(comorb_counts.items()), columns=['Comorbidade', 'Casos']).sort_values('Casos', ascending=True)
        
        fig, ax = plt.subplots(figsize=(4, 4.3))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0b0f19')
        
        bars = ax.barh(df_comorb['Comorbidade'], df_comorb['Casos'], color='#34d399', height=0.6)
        
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
        ax.set_xticklabels([])
        ax.grid(False)
        
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 3: PERFIL DE PACIENTE (PIRÂMIDE ETÁRIA & INTERNAÇÕES) ---
    row3_col1, row3_col2 = st.columns(2)
    
    with row3_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 4: Pirâmide Etária dos Óbitos")
        
        df_obitos = df[(df['Evolucao'].str.upper() == 'ÓBITO PELO COVID-19') & (df['Sexo'].str.upper().isin(['M', 'F']))].copy()
        pyramid_data = df_obitos.groupby(['FaixaEtaria', 'Sexo']).size().unstack(fill_value=0).reset_index()
        pyramid_data['ordem'] = pyramid_data['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
        pyramid_data = pyramid_data.sort_values('ordem')
        
        if len(pyramid_data) > 0:
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
            st.warning("Sem dados de óbito disponíveis.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row3_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 9: Taxa de Internação por Faixa Etária")
        
        df_internados = df[df['FicouInternado'] != 'Não Informado'].copy()
        interna_proportions = df_internados.groupby('FaixaEtaria').apply(
            lambda g: (g['FicouInternado'].str.upper() == 'SIM').sum() / len(g) * 100
        ).reset_index()
        interna_proportions.columns = ['FaixaEtaria', 'Porcentagem Internados']
        interna_proportions['ordem'] = interna_proportions['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
        interna_proportions = interna_proportions.sort_values('ordem')
        
        if len(interna_proportions) > 0:
            fig, ax = plt.subplots(figsize=(6, 4.3))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0b0f19')
            
            bars = ax.barh(interna_proportions['FaixaEtaria'], interna_proportions['Porcentagem Internados'], color='#f59e0b', height=0.6)
            
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
            st.warning("Sem dados de internação.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 4: TABELAS CRUZADAS (CROSSTABS) ---
    row4_col1, row4_col2 = st.columns(2)
    
    with row4_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 6: Top 5 Municípios vs. Evolução do Caso")
        
        if not municipio_filtro:
            top_cities = df[df['Municipio'] != 'Não Informado']['Municipio'].value_counts().head(5).index.tolist()
            df_top_cities = df[df['Municipio'].isin(top_cities)]
            ct = pd.crosstab(df_top_cities['Municipio'], df_top_cities['Evolucao'])
            st.dataframe(ct, use_container_width=True)
        else:
            ct = pd.crosstab(df['Municipio'], df['Evolucao'])
            st.dataframe(ct, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row4_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 7: Perfil de Casos por Sexo e Raça/Cor")
        ct_sex_raca = pd.crosstab(df['RacaCor'], df['Sexo'])
        st.dataframe(ct_sex_raca, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO 5: MÉTODOS DE TESTES & PROFISSIONAIS DE SAÚDE ---
    row5_col1, row5_col2 = st.columns(2)
    
    with row5_col1:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 8: Métodos de Testes Rápidos e Resultados")
        df_testes = df[df['TipoTesteRapido'] != 'Não Informado']
        if len(df_testes) > 0:
            ct_tests = pd.crosstab(df_testes['TipoTesteRapido'], df_testes['ResultadoTesteRapido'])
            st.dataframe(ct_tests, use_container_width=True)
        else:
            st.warning("Sem dados de testes rápidos.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with row5_col2:
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        st.subheader("Exercício 10: Notificações de Profissionais de Saúde")
        
        prof_counts = df['ProfissionalSaude'].value_counts()
        if len(prof_counts) > 0:
            fig, ax = plt.subplots(figsize=(4, 4))
            fig.patch.set_facecolor('#0f172a')
            ax.set_facecolor('#0b0f19')
            
            ax.pie(
                prof_counts.values,
                labels=prof_counts.index,
                colors=['#38bdf8', '#fb7185', '#64748b'],
                autopct='%1.1f%%',
                pctdistance=0.75,
                textprops={'color': '#f8fafc', 'fontsize': 9, 'weight': 'bold'},
                wedgeprops=dict(width=0.4, edgecolor='#0f172a', linewidth=2)
            )
            ax.set_title("Proporção - Profissionais de Saúde", color='#94a3b8', fontsize=11, pad=10)
            st.pyplot(fig)
        else:
            st.warning("Sem dados.")
        st.markdown('</div>', unsafe_allow_html=True)

    # --- FOOTER ---
    st.markdown("""
    <div style='text-align: center; margin-top: 50px; padding: 20px; border-top: 1px solid #1e293b;'>
        <p style='color: #64748b; font-size: 0.85rem;'>
            Tecnologias: Streamlit • Pandas in-memory | Trabalho Individual de Matheus Rhamet
        </p>
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro ao carregar os dados: {e}")
