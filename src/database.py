import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'historico.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def inicializar_banco():
    conn = get_connection()

    # Cria tabelas se não existirem
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS classificacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj_destinatario TEXT,
            nome_destinatario TEXT,
            cnpj_emitente TEXT,
            nome_emitente TEXT,
            numero_nf TEXT,
            ncm TEXT,
            descricao_produto TEXT,
            valor_total REAL,
            classificacao TEXT NOT NULL,
            confirmado_fiscal INTEGER DEFAULT 0,
            data_classificacao TEXT DEFAULT (date('now'))
        );

        CREATE TABLE IF NOT EXISTS regras_ncm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ncm TEXT NOT NULL,
            cnpj_destinatario TEXT NOT NULL DEFAULT '',
            classificacao TEXT NOT NULL,
            descricao TEXT,
            criado_em TEXT DEFAULT (date('now')),
            UNIQUE(ncm, cnpj_destinatario)
        );

        CREATE TABLE IF NOT EXISTS clientes (
            cnpj TEXT PRIMARY KEY,
            razao_social TEXT,
            cnae TEXT,
            descricao_cnae TEXT,
            atualizado_em TEXT DEFAULT (date('now'))
        );
    """)

    # Migração: renomeia colunas antigas (cnpj_cliente → cnpj_destinatario, etc.)
    colunas_existentes = [row[1] for row in conn.execute("PRAGMA table_info(classificacoes)").fetchall()]
    if 'cnpj_cliente' in colunas_existentes and 'cnpj_destinatario' not in colunas_existentes:
        tem_nome_cliente = 'nome_cliente' in colunas_existentes
        tem_nome_destinatario = 'nome_destinatario' in colunas_existentes
        if tem_nome_cliente:
            col_nome = "COALESCE(nome_cliente, '')"
        elif tem_nome_destinatario:
            col_nome = "COALESCE(nome_destinatario, '')"
        else:
            col_nome = "''"

        conn.executescript(f"""
            ALTER TABLE classificacoes RENAME TO classificacoes_old;

            CREATE TABLE classificacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cnpj_destinatario TEXT,
                nome_destinatario TEXT,
                cnpj_emitente TEXT,
                nome_emitente TEXT,
                numero_nf TEXT,
                ncm TEXT,
                descricao_produto TEXT,
                valor_total REAL,
                classificacao TEXT NOT NULL,
                confirmado_fiscal INTEGER DEFAULT 0,
                data_classificacao TEXT DEFAULT (date('now'))
            );

            INSERT INTO classificacoes
                (id, cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
                 numero_nf, ncm, descricao_produto, valor_total, classificacao,
                 confirmado_fiscal, data_classificacao)
            SELECT
                id,
                cnpj_cliente,
                {col_nome},
                COALESCE(cnpj_emitente, ''),
                COALESCE(nome_emitente, ''),
                COALESCE(numero_nf, ''),
                COALESCE(ncm, ''),
                COALESCE(descricao_produto, ''),
                COALESCE(valor_total, 0),
                classificacao,
                COALESCE(confirmado_fiscal, 0),
                COALESCE(data_classificacao, date('now'))
            FROM classificacoes_old;

            DROP TABLE classificacoes_old;
        """)

    # Migração: adiciona colunas que podem estar faltando em bancos antigos
    colunas_necessarias = {
        'classificacoes': [
            ('cnpj_destinatario', 'TEXT'),
            ('nome_destinatario', 'TEXT'),
            ('cnpj_emitente', 'TEXT'),
            ('nome_emitente', 'TEXT'),
            ('numero_nf', 'TEXT'),
            ('ncm', 'TEXT'),
            ('cfop', 'TEXT'),
            ('descricao_produto', 'TEXT'),
            ('valor_total', 'REAL'),
            ('confirmado_fiscal', 'INTEGER DEFAULT 0'),
            ('usuario', 'TEXT'),
        ]
    }
    for tabela, colunas in colunas_necessarias.items():
        colunas_existentes = [row[1] for row in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
        for coluna, tipo in colunas:
            if coluna not in colunas_existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")

    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_class_cnpj_ncm ON classificacoes(cnpj_destinatario, ncm, confirmado_fiscal);
        CREATE INDEX IF NOT EXISTS idx_class_data ON classificacoes(data_classificacao);
    """)

    # Migração: remove duplicatas mantendo apenas o registro mais antigo por (cnpj_dest, ncm, cfop, descricao)
    conn.execute("""
        DELETE FROM classificacoes
        WHERE confirmado_fiscal = 1
          AND id NOT IN (
              SELECT MIN(id)
              FROM classificacoes
              WHERE confirmado_fiscal = 1
              GROUP BY cnpj_destinatario, ncm, COALESCE(cfop, ''), descricao_produto
          )
    """)
    conn.commit()

    # Migração: regras_ncm — adiciona cnpj_destinatario para regras por empresa
    cols_regras = [row[1] for row in conn.execute("PRAGMA table_info(regras_ncm)").fetchall()]
    if 'cnpj_destinatario' not in cols_regras:
        conn.executescript("""
            ALTER TABLE regras_ncm RENAME TO regras_ncm_old;

            CREATE TABLE regras_ncm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ncm TEXT NOT NULL,
                cnpj_destinatario TEXT NOT NULL DEFAULT '',
                classificacao TEXT NOT NULL,
                descricao TEXT,
                criado_em TEXT DEFAULT (date('now')),
                UNIQUE(ncm, cnpj_destinatario)
            );

            INSERT INTO regras_ncm (ncm, cnpj_destinatario, classificacao, descricao, criado_em)
            SELECT ncm, '', classificacao, COALESCE(descricao,''), COALESCE(criado_em, date('now'))
            FROM regras_ncm_old;

            DROP TABLE regras_ncm_old;
        """)

    conn.commit()
    conn.close()


