let conversaAtual = null;

const loginTela = document.getElementById("loginTela");
const appTela = document.getElementById("appTela");
const loginForm = document.getElementById("loginForm");
const cadastroForm = document.getElementById("cadastroForm");
const perguntaInput = document.getElementById("pergunta");
const chat = document.getElementById("chat");
const listaConversas = document.getElementById("listaConversas");

function mostrarLogin() {
    loginTela.style.display = "flex";
    appTela.style.display = "none";
}

function mostrarApp() {
    loginTela.style.display = "none";
    appTela.style.display = "flex";
}

async function fazerLogin(event) {
    event.preventDefault();

    const usuario = document.getElementById("loginUsuario").value.trim();
    const senha = document.getElementById("loginSenha").value;

    try {
        const resposta = await fetch("/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                usuario: usuario,
                senha: senha
            })
        });

        const dados = await resposta.json();

        if (dados.sucesso) {
            mostrarApp();
            carregarConversas();
        } else {
            alert(dados.erro || "Usuário ou senha incorretos.");
        }

    } catch (erro) {
        console.error(erro);
        alert("Erro ao conectar com o servidor.");
    }
}

loginForm.addEventListener("submit", fazerLogin);


async function fazerCadastro(event) {
    event.preventDefault();

    const usuario = document.getElementById("cadastroUsuario").value.trim();
    const senha = document.getElementById("cadastroSenha").value;

    try {
        const resposta = await fetch("/cadastro", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                usuario: usuario,
                senha: senha
            })
        });

        const dados = await resposta.json();

        if (dados.sucesso) {
            alert("Conta criada com sucesso! Agora faça login.");
            document.getElementById("cadastroForm").reset();
        } else {
            alert(dados.erro || "Erro ao criar conta.");
        }

    } catch (erro) {
        console.error(erro);
        alert("Erro ao conectar com o servidor.");
    }
}

cadastroForm.addEventListener("submit", fazerCadastro);


async function carregarConversas() {
    try {
        const resposta = await fetch("/conversas");

        if (!resposta.ok) {
            return;
        }

        const conversas = await resposta.json();

        listaConversas.innerHTML = "";

        conversas.forEach(conversa => {
            const botao = document.createElement("button");

            botao.className = "conversa";
            botao.textContent = conversa.titulo || "Nova conversa";

            botao.addEventListener("click", () => {
                abrirConversa(conversa.id);
            });

            listaConversas.appendChild(botao);
        });

    } catch (erro) {
        console.error("Erro ao carregar conversas:", erro);
    }
}


async function novaConversa() {
    try {
        const resposta = await fetch("/nova_conversa", {
            method: "POST"
        });

        const dados = await resposta.json();

        if (dados.id) {
            conversaAtual = dados.id;
            limparChat();
            carregarConversas();
        }

    } catch (erro) {
        console.error(erro);
    }
}


async function abrirConversa(id) {
    try {
        const resposta = await fetch(`/conversa/${id}`);

        if (!resposta.ok) {
            return;
        }

        const dados = await resposta.json();

        conversaAtual = id;

        limparChat();

        dados.mensagens.forEach(mensagem => {
            adicionarMensagem(mensagem.papel, mensagem.conteudo);
        });

    } catch (erro) {
        console.error("Erro ao abrir conversa:", erro);
    }
}


function limparChat() {
    chat.innerHTML = "";
}


function adicionarMensagem(papel, texto) {
    const mensagem = document.createElement("div");

    mensagem.classList.add("mensagem");

    if (papel === "user") {
        mensagem.classList.add("usuario");
        mensagem.textContent = texto;
    } else {
        mensagem.classList.add("ia");

        if (typeof marked !== "undefined") {
            mensagem.innerHTML = marked.parse(texto);
        } else {
            mensagem.textContent = texto;
        }
    }

    chat.appendChild(mensagem);
    chat.scrollTop = chat.scrollHeight;
}


async function enviarPergunta() {
    const pergunta = perguntaInput.value.trim();

    if (!pergunta) {
        return;
    }

    adicionarMensagem("user", pergunta);

    perguntaInput.value = "";

    const carregando = document.createElement("div");
    carregando.className = "mensagem ia";
    carregando.textContent = "Pensando... 🤖";

    chat.appendChild(carregando);

    try {
        const resposta = await fetch("/perguntar", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                pergunta: pergunta
            })
        });

        const dados = await resposta.json();

        carregando.remove();

        if (dados.resposta) {
            adicionarMensagem("assistant", dados.resposta);
        } else {
            adicionarMensagem(
                "assistant",
                dados.erro || "Ocorreu um erro."
            );
        }

        carregarConversas();

    } catch (erro) {
        carregando.remove();

        console.error(erro);

        adicionarMensagem(
            "assistant",
            "Não consegui me conectar ao servidor. 😕"
        );
    }
}


document.getElementById("btnEnviar").addEventListener(
    "click",
    enviarPergunta
);


perguntaInput.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        event.preventDefault();
        enviarPergunta();
    }
});


document.getElementById("btnNovaConversa").addEventListener(
    "click",
    novaConversa
);


document.getElementById("btnTema").addEventListener(
    "click",
    function() {
        document.body.classList.toggle("dark");

        const tema = document.body.classList.contains("dark")
            ? "dark"
            : "light";

        localStorage.setItem("tema", tema);
    }
);


document.getElementById("btnLogout").addEventListener(
    "click",
    async function() {
        await fetch("/logout");
        location.reload();
    }
);


document.getElementById("uploadPdf").addEventListener(
    "change",
    async function() {

        const arquivo = this.files[0];

        if (!arquivo) {
            return;
        }

        const formulario = new FormData();

        formulario.append("arquivo", arquivo);

        try {

            const resposta = await fetch("/upload", {
                method: "POST",
                body: formulario
            });

            const dados = await resposta.json();

            if (dados.sucesso) {
                alert("PDF enviado com sucesso! 📄");
            } else {
                alert(dados.erro || "Erro ao enviar PDF.");
            }

        } catch (erro) {
            console.error(erro);
            alert("Erro ao enviar o PDF.");
        }

        this.value = "";
    }
);

// Verificar se já existe uma sessão
async function verificarLogin() {

    try {

        const resposta = await fetch("/usuario");

        const dados = await resposta.json();

        if (dados.logado) {
            mostrarApp();
            carregarConversas();
        } else {
            mostrarLogin();
        }

    } catch (erro) {

        console.error(erro);

        mostrarLogin();
    }
}


// Aplicar tema salvo
if (localStorage.getItem("tema") === "dark") {
    document.body.classList.add("dark");
}


// Iniciar
verificarLogin();