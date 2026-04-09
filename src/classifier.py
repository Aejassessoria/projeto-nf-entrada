import pandas as pd

try:
    import streamlit as st
    _db_url = st.secrets["DATABASE_URL"]
    from src.database_pg import buscar_historico_ncm, buscar_regra_ncm
except Exception:
    from src.database import buscar_historico_ncm, buscar_regra_ncm

VALOR_MINIMO_IMOBILIZADO = 1200.0

RESULTADO_IMOBILIZADO = 'IMOBILIZADO'
RESULTADO_USO_CONSUMO = 'USO E CONSUMO'
RESULTADO_REVENDA     = 'REVENDA'
RESULTADO_INCERTO     = 'INCERTO'

# Palavras na descrição que indicam uso e consumo
PALAVRAS_USO_CONSUMO = [
    'papel', 'caneta', 'limpeza', 'higiene', 'detergente', 'sabão', 'sabonete',
    'café', 'agua', 'água', 'aliment', 'refeiç', 'combustivel', 'combustível',
    'gasolina', 'etanol', 'envelope', 'toner', 'cartucho', 'ribbon', 'fita',
    'etiqueta', 'pilha', 'bateria descartável', 'luva', 'mascara', 'máscara',
    'epi', 'uniforme', 'embalagem', 'sacola', 'copo descartável',
]

# Palavras na descrição que indicam imobilizado (quando valor > 1200)
PALAVRAS_IMOBILIZADO = [
    'maquina', 'máquina', 'equipamento', 'aparelho', 'motor', 'compressor',
    'gerador', 'ar condicionado', 'elevador', 'veículo', 'veiculo', 'caminhão',
    'caminhao', 'carro', 'moto', 'computador', 'notebook', 'servidor',
    'impressora', 'scanner', 'câmera', 'camera', 'televisão', 'televisao',
    'monitor', 'projetor', 'mesa', 'cadeira', 'armário', 'armario',
    'estante', 'prateleira', 'balcão', 'balcao', 'refrigerador', 'freezer',
    'forno industrial', 'balança', 'balanca', 'torno', 'fresadora',
    'empilhadeira', 'drone', 'roteador', 'switch', 'nobreak', 'rack',
]

# Palavras na descrição que indicam matéria-prima
PALAVRAS_MATERIA_PRIMA = [
    'materia prima', 'matéria prima', 'insumo', 'ativo farmaceutico', 'ativo farmacêutico',
    'principio ativo', 'princípio ativo', 'excipiente', 'resina', 'polimero', 'polímero',
    'granulo', 'grânulo', 'pellet', 'concentrado', 'extrato', 'essencia', 'essência',
    'pigmento', 'corante', 'solvente', 'solvent', 'aditivo', 'catalisador',
    'arame', 'chapa', 'bobina', 'lingote', 'tarugo', 'barra', 'perfil',
    'fio de cobre', 'fio de aco', 'fio de aço', 'tubo', 'vergalhao', 'vergalhão',
    'tecido cru', 'fio', 'fibra', 'filamento',
    'oleo vegetal', 'óleo vegetal', 'oleo essencial', 'óleo essencial',
    'cera de', 'manteiga de', 'silicone', 'glicerina', 'parafina',
    'amido', 'farinha industrial', 'acucar industrial', 'açúcar industrial',
    'emulsificante', 'conservante', 'estabilizante', 'antioxidante',
]

# CFOP → classificação direta (usa os 3 últimos dígitos, ignorando o prefixo 1/2/3)
_CFOP_MAP = {
    # Imobilizado
    '551': RESULTADO_IMOBILIZADO,  # compra p/ ativo imobilizado
    '552': RESULTADO_IMOBILIZADO,  # retorno de bem do ativo imobilizado
    '553': RESULTADO_IMOBILIZADO,  # ativo imobilizado - produtor rural
    # Uso e consumo
    '556': RESULTADO_USO_CONSUMO,  # compra de material para uso e consumo
    '557': RESULTADO_USO_CONSUMO,  # compra de material p/ uso e consumo (já adquirido)
    '652': RESULTADO_USO_CONSUMO,  # combustível/lubrificante para uso e consumo
    # Revenda / industrialização
    '101': RESULTADO_REVENDA,      # compra para industrialização
    '102': RESULTADO_REVENDA,      # compra para comercialização
    '111': RESULTADO_REVENDA,      # industrialização sob encomenda
    '116': RESULTADO_REVENDA,      # industrialização por encomenda
    '122': RESULTADO_REVENDA,      # comercialização em consignação
    '401': RESULTADO_REVENDA,      # industrialização em Zona Franca
    '403': RESULTADO_REVENDA,      # comercialização em Zona Franca
}

