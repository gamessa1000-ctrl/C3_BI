import time
import tracemalloc
import pandas as pd
import duckdb
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

CSV_PATH = 'MICRODADOS.csv'
DB_PATH = 'dw_covid.db'
TEST_MUNICIPIO = 'SERRA'

def benchmark_csv():
    """Mede tempo e memória para carregar o CSV bruto e realizar as agregações com Pandas."""
    tracemalloc.start()
    start_time = time.time()
    
    # 1. Carregamento inicial do arquivo CSV
    load_start = time.time()
    df_raw = pd.read_csv(CSV_PATH, sep=';', encoding='latin-1', dtype=str)
    df_raw = df_raw.fillna('Não Informado')
    load_time = time.time() - load_start
    
    # 2. Execução dos filtros e agregações (simulando a renderização dos blocos do dashboard)
    query_start = time.time()
    
    # Filtro dinâmico
    df = df_raw[df_raw['Municipio'].str.upper() == TEST_MUNICIPIO].copy()
    
    # Ex 1: Contagens básicas
    total_rows = len(df)
    total_cols = len(df.columns)
    
    # Ex 2: Contagem de nulos
    null_counts = {}
    target_cols = ['DataCadastro', 'DataDiagnostico', 'DataEncerramento', 'DataObito', 'Evolucao']
    for col in target_cols:
        null_counts[col] = (df[col] == 'Não Informado').sum()
        
    # Ex 3: Evolução temporal
    df_dates = df[df['DataNotificacao'] != 'Não Informado'].copy()
    df_dates['AnoMes'] = df_dates['DataNotificacao'].str[:7]
    evolucao_temp = df_dates['AnoMes'].value_counts().sort_index()
    
    # Ex 4: Pirâmide etária de óbitos
    df_obitos = df[(df['Evolucao'].str.upper() == 'ÓBITO PELO COVID-19') & (df['Sexo'].str.upper().isin(['M', 'F']))].copy()
    pyramid_data = df_obitos.groupby(['FaixaEtaria', 'Sexo']).size().unstack(fill_value=0)
    
    # Ex 5: Comorbidades
    comorbidades_cols = [
        'ComorbidadePulmao', 'ComorbidadeCardio', 'ComorbidadeRenal',
        'ComorbidadeDiabetes', 'ComorbidadeTabagismo', 'ComorbidadeObesidade'
    ]
    comorb_counts = {col: (df[col].str.upper() == 'SIM').sum() for col in comorbidades_cols}
    
    # Ex 6: Crosstab do município selecionado
    ct_evolucao = pd.crosstab(df['Municipio'], df['Evolucao'])
    
    # Ex 7: Sexo vs Raça
    ct_sex_raca = pd.crosstab(df['RacaCor'], df['Sexo'])
    
    # Ex 8: Métodos de teste
    df_testes = df[df['TipoTesteRapido'] != 'Não Informado']
    ct_tests = pd.crosstab(df_testes['TipoTesteRapido'], df_testes['ResultadoTesteRapido'])
    
    # Ex 9: Internações por faixa etária
    df_internados = df[df['FicouInternado'] != 'Não Informado'].copy()
    interna_proportions = df_internados.groupby('FaixaEtaria').apply(
        lambda g: (g['FicouInternado'].str.upper() == 'SIM').sum() / len(g) * 100
    )
    
    # Ex 10: Profissionais de saúde
    prof_counts = df['ProfissionalSaude'].value_counts()
    
    query_time = time.time() - query_start
    total_time = time.time() - start_time
    
    # Pega o consumo máximo de RAM (em bytes)
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Converte para MB
    peak_memory_mb = peak_memory / (1024 * 1024)
    
    return load_time, query_time, total_time, peak_memory_mb