def salvar_cliente(cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios='', cnaes_secundarios_detalhados=None):
    conn = get_connection()
    # Garante colunas existem
    cols = [r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    if 'cnaes_secundarios' not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN cnaes_secundarios TEXT DEFAULT ''")
    if 'cnaes_secundarios_det' not in cols:
        conn.execute("ALTER TABLE clientes ADD COLUMN cnaes_secundarios_det TEXT DEFAULT ''")
    det_json = json.dumps(cnaes_secundarios_detalhados or [], ensure_ascii=False)
    conn.execute("""
        INSERT INTO clientes (cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios, cnaes_secundarios_det)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(cnpj) DO UPDATE SET
            razao_social=excluded.razao_social,
            cnae=excluded.cnae,
            descricao_cnae=excluded.descricao_cnae,
            cnaes_secundarios=excluded.cnaes_secundarios,
            cnaes_secundarios_det=excluded.cnaes_secundarios_det,
            atualizado_em=date('now')
    """, (cnpj, razao_social, cnae, descricao_cnae, cnaes_secundarios, det_json))
    conn.commit()
    conn.close()


def buscar_cliente(cnpj):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clientes WHERE cnpj = ?", (cnpj,)).fetchone()
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
    """Remove o cliente do cache local para forçar nova consulta à Receita Federal."""
    conn = get_connection()
    conn.execute("DELETE FROM clientes WHERE cnpj = ?", (cnpj,))
    conn.commit()
    conn.close()


def salvar_classificacao(cnpj_destinatario, nome_destinatario, cnpj_emitente,
                          nome_emitente, numero_nf, ncm, descricao, valor, classificacao, confirmado=False):
    conn = get_connection()
    conn.execute("""
        INSERT INTO classificacoes
            (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
             numero_nf, ncm, descricao_produto, valor_total, classificacao, confirmado_fiscal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
          numero_nf, ncm, descricao, valor, classificacao, int(confirmado)))
    conn.commit()
    conn.close()


def buscar_historico_ncm(cnpj_destinatario, ncm):
    """Retorna a classificação mais frequente confirmada para este cliente + NCM."""
    conn = get_connection()
    row = conn.execute("""
        SELECT classificacao, COUNT(*) as total
        FROM classificacoes
        WHERE cnpj_destinatario = ? AND ncm = ? AND confirmado_fiscal = 1
        GROUP BY classificacao
        ORDER BY total DESC
        LIMIT 1
    """, (cnpj_destinatario, ncm)).fetchone()
    conn.close()
    return row['classificacao'] if row else None


def buscar_regra_ncm(ncm, cnpj_destinatario=''):
    if not ncm:
        return None
    conn = get_connection()
    cap = ncm[:2] if len(ncm) >= 2 else ''
    # Tenta regra específica para o CNPJ, depois global
    row = conn.execute(
        "SELECT * FROM regras_ncm WHERE ncm IN (?,?) AND cnpj_destinatario = ? LIMIT 1",
        (ncm, cap, cnpj_destinatario)
    ).fetchone()
    if not row and cnpj_destinatario:
        row = conn.execute(
            "SELECT * FROM regras_ncm WHERE ncm IN (?,?) AND cnpj_destinatario = '' LIMIT 1",
            (ncm, cap)
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def salvar_regra_ncm(ncm, classificacao, descricao='', cnpj_destinatario=''):
    conn = get_connection()
    conn.execute("""
        INSERT INTO regras_ncm (ncm, cnpj_destinatario, classificacao, descricao)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ncm, cnpj_destinatario) DO UPDATE SET
            classificacao=excluded.classificacao,
            descricao=excluded.descricao
    """, (ncm, cnpj_destinatario, classificacao, descricao))
    conn.commit()
    conn.close()


def listar_regras_ncm():
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, c.razao_social
        FROM regras_ncm r
        LEFT JOIN clientes c ON c.cnpj = r.cnpj_destinatario AND r.cnpj_destinatario != ''
        ORDER BY r.ncm, r.cnpj_destinatario
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def deletar_regra_ncm(ncm, cnpj_destinatario=''):
    conn = get_connection()
    conn.execute("DELETE FROM regras_ncm WHERE ncm = ? AND cnpj_destinatario = ?", (ncm, cnpj_destinatario))
    conn.commit()
    conn.close()


def buscar_todas_regras_ncm() -> dict:
    """Retorna {(ncm, cnpj_destinatario): {classificacao, descricao}}. cnpj='' = regra global."""
    conn = get_connection()
    rows = conn.execute("SELECT ncm, cnpj_destinatario, classificacao, descricao FROM regras_ncm").fetchall()
    conn.close()
    return {
        (row['ncm'], row['cnpj_destinatario']): {
            'classificacao': row['classificacao'],
            'descricao': row['descricao'],
        }
        for row in rows
    }


def buscar_historico_cliente(cnpj_destinatario) -> dict:
    """Retorna {ncm: classificacao} com a classificação mais recente confirmada por NCM."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ncm, classificacao
        FROM classificacoes
        WHERE cnpj_destinatario = ? AND confirmado_fiscal = 1
          AND id IN (
              SELECT MAX(id) FROM classificacoes
              WHERE cnpj_destinatario = ? AND confirmado_fiscal = 1
              GROUP BY ncm
          )
    """, (cnpj_destinatario, cnpj_destinatario)).fetchall()
    conn.close()
    return {row['ncm']: row['classificacao'] for row in rows}


def deletar_historico_item(cnpj_destinatario: str, ncm: str, descricao_produto: str):
    """Remove todos os registros do histórico para um cliente + NCM + descrição específica.
    Itens diferentes com o mesmo NCM mas descrição diferente não são afetados."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM classificacoes WHERE cnpj_destinatario = ? AND ncm = ? AND descricao_produto = ?",
        (cnpj_destinatario, ncm, descricao_produto)
    )
    conn.commit()
    conn.close()


