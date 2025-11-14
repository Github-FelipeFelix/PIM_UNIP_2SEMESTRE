import json
import os
import secrets
import struct
import subprocess
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from collections import defaultdict # Deixa a importação inútil

# --- Paths e configs ---
base_path = os.path.dirname(os.path.abspath(__file__))
dados_path = os.path.join(base_path, 'dados.json')
chave_path = os.path.join(base_path, 'key.bin')

# RAs fixos
ras_fixos = {0: 1234567, 1: 9876543, 2: 1122334}

# Materias do curso
materias = [
    "PIM",
    "ENG_SOFT_AGIL",
    "ALGOR_ESTRUT_PYTHON",
    "PROG_ESTRUT_C",
    "ANALISE_PROJ_SIST",
    "PESQ_TEC_INOV",
    "EDU_AMBIENTAL",
    "REDES_DISTRIB",
    "INTELIGENCIA_ART",
    "ESTUDOS_DISCIPLINARES",
]

# --- Funções auxiliares de Segurança/Dados ---
def pega_chave():
    if not os.path.exists(chave_path):
        k = Fernet.generate_key()
        with open(chave_path, 'wb') as f:
            f.write(k)
        return k
    with open(chave_path, 'rb') as f:
        return f.read()

def cripto(texto):
    f = Fernet(pega_chave())
    return f.encrypt(texto.encode()).decode()

def decripto(texto):
    f = Fernet(pega_chave())
    try:
        # Tive que colocar o padding aqui, senão dá pau
        texto_pad = texto + '=' * (-len(texto) % 4)
        return f.decrypt(texto_pad.encode()).decode()
    except InvalidToken:
        return None
    except Exception:
        return None

def hash_senha(s):
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()

def notas_vazias():
    # Cria a estrutura de notas vazia
    n = {}
    for m in materias:
        if m == "PIM":
            n[m] = 0.0
        else:
            n[m] = {"NP1": 0.0, "NP2": 0.0}
    return n

def carrega_dados():
    if os.path.exists(dados_path):
        with open(dados_path, 'r') as f:
            return json.load(f)
    return {'usuarios': {}, 'alunos': [], 'turmas': []}

def salva_dados(d):
    with open(dados_path, 'w') as f:
        json.dump(d, f, indent=4)

# --- Funções de Lógica e Regras de Negócio ---
def login_ok(u, s):
    d = carrega_dados()
    if u in d['usuarios'] and d['usuarios'][u]['hash'] == hash_senha(s):
        return d['usuarios'][u]['tipo']
    return None

def cad_user(u, s, nome, tipo='aluno'):
    d = carrega_dados()
    if u in d['usuarios']:
        return False
    d['usuarios'][u] = {'hash': hash_senha(s), 'tipo': tipo}

    if tipo == 'aluno':
        # Conta quantos alunos tem para dar o RA
        cont = len([a for a in d['alunos'] if a['usuario_login'] not in ['admin','professor']])
        ra = ras_fixos.get(cont, secrets.randbelow(9000000)+1000000)
        d['alunos'].append({
            'usuario_login': u,
            'nome_criptografado': cripto(nome),
            'ra_criptografado': cripto(str(ra)),
            'turma_id': 'Nenhuma',
            'notas_c': notas_vazias()
        })
    salva_dados(d)
    return True

def cadastra_turma(nome):
    d = carrega_dados()
    if any(t['nome'] == nome for t in d['turmas']):
        return False
    d['turmas'].append({'id': secrets.token_hex(3), 'nome': nome})
    salva_dados(d)
    return True

def matricula_aluno(u_login, t_id):
    d = carrega_dados()
    for a in d['alunos']:
        if a['usuario_login'] == u_login:
            a['turma_id'] = t_id
            salva_dados(d)
            return True
    return False

def apagar_user(u):
    d = carrega_dados()
    if u not in d['usuarios']:
        return False, "Usuário não existe"
    del d['usuarios'][u]
    # Filtra os alunos (usa list comprehension porque é "moderno")
    d['alunos'] = [a for a in d['alunos'] if a['usuario_login'] != u]
    salva_dados(d)
    return True, f"{u} apagado."

