import streamlit as st
import pandas as pd
import time
from datetime import datetime
from supabase import create_client, Client

# Configuração inicial da página com o nome do projeto
st.set_page_config(page_title="MAPEAMENTO_FECHAMENTO_CONVIVA", layout="wide")

# --- CONEXÃO COM O BANCO DE DADOS (SUPABASE) ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# --- SISTEMA DE LOGIN MULTI-REGIÃO ---
def verificar_login():
    credenciais = {
        "APIAI": st.secrets["SENHA_APIAI"],
        "SANTOS": st.secrets["SENHA_SANTOS"],
        "BAURU": st.secrets["SENHA_BAURU"]
    }
    
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["regiao"] = None

    if not st.session_state["autenticado"]:
        st.title("🔒 Acesso Restrito - Conviva")
        st.write("Selecione a sua diretoria e digite a senha de acesso.")
        
        regiao_selecionada = st.selectbox("Região:", list(credenciais.keys()))
        senha_inserida = st.text_input("Senha:", type="password")
        
        if st.button("Entrar"):
            if senha_inserida == credenciais[regiao_selecionada]:
                st.session_state["autenticado"] = True
                st.session_state["regiao"] = regiao_selecionada
                st.rerun()
            else:
                st.error("Senha incorreta para a região selecionada.")
        return False
    return True