# Capítulos NCM tipicamente imobilizado
CAPITULOS_IMOBILIZADO = {
    '84': 'Máquinas e equipamentos mecânicos',
    '85': 'Máquinas e equipamentos elétricos',
    '86': 'Veículos ferroviários',
    '87': 'Veículos automóveis',
    '88': 'Aeronaves',
    '89': 'Embarcações',
    '90': 'Instrumentos ópticos e de precisão',
    '94': 'Móveis e mobiliário',
}

# Capítulos NCM tipicamente uso e consumo
CAPITULOS_USO_CONSUMO = {
    '22': 'Bebidas',
    '27': 'Combustíveis minerais',
    '34': 'Sabões e detergentes',
    '39': 'Plásticos e obras',
    '48': 'Papel e cartão',
    '63': 'Artigos têxteis confeccionados',
}

# Capítulos NCM tipicamente matéria-prima (forma primária / granel)
CAPITULOS_MATERIA_PRIMA = {
    '01': 'Animais vivos',
    '02': 'Carnes e miudezas',
    '03': 'Peixes e crustáceos',
    '04': 'Leite e laticínios',
    '05': 'Outros produtos de origem animal',
    '06': 'Plantas vivas',
    '07': 'Produtos hortícolas',
    '08': 'Frutas',
    '09': 'Café, chá, especiarias',
    '10': 'Cereais',
    '11': 'Produtos da indústria de moagem',
    '12': 'Sementes e oleaginosas',
    '13': 'Gomas, resinas e extratos vegetais',
    '14': 'Matérias vegetais para entrançar',
    '15': 'Gorduras e óleos animais/vegetais',
    '25': 'Sal, enxofre, minerais',
    '26': 'Minérios e escórias',
    '28': 'Produtos químicos inorgânicos',
    '29': 'Produtos químicos orgânicos',
    '30': 'Produtos farmacêuticos (ativos)',
    '31': 'Adubos e fertilizantes',
    '32': 'Extratos tânicos, corantes, tintas',
    '33': 'Óleos essenciais e resinoides',
    '35': 'Matérias albuminoides, amidos',
    '36': 'Pólvoras e explosivos',
    '37': 'Produtos fotográficos',
    '38': 'Produtos químicos diversos',
    '40': 'Borracha e suas obras (forma primária)',
    '41': 'Peles e couros',
    '44': 'Madeira e obras de madeira',
    '47': 'Pasta de madeira, papel reciclado',
    '50': 'Seda',
    '51': 'Lã e pelos finos',
    '52': 'Algodão',
    '53': 'Outras fibras têxteis vegetais',
    '54': 'Filamentos sintéticos ou artificiais',
    '55': 'Fibras sintéticas ou artificiais',
    '72': 'Ferro fundido, ferro e aço',
    '73': 'Obras de ferro fundido ou aço',
    '74': 'Cobre e suas obras',
    '75': 'Níquel e suas obras',
    '76': 'Alumínio e suas obras',
    '78': 'Chumbo e suas obras',
    '79': 'Zinco e suas obras',
    '80': 'Estanho e suas obras',
    '81': 'Outros metais comuns',
}

# Mapeamento CNAE industrial → capítulos NCM que são matéria-prima daquela indústria
MAPA_INDUSTRIA_MP = {
    '10': ['01', '02', '03', '04', '07', '08', '09', '10', '11', '12', '13', '15', '17', '20', '21', '28', '29', '33', '35', '38'],  # alimentos
    '11': ['10', '11', '12', '20', '22', '29'],  # bebidas
    '12': ['24'],  # fumo
    '13': ['50', '51', '52', '53', '54', '55', '56'],  # têxtil
    '14': ['50', '51', '52', '53', '54', '55', '56'],  # confecções
    '15': ['41', '43'],  # couro
    '16': ['44', '45'],  # madeira
    '17': ['44', '47'],  # papel e celulose
    '18': ['32', '48'],  # impressão
    '19': ['27'],  # petróleo
    '20': ['25', '26', '28', '29', '31', '32', '38', '39', '40'],  # químicos
    '21': ['28', '29', '30', '33', '35', '38'],  # farmacêutico/cosmético
    '22': ['28', '29', '39', '40'],  # borracha e plástico
    '23': ['25', '26', '28', '68', '69', '70'],  # minerais não-metálicos
    '24': ['26', '72', '73', '74', '75', '76', '78', '79', '80', '81'],  # metalurgia
    '25': ['72', '73', '74', '76'],  # produtos de metal
    '26': ['28', '29', '38', '72', '74', '76', '85'],  # eletrônicos
    '27': ['72', '73', '74', '76', '85'],  # equipamentos elétricos
    '28': ['72', '73', '74', '76'],  # máquinas e equipamentos
    '29': ['39', '40', '72', '73', '74', '76'],  # veículos
    '30': ['39', '72', '73', '76'],  # outros transportes
    '31': ['44', '39', '72', '73'],  # móveis
    '32': ['39', '70', '72', '73', '74', '76'],  # produtos diversos
    '33': ['72', '73', '84', '85'],  # manutenção industrial
}


