import os
import re
import sqlite3
import uuid
import unicodedata

from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from transformers import pipeline
from pypdf import PdfReader


# =========================================================
# CONFIGURAÇÃO
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "chave-temporaria-apenas-para-desenvolvimento"
)

DATABASE = "ia.db"
UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar():

    conexao = sqlite3.connect(DATABASE)

    conexao.row_factory = sqlite3.Row

    return conexao


def criar_banco():

    conexao = conectar()

    # USUÁRIOS
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    # CONVERSAS
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT,
            criada_em TEXT
        )
    """)

    # MENSAGENS
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER NOT NULL,
            papel TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criada_em TEXT
        )
    """)

    # MEMÓRIA
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            informacao TEXT NOT NULL
        )
    """)

    # DOCUMENTOS
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL,
            texto TEXT,
            enviado_em TEXT
        )
    """)

    conexao.commit()

    conexao.close()


criar_banco()


# =========================================================
# IA
# =========================================================

print("Carregando a IA...")

ia = pipeline(
    "text-generation",
    model="Qwen/Qwen2.5-0.5B-Instruct",
    device=-1
)

print("IA carregada!")


# =========================================================
# LOGIN OBRIGATÓRIO
# =========================================================

def login_obrigatorio(funcao):

    @wraps(funcao)
    def verificar(*args, **kwargs):

        if "usuario_id" not in session:

            return jsonify({
                "erro": "Você precisa estar logado."
            }), 401

        return funcao(*args, **kwargs)

    return verificar


# =========================================================
# MEMÓRIA
# =========================================================

def pegar_memoria():

    if "usuario_id" not in session:
        return []

    conexao = conectar()

    memoria = conexao.execute(
        """
        SELECT informacao
        FROM memoria
        WHERE usuario_id = ?
        ORDER BY id DESC
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    return [
        item["informacao"]
        for item in memoria
    ]


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

@app.route("/")
def inicio():

    return render_template("index.html")


# =========================================================
# USUÁRIO
# =========================================================

@app.route("/usuario")
def usuario():

    if "usuario_id" not in session:

        return jsonify({
            "logado": False
        })

    return jsonify({
        "logado": True,
        "usuario": session.get("usuario"),
        "usuario_id": session.get("usuario_id")
    })


# =========================================================
# CADASTRO
# =========================================================

@app.route("/cadastro", methods=["POST"])
def cadastro():

    dados = request.get_json() or {}

    usuario = dados.get(
        "usuario",
        ""
    ).strip()

    senha = dados.get(
        "senha",
        ""
    )

    if not usuario or not senha:

        return jsonify({
            "erro": "Preencha usuário e senha."
        }), 400

    if len(usuario) < 3:

        return jsonify({
            "erro": "O usuário precisa ter pelo menos 3 caracteres."
        }), 400

    if len(senha) < 4:

        return jsonify({
            "erro": "A senha precisa ter pelo menos 4 caracteres."
        }), 400

    conexao = conectar()

    usuario_existente = conexao.execute(
        """
        SELECT id
        FROM usuarios
        WHERE usuario = ?
        """,
        (usuario,)
    ).fetchone()

    if usuario_existente:

        conexao.close()

        return jsonify({
            "erro": "Esse usuário já existe."
        }), 400

    senha_hash = generate_password_hash(senha)

    cursor = conexao.execute(
        """
        INSERT INTO usuarios
        (usuario, senha)
        VALUES (?, ?)
        """,
        (
            usuario,
            senha_hash
        )
    )

    conexao.commit()

    usuario_id = cursor.lastrowid

    conexao.close()

    session["usuario_id"] = usuario_id
    session["usuario"] = usuario

    return jsonify({
        "sucesso": True,
        "mensagem": "Cadastro realizado com sucesso!"
    })


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["POST"])
def login():

    dados = request.get_json() or {}

    usuario = dados.get(
        "usuario",
        ""
    ).strip()

    senha = dados.get(
        "senha",
        ""
    )

    if not usuario or not senha:

        return jsonify({
            "erro": "Preencha usuário e senha."
        }), 400

    conexao = conectar()

    usuario_banco = conexao.execute(
        """
        SELECT *
        FROM usuarios
        WHERE usuario = ?
        """,
        (usuario,)
    ).fetchone()

    conexao.close()

    if not usuario_banco:

        return jsonify({
            "erro": "Usuário ou senha incorretos."
        }), 401

    if not check_password_hash(
        usuario_banco["senha"],
        senha
    ):

        return jsonify({
            "erro": "Usuário ou senha incorretos."
        }), 401

    session["usuario_id"] = usuario_banco["id"]
    session["usuario"] = usuario_banco["usuario"]

    return jsonify({
        "sucesso": True,
        "mensagem": "Login realizado com sucesso!"
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return jsonify({
        "sucesso": True
    })


# =========================================================
# LISTAR CONVERSAS
# =========================================================

@app.route("/conversas")
@login_obrigatorio
def conversas():

    conexao = conectar()

    lista = conexao.execute(
        """
        SELECT id, titulo, criada_em
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
            "titulo": conversa["titulo"],
            "criada_em": conversa["criada_em"]
        }
        for conversa in lista
    ])