def benchmark_dw():
    """Mede tempo e memória para conectar ao DuckDB e rodar as consultas agregadas via SQL."""
    tracemalloc.start()
    start_time = time.time()
    
    # 1. Carregamento inicial (conexão com o banco)
    load_start = time.time()
    con = duckdb.connect(DB_PATH, read_only=True)
    load_time = time.time() - load_start
    
    # 2. Execução dos filtros e agregações via SQL agrupados
    query_start = time.time()
    
    # Ex 1: Contagens básicas
    total_rows = con.execute("SELECT COUNT(*) FROM fato_notificacoes f JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade WHERE l.municipio = ?", [TEST_MUNICIPIO]).fetchone()[0]
    
    # Ex 2: Contagem de nulos
    con.execute("""
    SELECT 
        SUM(CASE WHEN f.fk_tempo_cadastro = -1 THEN 1 ELSE 0 END) as DataCadastro,
        SUM(CASE WHEN f.fk_tempo_diagnostico = -1 THEN 1 ELSE 0 END) as DataDiagnostico,
        SUM(CASE WHEN f.fk_tempo_encerramento = -1 THEN 1 ELSE 0 END) as DataEncerramento,
        SUM(CASE WHEN f.fk_tempo_obito = -1 THEN 1 ELSE 0 END) as DataObito,
        SUM(CASE WHEN ce.evolucao = 'NÃO INFORMADO' THEN 1 ELSE 0 END) as Evolucao
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
    WHERE l.municipio = ?
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 3: Evolução temporal
    con.execute("""
    SELECT t.ano_mes, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_tempo t ON f.fk_tempo_notificacao = t.sk_tempo
    WHERE t.sk_tempo != -1 AND l.municipio = ?
    GROUP BY t.ano_mes
    ORDER BY t.ano_mes
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 4: Pirâmide etária
    con.execute("""
    SELECT p.faixa_etaria, p.sexo, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
    JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
    WHERE ce.evolucao = 'ÓBITO PELO COVID-19' AND p.sexo IN ('M', 'F') AND l.municipio = ?
    GROUP BY p.faixa_etaria, p.sexo
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 5: Comorbidades
    con.execute("""
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
    WHERE l.municipio = ?
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 6: Crosstab do município selecionado
    con.execute("""
    SELECT l.municipio, ce.evolucao, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_classificacao_evolucao ce ON f.fk_classificacao_evolucao = ce.sk_classificacao_evolucao
    WHERE l.municipio = ?
    GROUP BY l.municipio, ce.evolucao
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 7: Sexo vs Raça
    con.execute("""
    SELECT p.raca_cor, p.sexo, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
    WHERE l.municipio = ?
    GROUP BY p.raca_cor, p.sexo
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 8: Métodos de teste
    con.execute("""
    SELECT e.tipo_teste_rapido, e.resultado_teste_rapido, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_exame e ON f.fk_exame = e.sk_exame
    WHERE e.tipo_teste_rapido != 'NÃO INFORMADO' AND l.municipio = ?
    GROUP BY e.tipo_teste_rapido, e.resultado_teste_rapido
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 9: Internações por faixa etária
    con.execute("""
    SELECT p.faixa_etaria, 
           SUM(CASE WHEN cl.ficou_internado = 'SIM' THEN 1 ELSE 0 END) as internados,
           COUNT(*) as total
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
    JOIN dim_clinico cl ON f.fk_clinico = cl.sk_clinico
    WHERE cl.ficou_internado != 'NÃO INFORMADO' AND l.municipio = ?
    GROUP BY p.faixa_etaria
    """, [TEST_MUNICIPIO]).df()
    
    # Ex 10: Profissionais de saúde
    con.execute("""
    SELECT p.profissional_saude, COUNT(*) 
    FROM fato_notificacoes f
    JOIN dim_localidade l ON f.fk_localidade = l.sk_localidade
    JOIN dim_paciente p ON f.fk_paciente = p.sk_paciente
    WHERE l.municipio = ?
    GROUP BY p.profissional_saude
    """, [TEST_MUNICIPIO]).df()
    
    query_time = time.time() - query_start
    total_time = time.time() - start_time
    
    # Pega o consumo máximo de RAM (em bytes)
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    con.close()
    
    # Converte para MB
    peak_memory_mb = peak_memory / (1024 * 1024)
    
    return load_time, query_time, total_time, peak_memory_mb

def main():
    print("=== INICIANDO TESTES DE PERFORMANCE (BENCHMARKING) ===")
    
    # Verifica se os arquivos necessários existem
    if not os.path.exists(CSV_PATH):
        print(f"Erro: O arquivo {CSV_PATH} não foi encontrado. Abortando benchmark.")
        return
    if not os.path.exists(DB_PATH):
        print(f"Erro: O banco {DB_PATH} não foi encontrado. Por favor, execute o 'etl_pipeline.py' primeiro.")
        return
        
    print(f"Testando abordagem CSV (Pandas)...")
    csv_load, csv_query, csv_total, csv_ram = benchmark_csv()
    print(f"Abordagem CSV Concluída. Tempo total: {csv_total:.2f}s | RAM: {csv_ram:.2f} MB")
    
    print(f"\nTestando abordagem DW (DuckDB)...")
    dw_load, dw_query, dw_total, dw_ram = benchmark_dw()
    print(f"Abordagem DW Concluída. Tempo total: {dw_total:.2f}s | RAM: {dw_ram:.2f} MB")
    
    print("\n=== RESULTADOS COMPARATIVOS ===")
    print(f"{'Métrica':<30} | {'CSV (Pandas)':<15} | {'DW (DuckDB)':<15} | {'Ganho / Redução':<18}")
    print("-" * 85)
    print(f"{'Tempo de Carregamento Inicial':<30} | {csv_load:13.3f}s | {dw_load:13.3f}s | {csv_load/max(dw_load, 0.001):12.1f}x mais rápido")
    print(f"{'Tempo de Resposta das Consultas':<30} | {csv_query:13.3f}s | {dw_query:13.3f}s | {csv_query/max(dw_query, 0.001):12.1f}x mais rápido")
    print(f"{'Tempo Total':<30} | {csv_total:13.3f}s | {dw_total:13.3f}s | {csv_total/max(dw_total, 0.001):12.1f}x mais rápido")
    print(f"{'Consumo Máximo de RAM':<30} | {csv_ram:10.2f} MB | {dw_ram:10.2f} MB | {((csv_ram - dw_ram)/csv_ram)*100:11.1f}% de economia")
    
    # ---------------------------------------------------------
    # GERAÇÃO DOS GRÁFICOS
    # ---------------------------------------------------------
    # Configuração de estilo Seaborn / Matplotlib premium
    sns.set_theme(style="darkgrid")
    
    # Gráfico 1: Comparativo de Tempo (Segundos)
    fig, ax = plt.subplots(figsize=(6, 5))
    categories = ['Carregamento', 'Consultas/Filtros', 'Tempo Total']
    csv_times = [csv_load, csv_query, csv_total]
    dw_times = [dw_load, dw_query, dw_total]
    
    x = np.arange(len(categories))
    width = 0.35
    
    rects1 = ax.bar(x - width/2, csv_times, width, label='CSV (Pandas)', color='#f43f5e')
    rects2 = ax.bar(x + width/2, dw_times, width, label='DW (DuckDB)', color='#10b981')
    
    ax.set_ylabel('Tempo (Segundos)', fontsize=12, fontweight='bold')
    ax.set_title('Comparativo de Tempo: CSV vs. Data Warehouse', fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.legend(frameon=True, facecolor='white', edgecolor='#cbd5e1')
    
    # Adiciona rótulos nos topos das barras
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}s' if height >= 0.01 else f'{height:.4f}s',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
                        
    autolabel(rects1)
    autolabel(rects2)
    plt.tight_layout()
    plt.savefig('benchmark_time.png', dpi=300)
    print("\n[+] Gráfico de tempo salvo como 'benchmark_time.png'")
    
    # Gráfico 2: Comparativo de Memória RAM (MB)
    fig, ax = plt.subplots(figsize=(5, 5))
    labels = ['CSV (Pandas)', 'DW (DuckDB)']
    ram_usage = [csv_ram, dw_ram]
    
    rects = ax.bar(labels, ram_usage, color=['#f43f5e', '#10b981'], width=0.5)
    ax.set_ylabel('Consumo de RAM (MB)', fontsize=12, fontweight='bold')
    ax.set_title('Consumo de Memória RAM: CSV vs. DW', fontsize=14, fontweight='bold', pad=15)
    
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height:.1f} MB',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
                    
    plt.tight_layout()
    plt.savefig('benchmark_memory.png', dpi=300)
    print("[+] Gráfico de memória RAM salvo como 'benchmark_memory.png'")
    
if __name__ == '__main__':
    main()