def _contem_palavra(texto: str, lista: list) -> bool:
    texto_lower = texto.lower()
    return any(p in texto_lower for p in lista)


def _is_industria(cnaes: list) -> tuple:
    """Retorna (True, cnae) se qualquer CNAE da lista for industrial (05-33). Caso contrário (False, '')."""
    for cnae in cnaes:
        if not cnae:
            continue
        try:
            if 5 <= int(str(cnae)[:2]) <= 33:
                return True, cnae
        except (ValueError, IndexError):
            pass
    return False, ''


def _is_materia_prima_industria(ncm: str, cnaes: list) -> tuple:
    """Verifica se o NCM é matéria-prima para qualquer indústria da lista de CNAEs.
    Retorna (True, cnae_que_bateu) ou (False, '')."""
    if not ncm:
        return False, ''
    capitulo = ncm[:2]
    for cnae in cnaes:
        segmento = str(cnae)[:2]
        if capitulo in MAPA_INDUSTRIA_MP.get(segmento, []):
            return True, cnae
    return False, ''


def _mesmo_segmento_ncm_cnae(ncm: str, cnaes: list, descs_cnae: list) -> tuple:
    """Verifica se o NCM bate com a atividade fim de qualquer CNAE da lista.
    Retorna (True, desc_cnae) ou (False, '')."""
    if not ncm:
        return False, ''

    capitulo = ncm[:2]

    mapa_cnae_ncm = {
        '47': ['84', '85', '87', '94', '62', '63', '39', '90'],
        '45': ['87'],
        '46': ['84', '85', '87', '94'],
        '10': ['02', '03', '04', '07', '08', '09', '11', '15', '16', '17', '18', '19', '20', '21'],
        '13': ['50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '60', '61', '62', '63'],
        '14': ['61', '62', '63'],
        '26': ['84', '85', '90'],
        '27': ['85'],
        '28': ['84'],
        '29': ['87'],
        '30': ['88', '89'],
        '31': ['94'],
        '32': ['90', '91', '92', '93', '95', '96'],
    }

    pares_descricao = [
        ('bicicleta', ['87']),
        ('autopeça', ['87']), ('auto peça', ['87']),
        ('farmácia', ['30']), ('farmacia', ['30']), ('medicamento', ['30']),
        ('livro', ['49']), ('papelaria', ['48', '49']),
        ('calçado', ['64']), ('calcado', ['64']),
        ('joia', ['71']), ('ótica', ['90']), ('otica', ['90']),
        ('informatica', ['84', '85']), ('informática', ['84', '85']),
        ('eletrodoméstico', ['84', '85']), ('eletrodomestico', ['84', '85']),
        ('móveis', ['94']), ('moveis', ['94']),
        ('ferragem', ['73', '83']), ('construção', ['68', '69', '70', '72', '73']),
    ]

    for cnae, desc_cnae in zip(cnaes, descs_cnae):
        segmento = str(cnae)[:2]
        desc_lower = (desc_cnae or '').lower()
        if capitulo in mapa_cnae_ncm.get(segmento, []):
            return True, desc_cnae
        for palavra, capitulos in pares_descricao:
            if palavra in desc_lower and capitulo in capitulos:
                return True, desc_cnae

    return False, ''


def _classificar_item(ncm, descricao, valor_unitario, cnpj_destinatario,
                      cnae_destinatario, desc_cnae_destinatario='',
                      cnaes_secundarios: list = None,
                      regras_ncm: dict = None, historico_ncm: dict = None,
                      cfop: str = '') -> dict:

    # Monta lista completa de CNAEs (principal + secundários)
    cnaes_todos = [cnae_destinatario] + (cnaes_secundarios or [])
    cnaes_todos = [c for c in cnaes_todos if c]
    descs_todos = [desc_cnae_destinatario] + [''] * len(cnaes_secundarios or [])

    # 1. Regra fixa por NCM (maior prioridade — decisão explícita do fiscal)
    cap = ncm[:2] if len(ncm) >= 2 else ''
    if regras_ncm is not None:
        # Regra específica do CNPJ tem prioridade sobre global ('')
        regra = (regras_ncm.get((ncm, cnpj_destinatario)) or
                 regras_ncm.get((cap, cnpj_destinatario)) or
                 regras_ncm.get((ncm, '')) or
                 regras_ncm.get((cap, '')))
    else:
        regra = buscar_regra_ncm(ncm, cnpj_destinatario)
    if regra:
        return {
            'classificacao': regra['classificacao'],
            'motivo': f'Regra cadastrada para NCM {ncm}: {regra.get("descricao", "")}',
            'confianca': 'alta',
        }

    # 2. Histórico salvo — classificação anterior confirmada para este cliente/NCM
    if historico_ncm is not None:
        historico = historico_ncm.get(ncm)
    else:
        historico = buscar_historico_ncm(cnpj_destinatario, ncm)
    if historico:
        return {
            'classificacao': historico,
            'motivo': f'Histórico: NCM {ncm} classificado anteriormente como {historico} para este cliente',
            'confianca': 'alta',
        }

    # 3. CFOP — declarado pelo emitente na NF (alta confiança)
    if cfop:
        cfop_limpo = ''.join(c for c in str(cfop) if c.isdigit())
        sufixo = cfop_limpo[-3:] if len(cfop_limpo) >= 3 else ''
        if sufixo in _CFOP_MAP:
            classif_cfop = _CFOP_MAP[sufixo]
            # CFOP de imobilizado só confirma se valor unitário > 1200
            if classif_cfop == RESULTADO_IMOBILIZADO and valor_unitario > 0 and valor_unitario <= VALOR_MINIMO_IMOBILIZADO:
                classif_cfop = RESULTADO_USO_CONSUMO
                motivo_cfop = f'CFOP {cfop_limpo} indica imobilizado, mas valor unitário R$ {valor_unitario:.2f} ≤ R$ 1.200,00 — classificado como uso e consumo'
            else:
                motivo_cfop = f'CFOP {cfop_limpo} indica {classif_cfop.lower()}'
            return {
                'classificacao': classif_cfop,
                'motivo': motivo_cfop,
                'confianca': 'alta',
            }

    eh_industria, cnae_ind = _is_industria(cnaes_todos)
    capitulo = cap

    # 3. Matéria-prima — algum CNAE é industrial + NCM bate com insumos
    if eh_industria:
        bate_mp, cnae_mp = _is_materia_prima_industria(ncm, cnaes_todos)
        if bate_mp:
            return {
                'classificacao': RESULTADO_REVENDA,
                'motivo': f'Produto compatível com a atividade do cliente (CNAE {cnae_mp})',
                'confianca': 'media',
            }
        if _contem_palavra(descricao, PALAVRAS_MATERIA_PRIMA):
            return {
                'classificacao': RESULTADO_REVENDA,
                'motivo': f'Produto compatível com a atividade do cliente: "{descricao[:60]}"',
                'confianca': 'media',
            }
        if capitulo in CAPITULOS_MATERIA_PRIMA:
            return {
                'classificacao': RESULTADO_REVENDA,
                'motivo': f'Produto compatível com a atividade do cliente — NCM {ncm}',
                'confianca': 'media',
            }

    # 4. Revenda — NCM bate com atividade-fim de algum CNAE (principal ou secundário)
    bate_seg, desc_seg = _mesmo_segmento_ncm_cnae(ncm, cnaes_todos, descs_todos)
    if not eh_industria and bate_seg:
        return {
            'classificacao': RESULTADO_REVENDA,
            'motivo': f'Produto compatível com a atividade do cliente ({desc_seg[:60]})',
            'confianca': 'media',
        }

    # 5. Palavras-chave na descrição → revenda
    if _contem_palavra(descricao, PALAVRAS_MATERIA_PRIMA):
        return {
            'classificacao': RESULTADO_REVENDA,
            'motivo': f'Produto compatível com a atividade do cliente: "{descricao[:60]}"',
            'confianca': 'media',
        }

    # 6. Valor unitário <= R$1.200 → uso e consumo (imobilizado exige valor unitário > 1.200)
    if valor_unitario > 0 and valor_unitario <= VALOR_MINIMO_IMOBILIZADO:
        return {
            'classificacao': RESULTADO_USO_CONSUMO,
            'motivo': f'Valor unitário R$ {valor_unitario:.2f} ≤ R$ 1.200,00 (abaixo do limite para imobilizado)',
            'confianca': 'alta',
        }

    # 7. Palavras-chave na descrição → uso e consumo
    if _contem_palavra(descricao, PALAVRAS_USO_CONSUMO):
        return {
            'classificacao': RESULTADO_USO_CONSUMO,
            'motivo': f'Descrição indica item de uso e consumo: "{descricao[:60]}"',
            'confianca': 'media',
        }

    # 8. Palavras-chave na descrição → imobilizado (só se valor unitário > 1200)
    if valor_unitario > VALOR_MINIMO_IMOBILIZADO and _contem_palavra(descricao, PALAVRAS_IMOBILIZADO):
        return {
            'classificacao': RESULTADO_IMOBILIZADO,
            'motivo': f'Descrição indica bem durável + valor unitário R$ {valor_unitario:.2f} > R$ 1.200,00: "{descricao[:60]}"',
            'confianca': 'media',
        }

    # 9. Capítulo NCM
    if capitulo in CAPITULOS_USO_CONSUMO:
        return {
            'classificacao': RESULTADO_USO_CONSUMO,
            'motivo': f'NCM capítulo {capitulo} — {CAPITULOS_USO_CONSUMO[capitulo]} (tipicamente uso e consumo)',
            'confianca': 'media',
        }

    if capitulo in CAPITULOS_IMOBILIZADO:
        if valor_unitario > VALOR_MINIMO_IMOBILIZADO:
            return {
                'classificacao': RESULTADO_IMOBILIZADO,
                'motivo': f'NCM capítulo {capitulo} — {CAPITULOS_IMOBILIZADO[capitulo]} + valor unitário R$ {valor_unitario:.2f} > R$ 1.200,00',
                'confianca': 'media',
            }
        else:
            return {
                'classificacao': RESULTADO_USO_CONSUMO,
                'motivo': f'NCM capítulo {capitulo} mas valor unitário R$ {valor_unitario:.2f} ≤ R$ 1.200,00',
                'confianca': 'media',
            }

    # 10. Incerto
    return {
        'classificacao': RESULTADO_INCERTO,
        'motivo': 'Não foi possível classificar automaticamente — análise manual necessária',
        'confianca': 'baixa',
    }


def classificar_planilha(df: pd.DataFrame, cnpj_destinatario: str, cnae_destinatario: str = '',
                         desc_cnae_destinatario: str = '', cnaes_secundarios: list = None,
                         regras_ncm: dict = None, historico_ncm: dict = None) -> pd.DataFrame:
    resultados = []
    for _, row in df.iterrows():
        resultado = _classificar_item(
            ncm=str(row.get('ncm', '') or '').strip(),
            descricao=str(row.get('descricao_produto', '') or '').strip(),
            valor_unitario=float(row.get('valor_unitario', 0) or 0),
            cnpj_destinatario=cnpj_destinatario,
            cnae_destinatario=cnae_destinatario,
            desc_cnae_destinatario=desc_cnae_destinatario,
            cnaes_secundarios=cnaes_secundarios or [],
            regras_ncm=regras_ncm,
            historico_ncm=historico_ncm,
            cfop=str(row.get('cfop', '') or '').strip(),
        )
        resultados.append(resultado)

    df = df.copy()
    df['classificacao'] = [r['classificacao'] for r in resultados]
    df['motivo'] = [r['motivo'] for r in resultados]
    df['confianca'] = [r['confianca'] for r in resultados]
    return df


def resumo_classificacao(df: pd.DataFrame) -> dict:
    total = len(df)
    imob    = (df['classificacao'] == RESULTADO_IMOBILIZADO).sum()
    uso     = (df['classificacao'] == RESULTADO_USO_CONSUMO).sum()
    revenda = (df['classificacao'] == RESULTADO_REVENDA).sum()
    incerto = (df['classificacao'] == RESULTADO_INCERTO).sum()
    automatizado = imob + uso + revenda
    return {
        'total': total,
        'imobilizado': int(imob),
        'uso_consumo': int(uso),
        'revenda': int(revenda),
        'incerto': int(incerto),
        'automatizado_pct': round(automatizado / total * 100, 1) if total > 0 else 0,
    }