# =========================================================
# NOVA CONVERSA
# =========================================================

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
        "sucesso": True,
        "conversa_id": conversa_id
    })


# =========================================================
# ABRIR CONVERSA
# =========================================================

@app.route("/conversa/<int:conversa_id>")
@login_obrigatorio
def abrir_conversa(conversa_id):

    conexao = conectar()

    conversa = conexao.execute(
        """
        SELECT *
        FROM conversas
        WHERE id = ?
        AND usuario_id = ?
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
        SELECT papel, conteudo, criada_em
        FROM mensagens
        WHERE conversa_id = ?
        ORDER BY id ASC
        """,
        (conversa_id,)
    ).fetchall()

    conexao.close()

    session["conversa_id"] = conversa_id

    return jsonify({
        "conversa": {
            "id": conversa["id"],
            "titulo": conversa["titulo"],
            "criada_em": conversa["criada_em"]
        },

        "mensagens": [
            {
                "papel": mensagem["papel"],
                "conteudo": mensagem["conteudo"],
                "criada_em": mensagem["criada_em"]
            }
            for mensagem in mensagens
        ]
    })


# =========================================================
# MEMÓRIA
# =========================================================

@app.route("/memoria")
@login_obrigatorio
def memoria():

    return jsonify({
        "memoria": pegar_memoria()
    })


# =========================================================
# NORMALIZAR TEXTO
# =========================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    texto = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# =========================================================
# PALAVRAS IMPORTANTES
# =========================================================

def palavras_importantes(texto):

    texto = normalizar_texto(texto)

    palavras = texto.split()

    palavras_ignoradas = {
        "qual",
        "quais",
        "como",
        "onde",
        "quando",
        "porque",
        "porquê",
        "para",
        "uma",
        "umas",
        "um",
        "uns",
        "que",
        "quem",
        "sobre",
        "esse",
        "essa",
        "isso",
        "este",
        "esta",
        "isto",
        "dos",
        "das",
        "do",
        "da",
        "de",
        "e",
        "ou",
        "a",
        "o",
        "as",
        "os",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "ao",
        "aos",
        "me",
        "se",
        "tem",
        "ter",
        "pdf",
        "documento",
        "principal",
        "assunto",
        "tema"
    }

    resultado = []

    for palavra in palavras:

        if len(palavra) < 3:
            continue

        if palavra in palavras_ignoradas:
            continue

        if palavra not in resultado:

            resultado.append(
                palavra
            )

    return resultado


# =========================================================
# IDENTIFICAR NOME DO PDF NA PERGUNTA
# =========================================================

def encontrar_documento_mencionado(
    pergunta,
    documentos
):

    pergunta_normalizada = normalizar_texto(
        pergunta
    )

    melhor_documento = None

    maior_pontuacao = 0

    for documento in documentos:

        nome = documento["nome"]

        nome_normalizado = normalizar_texto(
            nome
        )

        nome_sem_pdf = nome_normalizado.replace(
            " pdf",
            ""
        )

        pontos = 0

        if nome_normalizado in pergunta_normalizada:

            pontos += 100

        if nome_sem_pdf in pergunta_normalizada:

            pontos += 80

        partes = nome_sem_pdf.split()

        for parte in partes:

            if len(parte) >= 4 and parte in pergunta_normalizada:

                pontos += 5

        if pontos > maior_pontuacao:

            maior_pontuacao = pontos

            melhor_documento = documento

    return melhor_documento