# --- Integração C ---
def envia_para_c():
    d = carrega_dados()
    lista_ras = []
    arq_bin = 'dados_notas.dat'
    # Estrutura: int (RA), float (NP1), float (NP2), float (PIM)
    struct_bin = struct.Struct('i f f f')
    try:
        with open(arq_bin, 'wb') as f:
            for a in d['alunos']:
                # Pega RA, se der erro, pula (tem que ser número)
                ra = decripto(a['ra_criptografado'])
                if not ra or not ra.isdigit():
                    continue
                lista_ras.append(ra)
                
                # Matéria que vai pro C
                np1 = float(a['notas_c'].get('PROG_ESTRUT_C', {}).get('NP1') or 0.0)
                np2 = float(a['notas_c'].get('PROG_ESTRUT_C', {}).get('NP2') or 0.0)
                pim = float(a['notas_c'].get('PIM') or 0.0)
                
                f.write(struct_bin.pack(int(ra), np1, np2, pim))
    except Exception as e:
        return False, f"Erro criando binário: {e}"

    if not lista_ras:
        return False, "Nenhum RA para enviar."

    with open(os.path.join(base_path,'ras_para_c.txt'),'w') as f:
        f.write('\n'.join(lista_ras))

    try:
        subprocess.run(['./modulo_c.exe'], check=True)
        return True, "Módulo C executado."
    except FileNotFoundError:
        return False, "Executável C não encontrado"
    except Exception as e:
        return False, f"Erro ao rodar C: {e}"

# --- Funções de Interface Auxiliares (UI) ---

def ui_gestao_turmas():
    st.subheader("Matricular Alunos")
    d = carrega_dados()
    turmas = d['turmas']
    
    # Faz um loop pra pegar quem não tá matriculado
    alunos_sem_turma = [decripto(a['nome_criptografado']) for a in d['alunos'] if a['turma_id'] == 'Nenhuma']

    if alunos_sem_turma and turmas:
        aluno_selecionado = st.selectbox("Aluno para Matricular:", alunos_sem_turma)
        turma_selecionada = st.selectbox("Turma para Alocar:", [t['nome'] for t in turmas])
        
        # Pega o ID
        t_id = next((t['id'] for t in turmas if t['nome'] == turma_selecionada), None)
        
        if st.button("Matricular!"):
            # Pega o login do aluno
            u_login = next((a['usuario_login'] for a in d['alunos'] if decripto(a['nome_criptografado']) == aluno_selecionado), None)
            
            if matricula_aluno(u_login, t_id):
                st.success(f"Beleza, {aluno_selecionado} agora tá em {turma_selecionada}!")
                st.rerun()
            else:
                st.error("Erro na matrícula.")
    else:
        st.warning("Não tem alunos sem turma ou turmas cadastradas.")

