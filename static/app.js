console.log("PROJETO MASR — APP.JS 3.4 CARREGOU!");

/* =========================================================
   PROJETO MASR — JAVASCRIPT 3.4
   Configurações + Perfil + Projetos + Conversas + Arquivos
   ========================================================= */


/* =========================================================
   ESTADO
   ========================================================= */

let conversaAtual = null;
let enviandoPergunta = false;

let projetoAtualId = null;
let projetoAtual = null;

let projetoEditandoId = null;


/* =========================================================
   ELEMENTOS PRINCIPAIS
   ========================================================= */

const loginTela =
    document.getElementById("loginTela");

const appTela =
    document.getElementById("appTela");

const loginForm =
    document.getElementById("loginForm");

const cadastroForm =
    document.getElementById("cadastroForm");

const perguntaInput =
    document.getElementById("pergunta");

const chat =
    document.getElementById("chat");

const listaConversas =
    document.getElementById("listaConversas");

const btnEnviar =
    document.getElementById("btnEnviar");

const btnNovaConversa =
    document.getElementById("btnNovaConversa");

const btnTodasConversas =
    document.getElementById("btnTodasConversas");

const btnTema =
    document.getElementById("btnTema");

const btnLogout =
    document.getElementById("btnLogout");

const uploadPdf =
    document.getElementById("uploadPdf");


/* =========================================================
   ELEMENTOS — CONFIGURAÇÕES
   ========================================================= */

const btnConfiguracoes =
    document.getElementById("btnConfiguracoes");

const perfilUsuario =
    document.getElementById("perfilUsuario");

const nomeUsuario =
    document.getElementById("nomeUsuario");

const painelConfiguracoes =
    document.getElementById("painelConfiguracoes");

const fecharConfiguracoesFundo =
    document.getElementById("fecharConfiguracoesFundo");

const btnFecharConfiguracoes =
    document.getElementById("btnFecharConfiguracoes");

const btnFecharConfiguracoes2 =
    document.getElementById("btnFecharConfiguracoes2");

const usuarioConfiguracoes =
    document.getElementById("usuarioConfiguracoes");

const configTema =
    document.getElementById("configTema");


/* =========================================================
   ELEMENTOS — PROJETOS
   ========================================================= */

const listaProjetos =
    document.getElementById("listaProjetos");

const listaDocumentos =
    document.getElementById("listaDocumentos");

const btnNovoProjeto =
    document.getElementById("btnNovoProjeto");

const painelProjeto =
    document.getElementById("painelProjeto");

const fecharProjetoFundo =
    document.getElementById("fecharProjetoFundo");

const btnFecharProjeto =
    document.getElementById("btnFecharProjeto");

const btnCancelarProjeto =
    document.getElementById("btnCancelarProjeto");

const formProjeto =
    document.getElementById("formProjeto");

const tituloModalProjeto =
    document.getElementById("tituloModalProjeto");

const projetoNome =
    document.getElementById("projetoNome");

const projetoDescricao =
    document.getElementById("projetoDescricao");

const projetoIcones =
    document.getElementById("projetoIcones");

const btnSalvarProjeto =
    document.getElementById("btnSalvarProjeto");

const tituloProjetoAtual =
    document.getElementById("tituloProjetoAtual");

const subtituloProjetoAtual =
    document.getElementById("subtituloProjetoAtual");


/* =========================================================
   LOGIN / APP
   ========================================================= */

function mostrarLogin() {

    if (loginTela) {
        loginTela.style.display = "flex";
    }

    if (appTela) {
        appTela.style.display = "none";
    }
}


function mostrarApp() {

    if (loginTela) {
        loginTela.style.display = "none";
    }

    if (appTela) {
        appTela.style.display = "flex";
    }

    setTimeout(() => {

        if (perguntaInput) {
            perguntaInput.focus();
        }

    }, 100);
}


/* =========================================================
   LOGIN
   ========================================================= */

async function fazerLogin(event) {

    event.preventDefault();

    const usuario =
        document
            .getElementById("loginUsuario")
            .value
            .trim();

    const senha =
        document
            .getElementById("loginSenha")
            .value;

    if (!usuario || !senha) {

        mostrarAviso(
            "Preencha usuário e senha."
        );

        return;
    }

    try {

        const resposta =
            await fetch(
                "/login",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        usuario: usuario,
                        senha: senha
                    })
                }
            );

        const dados =
            await resposta.json();

        if (dados.sucesso) {

            loginForm.reset();

            mostrarApp();

            await carregarUsuario();

            await carregarProjetos();

            await carregarConversas();

        } else {

            mostrarAviso(
                dados.erro ||
                "Usuário ou senha incorretos."
            );
        }

    } catch (erro) {

        console.error(
            "Erro no login:",
            erro
        );

        mostrarAviso(
            "Não foi possível conectar ao servidor."
        );
    }
}


if (loginForm) {

    loginForm.addEventListener(
        "submit",
        fazerLogin
    );
}


/* =========================================================
   CADASTRO
   ========================================================= */

async function fazerCadastro(event) {

    event.preventDefault();

    const usuario =
        document
            .getElementById("cadastroUsuario")
            .value
            .trim();

    const senha =
        document
            .getElementById("cadastroSenha")
            .value;

    if (!usuario || !senha) {

        mostrarAviso(
            "Preencha todos os campos."
        );

        return;
    }

    try {

        const resposta =
            await fetch(
                "/cadastro",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        usuario: usuario,
                        senha: senha
                    })
                }
            );

        const dados =
            await resposta.json();

        if (dados.sucesso) {

            mostrarAviso(
                "Conta criada com sucesso! Agora faça login. ✅"
            );

            cadastroForm.reset();

        } else {

            mostrarAviso(
                dados.erro ||
                "Erro ao criar conta."
            );
        }

    } catch (erro) {

        console.error(
            "Erro no cadastro:",
            erro
        );

        mostrarAviso(
            "Não foi possível conectar ao servidor."
        );
    }
}


if (cadastroForm) {

    cadastroForm.addEventListener(
        "submit",
        fazerCadastro
    );
}


/* =========================================================
   USUÁRIO
   ========================================================= */