# =========================================================
# IDENTIFICAR TIPO DE PERGUNTA SOBRE PDF
# =========================================================

def identificar_tipo_pergunta(pergunta):

    texto = normalizar_texto(
        pergunta
    )

    tipos = {
        "titulo": False,
        "assunto": False,
        "objetivo": False,
        "resumo": False,
        "primeiro_paragrafo": False
    }

    if (
        "titulo" in texto
        or "nome do pdf" in texto
    ):
        tipos["titulo"] = True

    if (
        "assunto" in texto
        or "tema principal" in texto
        or "tema" in texto
        or "sobre o que" in texto
        or "fala sobre" in texto
    ):
        tipos["assunto"] = True

    if (
        "objetivo" in texto
        or "finalidade" in texto
        or "objetivos" in texto
    ):
        tipos["objetivo"] = True

    if (
        "resuma" in texto
        or "resumo" in texto
        or "resumir" in texto
    ):
        tipos["resumo"] = True

    if (
        "primeiro paragrafo" in texto
        or "primeiro parágrafo" in pergunta.lower()
    ):
        tipos["primeiro_paragrafo"] = True

    return tipos


# =========================================================
# CRIAR TRECHOS
# =========================================================

def criar_trechos(texto):

    trechos = []

    if not texto:
        return trechos

    # Primeiro trecho:
    # extremamente importante para título,
    # introdução e objetivo.
    inicio_importante = texto[:3000]

    trechos.append({
        "texto": inicio_importante,
        "tipo": "inicio",
        "pontos": 0
    })

    # Trechos menores para busca específica
    tamanho = 1200
    sobreposicao = 200

    inicio = 0

    while inicio < len(texto):

        fim = min(
            inicio + tamanho,
            len(texto)
        )

        trecho = texto[
            inicio:fim
        ]

        trechos.append({
            "texto": trecho,
            "tipo": "normal",
            "pontos": 0
        })

        if fim >= len(texto):
            break

        inicio = fim - sobreposicao

    return trechos


# =========================================================
# BUSCA INTELIGENTE NO PDF
# =========================================================

def buscar_trechos_pdf(
    pergunta,
    documentos
):

    tipo = identificar_tipo_pergunta(
        pergunta
    )

    documento_mencionado = (
        encontrar_documento_mencionado(
            pergunta,
            documentos
        )
    )

    documentos_para_busca = []

    if documento_mencionado:

        documentos_para_busca.append(
            documento_mencionado
        )

    else:

        documentos_para_busca = documentos


    palavras = palavras_importantes(
        pergunta
    )

    trechos = []

    for documento in documentos_para_busca:

        nome = documento["nome"]

        texto = documento["texto"] or ""

        if not texto.strip():
            continue

        partes = criar_trechos(
            texto
        )

        for parte in partes:

            trecho = parte["texto"]

            trecho_normalizado = normalizar_texto(
                trecho
            )

            pontos = 0

            palavras_encontradas = 0


            # -----------------------------------------
            # BUSCA POR PALAVRAS
            # -----------------------------------------

            for palavra in palavras:

                quantidade = (
                    trecho_normalizado.count(
                        palavra
                    )
                )

                if quantidade > 0:

                    palavras_encontradas += 1

                    pontos += min(
                        quantidade * 2,
                        8
                    )


            # -----------------------------------------
            # BÔNUS PARA O INÍCIO DO PDF
            # -----------------------------------------

            if parte["tipo"] == "inicio":

                if (
                    tipo["assunto"]
                    or tipo["titulo"]
                    or tipo["objetivo"]
                    or tipo["resumo"]
                    or tipo["primeiro_paragrafo"]
                ):

                    pontos += 30


            # -----------------------------------------
            # BÔNUS PARA DOCUMENTO MENCIONADO
            # -----------------------------------------

            if documento_mencionado:

                pontos += 50


            # -----------------------------------------
            # BÔNUS PARA PALAVRAS DE TÍTULO
            # -----------------------------------------

            primeiras_linhas = "\n".join(
                trecho.splitlines()[:12]
            )

            primeiras_linhas_normalizadas = (
                normalizar_texto(
                    primeiras_linhas
                )
            )

            if tipo["titulo"]:

                pontos += 20

            if tipo["assunto"]:

                palavras_assunto = [
                    "analise",
                    "analise e desenvolvimento",
                    "modelo",
                    "machine learning",
                    "previsao",
                    "precos",
                    "economicos",
                    "economica",
                    "pesquisa",
                    "estudo"
                ]

                for palavra in palavras_assunto:

                    if palavra in primeiras_linhas_normalizadas:

                        pontos += 8


            # -----------------------------------------
            # ADICIONAR TRECHO
            # -----------------------------------------

            if pontos > 0:

                trechos.append({
                    "nome": nome,
                    "texto": trecho,
                    "pontos": pontos,
                    "palavras": palavras_encontradas,
                    "tipo": parte["tipo"]
                })


    # =====================================================
    # ORDENAR
    # =====================================================

    trechos.sort(
        key=lambda item: (
            item["pontos"],
            item["palavras"]
        ),
        reverse=True
    )


    # =====================================================
    # EVITAR TRECHOS REPETIDOS
    # =====================================================

    selecionados = []

    textos_usados = set()

    for trecho in trechos:

        chave = trecho["texto"][:150]

        if chave in textos_usados:
            continue

        textos_usados.add(
            chave
        )

        selecionados.append(
            trecho
        )

        if len(selecionados) >= 3:
            break


    return selecionados


