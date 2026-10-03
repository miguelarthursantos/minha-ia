import sqlite3

BANCO = "ia.db"

conexao = sqlite3.connect(BANCO)

print("Verificando banco de dados...")

# Verifica as colunas atuais da tabela usuarios
colunas = conexao.execute("PRAGMA table_info(usuarios)").fetchall()

nomes_colunas = [coluna[1] for coluna in colunas]

print("Colunas atuais:", nomes_colunas)

# Adiciona email caso não exista
if "email" not in nomes_colunas:
    print("Adicionando coluna email...")
    conexao.execute("""
        ALTER TABLE usuarios
        ADD COLUMN email TEXT
    """)
    print("Coluna email adicionada com sucesso.")
else:
    print("A coluna email já existe.")

# Cria índice para email, se possível
try:
    conexao.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email
        ON usuarios(email)
        WHERE email IS NOT NULL
    """)
except sqlite3.IntegrityError:
    print("Não foi possível criar o índice único de email.")
    print("Isso pode acontecer se houver emails repetidos.")

conexao.commit()
conexao.close()

print()
print("Banco corrigido com sucesso!")