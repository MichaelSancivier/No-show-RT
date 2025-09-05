import io
from datetime import datetime
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Classificação No-show", layout="wide")
st.title("Classificação No-show")

# =========================================================
# Helpers
# =========================================================
def canon(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z_ ]+", "", str(s or ""))
    s = re.sub(r"\s+", "_", s.strip())
    return s.lower()

def read_catalog_from_excel_like_yours(file) -> list[dict]:
    """
    Lê o layout do seu Excel (3 tabelas lado a lado) na Planilha1:
      [0..10]  -> Tabela 1: Motivos/Quando/Exemplos/Texto mascara/dado1..dado7 (header na linha 1)
      [13..15] -> Tabela 2: #/Motivos/Ação sistêmica (header na linha 1)
      [18..19] -> Tabela 3: Campo/exemplo (header na linha 1)
    Retorna lista de motivos no formato do app.
    """
    df = pd.read_excel(file, sheet_name="Planilha1", engine="openpyxl")

    # --- Tabela 1
    hdr_row = 1  # cabeçalho na linha 1 (0-base = 1)
    tbl1 = df.iloc[hdr_row+1:, 0:11].copy()
    tbl1.columns = ["Motivos","Quando usar","Exemplos","Texto mascara","dado1","dado2","dado3","dado4","dado5","dado6","dado7"]
    tbl1 = tbl1.dropna(how="all")

    # --- Tabela 2
    tbl2 = df.iloc[hdr_row:, 13:16].copy()
    tbl2.columns = ["#","Motivos","Ação sistêmica"]
    tbl2 = tbl2.iloc[1:]  # remove linha de rótulo '#'
    acao_map = {}
    for _, r in tbl2.iterrows():
        mot = str(r["Motivos"]).strip()
        acao_map[mot] = str(r["Ação sistêmica"] or "").strip()

    # --- Tabela 3
    tbl3 = df.iloc[hdr_row:, 18:20].copy()
    tbl3.columns = ["Campo","exemplo"]
    tbl3 = tbl3.iloc[1:]  # remove linha de header
    placeholder_map = {canon(r["Campo"]): str(r["exemplo"] or "").strip() for _, r in tbl3.iterrows() if str(r["Campo"]).strip()}

    # --- Monta catálogo
    motivos = []
    for _, r in tbl1.iterrows():
        titulo = str(r["Motivos"]).strip()
        if not titulo:
            continue

        quando = str(r["Quando usar"] or "").strip()
        exemplos_txt = str(r["Exemplos"] or "").replace("\r","\n")
        exemplos = [p.strip() for p in re.split(r"\n|;|\|\|", exemplos_txt) if p.strip()]

        # Campos: dado1..dado7
        campos = []
        for col in ["dado1","dado2","dado3","dado4","dado5","dado6","dado7"]:
            val = str(r[col]).strip() if not pd.isna(r[col]) else ""
            if not val:
                continue
            name = slug(val)            # nome técnico
            label = val                 # rótulo como vem da planilha
            ph = placeholder_map.get(canon(val), "")
            campos.append({"name": name, "label": label, "placeholder": ph, "required": True})

        texto_mascara = str(r["Texto mascara"] or "").strip()

        # Ação sistêmica
        acao = acao_map.get(titulo, "Cancelar agendamento")

        motivo_dict = {
            "id": slug(titulo),
            "titulo": titulo,
            "acao": acao,
            "quando_usar": quando,
            "exemplos": exemplos,
            "campos": campos,
        }

        # --- Regra especial: duas alternativas para Cronograma de Instalação/Substituição de Placa
        if "cronograma de instalação/substituição de placa" in canon(titulo):
            alternativas = []
            if texto_mascara:
                alternativas.append(texto_mascara)
            # segunda alternativa vinda da sua documentação
            alternativas.append("Operação especial, não foi atendido veículo como substituição.")
            motivo_dict["mascara_opcoes"] = alternativas
        else:
            motivo_dict["mascara_opcoes"] = [texto_mascara] if texto_mascara else [""]

        motivos.append(motivo_dict)

    return motivos

# =========================================================
# Estado
# =========================================================
if "CATALOGO" not in st.session_state:
    st.session_state.CATALOGO = None
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []

# =========================================================
# Upload do Catálogo (Excel)
# =========================================================
st.markdown("### Carregar catálogo (Excel da documentação)")
up = st.file_uploader("Selecione o Excel (.xlsx) com as 3 tabelas (como o que você enviou)", type=["xlsx"])

if up and st.button("Processar catálogo"):
    try:
        st.session_state.CATALOGO = read_catalog_from_excel_like_yours(up)
        st.success(f"Catálogo carregado: {len(st.session_state.CATALOGO)} motivo(s).")
    except Exception as e:
        st.error(f"Falha ao processar catálogo: {e}")

if not st.session_state.CATALOGO:
    st.info("Envie o Excel e clique em **Processar catálogo** para começar.")
    st.stop()

CAT = st.session_state.CATALOGO
motivos_map = {m["titulo"]: m for m in CAT}

# =========================================================
# UI principal
# =========================================================
st.markdown("---")
st.markdown("1) **Motivos – selecionar um aqui:**")
motivo_titulo = st.selectbox("Motivo", list(motivos_map.keys()), index=0, label_visibility="collapsed")
motivo = motivos_map[motivo_titulo]

st.markdown("2) **Preencher as informações solicitadas.**")
col_esq, col_dir = st.columns([1.05, 1])

with col_esq:
    st.subheader("Dados")
    valores = {}
    erros = []
    for campo in motivo["campos"]:
        key = campo["name"]
        lbl = campo["label"]
        ph  = campo.get("placeholder","")
        req = bool(campo.get("required", True))
        val = st.text_input(lbl, value="", placeholder=ph, key=f"{motivo['id']}_{key}")
        valores[key] = val.strip()
        if req and not valores[key]:
            erros.append(f"Preencha o campo obrigatório: **{lbl}**")

    # Se houver mais de uma máscara, deixar o usuário escolher
    opcoes = motivo.get("mascara_opcoes", [""])
    versao_label = None
    if len(opcoes) > 1:
        versao_label = st.selectbox("Versão da máscara", [f"Alternativa {i+1}" for i in range(len(opcoes))])
        idx = int(versao_label.split()[-1]) - 1
        mascara_template = opcoes[idx]
    else:
        mascara_template = opcoes[0]

    # Tenta preencher placeholders por nome do campo (substituição básica)
    mascara_final = mascara_template
    for c in motivo["campos"]:
        placeholder = "{" + c["name"] + "}"
        if placeholder in mascara_final:
            mascara_final = mascara_final.replace(placeholder, valores.get(c["name"], ""))

    st.markdown("3) **Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
    st.text_area("Máscara gerada", value=mascara_final, height=110, label_visibility="collapsed")

    c1, c2, c3 = st.columns(3)
    add = c1.button("Adicionar à tabela")
    clear = c2.button("Limpar campos")
    exp = c3.button("Baixar Excel")

    if add:
        if erros:
            for e in erros:
                st.warning(e)
        else:
            linha = {
                "Motivo": motivo["titulo"],
                "Ação sistêmica": motivo.get("acao",""),
                "Quando usar": motivo.get("quando_usar",""),
                "Máscara": mascara_final,
            }
            for c in motivo["campos"]:
                linha[c["label"]] = valores.get(c["name"], "")
            # registra qual alternativa foi usada (se aplicável)
            if versao_label:
                linha["Versão máscara"] = versao_label
            st.session_state.LINHAS.append(linha)
            st.success("Linha adicionada.")

    if clear:
        for c in motivo["campos"]:
            st.session_state[f"{motivo['id']}_{c['name']}"] = ""

    if exp:
        df = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
        if df.empty:
            st.info("Nada para exportar ainda.")
        else:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df.to_excel(w, index=False, sheet_name="No-show")
            st.download_button(
                "Baixar Excel (No-show)",
                data=buf.getvalue(),
                file_name=f"no_show_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

with col_dir:
    st.subheader("O que fazer?")
    st.info(motivo.get("acao",""))
    st.subheader("Quando usar?")
    st.info(motivo.get("quando_usar",""))
    st.subheader("Exemplos")
    exs = motivo.get("exemplos", []) or []
    if not exs:
        st.caption("Sem exemplos cadastrados.")
    for ex in exs:
        st.success(ex)

st.markdown("---")
st.subheader("Prévia da tabela")
df_prev = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
st.dataframe(df_prev, use_container_width=True)