# =========================================================
# MONTAR CONTEXTO DO PDF
# =========================================================

def montar_contexto_pdf(trechos):

    if not trechos:

        return """
NENHUM TRECHO RELEVANTE FOI ENCONTRADO.

Não invente informações.
"""


    contexto = (
        "\n===== INFORMAÇÕES EXTRAÍDAS DO PDF =====\n"
    )

    for numero, trecho in enumerate(
        trechos,
        start=1
    ):

        contexto += (
            "\nTRECHO "
            + str(numero)
            + " | DOCUMENTO: "
            + trecho["nome"]
            + "\n"
            + trecho["texto"]
            + "\n"
        )

    contexto += (
        "\n===== FIM DAS INFORMAÇÕES =====\n"
    )

    return contexto


# =========================================================
# PERGUNTAR
# =========================================================

@app.route(
    "/perguntar",
    methods=["POST"]
)
@login_obrigatorio
def perguntar():

    dados = request.get_json() or {}

    pergunta = dados.get(
        "pergunta",
        ""
    ).strip()

    if not pergunta:

        return jsonify({
            "erro": "Digite uma pergunta."
        }), 400


    # =====================================================
    # IDENTIFICAR TIPO DA PERGUNTA
    # =====================================================

    tipo = identificar_tipo_pergunta(
        pergunta
    )

    pergunta_sobre_pdf = (
        tipo["titulo"]
        or tipo["assunto"]
        or tipo["objetivo"]
        or tipo["resumo"]
        or tipo["primeiro_paragrafo"]
        or "pdf" in normalizar_texto(pergunta)
        or "documento" in normalizar_texto(pergunta)
    )


    # =====================================================
    # CONVERSA
    # =====================================================

    conversa_id = session.get(
        "conversa_id"
    )

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


    # =====================================================
    # PEGAR DOCUMENTOS
    # =====================================================

    conexao = conectar()

    documentos = conexao.execute(
        """
        SELECT nome, texto
        FROM documentos
        WHERE usuario_id = ?
        """,
        (session["usuario_id"],)
    ).fetchall()


    # =====================================================
    # HISTÓRICO
    # =====================================================

    historico = []

    # Para perguntas sobre PDF, NÃO usamos o histórico.
    # Isso impede uma resposta errada anterior
    # de contaminar a resposta atual.

    if not pergunta_sobre_pdf:

        historico = conexao.execute(
            """
            SELECT papel, conteudo
            FROM mensagens
            WHERE conversa_id = ?
            ORDER BY id DESC
            LIMIT 4
            """,
            (conversa_id,)
        ).fetchall()

        historico = list(
            reversed(historico)
        )


    conexao.close()


    # =====================================================
    # BUSCAR PDF
    # =====================================================

    trechos = buscar_trechos_pdf(
        pergunta,
        documentos
    )


    # =====================================================
    # CONTEXTO PDF
    # =====================================================

    contexto_pdf = montar_contexto_pdf(
        trechos
    )


    # =====================================================
    # MEMÓRIA
    # =====================================================

    memoria_usuario = pegar_memoria()

    contexto_memoria = ""

    if memoria_usuario and not pergunta_sobre_pdf:

        contexto_memoria = (
            "\n\nMEMÓRIA DO USUÁRIO:\n"
            + "\n".join(
                "- " + item
                for item in memoria_usuario
            )
        )


    # =====================================================
    # INSTRUÇÕES ESPECÍFICAS
    # =====================================================

    if tipo["titulo"]:

        instrucao = """
O usuário quer saber o TÍTULO do documento.

Use somente o texto fornecido.

Procure o título nas primeiras linhas.

Responda somente com o título encontrado,
sem inventar outro.
"""


    elif tipo["assunto"]:

        instrucao = """
O usuário quer saber o ASSUNTO PRINCIPAL do documento.

Use principalmente o início do documento,
incluindo título, introdução e objetivo.

Identifique o tema central.

Não invente temas.

Não use conhecimento externo.

Responda em no máximo 2 frases.

Se o título deixar o assunto evidente,
use-o como base da resposta.
"""


    elif tipo["objetivo"]:

        instrucao = """
O usuário quer saber o OBJETIVO do documento.

Procure no início do documento e nos trechos
fornecidos expressões como objetivo, finalidade,
propósito, analisar, desenvolver, estudar ou investigar.

Responda somente com informações presentes
no documento.

Não invente.
"""


    elif tipo["primeiro_paragrafo"]:

        instrucao = """
O usuário quer o PRIMEIRO PARÁGRAFO do documento.

Use o começo do documento.

Resuma ou reproduza apenas o conteúdo
presente no primeiro parágrafo.

Não invente.
"""


    elif tipo["resumo"]:

        instrucao = """
O usuário quer um RESUMO do documento.

Use somente os trechos encontrados.

Faça um resumo curto e objetivo.

Não invente informações que não aparecem
no documento.
"""


    elif pergunta_sobre_pdf:

        instrucao = """
A pergunta é sobre um PDF.

Use somente as informações extraídas
do PDF fornecidas abaixo.

Não use conhecimento externo para completar
lacunas.

Se a informação não estiver disponível,
diga:

"Não encontrei essa informação nos PDFs disponíveis."

Não invente nomes, números, datas ou fatos.
"""


    else:

        instrucao = """
Responda normalmente em português do Brasil.

Use o histórico da conversa quando necessário.

Seja objetivo e claro.

Não invente informações.
"""


    # =====================================================
    # SISTEMA
    # =====================================================

    sistema = f"""
Você é uma inteligência artificial brasileira,
educativa, precisa e objetiva.

{instrucao}

IMPORTANTE:

As informações entre as marcações
"INFORMAÇÕES EXTRAÍDAS DO PDF"
são a fonte principal para perguntas sobre PDFs.

===== INFORMAÇÕES EXTRAÍDAS DO PDF =====

{contexto_pdf}

===== FIM DAS INFORMAÇÕES =====
"""


    # =====================================================
    # MENSAGENS PARA A IA
    # =====================================================

    mensagens = [
        {
            "role": "system",
            "content": (
                sistema
                + contexto_memoria
            )
        }
    ]


    # =====================================================
    # HISTÓRICO
    # =====================================================

    for mensagem in historico:

        mensagens.append({
            "role": mensagem["papel"],
            "content": mensagem["conteudo"]
        })


    # =====================================================
    # PERGUNTA
    # =====================================================

    mensagens.append({
        "role": "user",
        "content": pergunta
    })


    # =====================================================
    # DEBUG
    # =====================================================

    print(
        "\n=============================="
    )

    print(
        "PERGUNTA:"
    )

    print(
        pergunta
    )

    print(
        "\nTIPOS:"
    )

    print(
        tipo
    )

    print(
        "\nPDF MENCIONADO:"
    )

    documento_mencionado = (
        encontrar_documento_mencionado(
            pergunta,
            documentos
        )
    )

    if documento_mencionado:

        print(
            documento_mencionado["nome"]
        )

    else:

        print(
            "Nenhum documento específico"
        )

    print(
        "\nTRECHOS ENCONTRADOS:"
    )

    for trecho in trechos:

        print(
            "\n---",
            trecho["nome"],
            "---"
        )

        print(
            "Pontos:",
            trecho["pontos"]
        )

        print(
            "Tipo:",
            trecho["tipo"]
        )

        print(
            trecho["texto"][:700]
        )

    print(
        "==============================\n"
    )


    # =====================================================
    # GERAR RESPOSTA
    # =====================================================

    try:

        resultado = ia(
            mensagens,
            max_new_tokens=140,
            do_sample=False
        )

        resposta = (
            resultado[0]
            ["generated_text"]
            [-1]
            ["content"]
        ).strip()

    except Exception as erro:

        print(
            "ERRO NA IA:",
            erro
        )

        return jsonify({
            "erro": "Erro ao gerar resposta."
        }), 500


    # =====================================================
    # SALVAR MENSAGENS
    # =====================================================

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


    # =====================================================
    # RETORNO
    # =====================================================

    return jsonify({
        "resposta": resposta
    })


