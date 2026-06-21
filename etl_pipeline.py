import os
import time
import logging
import re
import pandas as pd
import numpy as np
import duckdb
from datetime import datetime

# Configuração de Logging robusto
logging.basicConfig(
    filename='etl_execution.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

DB_PATH = 'dw_covid.db'
CSV_PATH = 'MICRODADOS.csv'
CHUNK_SIZE = 500000

# Dicionário estático para mapear regionais de saúde de forma vetorizada (alta performance)
REGIONAL_MAP = {}
for m in ['SERRA', 'VITORIA', 'VILA VELHA', 'CARIACICA', 'GUARAPARI', 'VIANA', 'FUNDAO']:
    REGIONAL_MAP[m] = 'METROPOLITANA'
for m in ['CACHOEIRO DE ITAPEMIRIM', 'MARATAIZES', 'ITAPEMIRIM', 'PIUMA', 'MIMOSO DO SUL', 'ALEGRE', 'ANCHIETA']:
    # Anchieta é mapeada inicialmente como SUL, mas tratada dinamicamente para SCD Tipo 2
    REGIONAL_MAP[m] = 'SUL'
for m in ['SAO MATEUS', 'LINHARES', 'COLATINA', 'NOVA VENECIA', 'ARACRUZ', 'BARRA DE SAO FRANCISCO']:
    REGIONAL_MAP[m] = 'NORTE'

def parse_dates_to_sk(series):
    """Converte datas em SK de data no formato YYYYMMDD. Retorna -1 se nulo/inválido."""
    # Fast path: tenta parsear no formato padrão YYYY-MM-DD (99% dos casos)
    dt = pd.to_datetime(series, format='%Y-%m-%d', errors='coerce')
    
    # Slow path: apenas para registros que falharam e não são 'NÃO INFORMADO'
    failed_mask = dt.isna() & (series != 'NÃO INFORMADO')
    if failed_mask.any():
        dt.loc[failed_mask] = pd.to_datetime(series.loc[failed_mask], errors='coerce')
        
    sk = dt.dt.strftime('%Y%m%d')
    return sk.fillna('-1').astype(int)

def parse_age(series):
    """Extrai a idade em anos a partir do formato textual do dataset de forma vetorizada."""
    s = series.astype(str).str.lower()
    # Extrai o primeiro grupo de dígitos seguido de 'ano'
    years = s.str.extract(r'(\d+)\s*ano').astype(float)
    # Identifica menores de 1 ano (meses/dias sem a palavra 'ano')
    less_than_year = s.str.contains('mes|dia|dias|meses') & ~s.str.contains('ano')
    years.loc[less_than_year, 0] = 0.0
    return years[0].fillna(-1).astype(int)

def initialize_dw(con):
    """Cria o schema do DW e insere os registros padrão -1 (Não Informado)."""
    logging.info("Inicializando estrutura física do Data Warehouse no DuckDB...")
    
    # 1. Tabela dim_tempo
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_tempo (
        sk_tempo INT PRIMARY KEY,
        data DATE,
        ano INT,
        mes INT,
        mes_nome VARCHAR(30),
        dia INT,
        dia_semana INT,
        dia_semana_nome VARCHAR(30),
        trimestre INT,
        semestre INT,
        ano_mes VARCHAR(7)
    );
    """)
    
    # 2. Tabela dim_localidade
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_localidade (
        sk_localidade INT PRIMARY KEY,
        municipio VARCHAR(150),
        bairro VARCHAR(150),
        regional_saude VARCHAR(100),
        estado VARCHAR(2),
        nk_localidade VARCHAR(500),
        data_inicio DATE,
        data_fim DATE,
        versao INT,
        flg_atual BOOLEAN
    );
    """)
    
    # 3. Tabela dim_paciente
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_paciente (
        sk_paciente INT PRIMARY KEY,
        faixa_etaria VARCHAR(50),
        sexo VARCHAR(30),
        raca_cor VARCHAR(50),
        escolaridade VARCHAR(100),
        gestante VARCHAR(50),
        profissional_saude VARCHAR(30),
        possui_deficiencia VARCHAR(30),
        morador_de_rua VARCHAR(30),
        nk_paciente VARCHAR(500)
    );
    """)
    
    # 4. Tabela dim_exame
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_exame (
        sk_exame INT PRIMARY KEY,
        resultado_rt_pcr VARCHAR(50),
        resultado_teste_rapido VARCHAR(50),
        resultado_sorologia VARCHAR(50),
        resultado_sorologia_igg VARCHAR(50),
        tipo_teste_rapido VARCHAR(100),
        nk_exame VARCHAR(500)
    );
    """)
    
    # 5. Tabela dim_classificacao_evolucao
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_classificacao_evolucao (
        sk_classificacao_evolucao INT PRIMARY KEY,
        classificacao VARCHAR(100),
        evolucao VARCHAR(100),
        criterio_confirmacao VARCHAR(100),
        status_notificacao VARCHAR(100),
        nk_classificacao_evolucao VARCHAR(500)
    );
    """)
    
    # 6. Tabela dim_clinico (Junk Dimension)
    con.execute("""
    CREATE TABLE IF NOT EXISTS dim_clinico (
        sk_clinico INT PRIMARY KEY,
        febre VARCHAR(30),
        dificuldade_respiratoria VARCHAR(30),
        tosse VARCHAR(30),
        coriza VARCHAR(30),
        dor_garganta VARCHAR(30),
        diarreia VARCHAR(30),
        cefaleia VARCHAR(30),
        comorbidade_pulmao VARCHAR(30),
        comorbidade_cardio VARCHAR(30),
        comorbidade_renal VARCHAR(30),
        comorbidade_diabetes VARCHAR(30),
        comorbidade_tabagismo VARCHAR(30),
        comorbidade_obesidade VARCHAR(30),
        ficou_internado VARCHAR(30),
        viagem_brasil VARCHAR(30),
        viagem_internacional VARCHAR(30),
        nk_clinico VARCHAR(1000)
    );
    """)
    
    # 7. Tabela fato_notificacoes
    con.execute("""
    CREATE TABLE IF NOT EXISTS fato_notificacoes (
        id_notificacao INT PRIMARY KEY,
        fk_tempo_notificacao INT,
        fk_tempo_cadastro INT,
        fk_tempo_diagnostico INT,
        fk_tempo_encerramento INT,
        fk_tempo_obito INT,
        fk_localidade INT,
        fk_paciente INT,
        fk_exame INT,
        fk_classificacao_evolucao INT,
        fk_clinico INT,
        idade_anos INT,
        qtd_notificacao INT DEFAULT 1,
        qtd_confirmados INT DEFAULT 0,
        qtd_obitos INT DEFAULT 0,
        qtd_obitos_outros INT DEFAULT 0,
        qtd_curados INT DEFAULT 0
    );
    """)
    
    # Inserção de membros padrão -1 se não existirem
    logging.info("Inserindo registros padrão de integridade (-1: Não Informado)...")
    
    # Registro tempo -1
    con.execute("SELECT count(*) FROM dim_tempo WHERE sk_tempo = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_tempo VALUES (-1, '1900-01-01', 1900, 1, 'NÃO INFORMADO', 1, 1, 'NÃO INFORMADO', 1, 1, '1900-01')
        """)
        
    # Registro localidade -1
    con.execute("SELECT count(*) FROM dim_localidade WHERE sk_localidade = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_localidade VALUES (-1, 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'ES', 'N/A', '1900-01-01', '9999-12-31', 1, true)
        """)
        
    # Registro paciente -1
    con.execute("SELECT count(*) FROM dim_paciente WHERE sk_paciente = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_paciente VALUES (-1, 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'N/A')
        """)
        
    # Registro exame -1
    con.execute("SELECT count(*) FROM dim_exame WHERE sk_exame = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_exame VALUES (-1, 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'N/A')
        """)
        
    # Registro classificacao -1
    con.execute("SELECT count(*) FROM dim_classificacao_evolucao WHERE sk_classificacao_evolucao = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_classificacao_evolucao VALUES (-1, 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'N/A')
        """)
        
    # Registro clinico -1
    con.execute("SELECT count(*) FROM dim_clinico WHERE sk_clinico = -1")
    if con.fetchone()[0] == 0:
        con.execute("""
        INSERT INTO dim_clinico VALUES (-1, 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'NÃO INFORMADO', 'N/A')
        """)

    # Geração automática da dim_tempo
    con.execute("SELECT count(*) FROM dim_tempo WHERE sk_tempo != -1")
    if con.fetchone()[0] == 0:
        logging.info("Populando dim_tempo dinamicamente de 2020-01-01 a 2026-12-31...")
        con.execute("""
        INSERT INTO dim_tempo
        SELECT
            CAST(strftime(d, '%Y%m%d') AS INT) as sk_tempo,
            d::DATE as data,
            year(d) as ano,
            month(d) as mes,
            upper(strftime(d, '%B')) as mes_nome,
            day(d) as dia,
            dayofweek(d) as dia_semana,
            upper(strftime(d, '%A')) as dia_semana_nome,
            quarter(d) as trimestre,
            CASE WHEN quarter(d) <= 2 THEN 1 ELSE 2 END as semestre,
            strftime(d, '%Y-%m') as ano_mes
        FROM (
            SELECT generate_series::TIMESTAMP as d 
            FROM generate_series(TIMESTAMP '2020-01-01', TIMESTAMP '2026-12-31', INTERVAL 1 DAY)
        )
        """)
        logging.info("dim_tempo populada com sucesso.")

