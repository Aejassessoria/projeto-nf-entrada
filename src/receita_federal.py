import requests
import re
import time
import concurrent.futures
import streamlit as st

from src.database_pg import salvar_cliente, buscar_cliente

API_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
TIMEOUT = 10


def _limpar_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', cnpj)


def consultar_cnpj(cnpj: str) -> dict | None:
    """
    Consulta dados da empresa na API da Receita Federal (via BrasilAPI).
    Retorna dict com razao_social, cnae, descricao_cnae ou None em caso de erro.
    """
    cnpj_limpo = _limpar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        return None

    # Verifica cache local primeiro
    cached = buscar_cliente(cnpj_limpo)
    if cached:
        return cached

    try:
        url = API_URL.format(cnpj=cnpj_limpo)
        resp = requests.get(url, timeout=TIMEOUT)

        if resp.status_code == 429:
            time.sleep(2)
            resp = requests.get(url, timeout=TIMEOUT)

        if resp.status_code != 200:
            return None

        data = resp.json()

        cnae = str(data.get('cnae_fiscal', '') or '')
        descricao_cnae = data.get('cnae_fiscal_descricao', '') or ''
        razao_social = data.get('razao_social', '') or ''

        # CNAEs secundários (código + descrição)
        secundarios_raw = data.get('cnaes_secundarios') or []
        cnaes_secundarios_detalhados = [
            {'codigo': str(c['codigo']), 'descricao': c.get('descricao', '')}
            for c in secundarios_raw if c.get('codigo')
        ]
        cnaes_secundarios_codigos = [c['codigo'] for c in cnaes_secundarios_detalhados]
        cnaes_secundarios_str = ','.join(cnaes_secundarios_codigos)

        salvar_cliente(cnpj_limpo, razao_social, cnae, descricao_cnae, cnaes_secundarios_str,
                       cnaes_secundarios_detalhados=cnaes_secundarios_detalhados)

        return {
            'cnpj': cnpj_limpo,
            'razao_social': razao_social,
            'cnae': cnae,
            'descricao_cnae': descricao_cnae,
            'cnaes_secundarios': cnaes_secundarios_codigos,
            'cnaes_secundarios_detalhados': cnaes_secundarios_detalhados,
        }

    except Exception as e:
        st.warning(f"Falha ao consultar CNPJ {cnpj_limpo}: {e}")
        return None


def consultar_cnpjs_batch(lista_cnpjs: list) -> dict:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(consultar_cnpj, cnpj): cnpj for cnpj in lista_cnpjs}
        resultado = {}
        for future in concurrent.futures.as_completed(futures):
            cnpj = futures[future]
            info = future.result()
            if info:
                resultado[_limpar_cnpj(cnpj)] = info
    return resultado


def consultar_ncm(ncm: str) -> dict | None:
    """Consulta a descrição oficial do NCM na BrasilAPI."""
    ncm_limpo = re.sub(r'\D', '', ncm)
    if len(ncm_limpo) < 2:
        return None
    try:
        resp = requests.get(f"https://brasilapi.com.br/api/ncm/v1/{ncm_limpo}", timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return {
            'ncm': data.get('codigo', ncm_limpo),
            'descricao': data.get('descricao', ''),
        }
    except Exception as e:
        st.warning(f"Falha ao consultar NCM {ncm_limpo}: {e}")
        return None


def formatar_cnpj(cnpj: str) -> str:
    c = _limpar_cnpj(cnpj)
    if len(c) != 14:
        return cnpj
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