# =========================================================
# UPLOAD DE PDF
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
@login_obrigatorio
def upload():

    arquivo = request.files.get(
        "arquivo"
    )

    if not arquivo:

        return jsonify({
            "erro": "Nenhum arquivo enviado."
        }), 400


    nome = secure_filename(
        arquivo.filename
    )

    if not nome.lower().endswith(
        ".pdf"
    ):

        return jsonify({
            "erro": "Por enquanto, envie apenas arquivos PDF."
        }), 400


    nome_unico = (
        str(uuid.uuid4())
        + "_"
        + nome
    )

    caminho = os.path.join(
        app.config["UPLOAD_FOLDER"],
        nome_unico
    )

    arquivo.save(
        caminho
    )


    # =====================================================
    # LER PDF
    # =====================================================

    try:

        leitor = PdfReader(
            caminho
        )

        texto = ""

        for pagina in leitor.pages:

            texto += (
                pagina.extract_text()
                or ""
            )

            texto += "\n"


    except Exception as erro:

        return jsonify({
            "erro": (
                "Não foi possível ler o PDF: "
                + str(erro)
            )
        }), 500


    # =====================================================
    # VERIFICAR SE O PDF TEM TEXTO
    # =====================================================

    if not texto.strip():

        return jsonify({
            "erro": (
                "Não foi possível encontrar texto "
                "nesse PDF. Ele pode ser um PDF "
                "formado apenas por imagens."
            )
        }), 400


    # =====================================================
    # SALVAR DOCUMENTO
    # =====================================================

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


    print(
        "\nPDF ENVIADO:"
    )

    print(
        nome
    )

    print(
        "Caracteres extraídos:",
        len(texto)
    )


    return jsonify({
        "sucesso": True,
        "mensagem": (
            f"PDF '{nome}' enviado e lido com sucesso."
        )
    })


# =========================================================
# PESQUISAR DOCUMENTOS
# =========================================================

@app.route(
    "/pesquisar_documentos",
    methods=["POST"]
)
@login_obrigatorio
def pesquisar_documentos():

    dados = request.get_json() or {}

    pesquisa = dados.get(
        "pesquisa",
        ""
    ).strip().lower()

    if not pesquisa:

        return jsonify({
            "resultados": []
        })


    conexao = conectar()

    documentos = conexao.execute(
        """
        SELECT id, nome, texto
        FROM documentos
        WHERE usuario_id = ?
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()


    resultados = []

    pesquisa_normalizada = normalizar_texto(
        pesquisa
    )

    for documento in documentos:

        texto = documento["texto"] or ""

        texto_normalizado = normalizar_texto(
            texto
        )

        if pesquisa_normalizada in texto_normalizado:

            resultados.append({
                "id": documento["id"],
                "nome": documento["nome"]
            })


    return jsonify({
        "resultados": resultados
    })


# =========================================================
# INICIAR SERVIDOR
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )