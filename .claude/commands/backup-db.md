# Backup DB — Backup do Banco de Dados Neon

Gera um backup completo dos dados do banco PostgreSQL Neon antes de qualquer operação crítica (migração, atualizações, deploy).

## Verificação Prévia

Confirme que `pg_dump` está disponível:

```bash
where pg_dump 2>&1 || echo "pg_dump nao encontrado — instale o PostgreSQL client"
```

Leia a URL do banco atual:

```bash
python -c "
import sys
sys.path.insert(0, '.')
# Lê apenas o secrets.toml localmente (sem iniciar Streamlit)
try:
    with open('.streamlit/secrets.toml') as f:
        for line in f:
            if 'DATABASE_URL' in line:
                url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                # Oculta a senha no log
                parts = url.split('@')
                safe = parts[0].split(':')[0] + ':***@' + parts[1] if '@' in url else url
                print('Banco:', safe)
except Exception as e:
    print('Erro ao ler secrets.toml:', e)
"
```

## Executar Backup

```bash
BACKUP_FILE="backup_neon_$(date +%Y%m%d_%H%M).sql"

# Lê DATABASE_URL do secrets.toml
DB_URL=$(python -c "
with open('.streamlit/secrets.toml') as f:
    for line in f:
        if 'DATABASE_URL' in line:
            print(line.split('=', 1)[1].strip().strip('\"').strip(\"'\"))
")

echo "Iniciando backup para: $BACKUP_FILE"
pg_dump "$DB_URL" \
  --data-only \
  --no-owner \
  --inserts \
  -t classificacoes \
  -t regras_ncm \
  -t clientes \
  -f "$BACKUP_FILE"

echo "Backup concluido!"
```

## Verificar Backup

```bash
echo "=== Registros exportados por tabela ==="
grep -c "INSERT INTO.*classificacoes" "$BACKUP_FILE" && echo " registros em classificacoes" || echo "0 registros em classificacoes"
grep -c "INSERT INTO.*regras_ncm" "$BACKUP_FILE" && echo " registros em regras_ncm" || echo "0 registros em regras_ncm"
grep -c "INSERT INTO.*clientes" "$BACKUP_FILE" && echo " registros em clientes" || echo "0 registros em clientes"
echo ""
echo "Arquivo gerado: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"
```

## Resultado Esperado

Informe ao usuário:
- Nome do arquivo gerado (ex: `backup_neon_20240615_1430.sql`)
- Quantidade de registros por tabela
- Tamanho do arquivo
- Confirmação de que o backup está pronto para uso na migração

> Guarde este arquivo em local seguro antes de prosseguir com qualquer migração.