def carregar_mappings_do_db(con):
    """Carrega as tabelas de dimensão existentes na memória para lookup rápido e atribuição de IDs."""
    logging.info("Carregando mapeamentos existentes do banco para memória...")
    
    # 1. Localidade
    df = con.execute("SELECT sk_localidade, nk_localidade, regional_saude FROM dim_localidade").df()
    dict_localidade = {}
    for _, row in df.iterrows():
        dict_localidade[(row['nk_localidade'], row['regional_saude'])] = row['sk_localidade']
    max_localidade = df['sk_localidade'].max() if len(df) > 0 else 0
    
    # 2. Paciente
    df = con.execute("SELECT sk_paciente, nk_paciente FROM dim_paciente").df()
    dict_paciente = dict(zip(df['nk_paciente'], df['sk_paciente']))
    max_paciente = df['sk_paciente'].max() if len(df) > 0 else 0
    
    # 3. Exame
    df = con.execute("SELECT sk_exame, nk_exame FROM dim_exame").df()
    dict_exame = dict(zip(df['nk_exame'], df['sk_exame']))
    max_exame = df['sk_exame'].max() if len(df) > 0 else 0
    
    # 4. Classificacao
    df = con.execute("SELECT sk_classificacao_evolucao, nk_classificacao_evolucao FROM dim_classificacao_evolucao").df()
    dict_classificacao = dict(zip(df['nk_classificacao_evolucao'], df['sk_classificacao_evolucao']))
    max_classificacao = df['sk_classificacao_evolucao'].max() if len(df) > 0 else 0
    
    # 5. Clinico
    df = con.execute("SELECT sk_clinico, nk_clinico FROM dim_clinico").df()
    dict_clinico = dict(zip(df['nk_clinico'], df['sk_clinico']))
    max_clinico = df['sk_clinico'].max() if len(df) > 0 else 0

    return (dict_localidade, max_localidade,
            dict_paciente, max_paciente,
            dict_exame, max_exame,
            dict_classificacao, max_classificacao,
            dict_clinico, max_clinico)