async function carregarUsuario() {

    try {

        const resposta =
            await fetch(
                "/usuario"
            );

        if (!resposta.ok) {
            return;
        }

        const dados =
            await resposta.json();

        if (!dados.logado) {
            return;
        }

        const usuario =
            dados.usuario ||
            dados.nome ||
            dados.username ||
            "Usuário";

        if (nomeUsuario) {
            nomeUsuario.textContent =
                usuario;
        }

        if (usuarioConfiguracoes) {
            usuarioConfiguracoes.textContent =
                usuario;
        }

    } catch (erro) {

        console.error(
            "Erro ao carregar usuário:",
            erro
        );
    }
}


/* =========================================================
   CONFIGURAÇÕES — ABRIR
   ========================================================= */

function abrirConfiguracoes() {

    if (!painelConfiguracoes) {
        return;
    }

    painelConfiguracoes.classList.remove(
        "escondido"
    );

    painelConfiguracoes.setAttribute(
        "aria-hidden",
        "false"
    );

    sincronizarConfiguracoes();

    document.body.style.overflow =
        "hidden";
}


/* =========================================================
   CONFIGURAÇÕES — FECHAR
   ========================================================= */

function fecharConfiguracoes() {

    if (!painelConfiguracoes) {
        return;
    }

    painelConfiguracoes.classList.add(
        "escondido"
    );

    painelConfiguracoes.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.style.overflow =
        "";

    if (perguntaInput) {

        setTimeout(
            () => perguntaInput.focus(),
            100
        );
    }
}


/* =========================================================
   EVENTOS — CONFIGURAÇÕES
   ========================================================= */

if (btnConfiguracoes) {

    btnConfiguracoes.addEventListener(
        "click",
        abrirConfiguracoes
    );
}


if (perfilUsuario) {

    perfilUsuario.addEventListener(
        "click",
        abrirConfiguracoes
    );
}


if (btnFecharConfiguracoes) {

    btnFecharConfiguracoes.addEventListener(
        "click",
        fecharConfiguracoes
    );
}


if (btnFecharConfiguracoes2) {

    btnFecharConfiguracoes2.addEventListener(
        "click",
        fecharConfiguracoes
    );
}


if (fecharConfiguracoesFundo) {

    fecharConfiguracoesFundo.addEventListener(
        "click",
        fecharConfiguracoes
    );
}


/* =========================================================
   ESC — FECHAR PAINÉIS
   ========================================================= */

document.addEventListener(
    "keydown",
    event => {

        if (event.key !== "Escape") {
            return;
        }

        if (
            painelConfiguracoes &&
            !painelConfiguracoes.classList.contains(
                "escondido"
            )
        ) {

            fecharConfiguracoes();

            return;
        }

        if (
            painelProjeto &&
            !painelProjeto.classList.contains(
                "escondido"
            )
        ) {

            fecharPainelProjeto();
        }
    }
);


/* =========================================================
   ABAS DAS CONFIGURAÇÕES
   ========================================================= */

function configurarAbasConfiguracoes() {

    const botoes =
        document.querySelectorAll(
            ".config-menu-item"
        );

    const secoes =
        document.querySelectorAll(
            ".config-secao"
        );

    if (!botoes.length) {
        return;
    }

    botoes.forEach(
        botao => {

            botao.addEventListener(
                "click",
                () => {

                    const alvo =
                        botao.dataset.secao;

                    if (!alvo) {
                        return;
                    }

                    botoes.forEach(
                        item => {

                            item.classList.remove(
                                "ativo"
                            );
                        }
                    );

                    secoes.forEach(
                        secao => {

                            secao.classList.remove(
                                "ativa"
                            );
                        }
                    );

                    botao.classList.add(
                        "ativo"
                    );

                    const secao =
                        document.getElementById(
                            alvo
                        );

                    if (secao) {

                        secao.classList.add(
                            "ativa"
                        );
                    }
                }
            );
        }
    );
}


configurarAbasConfiguracoes();


/* =========================================================
   TEMA
   ========================================================= */

function obterTemaAtual() {

    return document.body.classList.contains(
        "dark"
    )
        ? "dark"
        : "light";
}


function aplicarTema(tema) {

    if (tema === "dark") {

        document.body.classList.add(
            "dark"
        );

    } else {

        document.body.classList.remove(
            "dark"
        );

        tema = "light";
    }

    localStorage.setItem(
        "tema",
        tema
    );

    sincronizarTemaInterface();
}


function sincronizarTemaInterface() {

    const tema =
        obterTemaAtual();

    if (configTema) {

        configTema.checked =
            tema === "dark";
    }

    if (btnTema) {

        btnTema.setAttribute(
            "aria-label",
            tema === "dark"
                ? "Ativar tema claro"
                : "Ativar tema escuro"
        );

        btnTema.setAttribute(
            "title",
            tema === "dark"
                ? "Tema claro"
                : "Tema escuro"
        );
    }
}


function sincronizarConfiguracoes() {

    sincronizarTemaInterface();

    carregarUsuario();
}


/* =========================================================
   BOTÃO TEMA
   ========================================================= */

if (btnTema) {

    btnTema.addEventListener(
        "click",
        () => {

            const novoTema =
                obterTemaAtual() === "dark"
                    ? "light"
                    : "dark";

            aplicarTema(
                novoTema
            );
        }
    );
}


/* =========================================================
   SWITCH DE TEMA
   ========================================================= */

if (configTema) {

    configTema.addEventListener(
        "change",
        () => {

            aplicarTema(
                configTema.checked
                    ? "dark"
                    : "light"
            );
        }
    );
}


/* =========================================================
   PROJETOS — CARREGAR
   ========================================================= */

async function carregarProjetos() {

    if (!listaProjetos) {
        return;
    }

    try {

        const resposta =
            await fetch(
                "/projetos"
            );

        if (!resposta.ok) {

            console.error(
                "Erro ao carregar projetos:",
                resposta.status
            );

            return;
        }

        const projetos =
            await resposta.json();

        renderizarProjetos(
            projetos
        );

        if (projetoAtualId !== null) {

            const projetoEncontrado =
                projetos.find(
                    projeto =>
                        Number(projeto.id) ===
                        Number(projetoAtualId)
                );

            if (projetoEncontrado) {

                projetoAtual =
                    projetoEncontrado;

            } else {

                projetoAtualId =
                    null;

                projetoAtual =
                    null;
            }

            atualizarCabecalhoProjeto();
        }

    } catch (erro) {

        console.error(
            "Erro ao carregar projetos:",
            erro
        );
    }
}


/* =========================================================
   RENDERIZAR PROJETOS
   ========================================================= */

