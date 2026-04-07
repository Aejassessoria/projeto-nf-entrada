import pandas as pd
import re

COLUNAS_ESPERADAS = {
    'ChaveAcesso': 'chave_acesso',
    'SerieDocumento': 'serie',
    'NumeroDocumento': 'numero_nf',
    'TipoOperacaoDocumento': 'tipo_operacao',
    'SituacaoDocumento': 'situacao',
    'IdItem': 'id_item',
    'DataEmissaoNfe': 'data_emissao',
    'UfEmitente': 'uf_emitente',
    'UfDestinatario': 'uf_destinatario',
    'CnpjEmitente': 'cnpj_emitente',
    'CpfEmitente': 'cpf_emitente',
    'CnpjCpfEmitente': 'cnpj_emitente_raw',
    'CnpjDestinatario': 'cnpj_destinatario',
    'CpfDestinatario': 'cpf_destinatario',
    'CnpjCpfDestinatario': 'cnpj_destinatario_raw',
    'NomeEmitente': 'nome_emitente',
    'NomeDestinatario': 'nome_destinatario',
    'Item': 'item',
    'Produto': 'codigo_produto',
    'GtinProduto': 'gtin',
    'NcmProduto': 'ncm',
    'DescricaoProduto': 'descricao_produto',
    'CfopProduto': 'cfop',
    'UnidadeComercial': 'unidade',
    'QuantidadeUnidadeComercial': 'quantidade',
    'ValorUnitarioComercial': 'valor_unitario',
    'ValorTotalProduto': 'valor_total',
    'ValorFrete': 'valor_frete',
    'OrigemMercadoria': 'origem',
    'ClassifOperacao': 'classif_operacao',
    'IcmsTributacao': 'icms_tributacao',
    'ValorIcmsBc': 'icms_bc',
    'PercentualIcmsAliq': 'icms_aliq',
    'ValorIcmsSemDifer': 'icms_valor',
}


def _limpar_cnpj(valor):
    if pd.isna(valor):
        return ''
    return re.sub(r'\D', '', str(valor))


def ler_planilha_sat(arquivo) -> pd.DataFrame:
    try:
        with pd.ExcelFile(arquivo) as xl:
            df = xl.parse(xl.sheet_names[0], dtype=str)
    except Exception as e:
        raise ValueError(f"Erro ao ler planilha: {e}")

    if len(df) > 50000:
        raise ValueError(
            f"Planilha contém {len(df):,} linhas. O limite suportado é 50.000 linhas por vez. "
            "Divida o arquivo em partes menores antes de importar."
        )

    df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed', na=False)]

    # Renomeia colunas por correspondência exata
    mapa = {}
    usados = set()
    for col in df.columns:
        col_strip = col.strip()
        for original, novo in COLUNAS_ESPERADAS.items():
            if original.lower() == col_strip.lower() and novo not in usados:
                mapa[col] = novo
                usados.add(novo)
                break
    df = df.rename(columns=mapa)

    # Fallbacks para CNPJ
    if 'cnpj_emitente' not in df.columns and 'cnpj_emitente_raw' in df.columns:
        df['cnpj_emitente'] = df['cnpj_emitente_raw']
    if 'cnpj_destinatario' not in df.columns and 'cnpj_destinatario_raw' in df.columns:
        df['cnpj_destinatario'] = df['cnpj_destinatario_raw']

    # Valida colunas essenciais
    essenciais = ['ncm', 'descricao_produto', 'valor_total', 'cnpj_emitente']
    faltando = [c for c in essenciais if c not in df.columns]
    if faltando:
        raise ValueError(
            f"Colunas não encontradas: {faltando}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    # Limpeza de CNPJs
    for col in ['cnpj_emitente', 'cnpj_destinatario', 'cnpj_emitente_raw', 'cnpj_destinatario_raw']:
        if col in df.columns:
            df[col] = df[col].apply(_limpar_cnpj)

    # Limpeza de NCM
    df['ncm'] = df['ncm'].apply(lambda x: re.sub(r'\D', '', str(x)) if pd.notna(x) else '')

    # Limpeza numérica
    for col in ['valor_total', 'valor_unitario', 'quantidade', 'valor_frete',
                'icms_bc', 'icms_aliq', 'icms_valor']:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '.', regex=False),
                errors='coerce'
            ).fillna(0.0)

    # Remove linhas sem NCM
    df = df[df['ncm'].str.len() > 0].reset_index(drop=True)

    # Formata data para padrão brasileiro
    if 'data_emissao' in df.columns:
        datas = pd.to_datetime(df['data_emissao'], errors='coerce', dayfirst=False)
        mask = datas.notna()
        df.loc[mask, 'data_emissao'] = datas[mask].dt.strftime('%d/%m/%Y')

    return df


def listar_clientes(df: pd.DataFrame) -> list:
    if 'cnpj_destinatario' not in df.columns:
        return []
    col_nome = 'nome_destinatario' if 'nome_destinatario' in df.columns else None
    cols = ['cnpj_destinatario'] + ([col_nome] if col_nome else [])
    clientes = df[cols].drop_duplicates()
    clientes = clientes[clientes['cnpj_destinatario'].str.len() >= 11]
    return clientes.to_dict('records')