# Apenas carrega o sistema se o login for válido
if verificar_login():
    st.sidebar.success(f"Logado na região: {st.session_state['regiao']}")
    
    # --- FUNÇÕES DE BANCO DE DADOS ---
    def carregar_base():
        try:
            resposta = supabase.table("colaboradores").select("*").eq("ativo", True).execute()
            if resposta.data:
                return pd.DataFrame(resposta.data)
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao ligar ao Supabase: {e}")
            return pd.DataFrame()

    def carregar_eventos():
        resposta = supabase.table("ocorrencias").select("*").execute()
        if resposta.data:
            return pd.DataFrame(resposta.data)
        return pd.DataFrame(columns=["data_registro", "data_evento", "escola", "cuidador", "tipo_evento", "observacao"])

    def salvar_evento(data_evento, escola, cuidador, tipo, obs):
        novo_registro = {
            "data_evento": data_evento.strftime("%Y-%m-%d"),
            "escola": escola,
            "cuidador": cuidador,
            "tipo_evento": tipo,
            "observacao": obs
        }
        supabase.table("ocorrencias").insert(novo_registro).execute()
        return True

    def substituir_colaborador(escola, cuidador_antigo, novo_nome, novo_cpf):
        try:
            # Procura o colaborador antigo
            busca = supabase.table("colaboradores").select("*").eq("escola", escola).eq("cuidador", cuidador_antigo).execute()
            
            if busca.data:
                id_colaborador = busca.data[0]['id']
                obs_antiga = busca.data[0]['observacao'] or ""
                nova_obs = f"[{datetime.now().strftime('%d/%m')}] Substituiu {cuidador_antigo}. {obs_antiga}"
                
                # Atualiza os dados no banco
                atualizacao = {
                    "cuidador": novo_nome.upper(),
                    "cpf": novo_cpf,
                    "observacao": nova_obs
                }
                supabase.table("colaboradores").update(atualizacao).eq("id", id_colaborador).execute()
                return True
            return False
        except Exception as e:
            st.error(f"Erro ao editar dados: {e}")
            return False

    # --- INTERFACE PRINCIPAL ---
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title("Gestão de Escala e Ocorrências")
    with col2:
        if st.button("Sair"):
            st.session_state["autenticado"] = False
            st.session_state["regiao"] = None
            st.rerun()

    menu = st.sidebar.selectbox("Navegação", ["Lançamento de Ocorrências", "Movimentação de Pessoal", "Relatório de Fechamento"])
    df_base = carregar_base()

    if not df_base.empty:
        if menu == "Lançamento de Ocorrências":
            st.header("Registro Diário de Ocorrências")
            
            escolas = df_base["escola"].dropna().unique().tolist()
            escola_selecionada = st.selectbox("Selecione a Unidade Escolar:", [""] + escolas)
            
            if escola_selecionada:
                cuidadores_escola = df_base[df_base["escola"] == escola_selecionada]["cuidador"].tolist()
                cuidador_selecionado = st.selectbox("Selecione o Colaborador:", [""] + cuidadores_escola)
                
                if cuidador_selecionado:
                    with st.form("form_evento", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            data_evento = st.date_input("Data da Ocorrência:")
                        with col2:
                            tipo_evento = st.selectbox("Tipo de Evento:", ["Falta", "Atestado", "Diária", "Dobra"])
                        
                        observacao = st.text_area("Observação / Justificativa:")
                        submit = st.form_submit_button("Salvar Ocorrência")
                        
                        if submit:
                            salvar_evento(data_evento, escola_selecionada, cuidador_selecionado, tipo_evento, observacao)
                            st.success("Ocorrência salva na nuvem com sucesso!")

        elif menu == "Movimentação de Pessoal":
            st.header("Desligamento e Nova Contratação")
            
            escolas = df_base["escola"].dropna().unique().tolist()
            escola_selecionada = st.selectbox("Selecione a Escola do Posto:", [""] + escolas)
            
            if escola_selecionada:
                cuidadores_escola = df_base[df_base["escola"] == escola_selecionada]["cuidador"].tolist()
                cuidador_antigo = st.selectbox("Colaborador a ser substituído (ou VAGO):", [""] + cuidadores_escola)
                
                if cuidador_antigo:
                    with st.form("form_substituicao"):
                        col1, col2 = st.columns(2)
                        with col1:
                            novo_nome = st.text_input("Nome Completo do Novo Colaborador:")
                        with col2:
                            novo_cpf = st.text_input("CPF do Novo Colaborador (apenas números):")
                        
                        submit_troca = st.form_submit_button("Confirmar Substituição")
                        
                        if submit_troca:
                            if novo_nome and novo_cpf:
                                sucesso = substituir_colaborador(escola_selecionada, cuidador_antigo, novo_nome, novo_cpf)
                                if sucesso:
                                    st.success(f"Substituição concluída! {novo_nome} agora ocupa o posto no banco de dados.")
                                    time.sleep(2)
                                    st.rerun()
                            else:
                                st.error("Preencha o Nome e o CPF.")

        elif menu == "Relatório de Fechamento":
            st.header("Fechamento do Mês")
            df_eventos = carregar_eventos()
            
            if not df_eventos.empty:
                st.subheader("Histórico Detalhado (Dia a Dia)")
                st.dataframe(df_eventos, use_container_width=True)
                
                csv_detalhado = df_eventos.to_csv(index=False).encode('utf-8')
                st.download_button("Baixar Histórico (CSV)", data=csv_detalhado, file_name="Historico_Ocorrencias.csv", mime="text/csv")
                st.markdown("---")
                
                st.subheader("Resumo Somado por Colaborador")
                resumo_eventos = pd.crosstab(df_eventos["cuidador"], df_eventos["tipo_evento"]).reset_index()
                df_fixo = df_base[["cuidador", "escola", "carga_horaria"]]
                relatorio_final = pd.merge(df_fixo, resumo_eventos, on="cuidador", how="left").fillna(0)
                
                for col in ["Falta", "Atestado", "Diária", "Dobra"]:
                    if col in relatorio_final.columns:
                        relatorio_final[col] = relatorio_final[col].astype(int)
                
                st.dataframe(relatorio_final, use_container_width=True)
                csv_resumo = relatorio_final.to_csv(index=False).encode('utf-8')
                st.download_button("Baixar Resumo para Pagamento (CSV)", data=csv_resumo, file_name="Resumo_Pagamento.csv", mime="text/csv")
            else:
                st.info("Nenhuma ocorrência registrada até o momento.")
    else:
        st.warning("O banco de dados ainda está vazio! Carregue os cuidadores no painel do Supabase.")