function renderizarProjetos(
    projetos
) {

    if (!listaProjetos) {
        return;
    }

    listaProjetos.innerHTML = "";

    if (!projetos || projetos.length === 0) {

        const vazio =
            document.createElement(
                "div"
            );

        vazio.className =
            "projetos-vazio";

        vazio.textContent =
            "Nenhum projeto ainda.";

        listaProjetos.appendChild(
            vazio
        );

        return;
    }

    projetos.forEach(
        projeto => {

            const item =
                document.createElement(
                    "div"
                );

            item.className =
                "projeto-item";

            item.dataset.id =
                projeto.id;

            if (
                Number(projeto.id) ===
                Number(projetoAtualId)
            ) {

                item.classList.add(
                    "ativo"
                );
            }


            /* BOTÃO PRINCIPAL */

            const botao =
                document.createElement(
                    "button"
                );

            botao.type =
                "button";

            botao.className =
                "projeto-botao";


            const icone =
                document.createElement(
                    "span"
                );

            icone.className =
                "projeto-item-icone";

            icone.textContent =
                projeto.icone ||
                "📁";


            const nome =
                document.createElement(
                    "span"
                );

            nome.className =
                "projeto-item-nome";

            nome.textContent =
                projeto.nome;


            botao.appendChild(
                icone
            );

            botao.appendChild(
                nome
            );


            botao.title =
                projeto.descricao ||
                projeto.nome;


            botao.addEventListener(
                "click",
                () => {

                    selecionarProjeto(
                        projeto
                    );
                }
            );


            /* AÇÕES */

            const acoes =
                document.createElement(
                    "div"
                );

            acoes.className =
                "projeto-acoes";


            const editar =
                document.createElement(
                    "button"
                );

            editar.type =
                "button";

            editar.className =
                "projeto-acao";

            editar.textContent =
                "✏️";

            editar.title =
                "Editar projeto";


            editar.addEventListener(
                "click",
                event => {

                    event.stopPropagation();

                    abrirEditarProjeto(
                        projeto
                    );
                }
            );


            const excluir =
                document.createElement(
                    "button"
                );

            excluir.type =
                "button";

            excluir.className =
                "projeto-acao";

            excluir.textContent =
                "🗑️";

            excluir.title =
                "Excluir projeto";


            excluir.addEventListener(
                "click",
                event => {

                    event.stopPropagation();

                    excluirProjeto(
                        projeto.id
                    );
                }
            );


            acoes.appendChild(
                editar
            );

            acoes.appendChild(
                excluir
            );


            item.appendChild(
                botao
            );

            item.appendChild(
                acoes
            );


            listaProjetos.appendChild(
                item
            );
        }
    );
}


/* =========================================================
   DOCUMENTOS — CARREGAR
   ========================================================= */

async function carregarDocumentos() {

    if (!listaDocumentos) {
        return;
    }

    /*
     * Se nenhum projeto está selecionado,
     * limpa a área e informa o usuário.
     */

    if (projetoAtualId === null) {

        renderizarDocumentos([]);

        return;
    }

    try {

        const resposta =
            await fetch(
                "/documentos"
            );

        if (!resposta.ok) {

            console.error(
                "Erro ao carregar documentos:",
                resposta.status
            );

            renderizarDocumentos([]);

            return;
        }

        const documentos =
            await resposta.json();

        renderizarDocumentos(
            documentos
        );

    } catch (erro) {

        console.error(
            "Erro ao carregar documentos:",
            erro
        );

        renderizarDocumentos([]);
    }
}


/* =========================================================
   RENDERIZAR DOCUMENTOS
   ========================================================= */

function renderizarDocumentos(
    documentos
) {

    if (!listaDocumentos) {
        return;
    }

    listaDocumentos.innerHTML = "";


    /*
     * Nenhum projeto selecionado
     */

    if (projetoAtualId === null) {

        const vazio =
            document.createElement(
                "div"
            );

        vazio.className =
            "documentos-vazio";

        vazio.textContent =
            "Selecione um projeto.";

        listaDocumentos.appendChild(
            vazio
        );

        return;
    }


    /*
     * Projeto sem arquivos
     */

    if (
        !documentos ||
        documentos.length === 0
    ) {

        const vazio =
            document.createElement(
                "div"
            );

        vazio.className =
            "documentos-vazio";

        vazio.textContent =
            "Nenhum arquivo ainda.";

        listaDocumentos.appendChild(
            vazio
        );

        return;
    }


    /*
     * Lista os arquivos
     */

    documentos.forEach(
        documento => {

            const item =
                document.createElement(
                    "div"
                );

            item.className =
                "documento-item";


            const icone =
                document.createElement(
                    "span"
                );

            icone.className =
                "documento-icone";

            icone.textContent =
                "📄";


            const nome =
                document.createElement(
                    "span"
                );

            nome.className =
                "documento-nome";

            nome.textContent =
                documento.nome;

            nome.title =
                documento.nome;


            item.appendChild(
                icone
            );

            item.appendChild(
                nome
            );


            listaDocumentos.appendChild(
                item
            );
        }
    );
}


/* =========================================================
   SELECIONAR PROJETO
   ========================================================= */

async function selecionarProjeto(
    projeto
) {

    if (!projeto) {
        return;
    }

    projetoAtualId =
        Number(projeto.id);

    projetoAtual =
        projeto;

    atualizarCabecalhoProjeto();

    conversaAtual =
        null;

    limparChat();

    mostrarMensagemInicial();


    /*
     * Atualiza visualmente os projetos.
     */

    await carregarProjetos();


    try {

        const resposta =
            await fetch(
                `/projeto/${projetoAtualId}`
            );

        if (!resposta.ok) {

            console.error(
                "Não foi possível carregar o projeto."
            );

        } else {

            const dados =
                await resposta.json();

            if (dados.projeto) {

                projetoAtual =
                    dados.projeto;
            }

            atualizarCabecalhoProjeto();


            /*
             * Mostra as conversas pertencentes
             * ao projeto.
             */

            if (
                Array.isArray(
                    dados.conversas
                )
            ) {

                renderizarConversas(
                    dados.conversas
                );

            } else {

                await carregarConversas();
            }
        }

    } catch (erro) {

        console.error(
            "Erro ao selecionar projeto:",
            erro
        );

        await carregarConversas();
    }


    /*
     * Carrega os arquivos do projeto.
     */

    await carregarDocumentos();


    if (perguntaInput) {
        perguntaInput.focus();
    }
}


/* =========================================================
   CABEÇALHO DO PROJETO
   ========================================================= */

function atualizarCabecalhoProjeto() {

    if (!tituloProjetoAtual) {
        return;
    }

    if (projetoAtual) {

        const icone =
            projetoAtual.icone ||
            "📁";

        tituloProjetoAtual.textContent =
            `${icone} ${projetoAtual.nome}`;

        if (subtituloProjetoAtual) {

            subtituloProjetoAtual.textContent =
                projetoAtual.descricao ||
                "Projeto ativo";
        }

    } else {

        tituloProjetoAtual.textContent =
            "Projeto MASR";

        if (subtituloProjetoAtual) {

            subtituloProjetoAtual.textContent =
                "Online";
        }
    }
}


/* =========================================================
   TODAS AS CONVERSAS
   ========================================================= */

function mostrarTodasConversas() {

    projetoAtualId =
        null;

    projetoAtual =
        null;

    conversaAtual =
        null;

    atualizarCabecalhoProjeto();

    limparChat();

    mostrarMensagemInicial();

    carregarProjetos();

    renderizarDocumentos([]);

    carregarConversas();

    if (perguntaInput) {
        perguntaInput.focus();
    }
}


if (btnTodasConversas) {

    btnTodasConversas.addEventListener(
        "click",
        mostrarTodasConversas
    );
}


/* =========================================================
   ABRIR MODAL DE PROJETO
   ========================================================= */

function abrirPainelProjeto(
    projeto = null
) {

    if (!painelProjeto) {
        return;
    }

    projetoEditandoId =
        projeto
            ? Number(projeto.id)
            : null;

    if (tituloModalProjeto) {

        tituloModalProjeto.textContent =
            projeto
                ? "Editar projeto"
                : "Novo projeto";
    }

    if (projetoNome) {

        projetoNome.value =
            projeto
                ? projeto.nome || ""
                : "";
    }

    if (projetoDescricao) {

        projetoDescricao.value =
            projeto
                ? projeto.descricao || ""
                : "";
    }

    selecionarIconeProjeto(
        projeto
            ? projeto.icone || "📁"
            : "📁"
    );

    if (btnSalvarProjeto) {

        btnSalvarProjeto.textContent =
            projeto
                ? "Salvar alterações"
                : "Criar projeto";
    }

    painelProjeto.classList.remove(
        "escondido"
    );

    painelProjeto.setAttribute(
        "aria-hidden",
        "false"
    );

    document.body.style.overflow =
        "hidden";

    setTimeout(
        () => {

            if (projetoNome) {
                projetoNome.focus();
            }

        },
        100
    );
}


/* =========================================================
   FECHAR MODAL DE PROJETO
   ========================================================= */

function fecharPainelProjeto() {

    if (!painelProjeto) {
        return;
    }

    painelProjeto.classList.add(
        "escondido"
    );

    painelProjeto.setAttribute(
        "aria-hidden",
        "true"
    );

    document.body.style.overflow =
        "";

    projetoEditandoId =
        null;

    if (formProjeto) {
        formProjeto.reset();
    }

    selecionarIconeProjeto(
        "📁"
    );
}


/* =========================================================
   BOTÕES DO MODAL
   ========================================================= */

if (btnNovoProjeto) {

    btnNovoProjeto.addEventListener(
        "click",
        () => {

            abrirPainelProjeto();
        }
    );
}


if (btnFecharProjeto) {

    btnFecharProjeto.addEventListener(
        "click",
        fecharPainelProjeto
    );
}


if (btnCancelarProjeto) {

    btnCancelarProjeto.addEventListener(
        "click",
        fecharPainelProjeto
    );
}


if (fecharProjetoFundo) {

    fecharProjetoFundo.addEventListener(
        "click",
        fecharPainelProjeto
    );
}


/* =========================================================
   ÍCONES DOS PROJETOS
   ========================================================= */

function configurarIconesProjeto() {

    const botoes =
        document.querySelectorAll(
            ".projeto-icone-opcao"
        );

    botoes.forEach(
        botao => {

            botao.addEventListener(
                "click",
                () => {

                    selecionarIconeProjeto(
                        botao.dataset.icone ||
                        botao.textContent.trim() ||
                        "📁"
                    );
                }
            );
        }
    );
}


function selecionarIconeProjeto(
    icone
) {

    if (projetoIcones) {

        projetoIcones.value =
            icone;
    }

    const botoes =
        document.querySelectorAll(
            ".projeto-icone-opcao"
        );

    botoes.forEach(
        botao => {

            const ativo =
                (
                    botao.dataset.icone ||
                    botao.textContent.trim()
                ) === icone;

            botao.classList.toggle(
                "ativo",
                ativo
            );
        }
    );
}


configurarIconesProjeto();


/* =========================================================
   CRIAR / EDITAR PROJETO
   ========================================================= */

if (formProjeto) {

    formProjeto.addEventListener(
        "submit",
        async event => {

            event.preventDefault();

            const nome =
                projetoNome
                    ? projetoNome.value.trim()
                    : "";

            const descricao =
                projetoDescricao
                    ? projetoDescricao.value.trim()
                    : "";

            const icone =
                projetoIcones
                    ? projetoIcones.value || "📁"
                    : "📁";

            if (!nome) {

                mostrarAviso(
                    "Digite um nome para o projeto."
                );

                return;
            }

            if (btnSalvarProjeto) {
                btnSalvarProjeto.disabled =
                    true;
            }

            const idEditado =
                projetoEditandoId;

            const editando =
                idEditado !== null;

            const url =
                editando
                    ? `/projeto/${idEditado}`
                    : "/projetos";

            const metodo =
                editando
                    ? "PUT"
                    : "POST";

            try {

                const resposta =
                    await fetch(
                        url,
                        {
                            method:
                                metodo,

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({
                                    nome:
                                        nome,

                                    descricao:
                                        descricao,

                                    icone:
                                        icone
                                })
                        }
                    );

                const dados =
                    await resposta.json();

                if (!resposta.ok) {

                    mostrarAviso(
                        dados.erro ||
                        "Não foi possível salvar o projeto."
                    );

                    return;
                }

                if (!dados.sucesso) {

                    mostrarAviso(
                        dados.erro ||
                        "Não foi possível salvar o projeto."
                    );

                    return;
                }

                fecharPainelProjeto();

                await carregarProjetos();


                /*
                 * Projeto criado:
                 * seleciona automaticamente.
                 */

                if (
                    !editando &&
                    dados.projeto
                ) {

                    await selecionarProjeto(
                        dados.projeto
                    );
                }


                /*
                 * Projeto editado:
                 * mantém o projeto aberto.
                 */

                else if (
                    editando &&
                    projetoAtualId !== null &&
                    Number(projetoAtualId) ===
                    Number(idEditado)
                ) {

                    if (dados.projeto) {

                        projetoAtual =
                            dados.projeto;
                    }

                    atualizarCabecalhoProjeto();

                    await carregarConversas();

                    await carregarDocumentos();
                }

                mostrarAviso(
                    editando
                        ? "Projeto atualizado! ✅"
                        : "Projeto criado! 📁✅"
                );

            } catch (erro) {

                console.error(
                    "Erro ao salvar projeto:",
                    erro
                );

                mostrarAviso(
                    "Não foi possível salvar o projeto."
                );

            } finally {

                if (btnSalvarProjeto) {

                    btnSalvarProjeto.disabled =
                        false;
                }
            }
        }
    );
}


