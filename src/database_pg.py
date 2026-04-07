import os
import json
import psycopg2
import psycopg2.extras
import streamlit as st


def get_connection():
    url = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def inicializar_banco():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS classificacoes (
            id SERIAL PRIMARY KEY,
            cnpj_destinatario TEXT,
            nome_destinatario TEXT,
            cnpj_emitente TEXT,
            nome_emitente TEXT,
            numero_nf TEXT,
            ncm TEXT,
            cfop TEXT,
            descricao_produto TEXT,
            valor_total REAL,
            classificacao TEXT NOT NULL,
            confirmado_fiscal INTEGER DEFAULT 0,
            usuario TEXT,
            data_classificacao DATE DEFAULT CURRENT_DATE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS regras_ncm (
            id SERIAL PRIMARY KEY,
            ncm TEXT NOT NULL,
            cnpj_destinatario TEXT NOT NULL DEFAULT '',
            classificacao TEXT NOT NULL,
            descricao TEXT,
            criado_em DATE DEFAULT CURRENT_DATE,
            UNIQUE(ncm, cnpj_destinatario)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            cnpj TEXT PRIMARY KEY,
            razao_social TEXT,
            cnae TEXT,
            descricao_cnae TEXT,
            cnaes_secundarios TEXT DEFAULT '',
            cnaes_secundarios_det TEXT DEFAULT '',
            atualizado_em DATE DEFAULT CURRENT_DATE
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_class_cnpj_ncm
        ON classificacoes(cnpj_destinatario, ncm, confirmado_fiscal)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_class_data
        ON classificacoes(data_classificacao)
    """)

    conn.commit()
    cur.close()
    conn.close()


def salvar_cliente(cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios='', cnaes_secundarios_detalhados=None):
    conn = get_connection()
    cur = conn.cursor()
    det_json = json.dumps(cnaes_secundarios_detalhados or [], ensure_ascii=False)
    cur.execute("""
        INSERT INTO clientes (cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios, cnaes_secundarios_det)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT(cnpj) DO UPDATE SET
            razao_social=EXCLUDED.razao_social,
            cnae=EXCLUDED.cnae,
            descricao_cnae=EXCLUDED.descricao_cnae,
            cnaes_secundarios=EXCLUDED.cnaes_secundarios,
            cnaes_secundarios_det=EXCLUDED.cnaes_secundarios_det,
            atualizado_em=CURRENT_DATE
    """, (cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios, det_json))
    conn.commit()
    cur.close()
    conn.close()


def buscar_cliente(cnpj):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clientes WHERE cnpj = %s", (cnpj,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    d = dict(row)
    raw = d.get('cnaes_secundarios') or ''
    d['cnaes_secundarios'] = [c for c in raw.split(',') if c]
    try:
        d['cnaes_secundarios_detalhados'] = json.loads(d.get('cnaes_secundarios_det') or '[]')
    except Exception:
        d['cnaes_secundarios_detalhados'] = []
    return d


def deletar_cache_cliente(cnpj: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM clientes WHERE cnpj = %s", (cnpj,))
    conn.commit()
    cur.close()
    conn.close()


def salvar_classificacao(cnpj_destinatario, nome_destinatario, cnpj_emitente,
                          nome_emitente, numero_nf, ncm, descricao, valor, classificacao, confirmado=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO classificacoes
            (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
             numero_nf, ncm, descricao_produto, valor_total, classificacao, confirmado_fiscal)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
          numero_nf, ncm, descricao, valor, classificacao, int(confirmado)))
    conn.commit()
    cur.close()
    conn.close()


def buscar_historico_ncm(cnpj_destinatario, ncm):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT classificacao, COUNT(*) as total
        FROM classificacoes
        WHERE cnpj_destinatario = %s AND ncm = %s AND confirmado_fiscal = 1
        GROUP BY classificacao
        ORDER BY total DESC
        LIMIT 1
    """, (cnpj_destinatario, ncm))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row['classificacao'] if row else None


def buscar_regra_ncm(ncm, cnpj_destinatario=''):
    if not ncm:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cap = ncm[:2] if len(ncm) >= 2 else ''
    cur.execute(
        "SELECT * FROM regras_ncm WHERE ncm = ANY(%s) AND cnpj_destinatario = %s LIMIT 1",
        ([ncm, cap], cnpj_destinatario)
    )
    row = cur.fetchone()
    if not row and cnpj_destinatario:
        cur.execute(
            "SELECT * FROM regras_ncm WHERE ncm = ANY(%s) AND cnpj_destinatario = '' LIMIT 1",
            ([ncm, cap],)
        )
        row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def salvar_regra_ncm(ncm, classificacao, descricao='', cnpj_destinatario=''):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO regras_ncm (ncm, cnpj_destinatario, classificacao, descricao)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(ncm, cnpj_destinatario) DO UPDATE SET
            classificacao=EXCLUDED.classificacao,
            descricao=EXCLUDED.descricao
    """, (ncm, cnpj_destinatario, classificacao, descricao))
    conn.commit()
    cur.close()
    conn.close()


def listar_regras_ncm():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, c.razao_social
        FROM regras_ncm r
        LEFT JOIN clientes c ON c.cnpj = r.cnpj_destinatario AND r.cnpj_destinatario != ''
        ORDER BY r.ncm, r.cnpj_destinatario
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def deletar_regra_ncm(ncm, cnpj_destinatario=''):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM regras_ncm WHERE ncm = %s AND cnpj_destinatario = %s", (ncm, cnpj_destinatario))
    conn.commit()
    cur.close()
    conn.close()


def buscar_todas_regras_ncm() -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ncm, cnpj_destinatario, classificacao, descricao FROM regras_ncm")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {
        (row['ncm'], row['cnpj_destinatario']): {
            'classificacao': row['classificacao'],
            'descricao': row['descricao'],
        }
        for row in rows
    }


def buscar_historico_cliente(cnpj_destinatario) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ncm, classificacao
        FROM classificacoes
        WHERE cnpj_destinatario = %s AND confirmado_fiscal = 1
          AND id IN (
              SELECT MAX(id) FROM classificacoes
              WHERE cnpj_destinatario = %s AND confirmado_fiscal = 1
              GROUP BY ncm
          )
    """, (cnpj_destinatario, cnpj_destinatario))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row['ncm']: row['classificacao'] for row in rows}