def run_etl():
    start_etl_time = time.time()
    logging.info("=== INICIANDO PIPELINE DE ETL (VETORIZADO) ===")
    
    con = duckdb.connect(DB_PATH)
    initialize_dw(con)
    
    (dict_localidade, max_localidade,
     dict_paciente, max_paciente,
     dict_exame, max_exame,
     dict_classificacao, max_classificacao,
     dict_clinico, max_clinico) = carregar_mappings_do_db(con)
     
    logging.info("Limpando dados históricos da FATO para carga completa...")
    con.execute("TRUNCATE TABLE fato_notificacoes;")
    
    total_linhas_processadas = 0
    contador_fato_id = 1
    
    cols_to_use = [
        'DataNotificacao', 'DataCadastro', 'DataDiagnostico', 'DataEncerramento', 'DataObito',
        'Classificacao', 'Evolucao', 'CriterioConfirmacao', 'StatusNotificacao',
        'Municipio', 'Bairro', 'FaixaEtaria', 'IdadeNaDataNotificacao', 'Sexo', 'RacaCor', 'Escolaridade',
        'Gestante', 'Febre', 'DificuldadeRespiratoria', 'Tosse', 'Coriza', 'DorGarganta', 'Diarreia',
        'Cefaleia', 'ComorbidadePulmao', 'ComorbidadeCardio', 'ComorbidadeRenal', 'ComorbidadeDiabetes',
        'ComorbidadeTabagismo', 'ComorbidadeObesidade', 'FicouInternado', 'ViagemBrasil', 'ViagemInternacional',
        'ProfissionalSaude', 'PossuiDeficiencia', 'MoradorDeRua', 'ResultadoRT_PCR', 'ResultadoTesteRapido',
        'ResultadoSorologia', 'ResultadoSorologia_IGG', 'TipoTesteRapido'
    ]
    
    logging.info(f"Leitura em lotes de {CSV_PATH} (chunksize={CHUNK_SIZE})")
    
    reconciliacao = {
        'csv_total': 5187769,
        'confirmados_csv': 0,
        'obitos_csv': 0,
        'obitos_outros_csv': 0,
        'curados_csv': 0
    }
    
    try:
        chunks = pd.read_csv(
            CSV_PATH,
            sep=';',
            encoding='latin-1',
            usecols=cols_to_use,
            chunksize=CHUNK_SIZE,
            dtype=str
        )
        
        for idx, chunk in enumerate(chunks):
            start_chunk_time = time.time()
            logging.info(f"Processando Lote #{idx+1} contendo {len(chunk)} linhas...")
            
            # --- 1. LIMPEZA VETORIZADA ---
            chunk = chunk.fillna('NÃO INFORMADO')
            for col in chunk.columns:
                chunk[col] = chunk[col].astype(str).str.strip().str.upper()
                chunk.loc[chunk[col] == '', col] = 'NÃO INFORMADO'
                
            # Reconciliação volumétrica
            reconciliacao['confirmados_csv'] += (chunk['Classificacao'] == 'CONFIRMADOS').sum()
            reconciliacao['obitos_csv'] += (chunk['Evolucao'] == 'ÓBITO PELO COVID-19').sum()
            reconciliacao['obitos_outros_csv'] += (chunk['Evolucao'] == 'ÓBITO POR OUTRAS CAUSAS').sum()
            reconciliacao['curados_csv'] += (chunk['Evolucao'] == 'CURA').sum()
            
            # --- 2. TRANSFORMAÇÃO VETORIZADA ---
            
            # 2.1 dim_localidade (Vetorização da Regional de Saúde & SCD Tipo 2)
            chunk['regional_saude'] = chunk['Municipio'].map(REGIONAL_MAP).fillna('OUTRAS REGIONAIS')
            is_anchieta = chunk['Municipio'] == 'ANCHIETA'
            if is_anchieta.any():
                chunk.loc[is_anchieta, 'regional_saude'] = np.where(
                    chunk.loc[is_anchieta, 'DataNotificacao'] >= '2021-01-01',
                    'METROPOLITANA',
                    'SUL'
                )
            
            # Natural Key via concatenação vetorizada direta (muito mais rápido que MD5)
            chunk['nk_localidade'] = chunk['Municipio'] + '|' + chunk['Bairro']
            
            # Seleciona registros únicos de localidade no chunk
            df_loc_unique = chunk[['Municipio', 'Bairro', 'regional_saude', 'nk_localidade', 'DataNotificacao']].drop_duplicates(subset=['nk_localidade', 'regional_saude'])
            
            new_localidades = []
            for _, r in df_loc_unique.iterrows():
                nk = r['nk_localidade']
                reg = r['regional_saude']
                if (nk, reg) not in dict_localidade:
                    # Trigger de SCD Tipo 2
                    check_exist = con.execute(
                        "SELECT sk_localidade, versao FROM dim_localidade WHERE nk_localidade = ? AND flg_atual = true", 
                        [nk]
                    ).fetchone()
                    
                    if check_exist:
                        old_sk = check_exist[0]
                        old_ver = check_exist[1]
                        con.execute(
                            "UPDATE dim_localidade SET flg_atual = false, data_fim = '2020-12-31' WHERE sk_localidade = ?",
                            [old_sk]
                        )
                        max_localidade += 1
                        new_sk = max_localidade
                        new_localidades.append((
                            new_sk, r['Municipio'], r['Bairro'], reg, 'ES', nk,
                            '2021-01-01', '9999-12-31', old_ver + 1, True
                        ))
                        dict_localidade[(nk, reg)] = new_sk
                        logging.info(f"SCD Tipo 2: Localidade {r['Municipio']}-{r['Bairro']} reclassificada. Antiga SK: {old_sk}, Nova SK: {new_sk}")
                    else:
                        max_localidade += 1
                        new_sk = max_localidade
                        new_localidades.append((
                            new_sk, r['Municipio'], r['Bairro'], reg, 'ES', nk,
                            '2020-01-01', '9999-12-31', 1, True
                        ))
                        dict_localidade[(nk, reg)] = new_sk
            
            if new_localidades:
                df_new_loc = pd.DataFrame(new_localidades, columns=[
                    'sk_localidade', 'municipio', 'bairro', 'regional_saude', 'estado', 'nk_localidade',
                    'data_inicio', 'data_fim', 'versao', 'flg_atual'
                ])
                con.execute("INSERT INTO dim_localidade SELECT * FROM df_new_loc")
                
            # Mapeamento do lookup vetorizado via dict map
            chunk['temp_key'] = list(zip(chunk['nk_localidade'], chunk['regional_saude']))
            chunk['fk_localidade'] = chunk['temp_key'].map(dict_localidade).fillna(-1).astype(int)

            # 2.2 dim_paciente
            chunk['nk_paciente'] = (
                chunk['FaixaEtaria'] + '|' + chunk['Sexo'] + '|' + chunk['RacaCor'] + '|' +
                chunk['Escolaridade'] + '|' + chunk['Gestante'] + '|' + chunk['ProfissionalSaude'] + '|' +
                chunk['PossuiDeficiencia'] + '|' + chunk['MoradorDeRua']
            )
            
            df_pac_unique = chunk[[
                'FaixaEtaria', 'Sexo', 'RacaCor', 'Escolaridade', 'Gestante', 
                'ProfissionalSaude', 'PossuiDeficiencia', 'MoradorDeRua', 'nk_paciente'
            ]].drop_duplicates('nk_paciente')
            
            new_pacientes = []
            for _, r in df_pac_unique.iterrows():
                nk = r['nk_paciente']
                if nk not in dict_paciente:
                    max_paciente += 1
                    new_pacientes.append((
                        max_paciente, r['FaixaEtaria'], r['Sexo'], r['RacaCor'], r['Escolaridade'],
                        r['Gestante'], r['ProfissionalSaude'], r['PossuiDeficiencia'], r['MoradorDeRua'], nk
                    ))
                    dict_paciente[nk] = max_paciente
                    
            if new_pacientes:
                df_new_pac = pd.DataFrame(new_pacientes, columns=[
                    'sk_paciente', 'faixa_etaria', 'sexo', 'raca_cor', 'escolaridade', 'gestante',
                    'profissional_saude', 'possui_deficiencia', 'morador_de_rua', 'nk_paciente'
                ])
                con.execute("INSERT INTO dim_paciente SELECT * FROM df_new_pac")
                
            chunk['fk_paciente'] = chunk['nk_paciente'].map(dict_paciente)

            # 2.3 dim_exame
            chunk['nk_exame'] = (
                chunk['ResultadoRT_PCR'] + '|' + chunk['ResultadoTesteRapido'] + '|' +
                chunk['ResultadoSorologia'] + '|' + chunk['ResultadoSorologia_IGG'] + '|' +
                chunk['TipoTesteRapido']
            )
            
            df_ex_unique = chunk[[
                'ResultadoRT_PCR', 'ResultadoTesteRapido', 'ResultadoSorologia', 
                'ResultadoSorologia_IGG', 'TipoTesteRapido', 'nk_exame'
            ]].drop_duplicates('nk_exame')
            
            new_exames = []
            for _, r in df_ex_unique.iterrows():
                nk = r['nk_exame']
                if nk not in dict_exame:
                    max_exame += 1
                    new_exames.append((
                        max_exame, r['ResultadoRT_PCR'], r['ResultadoTesteRapido'], r['ResultadoSorologia'],
                        r['ResultadoSorologia_IGG'], r['TipoTesteRapido'], nk
                    ))
                    dict_exame[nk] = max_exame
                    
            if new_exames:
                df_new_ex = pd.DataFrame(new_exames, columns=[
                    'sk_exame', 'resultado_rt_pcr', 'resultado_teste_rapido', 'resultado_sorologia',
                    'resultado_sorologia_igg', 'tipo_teste_rapido', 'nk_exame'
                ])
                con.execute("INSERT INTO dim_exame SELECT * FROM df_new_ex")
                
            chunk['fk_exame'] = chunk['nk_exame'].map(dict_exame)

            # 2.4 dim_classificacao_evolucao
            chunk['nk_classificacao_evolucao'] = (
                chunk['Classificacao'] + '|' + chunk['Evolucao'] + '|' +
                chunk['CriterioConfirmacao'] + '|' + chunk['StatusNotificacao']
            )
            
            df_ce_unique = chunk[[
                'Classificacao', 'Evolucao', 'CriterioConfirmacao', 'StatusNotificacao', 'nk_classificacao_evolucao'
            ]].drop_duplicates('nk_classificacao_evolucao')
            
            new_classificacoes = []
            for _, r in df_ce_unique.iterrows():
                nk = r['nk_classificacao_evolucao']
                if nk not in dict_classificacao:
                    max_classificacao += 1
                    new_classificacoes.append((
                        max_classificacao, r['Classificacao'], r['Evolucao'], r['CriterioConfirmacao'],
                        r['StatusNotificacao'], nk
                    ))
                    dict_classificacao[nk] = max_classificacao
                    
            if new_classificacoes:
                df_new_ce = pd.DataFrame(new_classificacoes, columns=[
                    'sk_classificacao_evolucao', 'classificacao', 'evolucao', 'criterio_confirmacao',
                    'status_notificacao', 'nk_classificacao_evolucao'
                ])
                con.execute("INSERT INTO dim_classificacao_evolucao SELECT * FROM df_new_ce")
                
            chunk['fk_classificacao_evolucao'] = chunk['nk_classificacao_evolucao'].map(dict_classificacao)

            # 2.5 dim_clinico (Junk Dimension)
            chunk['nk_clinico'] = (
                chunk['Febre'] + '|' + chunk['DificuldadeRespiratoria'] + '|' + chunk['Tosse'] + '|' +
                chunk['Coriza'] + '|' + chunk['DorGarganta'] + '|' + chunk['Diarreia'] + '|' + chunk['Cefaleia'] + '|' +
                chunk['ComorbidadePulmao'] + '|' + chunk['ComorbidadeCardio'] + '|' + chunk['ComorbidadeRenal'] + '|' +
                chunk['ComorbidadeDiabetes'] + '|' + chunk['ComorbidadeTabagismo'] + '|' + chunk['ComorbidadeObesidade'] + '|' +
                chunk['FicouInternado'] + '|' + chunk['ViagemBrasil'] + '|' + chunk['ViagemInternacional']
            )
            
            df_cli_unique = chunk[[
                'Febre', 'DificuldadeRespiratoria', 'Tosse', 'Coriza', 'DorGarganta', 'Diarreia', 'Cefaleia',
                'ComorbidadePulmao', 'ComorbidadeCardio', 'ComorbidadeRenal', 'ComorbidadeDiabetes', 
                'ComorbidadeTabagismo', 'ComorbidadeObesidade', 'FicouInternado', 'ViagemBrasil', 'ViagemInternacional',
                'nk_clinico'
            ]].drop_duplicates('nk_clinico')
            
            new_clinicos = []
            for _, r in df_cli_unique.iterrows():
                nk = r['nk_clinico']
                if nk not in dict_clinico:
                    max_clinico += 1
                    new_clinicos.append((
                        max_clinico, r['Febre'], r['DificuldadeRespiratoria'], r['Tosse'], r['Coriza'], r['DorGarganta'],
                        r['Diarreia'], r['Cefaleia'], r['ComorbidadePulmao'], r['ComorbidadeCardio'], r['ComorbidadeRenal'],
                        r['ComorbidadeDiabetes'], r['ComorbidadeTabagismo'], r['ComorbidadeObesidade'], r['FicouInternado'],
                        r['ViagemBrasil'], r['ViagemInternacional'], nk
                    ))
                    dict_clinico[nk] = max_clinico
                    
            if new_clinicos:
                df_new_cli = pd.DataFrame(new_clinicos, columns=[
                    'sk_clinico', 'febre', 'dificuldade_respiratoria', 'tosse', 'coriza', 'dor_garganta',
                    'diarreia', 'cefaleia', 'comorbidade_pulmao', 'comorbidade_cardio', 'comorbidade_renal',
                    'comorbidade_diabetes', 'comorbidade_tabagismo', 'comorbidade_obesidade', 'ficou_internado',
                    'viagem_brasil', 'viagem_internacional', 'nk_clinico'
                ])
                con.execute("INSERT INTO dim_clinico SELECT * FROM df_new_cli")
                
            chunk['fk_clinico'] = chunk['nk_clinico'].map(dict_clinico)

            # --- 3. TRANSFORMAÇÃO E PROCESSAMENTO DA FATO ---
            chunk['fk_tempo_notificacao'] = parse_dates_to_sk(chunk['DataNotificacao'])
            chunk['fk_tempo_cadastro'] = parse_dates_to_sk(chunk['DataCadastro'])
            chunk['fk_tempo_diagnostico'] = parse_dates_to_sk(chunk['DataDiagnostico'])
            chunk['fk_tempo_encerramento'] = parse_dates_to_sk(chunk['DataEncerramento'])
            chunk['fk_tempo_obito'] = parse_dates_to_sk(chunk['DataObito'])
            
            chunk['idade_anos'] = parse_age(chunk['IdadeNaDataNotificacao'])
            
            chunk['qtd_notificacao'] = 1
            chunk['qtd_confirmados'] = (chunk['Classificacao'] == 'CONFIRMADOS').astype(int)
            chunk['qtd_obitos'] = (chunk['Evolucao'] == 'ÓBITO PELO COVID-19').astype(int)
            chunk['qtd_obitos_outros'] = (chunk['Evolucao'] == 'ÓBITO POR OUTRAS CAUSAS').astype(int)
            chunk['qtd_curados'] = (chunk['Evolucao'] == 'CURA').astype(int)
            
            chunk['id_notificacao'] = range(contador_fato_id, contador_fato_id + len(chunk))
            contador_fato_id += len(chunk)
            
            df_fact = chunk[[
                'id_notificacao', 'fk_tempo_notificacao', 'fk_tempo_cadastro', 'fk_tempo_diagnostico',
                'fk_tempo_encerramento', 'fk_tempo_obito', 'fk_localidade', 'fk_paciente', 'fk_exame',
                'fk_classificacao_evolucao', 'fk_clinico', 'idade_anos', 'qtd_notificacao', 
                'qtd_confirmados', 'qtd_obitos', 'qtd_obitos_outros', 'qtd_curados'
            ]]
            
            # --- 4. CARGA (LOAD) DA FATO ---
            con.execute("INSERT INTO fato_notificacoes SELECT * FROM df_fact")
            
            total_linhas_processadas += len(chunk)
            end_chunk_time = time.time()
            logging.info(f"Lote #{idx+1} concluído. Tempo: {end_chunk_time - start_chunk_time:.2f} segundos. Acumulado: {total_linhas_processadas} registros.")
            
    except Exception as e:
        logging.error(f"FALHA NO PROCESSO DE ETL: {str(e)}", exc_info=True)
        con.close()
        raise e
        
    # --- 5. AUDITORIA E RECONCILIAÇÃO 1:1 ---
    logging.info("=== ETL CONCLUÍDO. EXECUTANDO AUDITORIA DE RECONCILIAÇÃO (Data Auditability 1:1) ===")
    
    dw_metrics = con.execute("""
    SELECT 
        COUNT(*),
        SUM(qtd_confirmados),
        SUM(qtd_obitos),
        SUM(qtd_obitos_outros),
        SUM(qtd_curados)
    FROM fato_notificacoes
    """).fetchone()
    
    audit_results = {
        'Fato_Total_Registros': dw_metrics[0],
        'Fato_Total_Confirmados': dw_metrics[1],
        'Fato_Total_Obitos_Covid': dw_metrics[2],
        'Fato_Total_Obitos_Outros': dw_metrics[3],
        'Fato_Total_Curados': dw_metrics[4]
    }
    
    reconciliation_ok = True
    
    if audit_results['Fato_Total_Registros'] != reconciliacao['csv_total']:
        logging.warning(f"Divergência de Registros! CSV: {reconciliacao['csv_total']} | Fato: {audit_results['Fato_Total_Registros']}")
        reconciliation_ok = False
    else:
        logging.info(f"Sucesso: Volume Total de Registros reconciliado perfeitamente! ({audit_results['Fato_Total_Registros']})")
        
    if audit_results['Fato_Total_Confirmados'] != reconciliacao['confirmados_csv']:
        logging.warning(f"Divergência de Casos Confirmados! CSV: {reconciliacao['confirmados_csv']} | Fato: {audit_results['Fato_Total_Confirmados']}")
        reconciliation_ok = False
    else:
        logging.info(f"Sucesso: Total de Casos Confirmados reconciliado perfeitamente! ({audit_results['Fato_Total_Confirmados']})")
        
    if audit_results['Fato_Total_Obitos_Covid'] != reconciliacao['obitos_csv']:
        logging.warning(f"Divergência de Óbitos Covid! CSV: {reconciliacao['obitos_csv']} | Fato: {audit_results['Fato_Total_Obitos_Covid']}")
        reconciliation_ok = False
    else:
        logging.info(f"Sucesso: Total de Óbitos Covid reconciliado perfeitamente! ({audit_results['Fato_Total_Obitos_Covid']})")
        
    if audit_results['Fato_Total_Curados'] != reconciliacao['curados_csv']:
        logging.warning(f"Divergência de Curados! CSV: {reconciliacao['curados_csv']} | Fato: {audit_results['Fato_Total_Curados']}")
        reconciliation_ok = False
    else:
        logging.info(f"Sucesso: Total de Casos Curados reconciliado perfeitamente! ({audit_results['Fato_Total_Curados']})")
        
    if reconciliation_ok:
        logging.info("RECONCILIAÇÃO VOLUMÉTRICA FINALIZADA COM SUCESSO - AUDITORIA 1:1 COMPACTA E VÁLIDA.")
    else:
        logging.error("AUDITORIA 1:1 APRESENTOU DIVERGÊNCIAS!")
        
    con.close()
    
    end_etl_time = time.time()
    logging.info(f"Tempo total de execução do ETL: {end_etl_time - start_etl_time:.2f} segundos ({ (end_etl_time - start_etl_time)/60:.2f} minutos).")
    logging.info("=== FIM DO PIPELINE ===")

if __name__ == '__main__':
    run_etl()