/* =========================================================
   ABRIR EDIÇÃO
   ========================================================= */

function abrirEditarProjeto(
    projeto
) {

    abrirPainelProjeto(
        projeto
    );
}


/* =========================================================
   EXCLUIR PROJETO
   ========================================================= */

async function excluirProjeto(
    id
) {

    const confirmar =
        confirm(
            "Tem certeza que deseja excluir este projeto?\n\nAs conversas do projeto continuarão salvas, mas ficarão sem projeto."
        );

    if (!confirmar) {
        return;
    }

    try {

        const resposta =
            await fetch(
                `/projeto/${id}`,
                {
                    method:
                        "DELETE"
                }
            );

        const dados =
            await resposta.json();

        if (!resposta.ok) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível excluir o projeto."
            );

            return;
        }

        if (!dados.sucesso) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível excluir o projeto."
            );

            return;
        }

        if (
            Number(projetoAtualId) ===
            Number(id)
        ) {

            projetoAtualId =
                null;

            projetoAtual =
                null;

            conversaAtual =
                null;

            limparChat();

            mostrarMensagemInicial();

            atualizarCabecalhoProjeto();

            renderizarDocumentos([]);
        }

        await carregarProjetos();

        await carregarConversas();

        mostrarAviso(
            "Projeto excluído. 🗑️"
        );

    } catch (erro) {

        console.error(
            "Erro ao excluir projeto:",
            erro
        );

        mostrarAviso(
            "Não foi possível excluir o projeto."
        );
    }
}


/* =========================================================
   CONVERSAS — CARREGAR
   ========================================================= */

async function carregarConversas() {

    if (!listaConversas) {
        return;
    }

    try {

        const resposta =
            await fetch(
                "/conversas"
            );

        if (!resposta.ok) {

            console.error(
                "Erro ao carregar conversas:",
                resposta.status
            );

            return;
        }

        const conversas =
            await resposta.json();

        let conversasExibidas =
            conversas;

        if (
            projetoAtualId !== null
        ) {

            conversasExibidas =
                conversas.filter(
                    conversa =>
                        Number(
                            conversa.projeto_id
                        ) ===
                        Number(
                            projetoAtualId
                        )
                );
        }

        renderizarConversas(
            conversasExibidas
        );

    } catch (erro) {

        console.error(
            "Erro ao carregar conversas:",
            erro
        );
    }
}


/* =========================================================
   RENDERIZAR CONVERSAS
   ========================================================= */

function renderizarConversas(
    conversas
) {

    if (!listaConversas) {
        return;
    }

    listaConversas.innerHTML = "";

    if (
        !conversas ||
        conversas.length === 0
    ) {

        const vazio =
            document.createElement(
                "div"
            );

        vazio.className =
            "conversas-vazio";

        vazio.textContent =
            "Nenhuma conversa ainda.";

        listaConversas.appendChild(
            vazio
        );

        return;
    }

    conversas.forEach(
        conversa => {

            const item =
                document.createElement(
                    "div"
                );

            item.className =
                "conversa-item";


            if (
                Number(conversa.id) ===
                Number(conversaAtual)
            ) {

                item.classList.add(
                    "ativa"
                );
            }


            const botao =
                document.createElement(
                    "button"
                );

            botao.type =
                "button";

            botao.className =
                "conversa";

            botao.textContent =
                conversa.titulo ||
                "Nova conversa";

            botao.title =
                conversa.titulo ||
                "Nova conversa";


            botao.addEventListener(
                "click",
                async () => {

                    await abrirConversa(
                        conversa.id
                    );
                }
            );


            const excluir =
                document.createElement(
                    "button"
                );

            excluir.type =
                "button";

            excluir.className =
                "btn-excluir-conversa";

            excluir.textContent =
                "🗑️";

            excluir.title =
                "Excluir conversa";

            excluir.setAttribute(
                "aria-label",
                "Excluir conversa"
            );


            excluir.addEventListener(
                "click",
                event => {

                    event.preventDefault();

                    event.stopPropagation();

                    excluirConversa(
                        conversa.id
                    );
                }
            );


            item.appendChild(
                botao
            );

            item.appendChild(
                excluir
            );

            listaConversas.appendChild(
                item
            );
        }
    );
}


/* =========================================================
   EXCLUIR CONVERSA
   ========================================================= */

async function excluirConversa(
    id
) {

    const confirmar =
        confirm(
            "Tem certeza que deseja excluir esta conversa?"
        );

    if (!confirmar) {
        return;
    }

    try {

        const resposta =
            await fetch(
                `/excluir_conversa/${id}`,
                {
                    method:
                        "DELETE"
                }
            );

        const dados =
            await resposta.json();

        if (!resposta.ok) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível excluir a conversa."
            );

            return;
        }

        if (!dados.sucesso) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível excluir a conversa."
            );

            return;
        }

        if (
            Number(conversaAtual) ===
            Number(id)
        ) {

            conversaAtual =
                null;

            limparChat();

            mostrarMensagemInicial();
        }

        await carregarConversas();

        mostrarAviso(
            "Conversa excluída. 🗑️"
        );

    } catch (erro) {

        console.error(
            "Erro ao excluir conversa:",
            erro
        );

        mostrarAviso(
            "Não foi possível excluir a conversa."
        );
    }
}


