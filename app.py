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
        color: #3b82f6;
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
        border-color: #3b82f6;
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

CSV_PATH = 'MICRODADOS.csv'

st.title("🦠 Monitoramento COVID-19 Espírito Santo (CSV Baseline)")
st.write("Esta versão consome dados diretamente do arquivo CSV bruto (~1.95 GB), utilizando processamento em memória com Pandas.")

# Sidebar de controle
st.sidebar.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR6sFsw_B-kM8bM8J2u98YjT6l2TzYj2K260w&s", width=80)
st.sidebar.header("Filtros do Painel")
municipio_filtro = st.sidebar.text_input("Filtrar por Município (ex: SERRA, VITORIA):", "").strip().upper()

# Função de Carregamento de Dados com Cache do Streamlit
@st.cache_data(show_spinner="Carregando e processando arquivo CSV (isso pode demorar de 30s a 1min)...")
def load_data():
    df = pd.read_csv(CSV_PATH, sep=';', encoding='latin-1', dtype=str)
    # Limpeza básica exigida na C1
    df = df.fillna('Não Informado')
    return df

try:
    df_raw = load_data()
    
    # Aplica filtro dinâmico de município se digitado
    if municipio_filtro:
        df = df_raw[df_raw['Municipio'].str.upper() == municipio_filtro].copy()
    else:
        df = df_raw
        
    # Layout em colunas para os Metadados Gerais (Exercício 1 e 2)
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 1: Metadados do Dataset (Volume Geral)")
        st.metric("Total de Linhas (Registros)", f"{len(df):,}")
        st.metric("Total de Colunas", f"{len(df.columns)}")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 2: Contagem de Nulos / Ausentes")
        # Conta valores que são 'Não Informado' (que representavam nulos na limpeza)
        null_counts = {}
        target_cols = ['DataCadastro', 'DataDiagnostico', 'DataEncerramento', 'DataObito', 'Evolucao']
        for col in target_cols:
            null_counts[col] = (df[col] == 'Não Informado').sum()
        df_nulls = pd.DataFrame(list(null_counts.items()), columns=['Coluna', 'Valores Ausentes'])
        st.dataframe(df_nulls, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Exercício 3: Evolução Temporal das Notificações
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 3: Evolução Temporal das Notificações (Por Mês)")
    # Agrupa por Ano-Mês da Notificação (extrai YYYY-MM)
    df_dates = df[df['DataNotificacao'] != 'Não Informado'].copy()
    df_dates['AnoMes'] = df_dates['DataNotificacao'].str[:7]
    evolucao_temp = df_dates['AnoMes'].value_counts().sort_index().reset_index()
    evolucao_temp.columns = ['Ano-Mês', 'Notificações']
    
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor('#0b0f19')
    ax.set_facecolor('#0f172a')
    
    ax.bar(evolucao_temp['Ano-Mês'], evolucao_temp['Notificações'], color='#3b82f6')
    ax.set_xticklabels(evolucao_temp['Ano-Mês'], rotation=45, ha='right', color='#94a3b8')
    ax.tick_params(colors='#94a3b8')
    ax.spines['bottom'].set_color('#1e293b')
    ax.spines['left'].set_color('#1e293b')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title("Casos Notificados ao Longo do Tempo", color='#60a5fa', fontsize=12)
    
    st.pyplot(fig)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 4: Pirâmide Etária dos Óbitos por COVID-19
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 4: Pirâmide Etária de Óbitos por COVID-19")
    df_obitos = df[(df['Evolucao'].str.upper() == 'ÓBITO PELO COVID-19') & (df['Sexo'].str.upper().isin(['M', 'F']))].copy()
    
    # Agrupa faixas etárias e sexo
    pyramid_data = df_obitos.groupby(['FaixaEtaria', 'Sexo']).size().unstack(fill_value=0).reset_index()
    # Ordena as faixas etárias
    pyramid_data['ordem'] = pyramid_data['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
    pyramid_data = pyramid_data.sort_values('ordem')
    
    if len(pyramid_data) > 0:
        if 'M' not in pyramid_data.columns: pyramid_data['M'] = 0
        if 'F' not in pyramid_data.columns: pyramid_data['F'] = 0
        
        # Valores negativos para os homens para fazer a pirâmide
        males = -pyramid_data['M'].values
        females = pyramid_data['F'].values
        categories = pyramid_data['FaixaEtaria'].values
        
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor('#0b0f19')
        ax.set_facecolor('#0f172a')
        
        ax.barh(categories, males, color='#3b82f6', label='Masculino')
        ax.barh(categories, females, color='#ec4899', label='Feminino')
        
        # Transforma ticks do eixo X em absolutos
        abs_ticks = np.abs(ax.get_xticks())
        ax.set_xticklabels([f"{val:,.0f}" for val in abs_ticks])
        ax.tick_params(colors='#94a3b8')
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(facecolor='#0f172a', edgecolor='#1e293b', labelcolor='#f1f5f9')
        ax.set_title("Distribuição de Óbitos por Sexo e Faixa Etária", color='#60a5fa', fontsize=12)
        
        st.pyplot(fig)
    else:
        st.warning("Sem dados de óbito disponíveis para o filtro selecionado.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 5: Distribuição por Comorbidades
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 5: Distribuição por Comorbidades")
    comorbidades_cols = [
        'ComorbidadePulmao', 'ComorbidadeCardio', 'ComorbidadeRenal',
        'ComorbidadeDiabetes', 'ComorbidadeTabagismo', 'ComorbidadeObesidade'
    ]
    comorb_counts = {}
    for col in comorbidades_cols:
        comorb_counts[col.replace('Comorbidade', '')] = (df[col].str.upper() == 'SIM').sum()
    df_comorb = pd.DataFrame(list(comorb_counts.items()), columns=['Comorbidade', 'Casos']).sort_values('Casos', ascending=False)
    
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor('#0b0f19')
    ax.set_facecolor('#0f172a')
    ax.bar(df_comorb['Comorbidade'], df_comorb['Casos'], color='#10b981')
    ax.tick_params(colors='#94a3b8')
    ax.spines['bottom'].set_color('#1e293b')
    ax.spines['left'].set_color('#1e293b')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title("Prevalência de Comorbidades Declaradas", color='#60a5fa', fontsize=12)
    st.pyplot(fig)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Exercício 6: Crosstab: Top 5 Municípios vs. Evolução
    st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
    st.subheader("Exercício 6: Crosstab - Top 5 Municípios com Mais Casos vs. Evolução do Caso")
    # Apenas se não houver filtro de município ativo para fazer sentido a tabela comparativa
    if not municipio_filtro:
        top_cities = df[df['Municipio'] != 'Não Informado']['Municipio'].value_counts().head(5).index.tolist()
        df_top_cities = df[df['Municipio'].isin(top_cities)]
        ct = pd.crosstab(df_top_cities['Municipio'], df_top_cities['Evolucao'])
        st.dataframe(ct, use_container_width=True)
    else:
        # Se filtrado, exibe crosstab do município selecionado
        ct = pd.crosstab(df['Municipio'], df['Evolucao'])
        st.dataframe(ct, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Colunas para Exercícios 7 e 8
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 7: Perfil de Casos por Sexo e Raça/Cor")
        ct_sex_raca = pd.crosstab(df['RacaCor'], df['Sexo'])
        st.dataframe(ct_sex_raca, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col4:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 8: Análise de Métodos de Teste e Resultados")
        # Filtra os testes rápidos
        df_testes = df[df['TipoTesteRapido'] != 'Não Informado']
        ct_tests = pd.crosstab(df_testes['TipoTesteRapido'], df_testes['ResultadoTesteRapido'])
        st.dataframe(ct_tests, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Colunas para Exercícios 9 e 10
    col5, col6 = st.columns(2)
    
    with col5:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 9: Proporção de Internações por Faixa Etária")
        # Proporção de 'SIM' em FicouInternado por faixa etária
        df_internados = df[df['FicouInternado'] != 'Não Informado'].copy()
        interna_proportions = df_internados.groupby('FaixaEtaria').apply(
            lambda g: (g['FicouInternado'].str.upper() == 'SIM').sum() / len(g) * 100
        ).reset_index()
        interna_proportions.columns = ['FaixaEtaria', 'Porcentagem Internados']
        # Ordena faixas etárias
        interna_proportions['ordem'] = interna_proportions['FaixaEtaria'].str.extract(r'(\d+)').astype(float).fillna(999)
        interna_proportions = interna_proportions.sort_values('ordem')
        
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor('#0b0f19')
        ax.set_facecolor('#0f172a')
        ax.barh(interna_proportions['FaixaEtaria'], interna_proportions['Porcentagem Internados'], color='#f59e0b')
        ax.tick_params(colors='#94a3b8')
        ax.spines['bottom'].set_color('#1e293b')
        ax.spines['left'].set_color('#1e293b')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.set_xlabel("Taxa de Internação (%)", color='#94a3b8')
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col6:
        st.markdown('<div class="exercise-box">', unsafe_allow_html=True)
        st.subheader("Exercício 10: Notificações de Profissionais de Saúde")
        prof_counts = df['ProfissionalSaude'].value_counts()
        
        fig, ax = plt.subplots(figsize=(4, 4))
        fig.patch.set_facecolor('#0b0f19')
        ax.set_facecolor('#0f172a')
        
        ax.pie(
            prof_counts.values,
            labels=prof_counts.index,
            colors=['#3b82f6', '#f43f5e', '#64748b'],
            autopct='%1.1f%%',
            textprops={'color': '#f1f5f9'}
        )
        ax.set_title("Casos - Profissionais de Saúde", color='#60a5fa')
        st.pyplot(fig)
        st.markdown('</div>', unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro ao carregar o arquivo CSV: {e}")
    st.info("Por favor, verifique se o arquivo MICRODADOS.csv está na mesma pasta do script.")