def listar_historico_itens(cnpj_destinatario: str = None) -> list:
    """Retorna todos os itens confirmados do histórico, do mais recente ao mais antigo."""
    conn = get_connection()
    if cnpj_destinatario:
        rows = conn.execute("""
            SELECT id, cnpj_destinatario, nome_destinatario, ncm, cfop,
                   descricao_produto, classificacao, usuario, data_classificacao
            FROM classificacoes
            WHERE cnpj_destinatario = ? AND confirmado_fiscal = 1
            ORDER BY id DESC
        """, (cnpj_destinatario,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, cnpj_destinatario, nome_destinatario, ncm, cfop,
                   descricao_produto, classificacao, usuario, data_classificacao
            FROM classificacoes
            WHERE confirmado_fiscal = 1
            ORDER BY id DESC
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def salvar_classificacoes_batch(lista_de_tuplas):
    """Tuplas: (cnpj_dest, nome_dest, cnpj_emit, nome_emit, numero_nf, ncm, cfop, descricao, valor, classificacao, confirmado, usuario)

    Regras de unicidade por (cnpj_dest, ncm, descricao):
    - Registro inexistente → insere com data atual
    - Registro existente com mesma classificação → não altera (mantém data original)
    - Registro existente com classificação diferente → atualiza classificação, usuário e data
    """
    conn = get_connection()
    for t in lista_de_tuplas:
        cnpj_dest, nome_dest, cnpj_emit, nome_emit, numero_nf, ncm, cfop, descricao, valor, classificacao, confirmado, usuario = t

        existing = conn.execute("""
            SELECT id, classificacao FROM classificacoes
            WHERE cnpj_destinatario = ? AND ncm = ? AND descricao_produto = ? AND confirmado_fiscal = 1
        """, (cnpj_dest, ncm, descricao)).fetchone()

        if existing is None:
            conn.execute("""
                INSERT INTO classificacoes
                    (cnpj_destinatario, nome_destinatario, cnpj_emitente, nome_emitente,
                     numero_nf, ncm, descricao_produto, valor_total, classificacao, confirmado_fiscal, usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cnpj_dest, nome_dest, cnpj_emit, nome_emit, numero_nf, ncm, descricao, valor, classificacao, confirmado, usuario))
        elif existing['classificacao'] != classificacao:
            # Reclassificado: atualiza classificação, usuário e data
            conn.execute("""
                UPDATE classificacoes
                SET classificacao = ?, usuario = ?, data_classificacao = date('now'),
                    nome_destinatario = ?, cnpj_emitente = ?, nome_emitente = ?
                WHERE id = ?
            """, (classificacao, usuario, nome_dest, cnpj_emit, nome_emit, existing['id']))
        # Mesma classificação: não faz nada (mantém data original)
    conn.commit()
    conn.close()