/* =========================================================
   ABRIR CONVERSA
   ========================================================= */

async function abrirConversa(
    id
) {

    try {

        const resposta =
            await fetch(
                `/conversa/${id}`
            );

        if (!resposta.ok) {

            mostrarAviso(
                "Não foi possível abrir a conversa."
            );

            return;
        }

        const dados =
            await resposta.json();

        conversaAtual =
            Number(id);


        /*
         * Descobre o projeto da conversa.
         */

        if (
            dados.projeto_id !== undefined &&
            dados.projeto_id !== null
        ) {

            projetoAtualId =
                Number(
                    dados.projeto_id
                );

            try {

                const respostaProjeto =
                    await fetch(
                        `/projeto/${projetoAtualId}`
                    );

                if (
                    respostaProjeto.ok
                ) {

                    const dadosProjeto =
                        await respostaProjeto.json();

                    if (
                        dadosProjeto.projeto
                    ) {

                        projetoAtual =
                            dadosProjeto.projeto;
                    }
                }

            } catch (erroProjeto) {

                console.error(
                    "Erro ao carregar projeto da conversa:",
                    erroProjeto
                );
            }

        } else {

            projetoAtualId =
                null;

            projetoAtual =
                null;
        }


        atualizarCabecalhoProjeto();

        limparChat();


        if (
            !dados.mensagens ||
            dados.mensagens.length === 0
        ) {

            mostrarMensagemInicial();

        } else {

            dados.mensagens.forEach(
                mensagem => {

                    adicionarMensagem(
                        mensagem.papel,
                        mensagem.conteudo
                    );
                }
            );
        }


        await carregarProjetos();

        await carregarDocumentos();

        await carregarConversas();


        if (perguntaInput) {
            perguntaInput.focus();
        }

    } catch (erro) {

        console.error(
            "Erro ao abrir conversa:",
            erro
        );

        mostrarAviso(
            "Não foi possível abrir esta conversa."
        );
    }
}


/* =========================================================
   NOVA CONVERSA
   ========================================================= */

async function novaConversa() {

    try {

        const corpo = {};


        if (
            projetoAtualId !== null
        ) {

            corpo.projeto_id =
                projetoAtualId;
        }


        const resposta =
            await fetch(
                "/nova_conversa",
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            corpo
                        )
                }
            );


        const dados =
            await resposta.json();


        if (!resposta.ok) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível criar uma nova conversa."
            );

            return;
        }


        if (!dados.sucesso) {

            mostrarAviso(
                dados.erro ||
                "Não foi possível criar uma nova conversa."
            );

            return;
        }


        conversaAtual =
            Number(
                dados.conversa_id
            );


        if (
            dados.projeto_id !== undefined &&
            dados.projeto_id !== null
        ) {

            projetoAtualId =
                Number(
                    dados.projeto_id
                );
        }


        limparChat();

        mostrarMensagemInicial();

        await carregarConversas();


        if (perguntaInput) {
            perguntaInput.focus();
        }

    } catch (erro) {

        console.error(
            "Erro ao criar conversa:",
            erro
        );

        mostrarAviso(
            "Não foi possível criar uma nova conversa."
        );
    }
}


if (btnNovaConversa) {

    btnNovaConversa.addEventListener(
        "click",
        novaConversa
    );
}


/* =========================================================
   LIMPAR CHAT
   ========================================================= */

function limparChat() {

    if (chat) {
        chat.innerHTML = "";
    }
}


/* =========================================================
   MENSAGEM INICIAL
   ========================================================= */

function mostrarMensagemInicial() {

    if (!chat) {
        return;
    }

    const elemento =
        document.createElement(
            "div"
        );

    elemento.className =
        "bem-vindo";

    elemento.innerHTML = `
        <div class="avatar grande">
            🤖
        </div>

        <h1>Olá! 👋</h1>

        <p>
            Eu sou a sua IA.
            Faça uma pergunta para começarmos.
        </p>
    `;

    chat.appendChild(
        elemento
    );
}


/* =========================================================
   ADICIONAR MENSAGEM
   ========================================================= */

function adicionarMensagem(
    papel,
    texto
) {

    removerMensagemInicial();

    const mensagem =
        document.createElement(
            "div"
        );

    mensagem.classList.add(
        "mensagem"
    );


    /* USUÁRIO */

    if (papel === "user") {

        mensagem.classList.add(
            "usuario"
        );

        mensagem.textContent =
            texto;


    /* IA */

    } else {

        mensagem.classList.add(
            "ia"
        );

        if (
            typeof marked !==
            "undefined"
        ) {

            mensagem.innerHTML =
                marked.parse(
                    texto
                );

        } else {

            mensagem.textContent =
                texto;
        }

        adicionarBotaoCopiar(
            mensagem,
            texto
        );
    }


    if (chat) {

        chat.appendChild(
            mensagem
        );
    }

    rolarChat();
}


/* =========================================================
   BOTÃO COPIAR
   ========================================================= */

function adicionarBotaoCopiar(
    mensagem,
    texto
) {

    const botao =
        document.createElement(
            "button"
        );

    botao.className =
        "btn-copiar";

    botao.type =
        "button";

    botao.textContent =
        "📋";

    botao.title =
        "Copiar resposta";

    botao.setAttribute(
        "aria-label",
        "Copiar resposta"
    );

    botao.addEventListener(
        "click",
        async () => {

            try {

                await navigator.clipboard.writeText(
                    texto
                );

                botao.textContent =
                    "✅";

                botao.title =
                    "Copiado!";

                setTimeout(
                    () => {

                        botao.textContent =
                            "📋";

                        botao.title =
                            "Copiar resposta";

                    },
                    1500
                );

            } catch (erro) {

                console.error(
                    "Erro ao copiar:",
                    erro
                );

                mostrarAviso(
                    "Não foi possível copiar a resposta."
                );
            }
        }
    );

    mensagem.appendChild(
        botao
    );
}


/* =========================================================
   INDICADOR "PENSANDO"
   ========================================================= */

function criarMensagemPensando() {

    const carregando =
        document.createElement(
            "div"
        );

    carregando.className =
        "mensagem ia pensando";

    carregando.innerHTML = `
        Pensando
        <span>•</span>
        <span>•</span>
        <span>•</span>
    `;

    return carregando;
}


/* =========================================================
   BOTÃO ENVIAR
   ========================================================= */

function atualizarBotaoEnviar(
    carregando
) {

    if (!btnEnviar) {
        return;
    }

    if (carregando) {

        btnEnviar.disabled =
            true;

        btnEnviar.style.opacity =
            "0.6";

        btnEnviar.textContent =
            "Pensando...";

    } else {

        btnEnviar.disabled =
            false;

        btnEnviar.style.opacity =
            "1";

        btnEnviar.textContent =
            "Enviar";
    }
}


if (btnEnviar) {

    btnEnviar.onclick = function () {
        enviarPergunta();
    };
}


/* =========================================================
   ENVIAR PERGUNTA
   ========================================================= */

async function enviarPergunta() {

    console.log(
        "1 - FUNÇÃO FOI CHAMADA"
    );

    if (enviandoPergunta) {
        return;
    }

    const pergunta =
        perguntaInput.value.trim();

    console.log(
        "2 - PERGUNTA:",
        pergunta
    );

    if (!pergunta) {
        return;
    }

    enviandoPergunta =
        true;

    atualizarBotaoEnviar(
        true
    );

    console.log(
        "3 - VAI ADICIONAR MENSAGEM"
    );

    adicionarMensagem(
        "user",
        pergunta
    );

    console.log(
        "4 - MENSAGEM ADICIONADA"
    );

    perguntaInput.value =
        "";

    const pensando =
        criarMensagemPensando();

    if (chat) {

        chat.appendChild(
            pensando
        );
    }

    rolarChat();

    try {

        console.log(
            "5 - VAI ENVIAR PARA O SERVIDOR"
        );

        const resposta =
            await fetch(
                "/perguntar",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        pergunta:
                            pergunta
                    })
                }
            );

        console.log(
            "6 - RESPOSTA DO SERVIDOR:",
            resposta.status
        );

        const dados =
            await resposta.json();

        console.log(
            "7 - DADOS:",
            dados
        );

        pensando.remove();

        if (dados.resposta) {

            adicionarMensagem(
                "assistant",
                dados.resposta
            );

        } else {

            adicionarMensagem(
                "assistant",
                dados.erro ||
                "Ocorreu um erro."
            );
        }


        if (
            dados.conversa_id !== undefined &&
            dados.conversa_id !== null
        ) {

            conversaAtual =
                Number(
                    dados.conversa_id
                );
        }

        await carregarConversas();

    } catch (erro) {

        console.error(
            "ERRO:",
            erro
        );

        pensando.remove();

        adicionarMensagem(
            "assistant",
            "Não consegui me conectar ao servidor. 😕"
        );

    } finally {

        enviandoPergunta =
            false;

        atualizarBotaoEnviar(
            false
        );

        if (perguntaInput) {
            perguntaInput.focus();
        }
    }
}


/* =========================================================
   ENTER / SHIFT + ENTER
   ========================================================= */

if (perguntaInput) {

    perguntaInput.addEventListener(
        "keydown",
        function(event) {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                enviarPergunta();
            }
        }
    );
}


/* =========================================================
   LOGOUT
   ========================================================= */

if (btnLogout) {

    btnLogout.addEventListener(
        "click",
        async function() {

            try {

                await fetch(
                    "/logout"
                );

                location.reload();

            } catch (erro) {

                console.error(
                    erro
                );

                mostrarAviso(
                    "Erro ao sair da conta."
                );
            }
        }
    );
}


/* =========================================================
   UPLOAD DE PDF
   ========================================================= */

if (uploadPdf) {

    uploadPdf.addEventListener(
        "change",
        async function() {

            const arquivo =
                this.files[0];

            if (!arquivo) {
                return;
            }


            if (
                arquivo.type !==
                "application/pdf"
            ) {

                mostrarAviso(
                    "Selecione um arquivo PDF."
                );

                this.value =
                    "";

                return;
            }


            const formulario =
                new FormData();

            formulario.append(
                "arquivo",
                arquivo
            );


            mostrarAviso(
                `Enviando "${arquivo.name}"... 📄`
            );


            try {

                const resposta =
                    await fetch(
                        "/upload",
                        {
                            method:
                                "POST",

                            body:
                                formulario
                        }
                    );


                const dados =
                    await resposta.json();


                if (dados.sucesso) {

                    mostrarAviso(
                        "PDF enviado com sucesso! 📄✅"
                    );


                    /*
                     * Atualiza a lista de arquivos
                     * imediatamente após o upload.
                     */

                    await carregarDocumentos();


                } else {

                    mostrarAviso(
                        dados.erro ||
                        "Erro ao enviar PDF."
                    );
                }


            } catch (erro) {

                console.error(
                    "Erro no upload:",
                    erro
                );

                mostrarAviso(
                    "Erro ao enviar o PDF."
                );

            } finally {

                this.value =
                    "";
            }
        }
    );
}


/* =========================================================
   VERIFICAR LOGIN
   ========================================================= */

async function verificarLogin() {

    try {

        const resposta =
            await fetch(
                "/usuario"
            );

        const dados =
            await resposta.json();

        if (dados.logado) {

            mostrarApp();

            await carregarUsuario();

            await carregarProjetos();

            await carregarConversas();

        } else {

            mostrarLogin();
        }

    } catch (erro) {

        console.error(
            "Erro ao verificar login:",
            erro
        );

        mostrarLogin();
    }
}


/* =========================================================
   AVISOS
   ========================================================= */

function mostrarAviso(
    texto
) {

    const aviso =
        document.createElement(
            "div"
        );

    aviso.textContent =
        texto;

    aviso.style.position =
        "fixed";

    aviso.style.left =
        "50%";

    aviso.style.bottom =
        "25px";

    aviso.style.transform =
        "translateX(-50%)";

    aviso.style.zIndex =
        "9999";

    aviso.style.maxWidth =
        "90%";

    aviso.style.padding =
        "12px 18px";

    aviso.style.borderRadius =
        "12px";

    aviso.style.background =
        "var(--primary)";

    aviso.style.color =
        "white";

    aviso.style.fontSize =
        "14px";

    aviso.style.fontWeight =
        "500";

    aviso.style.boxShadow =
        "0 8px 30px rgba(0,0,0,0.2)";

    aviso.style.animation =
        "aparecer 0.25s ease";

    document.body.appendChild(
        aviso
    );

    setTimeout(
        () => {

            aviso.style.opacity =
                "0";

            aviso.style.transition =
                "opacity 0.25s ease";

            setTimeout(
                () => {

                    aviso.remove();

                },
                250
            );

        },
        2500
    );
}


/* =========================================================
   FUNÇÕES AUXILIARES
   ========================================================= */

function removerMensagemInicial() {

    if (!chat) {
        return;
    }

    const inicial =
        chat.querySelector(
            ".bem-vindo"
        );

    if (inicial) {
        inicial.remove();
    }
}


function rolarChat() {

    if (!chat) {
        return;
    }

    setTimeout(
        () => {

            chat.scrollTo({

                top:
                    chat.scrollHeight,

                behavior:
                    "smooth"
            });

        },
        50
    );
}


/* =========================================================
   APLICAR TEMA SALVO
   ========================================================= */

const temaSalvo =
    localStorage.getItem(
        "tema"
    );

if (temaSalvo === "dark") {

    document.body.classList.add(
        "dark"
    );

} else {

    document.body.classList.remove(
        "dark"
    );
}

sincronizarTemaInterface();


/* =========================================================
   INICIAR
   ========================================================= */

verificarLogin();

// ==========================================================
// CRIADOR DE SITES
// ==========================================================

(function () {

    const btnCriadorSites =
        document.getElementById("btnCriadorSites");

    const painelCriadorSites =
        document.getElementById("painelCriadorSites");

    const btnFecharCriadorSites =
        document.getElementById("btnFecharCriadorSites");

    const btnCancelarCriadorSites =
        document.getElementById("btnCancelarCriadorSites");

    const fecharCriadorSitesFundo =
        document.getElementById("fecharCriadorSitesFundo");

    const btnGerarSite =
        document.getElementById("btnGerarSite");

    const descricaoSite =
        document.getElementById("descricaoSite");

    const localizacaoSite =
        document.getElementById("localizacaoSite");

    const previewSite =
        document.getElementById("previewSite");


    // ======================================================
    // GERAR SITE
    // ======================================================

    async function gerarSite() {

        console.log("GERAR SITE FOI CHAMADO!");

        if (!descricaoSite) {
            console.error("Campo descrição do site não encontrado.");
            return;
        }

        const descricao =
            descricaoSite.value.trim();

        const localizacao =
            localizacaoSite
                ? localizacaoSite.value.trim()
                : "";

        if (!descricao) {

            alert(
                "Descreva o site que você deseja criar."
            );

            return;
        }

        const prompt =
            localizacao
                ? `${descricao}\n\nLocalização: ${localizacao}`
                : descricao;


        try {

            console.log(
                "VOU ENVIAR PARA /sites"
            );


            const resposta =
                await fetch(
                    "/sites",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                nome: "Novo Site",
                                prompt: prompt
                            })
                    }
                );


            console.log(
                "RESPOSTA /sites:",
                resposta.status
            );


            const dados =
                await resposta.json();


            console.log(
                "DADOS RECEBIDOS:",
                dados
            );


            if (
                !resposta.ok ||
                !dados.sucesso
            ) {

                throw new Error(
                    dados.erro ||
                    "Não foi possível criar o site."
                );
            }


            // ==================================================
            // MOSTRAR SITE NO PREVIEW
            // ==================================================

            if (!previewSite) {

                console.error(
                    "Elemento previewSite não encontrado."
                );

                return;
            }


            previewSite.innerHTML = `
                <iframe
                    id="iframePreviewSite"
                    style="
                        width: 100%;
                        height: 80vh;
                        min-height: 700px;
                        border: none;
                        border-radius: 12px;
                        background: white;
                        display: block;
                    "
                    sandbox="allow-scripts"
                ></iframe>
            `;


            const iframe =
                document.getElementById(
                    "iframePreviewSite"
                );


            if (iframe) {

                /*
                 * O servidor agora deverá retornar
                 * UM HTML COMPLETO.
                 */

                iframe.srcdoc =
                    dados.html || "";

            }


            const status =
                document.querySelector(
                    ".preview-status"
                );


            if (status) {

                status.textContent =
                    "Site criado";

            }


            console.log(
                "SITE EXIBIDO COM SUCESSO!"
            );

        } catch (erro) {

            console.error(
                "Erro ao criar site:",
                erro
            );

            alert(
                "Erro ao criar o site: " +
                erro.message
            );
        }
    }


    // ======================================================
    // ABRIR CRIADOR DE SITES
    // ======================================================

    function abrirCriadorSites() {

        if (!painelCriadorSites) {
            return;
        }

        painelCriadorSites.classList.remove(
            "escondido"
        );

        painelCriadorSites.setAttribute(
            "aria-hidden",
            "false"
        );

    }


    // ======================================================
    // FECHAR CRIADOR DE SITES
    // ======================================================

    function fecharCriadorSites() {

        if (!painelCriadorSites) {
            return;
        }

        painelCriadorSites.classList.add(
            "escondido"
        );

        painelCriadorSites.setAttribute(
            "aria-hidden",
            "true"
        );

    }


    // ======================================================
    // EVENTO — ABRIR
    // ======================================================

    if (btnCriadorSites) {

        btnCriadorSites.addEventListener(
            "click",
            abrirCriadorSites
        );

    }


    // ======================================================
    // EVENTO — FECHAR
    // ======================================================

    if (btnFecharCriadorSites) {

        btnFecharCriadorSites.addEventListener(
            "click",
            fecharCriadorSites
        );

    }


    if (btnCancelarCriadorSites) {

        btnCancelarCriadorSites.addEventListener(
            "click",
            fecharCriadorSites
        );

    }


    if (fecharCriadorSitesFundo) {

        fecharCriadorSitesFundo.addEventListener(
            "click",
            fecharCriadorSites
        );

    }


    // ======================================================
    // EVENTO — GERAR SITE
    // ======================================================

    console.log(
        "Botão Gerar Site encontrado:",
        btnGerarSite
    );

    console.log(
        "Descrição encontrada:",
        descricaoSite
    );

    console.log(
        "Preview encontrado:",
        previewSite
    );


    if (btnGerarSite) {

        btnGerarSite.addEventListener(
            "click",
            function () {

                console.log(
                    "CLIQUE NO GERAR SITE FOI DETECTADO!"
                );

                gerarSite();

            }
        );

    }

})();