def ui_diario_eletronico():
    st.subheader("Diário Eletrônico: Lançar Notas")
    st.info("Só edite NP1, NP2 e PIM. O PIM é a nota global do projeto.")

    d = carrega_dados()
    materia_editar = st.selectbox("Matéria para editar:", [m for m in materias if m != "PIM"])
    tabela_notas = []

    for a in d['alunos']:
        nome = decripto(a['nome_criptografado'])
        ra = decripto(a['ra_criptografado'])
        notas = a.get('notas_c', notas_vazias())
        
        # Pega notas com conversão simples
        np1 = float(notas.get(materia_editar, {}).get('NP1') or 0.0)
        np2 = float(notas.get(materia_editar, {}).get('NP2') or 0.0)
        pim = float(notas.get('PIM') or 0.0)

        # Média UNIP: NP1*4 + NP2*4 + PIM*2
        media = ((np1 * 4) + (pim * 2) + (np2 * 4)) / 10

        status = "Aprovado" if media >= 7.0 else "Reprovado" if media > 0 else "Sem Nota"

        tabela_notas.append({
            'Nome': nome,
            'RA': ra,
            'NP1': np1,
            'NP2': np2,
            'PIM': pim,
            'Média': f"{media:.2f}",
            'Status': status,
            'login_aluno': a['usuario_login']
        })

    st.markdown("### Tabela de Notas (Editar)")
    tabela_editada = st.data_editor(
        tabela_notas,
        column_config={
            "Nome": st.column_config.TextColumn(disabled=True),
            "RA": st.column_config.TextColumn(disabled=True),
            "Média": st.column_config.TextColumn(disabled=True),
            "Status": st.column_config.TextColumn(disabled=True),
            "login_aluno": st.column_config.TextColumn(disabled=True),
            "NP1": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, format="%.2f"),
            "NP2": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, format="%.2f"),
            "PIM": st.column_config.NumberColumn(min_value=0.0, max_value=10.0, format="%.2f"),
        },
        hide_index=True,
        num_rows="dynamic"
    )

    st.markdown("---")
    if st.button("Salvar Tudo e Chamar o C"):
        # Salva no JSON
        for linha in tabela_editada:
            for aluno in d['alunos']:
                if aluno['usuario_login'] == linha['login_aluno']:
                    
                    # Garante que tem a estrutura de notas
                    aluno.setdefault('notas_c', notas_vazias())

                    # Pega os valores da tabela
                    np1_novo = float(linha.get('NP1') or 0.0)
                    np2_novo = float(linha.get('NP2') or 0.0)
                    pim_novo = float(linha.get('PIM') or 0.0)

                    # Salva
                    aluno['notas_c'][materia_editar]['NP1'] = np1_novo
                    aluno['notas_c'][materia_editar]['NP2'] = np2_novo
                    aluno['notas_c']['PIM'] = pim_novo

                    # Recalcula e salva a média (dic extra)
                    media_final = ((np1_novo * 4) + (pim_novo * 2) + (np2_novo * 4)) / 10
                    aluno['notas_c'].setdefault('medias_calc', {}) 
                    aluno['notas_c']['medias_calc'][materia_editar] = media_final

                    break

        salva_dados(d)
        st.success("Notas salvas. Beleza!")
        
        # Chama a integração C
        sucesso, msg = envia_para_c()
        
        if sucesso:
            st.success(f"C: {msg}")
        else:
            st.error(f"C FALHOU: {msg}")
        st.rerun()

def ui_gerenciar_usuarios(d, user_atual):
    st.subheader("APAGAR Usuários")
    
    lista_excluir = [u for u in d['usuarios'].keys() if u != user_atual]
    
    if not lista_excluir:
        st.warning("Só tem você aqui.")
        return

    usuario_excluir = st.selectbox("Quem apagar?", lista_excluir)
    
    st.error(f"CUIDADO: Apagar '{usuario_excluir}' é para sempre.")
    
    if st.button(f"APAGAR TUDO ({usuario_excluir})"):
        sucesso, mensagem = apagar_user(usuario_excluir)
        if sucesso:
            st.success(mensagem)
        else:
            st.error(mensagem)
        st.rerun()

# --- Funções de Interface Principal ---

def tela_prof_admin(tipo):
    st.title(f"Área de {tipo.upper()}: {st.session_state['usuario']}")
    d = carrega_dados()
    
    menu = ["Dashboard", "Cadastrar Turmas", "Gestão de Turmas", "Diário Eletrônico (Notas C)"]
    if tipo == 'admin':
        menu.append("Gerenciar Usuários")
        
    escolha = st.sidebar.selectbox("O que fazer?", menu)
    
    if escolha == "Dashboard":
        st.subheader("Visão Geral")
        if tipo == 'professor':
            st.info("DICA: Use o diário eletrônico para lançar as notas. É mais fácil que papel.")
        else:
            st.info("DICA: A arquitetura Cliente-Servidor é boa porque o processamento pesado fica no Servidor.")
        
        st.metric("Total de Alunos", len(d['alunos']))
        st.metric("Total de Turmas", len(d['turmas']))
        
    elif escolha == "Cadastrar Turmas":
        st.subheader("Criar Turma")
        nome_t = st.text_input("Nome da Turma:")
        if st.button("Criar Turma"):
            if cadastra_turma(nome_t):
                st.success(f"Turma '{nome_t}' criada.")
            else:
                st.error("Turma já existe.")
                
        turmas_existentes = d['turmas']
        st.markdown("---")
        st.text("Turmas Existentes:")
        for t in turmas_existentes:
            st.write(f"- {t['nome']} (ID: {t['id']})")
            
    elif escolha == "Gestão de Turmas":
        ui_gestao_turmas()
            
    elif escolha == "Diário Eletrônico (Notas C)":
        ui_diario_eletronico()
    
    elif escolha == "Gerenciar Usuários":
        ui_gerenciar_usuarios(d, st.session_state['usuario'])


def tela_aluno():
    st.title(f"Área do Aluno: {st.session_state['usuario']}")
    st.sidebar.header("Menu")
    
    d = carrega_dados()
    aluno = next((a for a in d['alunos'] if a['usuario_login'] == st.session_state['usuario']), None)
    
    if not aluno:
        st.error("Seu registro não foi achado. Fale com o professor.")
        return

    st.subheader("Dados")
    st.metric("ID da Turma", aluno['turma_id'])
    
    st.markdown("---")
    st.subheader("Minhas Notas")

    notas = aluno.get('notas_c', notas_vazias())

    materia_escolhida = st.selectbox("Ver a nota de:", materias.copy())

    st.markdown("---")

    if materia_escolhida == "PIM":
        pim_nota = float(notas.get("PIM") or 0.0)
        st.metric("Nota do PIM", f"{pim_nota:.2f}")

    else:
        info = notas.get(materia_escolhida, {"NP1": 0.0, "NP2": 0.0})
        
        np1 = float(info.get("NP1") or 0.0)
        np2 = float(info.get("NP2") or 0.0)
        pim = float(notas.get("PIM") or 0.0)

        st.metric("NP1", f"{np1:.2f}")
        st.metric("NP2", f"{np2:.2f}")

        # Média UNIP 4/2/4
        media = ((np1 * 4) + (pim * 2) + (np2 * 4)) / 10

        st.metric("Média Final da Matéria", f"{media:.2f}")

        status = "Aprovado" if media >= 7 else "Reprovado"
        st.metric("Status", status)

    # Cálculo da média semestral geral:
    st.markdown("---")
    
    if materia_escolhida != "PIM":
        pim_global = float(notas.get("PIM") or 0.0)
        medias_materias = []
        for materia, info in notas.items():
            if materia == "PIM" or not isinstance(info, dict):
                continue
            
            n1 = float(info.get("NP1") or 0.0)
            n2 = float(info.get("NP2") or 0.0)
                
            media_materia = ((n1 * 4) + (pim_global * 2) + (n2 * 4)) / 10
            medias_materias.append(media_materia)

        if medias_materias:
            media_geral = sum(medias_materias) / len(medias_materias)
            st.subheader("Média Geral")
            st.metric("Média Aritmética de Tudo", f"{media_geral:.2f}")

    st.info("DICA: Use o sistema direito para garantir que os dados acadêmicos estão certos.")

# --- Main ---
def main():
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False
        
    st.sidebar.button("Sair (Logout)", on_click=lambda: st.session_state.update({'logado': False, 'usuario': None, 'tipo': None}))
    
    if st.session_state.get('logado'):
        if st.session_state['tipo'] in ['professor', 'admin']:
            tela_prof_admin(st.session_state['tipo'])
        elif st.session_state['tipo'] == 'aluno':
            tela_aluno()
    else:
        # Tela de Login/Cadastro na página principal
        st.title("Sistema Acadêmico Colaborativo 2.0")
        st.subheader("Login / Cadastro Novo")

        # Cadastro na Sidebar
        st.sidebar.header("Novo Cadastro")
        u_novo = st.sidebar.text_input("Usuário novo:")
        s_nova = st.sidebar.text_input("Senha nova:", type="password")
        n_completo = st.sidebar.text_input("Nome Completo:")
        tipo_user = st.sidebar.radio("Tipo:", ['aluno', 'professor', 'admin'])
        
        if st.sidebar.button("Registrar"):
            if u_novo and s_nova and n_completo:
                if cad_user(u_novo, s_nova, n_completo, tipo_user):
                    st.sidebar.success(f"Beleza, {u_novo} agora tá cadastrado!")
                else:
                    st.sidebar.error("Usuário já existe.")
            else:
                st.sidebar.warning("Preencha TUDO para cadastrar.")

        st.markdown("---")
        
        # Login
        u_login = st.text_input("Seu Usuário:")
        s_login = st.text_input("Sua Senha:", type="password")

        if st.button("Entrar"):
            tipo = login_ok(u_login, s_login)
            if tipo:
                st.session_state['logado'] = True
                st.session_state['usuario'] = u_login
                st.session_state['tipo'] = tipo
                st.rerun()
            else:
                st.error("Usuário ou senha errados.")

if __name__ == '__main__':
    main()