def deletar_historico_item(cnpj_destinatario: str, ncm: str, descricao_produto: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM classificacoes WHERE cnpj_destinatario = %s AND ncm = %s AND descricao_produto = %s",
        (cnpj_destinatario, ncm, descricao_produto)
    )
    conn.commit()
    cur.close()
    conn.close()


def listar_historico_itens(cnpj_destinatario: str = None) -> list:
    conn = get_connection()
    cur = conn.cursor()
    if cnpj_destinatario:
        cur.execute("""
            SELECT id, cnpj_destinatario, nome_destinatario, ncm, cfop,
                   descricao_produto, classificacao, usuario, data_classificacao
            FROM classificacoes
            WHERE cnpj_destinatario = %s AND confirmado_fiscal = 1
            ORDER BY id DESC
        """, (cnpj_destinatario,))
    else:
        cur.execute("""
            SELECT id, cnpj_destinatario, nome_destinatario, ncm, cfop,
                   descricao_produto, classificacao, usuario, data_classificacao
            FROM classificacoes
            WHERE confirmado_fiscal = 1
            ORDER BY id DESC
        """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def salvar_classificacoes_batch(lista_de_tuplas):
    conn = get_connection()
    cur = conn.cursor()
    for t in lista_de_tuplas:
        cnpj_dest, nome_dest, cnpj_emit, nome_emit, numero_nf, ncm, cfop, descricao, valor, classificacao, confirmado, usuario = t

        cur.execute("""
            SELECT id, classificacao FROM classificacoes
            WHERE cnpj_destinatario = %s AND ncm = %s AND descricao_produto = %s AND confirmado_fiscal = 1
        """, (cnpj_dest, ncm, descricao))
        existing = cur.fetchone()

        if existing is None:
            cur.execute("""
                INSERT INTO classificacoes
                    (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
                     numero_nf, ncm, cfop, descricao_produto, valor_total, classificacao, confirmado_fiscal, usuario)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (cnpj_dest, nome_dest, cnpj_emit, nome_emit, numero_nf, ncm, cfop, descricao, valor, classificacao, confirmado, usuario))
        elif existing['classificacao'] != classificacao:
            cur.execute("""
                UPDATE classificacoes
                SET classificacao = %s, usuario = %s, data_classificacao = CURRENT_DATE,
                    nome_destinatario = %s, cnpj_emitente = %s, nome_emitente = %s
                WHERE id = %s
            """, (classificacao, usuario, nome_dest, cnpj_emit, nome_emit, existing['id']))

    conn.commit()
    cur.close()
    conn.close()


def get_connection_raw():
    """Retorna conexão sem RealDictCursor — para uso no app.py com queries diretas."""
    url = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn
