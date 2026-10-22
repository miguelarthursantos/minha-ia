
import os
import re
import sqlite3
import uuid
import unicodedata
import hashlib
import threading
from collections import OrderedDict

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
# CACHE DE CONSULTAS
# =========================================================

CACHE_MAXIMO = 128
CACHE_TTL = 600

_cache_consultas = OrderedDict()
_cache_lock = threading.Lock()


def _cache_chave(pergunta, documentos):

    partes = [
        normalizar_texto(pergunta)
    ]

    for documento in documentos:

        try:
            identificador = str(documento["id"])
        except (KeyError, IndexError):
            identificador = str(documento["nome"])

        texto = documento["texto"] or ""

        assinatura = hashlib.sha256(
            texto.encode("utf-8", errors="ignore")
        ).hexdigest()[:16]

        partes.append(
            identificador + ":" + assinatura
        )

    return "|".join(partes)


def limpar_cache_consultas():

    with _cache_lock:
        _cache_consultas.clear()

    print("CACHE DE CONSULTAS LIMPO.", flush=True)


def buscar_cache_consulta(chave):

    agora = datetime.now().timestamp()

    with _cache_lock:

        item = _cache_consultas.get(chave)

        if item is None:
            return None

        criado_em, valor = item

        if agora - criado_em > CACHE_TTL:

            _cache_consultas.pop(chave, None)
            return None

        _cache_consultas.move_to_end(chave)

        return [dict(trecho) for trecho in valor]


def salvar_cache_consulta(chave, valor):

    agora = datetime.now().timestamp()

    with _cache_lock:

        _cache_consultas[chave] = (
            agora,
            [dict(trecho) for trecho in valor]
        )

        _cache_consultas.move_to_end(chave)

        while len(_cache_consultas) > CACHE_MAXIMO:
            _cache_consultas.popitem(last=False)



# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar():

    conexao = sqlite3.connect(DATABASE)

    conexao.row_factory = sqlite3.Row

    return conexao


def criar_banco():

    conexao = conectar()

    # -----------------------------------------------------
    # USUÁRIOS
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    colunas_usuarios = conexao.execute(
        "PRAGMA table_info(usuarios)"
    ).fetchall()

    nomes_colunas_usuarios = {
        coluna["name"] for coluna in colunas_usuarios
    }

    if "email" not in nomes_colunas_usuarios:
        conexao.execute("ALTER TABLE usuarios ADD COLUMN email TEXT")


    # -----------------------------------------------------
    # PROJETOS
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            descricao TEXT,
            icone TEXT,
            criada_em TEXT,
            atualizada_em TEXT
        )
    """)

    # -----------------------------------------------------
    # SITES CRIADOS PELO USUÁRIO
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            prompt TEXT,
            html TEXT,
            css TEXT,
            js TEXT,
            criada_em TEXT,
            atualizada_em TEXT
        )
    """)

    # -----------------------------------------------------
    # CONVERSAS
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT,
            criada_em TEXT
        )
    """)


    # -----------------------------------------------------
    # MIGRAÇÃO:
    # ADICIONAR PROJETO ÀS CONVERSAS
    # -----------------------------------------------------

    colunas_conversas = conexao.execute(
        "PRAGMA table_info(conversas)"
    ).fetchall()

    nomes_colunas_conversas = {
        coluna["name"]
        for coluna in colunas_conversas
    }

    if "projeto_id" not in nomes_colunas_conversas:

        conexao.execute("""
            ALTER TABLE conversas
            ADD COLUMN projeto_id INTEGER
        """)


    # -----------------------------------------------------
    # MENSAGENS
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversa_id INTEGER NOT NULL,
            papel TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criada_em TEXT
        )
    """)


    # -----------------------------------------------------
    # MEMÓRIA
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS memoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            informacao TEXT NOT NULL
        )
    """)


    # -----------------------------------------------------
    # DOCUMENTOS
    # -----------------------------------------------------

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL,
            texto TEXT,
            enviado_em TEXT,
            projeto_id INTEGER
        )
    """)


    # -----------------------------------------------------
    # MIGRAÇÃO:
    # ADICIONAR PROJETO AOS DOCUMENTOS
    # -----------------------------------------------------

    colunas_documentos = conexao.execute(
        "PRAGMA table_info(documentos)"
    ).fetchall()

    nomes_colunas_documentos = {
        coluna["name"]
        for coluna in colunas_documentos
    }

    if "projeto_id" not in nomes_colunas_documentos:

        conexao.execute("""
            ALTER TABLE documentos
            ADD COLUMN projeto_id INTEGER
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

# O modelo pode trazer max_length=20 no generation_config.
# Usamos somente max_new_tokens para evitar conflito e respostas truncadas.
try:
    ia.model.generation_config.max_length = None
except Exception:
    pass


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
# MEMÓRIA INTELIGENTE
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


def adicionar_memoria(informacao):

    if "usuario_id" not in session:
        return False

    informacao = str(informacao).strip()

    if not informacao:
        return False

    if len(informacao) > 500:
        informacao = informacao[:500].strip()

    conexao = conectar()

    memorias = conexao.execute(
        """
        SELECT informacao
        FROM memoria
        WHERE usuario_id = ?
        """,
        (session["usuario_id"],)
    ).fetchall()

    informacao_normalizada = normalizar_texto(informacao)

    for memoria in memorias:

        if normalizar_texto(memoria["informacao"]) == informacao_normalizada:

            conexao.close()
            return False

    conexao.execute(
        """
        INSERT INTO memoria
        (usuario_id, informacao)
        VALUES (?, ?)
        """,
        (session["usuario_id"], informacao)
    )

    conexao.commit()
    conexao.close()

    return True


def encontrar_memoria_por_texto(texto):

    if "usuario_id" not in session:
        return []

    palavras = palavras_importantes(texto)

    if not palavras:
        return []

    conexao = conectar()

    memorias = conexao.execute(
        """
        SELECT id, informacao
        FROM memoria
        WHERE usuario_id = ?
        ORDER BY id DESC
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    resultados = []

    for memoria in memorias:

        memoria_normalizada = normalizar_texto(memoria["informacao"])
        pontos = 0

        for palavra in palavras:
            if palavra in memoria_normalizada:
                pontos += 1

        if pontos > 0:
            resultados.append({
                "id": memoria["id"],
                "informacao": memoria["informacao"],
                "pontos": pontos
            })

    resultados.sort(
        key=lambda item: item["pontos"],
        reverse=True
    )

    return resultados


def apagar_memoria_por_texto(texto):

    if "usuario_id" not in session:
        return []

    resultados = encontrar_memoria_por_texto(texto)

    if not resultados:
        return []

    maior_pontuacao = resultados[0]["pontos"]

    selecionadas = [
        item for item in resultados
        if item["pontos"] == maior_pontuacao
    ]

    conexao = conectar()

    for memoria in selecionadas:
        conexao.execute(
            """
            DELETE FROM memoria
            WHERE id = ?
            AND usuario_id = ?
            """,
            (memoria["id"], session["usuario_id"])
        )

    conexao.commit()
    conexao.close()

    return [
        item["informacao"]
        for item in selecionadas
    ]


def identificar_comando_memoria(pergunta):

    texto = pergunta.strip()
    texto_normalizado = normalizar_texto(texto)

    comandos_salvar = [
        "lembre que",
        "lembra que",
        "memorize que",
        "guarde que",
        "guarda que",
        "anote que",
        "anota que"
    ]

    for comando in comandos_salvar:

        comando_normalizado = normalizar_texto(comando)

        if texto_normalizado.startswith(comando_normalizado):

            informacao = texto[len(comando):].strip()

            if informacao:
                return {
                    "tipo": "salvar",
                    "informacao": informacao
                }

    comandos_apagar = [
        "esqueça que",
        "esquece que",
        "apague a memória sobre",
        "apaga a memória sobre",
        "delete a memória sobre",
        "deleta a memória sobre",
        "esqueça",
        "esquece"
    ]

    for comando in comandos_apagar:

        comando_normalizado = normalizar_texto(comando)

        if texto_normalizado.startswith(comando_normalizado):

            informacao = texto[len(comando):].strip()

            if informacao:
                return {
                    "tipo": "apagar",
                    "informacao": informacao
                }

    perguntas_memoria = [
        "o que voce lembra de mim",
        "o que voce sabe sobre mim",
        "o que voce lembra sobre mim",
        "quais sao minhas memorias",
        "quais sao as minhas memorias",
        "mostre minhas memorias",
        "mostra minhas memorias",
        "liste minhas memorias",
        "lista minhas memorias",
        "o que esta salvo sobre mim"
    ]

    for pergunta_memoria in perguntas_memoria:

        if texto_normalizado == pergunta_memoria:
            return {"tipo": "listar"}

    return {"tipo": None}



def extrair_memorias_automaticas(texto):

    """
    Identifica frases simples que representam informações
    pessoais úteis e explícitas fornecidas pelo usuário.

    A função é propositalmente conservadora: ela não tenta
    interpretar qualquer frase como memória.
    """

    import re

    texto_original = str(texto).strip()
    texto_normalizado = normalizar_texto(texto_original)

    if not texto_original:
        return []

    # Não salvar comandos explícitos aqui. Eles já são tratados
    # separadamente por identificar_comando_memoria().
    if identificar_comando_memoria(texto_original)["tipo"]:
        return []

    padroes = [
        # Nome
        r"\bmeu nome é (.+?)(?:[.!?]|$)",
        r"\beu me chamo (.+?)(?:[.!?]|$)",
        r"\bmeu nome e (.+?)(?:[.!?]|$)",

        # Idade
        r"\beu tenho (\d{1,3}) anos(?:[.!?]|$)",
        r"\btenho (\d{1,3}) anos(?:[.!?]|$)",

        # Estudos / escola
        r"\beu estudo no (.+?)(?:[.!?]|$)",
        r"\beu estudo na (.+?)(?:[.!?]|$)",
        r"\bestudo no (.+?)(?:[.!?]|$)",
        r"\bestudo na (.+?)(?:[.!?]|$)",
        r"\bestou estudando (?!para )(.+?)(?:[.!?]|$)",
        r"\bestou estudando para (.+?)(?:[.!?]|$)",

        # Objetivos
        r"\bmeu objetivo é (.+?)(?:[.!?]|$)",
        r"\bmeu objetivo e (.+?)(?:[.!?]|$)",
        r"\bmeu objetivo é aprender (.+?)(?:[.!?]|$)",
        r"\bmeu objetivo e aprender (.+?)(?:[.!?]|$)",

        # Preferências
        r"\beu gosto de (.+?)(?:[.!?]|$)",
        r"\beu gosto muito de (.+?)(?:[.!?]|$)",
        r"\beu prefiro (.+?)(?:[.!?]|$)",
        r"\beu não gosto de (.+?)(?:[.!?]|$)",
        r"\beu nao gosto de (.+?)(?:[.!?]|$)",
    ]

    memorias = []

    # Nome
    for padrao in padroes[:3]:
        resultado = re.search(padrao, texto_original, flags=re.IGNORECASE)
        if resultado:
            nome = resultado.group(1).strip()
            if 1 <= len(nome) <= 100:
                memorias.append("O nome do usuário é " + nome)
                break

    # Idade
    for padrao in padroes[3:5]:
        resultado = re.search(padrao, texto_normalizado, flags=re.IGNORECASE)
        if resultado:
            idade = resultado.group(1).strip()
            memorias.append("O usuário tem " + idade + " anos")
            break

    # Estudos
    for padrao in padroes[5:11]:
        resultado = re.search(padrao, texto_original, flags=re.IGNORECASE)
        if resultado:
            assunto = resultado.group(1).strip()
            if 2 <= len(assunto) <= 180:
                prefixo = "O usuário está estudando "
                if "para" in padrao:
                    prefixo = "O usuário está estudando para "
                elif "estudo no" in padrao.lower() or "estudo na" in padrao.lower():
                    prefixo = "O usuário estuda em "
                memorias.append(prefixo + assunto)
                break

    # Objetivo
    for padrao in padroes[11:15]:
        resultado = re.search(padrao, texto_original, flags=re.IGNORECASE)
        if resultado:
            objetivo = resultado.group(1).strip()
            if 2 <= len(objetivo) <= 180:
                memorias.append("O objetivo do usuário é " + objetivo)
                break

    # Preferências
    for padrao in padroes[15:20]:
        resultado = re.search(padrao, texto_original, flags=re.IGNORECASE)
        if resultado:
            preferencia = resultado.group(1).strip()
            if 2 <= len(preferencia) <= 180:
                frase = padrao.lower()
                if "não gosto" in frase or "nao gosto" in frase:
                    memorias.append("O usuário não gosta de " + preferencia)
                elif "prefiro" in frase:
                    memorias.append("O usuário prefere " + preferencia)
                else:
                    memorias.append("O usuário gosta de " + preferencia)
                break

    # Evita duplicações caso mais de um padrão gere a mesma informação.
    resultado_final = []
    vistos = set()

    for memoria in memorias:
        chave = normalizar_texto(memoria)
        if chave not in vistos:
            vistos.add(chave)
            resultado_final.append(memoria)

    return resultado_final

def formatar_memorias():

    memorias = pegar_memoria()

    if not memorias:
        return "Ainda não tenho nenhuma memória salva sobre você."

    resposta = (
        "Estas são as informações que tenho salvas sobre você:\n\n"
    )

    for numero, memoria in enumerate(memorias, start=1):
        resposta += f"{numero}. {memoria}\n"

    return resposta.strip()


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
# PROJETOS
# =========================================================

@app.route(
    "/projetos",
    methods=["GET"]
)
@login_obrigatorio
def listar_projetos():

    conexao = conectar()

    projetos = conexao.execute(
        """
        SELECT
            id,
            nome,
            descricao,
            icone,
            criada_em,
            atualizada_em
        FROM projetos
        WHERE usuario_id = ?
        ORDER BY id DESC
        """,
        (session["usuario_id"],)
    ).fetchall()

    conexao.close()

    return jsonify([
        {
            "id": projeto["id"],
            "nome": projeto["nome"],
            "descricao": projeto["descricao"],
            "icone": projeto["icone"],
            "criada_em": projeto["criada_em"],
            "atualizada_em": projeto["atualizada_em"]
        }
        for projeto in projetos
    ])

# =========================================================
# CRIADOR DE SITES — CRIAR SITE
# =========================================================

@app.route("/sites", methods=["POST"])
@login_obrigatorio
def criar_site():

    print(">>> ROTA /sites FOI ALCANÇADA <<<", flush=True)

    dados = request.get_json() or {}

    nome = str(
        dados.get(
            "nome",
            ""
        )
    ).strip()

    prompt = str(
        dados.get(
            "prompt",
            ""
        )
    ).strip()

    if not nome:
        nome = "Novo Site"

    if not prompt:

        return jsonify({
            "sucesso": False,
            "erro": "Descreva o site que deseja criar."
        }), 400

    # -----------------------------------------------------
    # INSTRUÇÃO PARA A IA
    # -----------------------------------------------------

    instrucao = f"""
Você é um gerador profissional de páginas HTML.

Sua única tarefa é criar UM SITE COMPLETO em HTML.

DESCRIÇÃO DO USUÁRIO:
{prompt}

REGRAS ABSOLUTAMENTE OBRIGATÓRIAS:

1. Responda SOMENTE com código HTML.
2. A primeira coisa da resposta deve ser:
<!DOCTYPE html>
3. Gere um documento HTML completo.
4. O documento deve conter <html>, <head> e <body>.
5. Todo o CSS deve ficar dentro de uma tag <style>.
6. Todo o JavaScript necessário deve ficar dentro de uma tag <script>.
7. NÃO crie arquivos separados.
8. NÃO gere Python.
9. NÃO gere Flask.
10. NÃO use @app.route.
11. NÃO use def.
12. NÃO use return como código Python.
13. NÃO escreva código de servidor.
14. NÃO escreva explicações.
15. NÃO use Markdown.
16. NÃO use blocos de código com ```html, ```python, ```css ou ```javascript.
17. O resultado precisa funcionar quando for salvo como arquivo .html e aberto diretamente no navegador.
18. Crie um design moderno e responsivo.
19. Coloque todos os elementos necessários dentro do próprio HTML.
20. Use JavaScript somente quando for necessário para alguma interação.
21. Não invente informações reais de empresas, pessoas, endereços, telefones ou preços.
22. Se alguma informação não for fornecida, utilize informações genéricas.

ENTREGUE SOMENTE O DOCUMENTO HTML COMPLETO.
"""

    # -----------------------------------------------------
    # GERAR HTML COMPLETO
    # -----------------------------------------------------

    try:

        resultado = ia(
            instrucao,
            max_new_tokens=2500,
            do_sample=True,
            temperature=0.7,
            return_full_text=False
        )

        html = str(
            resultado[0]["generated_text"]
        ).strip()

    except Exception as erro:

        print(
            "ERRO AO GERAR SITE:",
            erro,
            flush=True
        )

        return jsonify({
            "sucesso": False,
            "erro": "Não foi possível gerar o site com a IA."
        }), 500

    # -----------------------------------------------------
    # LIMPAR POSSÍVEL MARKDOWN
    # -----------------------------------------------------

    if "```html" in html.lower():

        inicio = html.lower().find(
            "```html"
        )

        html = html[
            inicio + len("```html"):
        ].strip()

        if "```" in html:

            html = html.split(
                "```",
                1
            )[0].strip()

    elif html.startswith("```"):

        html = html[
            3:
        ].strip()

        if html.endswith("```"):

            html = html[
                :-3
            ].strip()

    # -----------------------------------------------------
    # REMOVER TEXTO ANTES DO DOCTYPE OU HTML
    # -----------------------------------------------------

    html_normalizado = html.lower()

    posicao_doctype = html_normalizado.find(
        "<!doctype"
    )

    if posicao_doctype > 0:

        html = html[
            posicao_doctype:
        ].strip()

    else:

        posicao_html = html_normalizado.find(
            "<html"
        )

        if posicao_html > 0:

            html = html[
                posicao_html:
            ].strip()

    # -----------------------------------------------------
    # GARANTIR DOCTYPE
    # -----------------------------------------------------

    html_normalizado = html.lower()

    if "<!doctype html" not in html_normalizado and "<html" in html_normalizado:

        html = "<!DOCTYPE html>\n" + html
        html_normalizado = html.lower()

    # -----------------------------------------------------
    # VERIFICAÇÃO BÁSICA
    # -----------------------------------------------------

    if (
        "<!doctype html" not in html_normalizado
        or "<html" not in html_normalizado
        or "<body" not in html_normalizado
    ):

        print(
            "HTML GERADO PELA IA:",
            html,
            flush=True
        )

        return jsonify({
            "sucesso": False,
            "erro": (
                "A IA não conseguiu gerar "
                "um HTML completo e válido."
            )
        }), 500

    # -----------------------------------------------------
    # SALVAR SITE
    # -----------------------------------------------------

    conexao = conectar()

    agora = datetime.now().isoformat()

    cursor = conexao.execute(
        """
        INSERT INTO sites (
            usuario_id,
            nome,
            prompt,
            html,
            css,
            js,
            criada_em,
            atualizada_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["usuario_id"],
            nome,
            prompt,
            html,
            "",
            "",
            agora,
            agora
        )
    )

    site_id = cursor.lastrowid

    conexao.commit()
    conexao.close()

    # -----------------------------------------------------
    # RETORNAR SITE
    # -----------------------------------------------------

    return jsonify({
        "sucesso": True,
        "id": site_id,
        "nome": nome,
        "html": html,
        "css": "",
        "js": ""
    })

# =========================================================
# VISUALIZAR SITE CRIADO
# =========================================================

@app.route("/site/<int:site_id>")
@login_obrigatorio
def visualizar_site(site_id):

    conexao = conectar()

    site = conexao.execute(
        """
        SELECT *
        FROM sites
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            site_id,
            session["usuario_id"]
        )
    ).fetchone()

    conexao.close()

    if not site:

        return "Site não encontrado.", 404

    return render_template(
        "site_visualizacao.html",
        site=site
    )


# =========================================================
# CRIAR PROJETO
# =========================================================

@app.route(
    "/projetos",
    methods=["POST"]
)
@login_obrigatorio
def criar_projeto():

    dados = request.get_json() or {}

    nome = str(
        dados.get(
            "nome",
            ""
        )
    ).strip()

    descricao = str(
        dados.get(
            "descricao",
            ""
        )
    ).strip()

    icone = str(
        dados.get(
            "icone",
            "📁"
        )
    ).strip()

    if not nome:

        return jsonify({
            "erro": "Digite um nome para o projeto."
        }), 400

    if len(nome) > 100:

        return jsonify({
            "erro": "O nome do projeto é muito grande."
        }), 400

    if len(descricao) > 500:

        return jsonify({
            "erro": "A descrição do projeto é muito grande."
        }), 400

    if not icone:

        icone = "📁"

    agora = datetime.now().isoformat()

    conexao = conectar()

    cursor = conexao.execute(
        """
        INSERT INTO projetos
        (
            usuario_id,
            nome,
            descricao,
            icone,
            criada_em,
            atualizada_em
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session["usuario_id"],
            nome,
            descricao,
            icone,
            agora,
            agora
        )
    )

    conexao.commit()

    projeto_id = cursor.lastrowid

    conexao.close()

    return jsonify({
        "sucesso": True,
        "projeto": {
            "id": projeto_id,
            "nome": nome,
            "descricao": descricao,
            "icone": icone,
            "criada_em": agora,
            "atualizada_em": agora
        }
    })


# =========================================================
# ABRIR PROJETO
# =========================================================

@app.route(
    "/projeto/<int:projeto_id>",
    methods=["GET"]
)
@login_obrigatorio
def abrir_projeto(projeto_id):

    conexao = conectar()

    projeto = conexao.execute(
        """
        SELECT
            id,
            nome,
            descricao,
            icone,
            criada_em,
            atualizada_em
        FROM projetos
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    ).fetchone()

    if not projeto:

        conexao.close()

        return jsonify({
            "erro": "Projeto não encontrado."
        }), 404

    # -----------------------------------------------------
    # DEFINIR PROJETO ATUAL NA SESSÃO
    # -----------------------------------------------------

    session["projeto_id"] = projeto_id

    conversas = conexao.execute(
        """
        SELECT
            id,
            titulo,
            criada_em,
            projeto_id
        FROM conversas
        WHERE projeto_id = ?
        AND usuario_id = ?
        ORDER BY id DESC
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    ).fetchall()

    conexao.close()

    return jsonify({
        "projeto": {
            "id": projeto["id"],
            "nome": projeto["nome"],
            "descricao": projeto["descricao"],
            "icone": projeto["icone"],
            "criada_em": projeto["criada_em"],
            "atualizada_em": projeto["atualizada_em"]
        },

        "conversas": [
            {
                "id": conversa["id"],
                "titulo": conversa["titulo"],
                "criada_em": conversa["criada_em"],
                "projeto_id": conversa["projeto_id"]
            }
            for conversa in conversas
        ]
    })


# =========================================================
# LISTAR DOCUMENTOS DO PROJETO
# =========================================================

@app.route(
    "/documentos",
    methods=["GET"]
)
@login_obrigatorio
def listar_documentos():

    projeto_id = session.get(
        "projeto_id"
    )

    conexao = conectar()

    if projeto_id is not None:

        documentos = conexao.execute(
            """
            SELECT
                id,
                nome,
                enviado_em
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id = ?
            ORDER BY id DESC
            """,
            (
                session["usuario_id"],
                projeto_id
            )
        ).fetchall()

    else:

        documentos = conexao.execute(
            """
            SELECT
                id,
                nome,
                enviado_em
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id IS NULL
            ORDER BY id DESC
            """,
            (
                session["usuario_id"],
            )
        ).fetchall()

    conexao.close()

    return jsonify([
        {
            "id": documento["id"],
            "nome": documento["nome"],
            "enviado_em": documento["enviado_em"]
        }
        for documento in documentos
    ])


# =========================================================
# EDITAR PROJETO
# =========================================================

@app.route(
    "/projeto/<int:projeto_id>",
    methods=["PUT"]
)
@login_obrigatorio
def editar_projeto(projeto_id):

    dados = request.get_json() or {}

    nome = str(
        dados.get(
            "nome",
            ""
        )
    ).strip()

    descricao = str(
        dados.get(
            "descricao",
            ""
        )
    ).strip()

    icone = str(
        dados.get(
            "icone",
            "📁"
        )
    ).strip()

    if not nome:

        return jsonify({
            "erro": "O nome do projeto não pode ficar vazio."
        }), 400

    if len(nome) > 100:

        return jsonify({
            "erro": "O nome do projeto é muito grande."
        }), 400

    if len(descricao) > 500:

        return jsonify({
            "erro": "A descrição do projeto é muito grande."
        }), 400

    if not icone:

        icone = "📁"

    conexao = conectar()

    projeto = conexao.execute(
        """
        SELECT id
        FROM projetos
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    ).fetchone()

    if not projeto:

        conexao.close()

        return jsonify({
            "erro": "Projeto não encontrado."
        }), 404

    agora = datetime.now().isoformat()

    conexao.execute(
        """
        UPDATE projetos
        SET
            nome = ?,
            descricao = ?,
            icone = ?,
            atualizada_em = ?
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            nome,
            descricao,
            icone,
            agora,
            projeto_id,
            session["usuario_id"]
        )
    )

    conexao.commit()

    conexao.close()

    return jsonify({
        "sucesso": True,
        "projeto": {
            "id": projeto_id,
            "nome": nome,
            "descricao": descricao,
            "icone": icone,
            "atualizada_em": agora
        }
    })


# =========================================================
# EXCLUIR PROJETO
# =========================================================

@app.route(
    "/projeto/<int:projeto_id>",
    methods=["DELETE"]
)
@login_obrigatorio
def excluir_projeto(projeto_id):

    conexao = conectar()

    projeto = conexao.execute(
        """
        SELECT id
        FROM projetos
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    ).fetchone()

    if not projeto:

        conexao.close()

        return jsonify({
            "erro": "Projeto não encontrado."
        }), 404

    conexao.execute(
        """
        UPDATE conversas
        SET projeto_id = NULL
        WHERE projeto_id = ?
        AND usuario_id = ?
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    )

    conexao.execute(
        """
        DELETE FROM projetos
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            projeto_id,
            session["usuario_id"]
        )
    )

    conexao.commit()

    conexao.close()

    if session.get("projeto_id") == projeto_id:

        session.pop(
            "projeto_id",
            None
        )

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
        SELECT
            id,
            titulo,
            criada_em,
            projeto_id
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
            "criada_em": conversa["criada_em"],
            "projeto_id": conversa["projeto_id"]
        }
        for conversa in lista
    ])


# =========================================================
# EXCLUIR CONVERSA
# =========================================================

@app.route(
    "/excluir_conversa/<int:conversa_id>",
    methods=["DELETE"]
)
@login_obrigatorio
def excluir_conversa(conversa_id):

    usuario_id = session["usuario_id"]

    conexao = conectar()

    conversa = conexao.execute(
        """
        SELECT id
        FROM conversas
        WHERE id = ?
        AND usuario_id = ?
        """,
        (
            conversa_id,
            usuario_id
        )
    ).fetchone()

    if not conversa:

        conexao.close()

        return jsonify({
            "erro": "Conversa não encontrada."
        }), 404

    conexao.execute(
        """
        DELETE FROM mensagens
        WHERE conversa_id = ?
        """,
        (conversa_id,)
    )

    conexao.execute(
        """
        DELETE FROM conversas
        WHERE id = ?
        """,
        (conversa_id,)
    )

    conexao.commit()
    conexao.close()

    if session.get("conversa_id") == conversa_id:

        session.pop(
            "conversa_id",
            None
        )

    return jsonify({
        "sucesso": True
    })


# =========================================================
# NOVA CONVERSA
# =========================================================

@app.route(
    "/nova_conversa",
    methods=["POST"]
)
@login_obrigatorio
def nova_conversa():

    dados = request.get_json() or {}

    projeto_id = dados.get(
        "projeto_id"
    )

    if projeto_id in (
        None,
        "",
        0
    ):

        projeto_id = None

    else:

        try:

            projeto_id = int(
                projeto_id
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify({
                "erro": "Projeto inválido."
            }), 400

        conexao = conectar()

        projeto = conexao.execute(
            """
            SELECT id
            FROM projetos
            WHERE id = ?
            AND usuario_id = ?
            """,
            (
                projeto_id,
                session["usuario_id"]
            )
        ).fetchone()

        conexao.close()

        if not projeto:

            return jsonify({
                "erro": "Projeto não encontrado."
            }), 404

    conexao = conectar()

    cursor = conexao.execute(
        """
        INSERT INTO conversas
        (
            usuario_id,
            titulo,
            criada_em,
            projeto_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            session["usuario_id"],
            "Nova conversa",
            datetime.now().isoformat(),
            projeto_id
        )
    )

    conexao.commit()

    conversa_id = cursor.lastrowid

    conexao.close()

    session["conversa_id"] = conversa_id

    if projeto_id is not None:

        session["projeto_id"] = projeto_id

    else:

        session.pop(
            "projeto_id",
            None
        )

    return jsonify({
        "sucesso": True,
        "conversa_id": conversa_id,
        "projeto_id": projeto_id
    })


# =========================================================
# ABRIR CONVERSA
# =========================================================

@app.route(
    "/conversa/<int:conversa_id>"
)
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

    if conversa["projeto_id"] is not None:

        session["projeto_id"] = conversa["projeto_id"]

    else:

        session.pop(
            "projeto_id",
            None
        )

    return jsonify({
        "conversa": {
            "id": conversa["id"],
            "titulo": conversa["titulo"],
            "criada_em": conversa["criada_em"],
            "projeto_id": conversa["projeto_id"]
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
        "tema",
        "diz",
        "fala",
        "falar",
        "conta",
        "trata",
        "conteudo",
        "informacao",
        "informacoes"
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
# IDENTIFICAR NOME DO PDF
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

            if (
                len(parte) >= 4
                and parte in pergunta_normalizada
            ):

                pontos += 5

        if pontos > maior_pontuacao:

            maior_pontuacao = pontos

            melhor_documento = documento

    return melhor_documento


# =========================================================
# IDENTIFICAR TIPO DE PERGUNTA
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
        or "o que diz" in texto
        or "o que fala" in texto
        or "do que fala" in texto
        or "do que se trata" in texto
        or "conteudo do pdf" in texto
        or "conteudo do documento" in texto
        or "o que tem no pdf" in texto
        or "o que tem no documento" in texto
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

    inicio_importante = texto[:3000]

    trechos.append({
        "texto": inicio_importante,
        "tipo": "inicio",
        "pontos": 0
    })

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

    print("CACHE TESTE: ENTROU EM buscar_trechos_pdf", flush=True)

    if not documentos:
        print("BUSCA PDF: nenhum documento disponível", flush=True)
        return []

    chave_cache = _cache_chave(
        pergunta,
        documentos
    )

    resultado_cache = buscar_cache_consulta(
        chave_cache
    )

    if resultado_cache is not None:
        print("CACHE DE CONSULTA: HIT", flush=True)
        return resultado_cache

    print("CACHE DE CONSULTA: MISS", flush=True)

    tipo = identificar_tipo_pergunta(
        pergunta
    )

    documento_mencionado = encontrar_documento_mencionado(
        pergunta,
        documentos
    )

    if documento_mencionado:
        documentos_para_busca = [documento_mencionado]
    else:
        documentos_para_busca = documentos

    palavras = palavras_importantes(pergunta)
    trechos = []

    for documento in documentos_para_busca:

        nome = documento["nome"]
        texto = documento["texto"] or ""

        if not texto.strip():
            continue

        partes = criar_trechos(texto)

        for indice, parte in enumerate(partes):

            trecho = parte["texto"]
            trecho_normalizado = normalizar_texto(trecho)

            pontos = 0
            palavras_encontradas = 0

            # Correspondência das palavras da pergunta.
            for palavra in palavras:
                quantidade = trecho_normalizado.count(palavra)
                if quantidade > 0:
                    palavras_encontradas += 1
                    pontos += min(quantidade * 3, 12)

            # Perguntas sobre o documento inteiro devem priorizar o início.
            if tipo["resumo"] or tipo["assunto"] or tipo["objetivo"]:
                if parte["tipo"] == "inicio":
                    pontos += 50
                elif indice == 1:
                    pontos += 15

            if tipo["titulo"] and parte["tipo"] == "inicio":
                pontos += 60

            if tipo["primeiro_paragrafo"] and parte["tipo"] == "inicio":
                pontos += 60

            if documento_mencionado:
                pontos += 50

            # Se houver palavras relevantes, dê um pequeno bônus ao início.
            if palavras and parte["tipo"] == "inicio":
                pontos += 10

            # Nunca descarte o início de um PDF quando a pergunta é claramente
            # sobre o conteúdo do próprio PDF.
            if not palavras and parte["tipo"] == "inicio":
                pontos += 40

            if pontos > 0:
                trechos.append({
                    "nome": nome,
                    "texto": trecho,
                    "pontos": pontos,
                    "palavras": palavras_encontradas,
                    "tipo": parte["tipo"]
                })

    # Fallback importante: perguntas genéricas como
    # "o que diz o pdf?" devem sempre receber contexto do PDF.
    if not trechos:

        print(
            "BUSCA PDF: nenhum trecho pontuado; usando início dos documentos.",
            flush=True
        )

        for documento in documentos_para_busca:

            texto = documento["texto"] or ""

            if not texto.strip():
                continue

            partes = criar_trechos(texto)

            for parte in partes[:2]:
                trechos.append({
                    "nome": documento["nome"],
                    "texto": parte["texto"],
                    "pontos": 1,
                    "palavras": 0,
                    "tipo": parte["tipo"]
                })

    trechos.sort(
        key=lambda item: (
            item["pontos"],
            item["palavras"]
        ),
        reverse=True
    )

    selecionados = []
    textos_usados = set()

    for trecho in trechos:

        chave = trecho["texto"][:200]

        if chave in textos_usados:
            continue

        textos_usados.add(chave)
        selecionados.append(trecho)

        if len(selecionados) >= 3:
            break

    salvar_cache_consulta(
        chave_cache,
        selecionados
    )

    print(
        "CACHE DE CONSULTA: SALVO | trechos:",
        len(selecionados),
        flush=True
    )

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

    # -----------------------------------------------------
    # MEMÓRIA AUTOMÁTICA
    # -----------------------------------------------------

    memorias_automaticas = extrair_memorias_automaticas(
        pergunta
    )

    for informacao in memorias_automaticas:
        adicionou = adicionar_memoria(informacao)

        if adicionou:
            print(
                "MEMÓRIA AUTOMÁTICA SALVA:",
                informacao
            )

    # -----------------------------------------------------
    # COMANDOS DE MEMÓRIA
    # -----------------------------------------------------

    comando_memoria = identificar_comando_memoria(pergunta)
    tipo_comando_memoria = comando_memoria["tipo"]

    if tipo_comando_memoria == "salvar":

        informacao = comando_memoria["informacao"]
        salvou = adicionar_memoria(informacao)

        if salvou:
            return jsonify({
                "resposta": (
                    "Certo! Vou me lembrar disso: "
                    + informacao
                )
            })

        return jsonify({
            "resposta": "Eu já tinha essa informação na memória."
        })

    if tipo_comando_memoria == "listar":

        return jsonify({
            "resposta": formatar_memorias()
        })

    if tipo_comando_memoria == "apagar":

        informacao = comando_memoria["informacao"]
        apagadas = apagar_memoria_por_texto(informacao)

        if not apagadas:
            return jsonify({
                "resposta": (
                    "Não encontrei uma memória correspondente "
                    "para esquecer."
                )
            })

        resposta_memoria = "Certo! Esqueci estas informações:\n\n"

        for memoria in apagadas:
            resposta_memoria += "- " + memoria + "\n"

        return jsonify({
            "resposta": resposta_memoria.strip()
        })

    tipo = identificar_tipo_pergunta(
        pergunta
    )

    pergunta_normalizada = normalizar_texto(
        pergunta
    )

    pergunta_sobre_pdf = (
        tipo["titulo"]
        or tipo["assunto"]
        or tipo["objetivo"]
        or tipo["resumo"]
        or tipo["primeiro_paragrafo"]
        or "pdf" in pergunta_normalizada
        or "documento" in pergunta_normalizada
    )

    conversa_id = session.get(
        "conversa_id"
    )

    if not conversa_id:

        projeto_id = session.get(
            "projeto_id"
        )

        conexao = conectar()

        cursor = conexao.execute(
            """
            INSERT INTO conversas
            (
                usuario_id,
                titulo,
                criada_em,
                projeto_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                session["usuario_id"],
                pergunta[:40],
                datetime.now().isoformat(),
                projeto_id
            )
        )

        conexao.commit()

        conversa_id = cursor.lastrowid

        conexao.close()

        session["conversa_id"] = conversa_id


    conexao = conectar()


    # -----------------------------------------------------
    # DOCUMENTOS DO PROJETO ATUAL
    # -----------------------------------------------------

    projeto_id_atual = session.get(
        "projeto_id"
    )

    if projeto_id_atual is not None:

        documentos = conexao.execute(
            """
            SELECT id, nome, texto
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id = ?
            """,
            (
                session["usuario_id"],
                projeto_id_atual
            )
        ).fetchall()

    else:

        documentos = conexao.execute(
            """
            SELECT id, nome, texto
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id IS NULL
            """,
            (
                session["usuario_id"],
            )
        ).fetchall()


    # -----------------------------------------------------
    # HISTÓRICO
    # -----------------------------------------------------

    historico = []

    if not pergunta_sobre_pdf:

        historico = conexao.execute(
            """
            SELECT papel, conteudo
            FROM mensagens
            WHERE conversa_id = ?
            ORDER BY id DESC
            LIMIT 2
            """,
            (conversa_id,)
        ).fetchall()

        historico = list(
            reversed(historico)
        )

    conexao.close()


    # -----------------------------------------------------
    # BUSCA PDF
    # -----------------------------------------------------

    trechos = buscar_trechos_pdf(
        pergunta,
        documentos
    )

    contexto_pdf = montar_contexto_pdf(
        trechos
    )

    # -----------------------------------------------------
    # MEMÓRIA RELEVANTE
    # -----------------------------------------------------

    memorias_relevantes = []

    if not pergunta_sobre_pdf:
        memorias_relevantes = encontrar_memoria_por_texto(
            pergunta
        )

    contexto_memoria = ""

    if memorias_relevantes:

        contexto_memoria = (
            "\n\n===== MEMÓRIAS RELEVANTES DO USUÁRIO =====\n"
        )

        for memoria in memorias_relevantes[:5]:

            contexto_memoria += (
                "- "
                + memoria["informacao"]
                + "\n"
            )

        contexto_memoria += (
            "===== FIM DAS MEMÓRIAS =====\n"
        )


    # -----------------------------------------------------
    # INSTRUÇÕES DA IA
    # -----------------------------------------------------

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

Use obrigatoriamente as informações extraídas
do PDF fornecidas abaixo.

Se a pergunta for genérica, como "o que diz o pdf?",
"o que tem no pdf?" ou "sobre o que é o pdf?",
faça um resumo curto do conteúdo usando principalmente
o início do documento e os demais trechos fornecidos.

Não responda que a informação não foi encontrada
se houver qualquer trecho do PDF fornecido.

Só diga "Não encontrei essa informação nos PDFs disponíveis."
quando o contexto realmente estiver vazio.

Não use conhecimento externo e não invente nomes,
números, datas ou fatos.
"""

    else:

        instrucao = """
Responda em português do Brasil.

Seja rápido, claro e completo.

Explique a resposta de forma simples, mas suficiente
para o usuário entender o assunto.

Quando a pergunta pedir uma definição:
- dê a definição;
- explique brevemente;
- dê um exemplo quando isso ajudar.

Não faça introduções desnecessárias.
Não repita a pergunta.
Não invente informações.

Use o histórico somente quando ele for necessário
para entender a pergunta atual.
"""


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


    mensagens = [
        {
            "role": "system",
            "content": (
                sistema
                + contexto_memoria
            )
        }
    ]


    for mensagem in historico:

        mensagens.append({
            "role": mensagem["papel"],
            "content": mensagem["conteudo"]
        })


    mensagens.append({
        "role": "user",
        "content": pergunta
    })


    # -----------------------------------------------------
    # LOG
    # -----------------------------------------------------

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
        "\nPROJETO ATUAL:"
    )

    print(
        projeto_id_atual
    )

    print(
        "\nTIPOS:"
    )

    print(
        tipo
    )


    documento_mencionado = (
        encontrar_documento_mencionado(
            pergunta,
            documentos
        )
    )


    print(
        "\nPDF MENCIONADO:"
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


    # -----------------------------------------------------
    # GERAR RESPOSTA
    # -----------------------------------------------------

    try:

        if pergunta_sobre_pdf:
            limite_tokens = 140
        else:
            limite_tokens = 80

        resultado = ia(
            mensagens,
            max_new_tokens=limite_tokens,
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


    # -----------------------------------------------------
    # SALVAR MENSAGENS
    # -----------------------------------------------------

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

        try:
            if os.path.exists(caminho):
                os.remove(caminho)
        except OSError:
            pass

        return jsonify({
            "erro": (
                "Não foi possível ler o PDF: "
                + str(erro)
            )
        }), 500

    if not texto.strip():

        try:
            if os.path.exists(caminho):
                os.remove(caminho)
        except OSError:
            pass

        return jsonify({
            "erro": (
                "Não foi possível encontrar texto "
                "nesse PDF. Ele pode ser um PDF "
                "formado apenas por imagens."
            )
        }), 400


    # -----------------------------------------------------
    # PROJETO ATUAL
    # -----------------------------------------------------

    projeto_id = session.get(
        "projeto_id"
    )

    conexao = conectar()


    if projeto_id is not None:

        projeto = conexao.execute(
            """
            SELECT id
            FROM projetos
            WHERE id = ?
            AND usuario_id = ?
            """,
            (
                projeto_id,
                session["usuario_id"]
            )
        ).fetchone()

        if not projeto:

            projeto_id = None


    # -----------------------------------------------------
    # SALVAR DOCUMENTO
    # -----------------------------------------------------

    conexao.execute(
        """
        INSERT INTO documentos
        (
            usuario_id,
            nome,
            caminho,
            texto,
            enviado_em,
            projeto_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            session["usuario_id"],
            nome,
            caminho,
            texto,
            datetime.now().isoformat(),
            projeto_id
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
        "Projeto:",
        projeto_id
    )

    print(
        "Caracteres extraídos:",
        len(texto)
    )

    limpar_cache_consultas()


    return jsonify({
        "sucesso": True,
        "mensagem": (
            f"PDF '{nome}' enviado e lido com sucesso."
        )
    })


# =========================================================
# EXCLUIR DOCUMENTO
# =========================================================

@app.route(
    "/excluir_documento/<int:id>",
    methods=["DELETE"]
)
@login_obrigatorio
def excluir_documento(id):

    conexao = conectar()

    documento = conexao.execute(
        """
        SELECT id, nome, caminho, projeto_id
        FROM documentos
        WHERE id = ?
        AND usuario_id = ?
        """,
        (id, session["usuario_id"])
    ).fetchone()

    if not documento:
        conexao.close()
        return jsonify({"erro": "Arquivo não encontrado."}), 404

    conexao.execute(
        """
        DELETE FROM documentos
        WHERE id = ? AND usuario_id = ?
        """,
        (id, session["usuario_id"])
    )
    conexao.commit()
    conexao.close()

    caminho = documento["caminho"]
    if caminho and os.path.exists(caminho):
        try:
            os.remove(caminho)
        except OSError as erro:
            print("Aviso ao remover arquivo físico:", erro, flush=True)

    limpar_cache_consultas()

    return jsonify({
        "sucesso": True,
        "mensagem": "Arquivo excluído com sucesso!"
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

    projeto_id_atual = session.get(
        "projeto_id"
    )


    if projeto_id_atual is not None:

        documentos = conexao.execute(
            """
            SELECT id, nome, texto
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id = ?
            """,
            (
                session["usuario_id"],
                projeto_id_atual
            )
        ).fetchall()

    else:

        documentos = conexao.execute(
            """
            SELECT id, nome, texto
            FROM documentos
            WHERE usuario_id = ?
            AND projeto_id IS NULL
            """,
            (
                session["usuario_id"],
            )
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
# CRIADOR DE SITES
# =========================================================

@app.route(
    "/gerar_site",
    methods=["POST"]
)
@login_obrigatorio
def gerar_site():

    dados = request.get_json() or {}

    descricao = str(
        dados.get(
            "descricao",
            ""
        )
    ).strip()

    localizacao = str(
        dados.get(
            "localizacao",
            ""
        )
    ).strip()

    if not descricao:

        return jsonify({
            "erro": "Descreva o site que você deseja criar."
        }), 400

    if len(descricao) > 5000:

        return jsonify({
            "erro": "A descrição do site é muito grande."
        }), 400

    if len(localizacao) > 500:

        return jsonify({
            "erro": "A localização informada é muito grande."
        }), 400


    # -----------------------------------------------------
    # INSTRUÇÕES PARA A IA
    # -----------------------------------------------------

    contexto_localizacao = ""

    if localizacao:

        contexto_localizacao = f"""
Localização informada pelo usuário:

{localizacao}

Use essa localização somente como informação
fornecida pelo usuário.

Não invente endereço, telefone, horário,
preços, avaliações ou qualquer outro dado.
"""


    prompt = f"""
Você é um gerador de páginas web.

Crie um site completo usando HTML, CSS e JavaScript.

DESCRIÇÃO DO SITE:

{descricao}

{contexto_localizacao}

REGRAS:

1. Gere somente código HTML.
2. O CSS deve estar dentro de uma tag <style>.
3. O JavaScript deve estar dentro de uma tag <script>.
4. O site deve ser responsivo.
5. O visual deve ser moderno e profissional.
6. Não invente informações específicas sobre empresas.
7. Quando uma informação não for fornecida,
   use textos genéricos ou espaços reservados.
8. Não use Markdown.
9. Não coloque ```html.
10. O resultado deve começar diretamente com <!DOCTYPE html>.
"""


    mensagens_site = [
        {
            "role": "system",
            "content": """
Você é uma inteligência artificial especializada
em criação de sites.

Sua tarefa é gerar páginas HTML completas,
modernas, responsivas e funcionais.

Respeite rigorosamente as informações fornecidas
pelo usuário.

Nunca invente informações específicas.
"""
        },
        {
            "role": "user",
            "content": prompt
        }
    ]


    # -----------------------------------------------------
    # GERAR SITE
    # -----------------------------------------------------

    try:

        resultado = ia(
            mensagens_site,
            max_new_tokens=900,
            do_sample=False
        )

        site_html = (
            resultado[0]
            ["generated_text"]
            [-1]
            ["content"]
        ).strip()

    except Exception as erro:

        print(
            "ERRO AO GERAR SITE:",
            erro,
            flush=True
        )

        return jsonify({
            "erro": "Não foi possível gerar o site."
        }), 500


    # -----------------------------------------------------
    # LIMPAR MARKDOWN CASO A IA USE
    # -----------------------------------------------------

    if site_html.startswith("```html"):

        site_html = site_html[
            len("```html"):
        ].strip()

    elif site_html.startswith("```"):

        site_html = site_html[
            len("```"):
        ].strip()


    if site_html.endswith("```"):

        site_html = site_html[
            :-3
        ].strip()


    # -----------------------------------------------------
    # VERIFICAÇÃO BÁSICA
    # -----------------------------------------------------

    if "<html" not in site_html.lower():

        return jsonify({
            "erro": (
                "A IA não conseguiu gerar "
                "um HTML válido."
            )
        }), 500


    return jsonify({
        "sucesso": True,
        "site": site_html
    })

# =========================================================
# INICIAR SERVIDOR
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )
