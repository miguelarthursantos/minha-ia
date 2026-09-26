import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for
)

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from transformers import pipeline
from pypdf import PdfReader
import markdown


# ==========================================
# CONFIGURAÇÕES
# ==========================================

app = Flask(__name__)

app.secret_key = "troque-esta-chave-por-uma-chave-secreta"

DATABASE = "ia.db"
UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==========================================
# BANCO DE DADOS
# ==========================================

def conectar():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_banco():

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT DEFAULT 'Nova conversa',
            criada_em TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER NOT NULL,
            papel TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criada_em TEXT,
            FOREIGN KEY(conversa_id) REFERENCES conversas(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            informacao TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL,
            texto TEXT,
            enviado_em TEXT,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    conexao.commit()
    conexao.close()


criar_banco()


# ==========================================
# IA
# ==========================================

print("Carregando a IA...")

ia = pipeline(
    "text-generation",
    model="Qwen/Qwen2.5-0.5B-Instruct"
)

print("IA carregada!")


# ==========================================
# LOGIN
# ==========================================

def login_obrigatorio(funcao):

    @wraps(funcao)
    def verificar(*args, **kwargs):

        if "usuario_id" not in session:
            return jsonify({
                "erro": "Você precisa estar logado."
            }), 401

        return funcao(*args, **kwargs)

    return verificar


# ==========================================
# PÁGINA PRINCIPAL
# ==========================================

@app.route("/")
def inicio():

    if "usuario_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")

# ==========================================
# VERIFICAR USUÁRIO
# ==========================================

@app.route("/usuario")
def usuario():

    if "usuario_id" in session:
        return jsonify({
            "logado": True,
            "usuario": session.get("usuario")
        })

    return jsonify({
        "logado": False
    })
# ==========================================
# LOGIN
# ==========================================


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":
        return render_template("index.html", tela_login=True)

    dados = request.get_json()

    usuario = dados.get("usuario", "").strip()
    senha = dados.get("senha", "")

    conexao = conectar()

    pessoa = conexao.execute(
        "SELECT * FROM usuarios WHERE usuario = ?",
        (usuario,)
    ).fetchone()

    conexao.close()

    if not pessoa or not check_password_hash(pessoa["senha"], senha):

        return jsonify({
            "erro": "Usuário ou senha incorretos."
        }), 401

    session["usuario_id"] = pessoa["id"]
    session["usuario"] = pessoa["usuario"]

    return jsonify({
        "sucesso": True
    })


# ==========================================
# CADASTRO
# ==========================================

@app.route("/cadastro", methods=["POST"])
def cadastro():

    dados = request.get_json()

    usuario = dados.get("usuario", "").strip()
    senha = dados.get("senha", "")

    if len(usuario) < 3:
        return jsonify({
            "erro": "O usuário precisa ter pelo menos 3 caracteres."
        }), 400

    if len(senha) < 4:
        return jsonify({
            "erro": "A senha precisa ter pelo menos 4 caracteres."
        }), 400

    conexao = conectar()

    try:

        conexao.execute(
            """
            INSERT INTO usuarios (usuario, senha)
            VALUES (?, ?)
            """,
            (
                usuario,
                generate_password_hash(senha)
            )
        )

        conexao.commit()

    except sqlite3.IntegrityError:

        conexao.close()

        return jsonify({
            "erro": "Esse usuário já existe."
        }), 400

    conexao.close()

    return jsonify({
        "sucesso": True
    })


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ==========================================
# LISTAR CONVERSAS
# ==========================================

@app.route("/conversas")
@login_obrigatorio
def conversas():

    conexao = conectar()

    lista = conexao.execute(
        """
        SELECT id, titulo
        FROM conversas
        WHERE usuario_id = ?
        ORDER BY id DESC
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    return jsonify([
        {
            "id": conversa["id"],
            "titulo": conversa["titulo"]
        }
        for conversa in lista
    ])


# ==========================================
# NOVA CONVERSA
# ==========================================

@app.route("/nova_conversa", methods=["POST"])
@login_obrigatorio
def nova_conversa():

    conexao = conectar()

    cursor = conexao.execute(
        """
        INSERT INTO conversas
        (usuario_id, titulo, criada_em)
        VALUES (?, ?, ?)
        """,
        (
            session["usuario_id"],
            "Nova conversa",
            datetime.now().isoformat()
        )
    )

    conexao.commit()

    conversa_id = cursor.lastrowid

    conexao.close()

    session["conversa_id"] = conversa_id

    return jsonify({
        "id": conversa_id
    })


# ==========================================
# CARREGAR CONVERSA
# ==========================================

@app.route("/conversa/<int:conversa_id>")
@login_obrigatorio
def carregar_conversa(conversa_id):

    conexao = conectar()

    conversa = conexao.execute(
        """
        SELECT *
        FROM conversas
        WHERE id = ? AND usuario_id = ?
        """,
        (
            conversa_id,
            session["usuario_id"]
        )
    ).fetchone()

    if not conversa:

        conexao.close()

        return jsonify({
            "erro": "Conversa não encontrada."
        }), 404

    mensagens = conexao.execute(
        """
        SELECT papel, conteudo
        FROM mensagens
        WHERE conversa_id = ?
        ORDER BY id
        """,
        (conversa_id,)
    ).fetchall()

    conexao.close()

    session["conversa_id"] = conversa_id

    return jsonify({
        "titulo": conversa["titulo"],
        "mensagens": [
            {
                "papel": mensagem["papel"],
                "conteudo": mensagem["conteudo"]
            }
            for mensagem in mensagens
        ]
    })


# ==========================================
# MEMÓRIA
# ==========================================

def pegar_memoria():

    conexao = conectar()

    memorias = conexao.execute(
        """
        SELECT informacao
        FROM memoria
        WHERE usuario_id = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    return [
        memoria["informacao"]
        for memoria in memorias
    ]


@app.route("/memoria", methods=["GET", "POST"])
@login_obrigatorio
def memoria():

    if request.method == "GET":

        return jsonify({
            "memoria": pegar_memoria()
        })

    dados = request.get_json()

    informacao = dados.get("informacao", "").strip()

    if not informacao:

        return jsonify({
            "erro": "Digite uma informação."
        }), 400

    conexao = conectar()

    conexao.execute(
        """
        INSERT INTO memoria
        (usuario_id, informacao)
        VALUES (?, ?)
        """,
        (
            session["usuario_id"],
            informacao
        )
    )

    conexao.commit()
    conexao.close()

    return jsonify({
        "sucesso": True
    })

@app.route("/perguntar", methods=["POST"])
@login_obrigatorio
def perguntar():

    dados = request.get_json() or {}
    pergunta = dados.get("pergunta", "").strip()

    if not pergunta:
        return jsonify({
            "erro": "Digite uma pergunta."
        }), 400

    # ==========================================
    # CONVERSA
    # ==========================================

    conversa_id = session.get("conversa_id")

    if not conversa_id:

        conexao = conectar()

        cursor = conexao.execute(
            """
            INSERT INTO conversas
            (usuario_id, titulo, criada_em)
            VALUES (?, ?, ?)
            """,
            (
                session["usuario_id"],
                pergunta[:40],
                datetime.now().isoformat()
            )
        )

        conexao.commit()

        conversa_id = cursor.lastrowid

        conexao.close()

        session["conversa_id"] = conversa_id

    # ==========================================
    # BANCO DE DADOS
    # ==========================================

    conexao = conectar()

    historico = conexao.execute(
        """
        SELECT papel, conteudo
        FROM mensagens
        WHERE conversa_id = ?
        ORDER BY id DESC
        LIMIT 8
        """,
        (conversa_id,)
    ).fetchall()

    documentos = conexao.execute(
        """
        SELECT nome, texto
        FROM documentos
        WHERE usuario_id = ?
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    historico = list(reversed(historico))

    # ==========================================
    # BUSCA NOS PDFs
    # ==========================================

    palavras = []

    for palavra in pergunta.lower().split():

        palavra = palavra.strip(
            ".,!?;:\"'()[]{}"
        )

        if len(palavra) >= 3:
            palavras.append(palavra)

    trechos = []

    for documento in documentos:

        nome = documento["nome"]
        texto = documento["texto"] or ""

        if not texto.strip():
            continue

        texto_lower = texto.lower()

        # Dividir o documento em blocos
        tamanho = 1500
        sobreposicao = 250

        inicio = 0

        while inicio < len(texto):

            fim = min(
                inicio + tamanho,
                len(texto)
            )

            trecho = texto[inicio:fim]
            trecho_lower = trecho.lower()

            pontos = 0
            palavras_encontradas = 0

            for palavra in palavras:

                quantidade = trecho_lower.count(palavra)

                if quantidade > 0:

                    palavras_encontradas += 1

                    pontos += min(
                        quantidade,
                        3
                    )

            # Só aceitar trechos que realmente
            # tenham alguma palavra da pergunta
            if pontos > 0:

                trechos.append({
                    "nome": nome,
                    "texto": trecho,
                    "pontos": pontos,
                    "palavras": palavras_encontradas
                })

            if fim >= len(texto):
                break

            inicio = fim - sobreposicao

    # ==========================================
    # ORDENAR RESULTADOS
    # ==========================================

    trechos.sort(
        key=lambda item: (
            item["palavras"],
            item["pontos"]
        ),
        reverse=True
    )

    # Máximo de 4 trechos
    trechos = trechos[:4]

    # ==========================================
    # CONTEXTO DOS PDFs
    # ==========================================

    contexto_pdf = ""

    if trechos:

        contexto_pdf = (
            "\n\n===== CONTEÚDO ENCONTRADO NOS PDFs =====\n"
        )

        for trecho in trechos:

            contexto_pdf += (
                "\nDOCUMENTO: "
                + trecho["nome"]
                + "\n"
            )

            contexto_pdf += (
                trecho["texto"]
                + "\n"
            )

        contexto_pdf += (
            "\n===== FIM DO CONTEÚDO DOS PDFs =====\n"
        )

    # ==========================================
    # INFORMAÇÃO SOBRE A AUSÊNCIA DE RESULTADOS
    # ==========================================

    if not trechos:

        contexto_pdf = """
NENHUM TRECHO RELEVANTE DOS PDFs FOI ENCONTRADO.

Se a pergunta for sobre os PDFs,
você deve informar que não encontrou
a informação nos documentos.

Não invente informações que não estão
nos trechos dos PDFs.
"""

    # ==========================================
    # MEMÓRIA
    # ==========================================

    memoria_usuario = pegar_memoria()

    contexto_memoria = ""

    if memoria_usuario:

        contexto_memoria = (
            "\n\nMEMÓRIA DO USUÁRIO:\n"
            + "\n".join(
                "- " + item
                for item in memoria_usuario
            )
        )

    # ==========================================
    # SISTEMA DA IA
    # ==========================================

    sistema = """
Você é uma inteligência artificial brasileira
amigável, educativa e precisa.

Responda em português do Brasil.

REGRAS ABSOLUTAS:

1. Quando a pergunta estiver relacionada aos PDFs,
   use SOMENTE as informações presentes no conteúdo
   dos PDFs fornecido abaixo.

2. NÃO invente informações.

3. NÃO complete informações ausentes usando
   conhecimento próprio.

4. Se a informação não estiver nos trechos fornecidos,
   diga claramente:

"Não encontrei essa informação nos PDFs disponíveis."

5. Nunca diga que uma informação veio de um PDF
   se ela não estiver no conteúdo fornecido.

6. Se o usuário pedir uma frase do PDF,
   copie somente uma frase que realmente esteja
   no conteúdo fornecido.

7. Se o usuário pedir um resumo,
   resuma somente o conteúdo encontrado.

8. Se a pergunta NÃO estiver relacionada aos PDFs,
   você pode responder normalmente usando seu
   conhecimento.

9. Não invente nomes, matérias, programas,
   capítulos, questões, páginas ou informações
   que não estejam no contexto.

10. Seja claro e direto.
"""

    mensagens = [
        {
            "role": "system",
            "content": (
                sistema
                + contexto_memoria
                + contexto_pdf
            )
        }
    ]

    # ==========================================
    # HISTÓRICO
    # ==========================================

    for mensagem in historico:

        mensagens.append({
            "role": mensagem["papel"],
            "content": mensagem["conteudo"]
        })

    # ==========================================
    # PERGUNTA
    # ==========================================

    mensagens.append({
        "role": "user",
        "content": pergunta
    })
    print("\n==============================")
print("PERGUNTA:")
print(pergunta)

    # ==========================================
    # IA
    # ==========================================
    
    print("\n==============================")
print("PERGUNTA:")
print(pergunta)

print("\nTRECHOS ENCONTRADOS:")

for trecho in trechos:
    print("\n---", trecho["nome"], "---")
    print("Pontos:", trecho["pontos"])
    print(trecho["texto"][:1000])

print("==============================\n")
   
 try:

        resultado = ia(
            mensagens,
            max_new_tokens=400,
            do_sample=False
        )

        resposta = (
            resultado[0]
            ["generated_text"]
            [-1]
            ["content"]
        )

    except Exception as erro:

        print("ERRO NA IA:", erro)

        return jsonify({
            "erro": "Erro ao gerar resposta."
        }), 500

    # ==========================================
    # SALVAR MENSAGENS
    # ==========================================

    conexao = conectar()

    conexao.execute(
        """
        INSERT INTO mensagens
        (conversa_id, papel, conteudo, criada_em)
        VALUES (?, ?, ?, ?)
        """,
        (
            conversa_id,
            "user",
            pergunta,
            datetime.now().isoformat()
        )
    )

    conexao.execute(
        """
        INSERT INTO mensagens
        (conversa_id, papel, conteudo, criada_em)
        VALUES (?, ?, ?, ?)
        """,
        (
            conversa_id,
            "assistant",
            resposta,
            datetime.now().isoformat()
        )
    )

    conexao.commit()
    conexao.close()

    return jsonify({
        "resposta": resposta
    })

# ==========================================
# UPLOAD DE PDF
# ==========================================

@app.route("/upload", methods=["POST"])
@login_obrigatorio
def upload():

    arquivo = request.files.get("arquivo")

    if not arquivo:

        return jsonify({
            "erro": "Nenhum arquivo enviado."
        }), 400

    nome = secure_filename(arquivo.filename)

    if not nome.lower().endswith(".pdf"):

        return jsonify({
            "erro": "Por enquanto, envie apenas arquivos PDF."
        }), 400

    nome_unico = str(uuid.uuid4()) + "_" + nome

    caminho = os.path.join(
        app.config["UPLOAD_FOLDER"],
        nome_unico
    )

    arquivo.save(caminho)

    try:

        leitor = PdfReader(caminho)

        texto = ""

        for pagina in leitor.pages:

            texto += pagina.extract_text() or ""

    except Exception as erro:

        return jsonify({
            "erro": f"Não foi possível ler o PDF: {erro}"
        }), 500

    conexao = conectar()

    conexao.execute(
        """
        INSERT INTO documentos
        (usuario_id, nome, caminho, texto, enviado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session["usuario_id"],
            nome,
            caminho,
            texto,
            datetime.now().isoformat()
        )
    )

    conexao.commit()
    conexao.close()

    return jsonify({
        "sucesso": True,
        "mensagem": f"PDF '{nome}' enviado e lido com sucesso."
    })


# ==========================================
# PESQUISA NOS DOCUMENTOS
# ==========================================

@app.route("/pesquisar_documentos", methods=["POST"])
@login_obrigatorio
def pesquisar_documentos():

    dados = request.get_json()

    pergunta = dados.get("pergunta", "").strip()

    if not pergunta:

        return jsonify({
            "erro": "Digite algo para pesquisar."
        }), 400

    palavras = pergunta.lower().split()

    conexao = conectar()

    documentos = conexao.execute(
        """
        SELECT nome, texto
        FROM documentos
        WHERE usuario_id = ?
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    resultados = []

    for documento in documentos:

        texto = documento["texto"] or ""
        texto_lower = texto.lower()

        pontos = sum(
            1
            for palavra in palavras
            if len(palavra) > 2 and palavra in texto_lower
        )

        if pontos > 0:

            posicao = texto_lower.find(palavras[0])

            if posicao < 0:
                posicao = 0

            inicio = max(0, posicao - 300)
            fim = min(len(texto), posicao + 1000)

            trecho = texto[inicio:fim]

            resultados.append({
                "nome": documento["nome"],
                "trecho": trecho,
                "pontos": pontos
            })

    resultados.sort(
        key=lambda x: x["pontos"],
        reverse=True
    )

    return jsonify({
        "resultados": resultados[:5]
    })


# ==========================================
# EXECUTAR
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000
    )