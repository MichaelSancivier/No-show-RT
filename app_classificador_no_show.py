# -*- coding: utf-8 -*-
# app_classificador_no_show.py
# Modelo híbrido: máscaras corrigidas + aliases mínimos
# Atualiza a máscara (campo amarelo) automaticamente ao mudar seleção/campos.

import io
import re
import json
import hashlib
from datetime import datetime
import pandas as pd
import streamlit as st

# =========================
# Aparência e Config
# =========================
st.set_page_config(page_title="Classificação No-show", layout="wide")
st.markdown("""
<style>
/* caixas info azul */
.stAlert[data-baseweb="notification"] { border-left: 6px solid #1e3a8a !important; }
.stAlert[data-baseweb="notification"] .st-bz { color: #0f172a !important; }

/* exemplos em verde */
.stAlert[data-baseweb="notification"] .st-c0 { color: #064e3b !important; }

/* botões */
.stButton>button {
  background: #0b2948 !important; color: #fff !important;
  border-radius: 10px !important; padding: 0.6rem 1rem !important; border: none !important;
}
.stButton>button:hover { opacity: .95; }

/* campo amarelo */
textarea, .stTextArea textarea {
  background: #fffde7 !important; border: 1px solid #facc15 !important;
}

/* borda inputs */
input, .stTextInput>div>div>input { border: 1px solid #93c5fd; }
</style>
""")

# =========================
# Utils
# =========================
def slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-ZÀ-ÿ/ _-]+", "", str(s or ""))
    s = s.strip().lower()
    s = (s.replace("ç","c").replace("á","a").replace("à","a").replace("â","a").replace("ã","a")
           .replace("é","e").replace("ê","e").replace("í","i")
           .replace("ó","o").replace("ô","o").replace("õ","o")
           .replace("ú","u").replace("ü","u"))
    s = s.replace("/", "_")
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")

def normalize_token(token: str) -> str:
    """
    Normaliza [TOKENS] para chaves dos campos.
    Suporta [DATA/HORA], [DATA/HORA 2], [DATA 3], etc.
    Também une variações como [DESCREVER O PROBLEMA] -> descreber_o_problema.
    """
    t = slug(token)

    # Qualquer variação contendo "descr" + "problema" vira o campo do input azul
    if ("descr" in t) and ("problema" in t):
        return "descreber_o_problema"

    # DATA/HORA 1..N
    m = re.match(r"^data_hora(?:_(\d+))?$", t)
    if m:
        n = m.group(1)
        if not n or n == "1":
            return "__DATAHORA__"
        return f"__DATAHORA{n}__"

    # DATA 1..N
    m = re.match(r"^data(?:_(\d+))?$", t)
    if m:
        n = m.group(1)
        return "data" if not n or n == "1" else f"data_{n}"

    # HORA 1..N
    m = re.match(r"^hora(?:_(\d+))?$", t)
    if m:
        n = m.group(1)
        return "hora" if not n or n == "1" else f"hora_{n}"

    mapping = {
        # nomes
        "nome": "nome",
        "cliente": "nome",
        "nome_cliente": "nome",
        "nome_tecnico": "nome_tecnico",
        "tecnico": "nome_tecnico",

        # canais / papéis
        "canal": "canal",
        "especialista": "especialista",

        # numerações
        "numero_ordem_de_servico": "numero_os",
        "numero_os": "numero_os",
        "numero": "asm",  # em alguns textos de instabilidade, [NÚMERO] é a ASM

        # erro/tipo/explicação
        "tipo": "tipo_erro",
        "tipo_erro": "tipo_erro",
        "explique_a_situacao": "explique",
        "explique": "explique",

        # equipamento / sistema
        "equipamento_sistema": "equipamento_sistema",

        # outros
        "asm": "asm",
        "motivo": "motivo",
        "item": "item",

        # ==== ALIASES MÍNIMOS (LEGADO) ====
        "erro_de_agendamento_encaixe": "motivo",
        "demanda_excedida": "motivo",
        "descreva_situacao": "item",
        "descreva_situação": "item",
    }

    # fallback para descrições
    if t in ("descreva", "descrever", "descrever_problema", "descrever_o_problema",
             "descreva_o_problema", "descricao_do_problema"):
        return "descreber_o_problema"

    return mapping.get(t, t)

def build_mask(template: str, values: dict) -> str:
    """
    Substitui [TOKENS] pelos valores dos campos.
    - [DATA/HORA], [DATA/HORA 2], [DATA], [HORA], etc.
    Remove tokens desconhecidos.
    """
    text = str(template or "")
    tokens = re.findall(r"\[([^\]]+)\]", text)
    for tok in tokens:
        norm = normalize_token(tok)

        # DATA/HORA 1..N
        if norm.startswith("__DATAHORA"):
            if norm == "__DATAHORA__":
                d_key, h_key = "data", "hora"
            elif norm == "__DATAHORA2__":
                d_key, h_key = "data_2", "hora_2"
            elif norm == "__DATAHORA3__":
                d_key, h_key = "data_3", "hora_3"
            else:
                d_key, h_key = "data", "hora"
            d = values.get(d_key, "").strip()
            h = values.get(h_key, "").strip()
            rep = (f"{d} {h}".strip())
            text = text.replace(f"[{tok}]", rep)
            continue

        # chave normalizada direta
        if norm in values and values.get(norm, "") != "":
            text = text.replace(f"[{tok}]", values.get(norm, "").strip())
            continue

        # fallback por slug literal do token
        s = slug(tok)
        if s in values and values.get(s, "") != "":
            text = text.replace(f"[{tok}]", values.get(s, "").strip())
            continue

        # se nada mapeou -> apaga o token
        text = text.replace(f"[{tok}]", "")

    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

def campos(*labels):
    out = []
    for lbl in labels:
        if not lbl:
            continue
        out.append({
            "name": slug(lbl),
            "label": lbl,
            "placeholder": "",
            "required": True
        })
    return out

# =========================
# Catálogo de motivos (com as máscaras corrigidas)
# =========================
CATALOGO = [
    {
        "id": "improdutivo_ponto_fixo_movel",
        "titulo": "Atendimento Improdutivo – Ponto Fixo/Móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o veículo está presente mas não foi possível realizar o serviço por fatores externos (chuva ou local sem condição).",
        "exemplos": [
            "1) O cliente trouxe o veículo, ele compareceu para atendimento, mas o veículo apresentou falhas elétrica.",
            "2) O local para atendimento não possuía cobertura para atendimento. (chuva, etc.)."
        ],
        "campos": campos("Descreber o Problema"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            # Observação: [DESCREVER O PROBLEMA] será normalizado -> descreber_o_problema
            "template": "Veículo compareceu para atendimento, porém por [DESCREVER O PROBLEMA], não foi possível realizar o serviço."
        }]
    },

    # 11) Falta De Equipamento - Acessórios Imobilizado
    {
        "id": "falta_acessorios_imobilizado",
        "titulo": "Falta De Equipamento - Acessórios Imobilizado",
        "acao": "Cancelar agendamento",
        "quando_usar": "Falta de acessórios que estão alocados (imobilizado) e impedem o atendimento.",
        "exemplos": ["Agendamento precisará ser cancelado, material ainda não chegou."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 12) Falta De Equipamento - Item Reservado Não Compatível
    {
        "id": "falta_item_reservado_incompativel",
        "titulo": "Falta De Equipamento - Item Reservado Não Compatível",
        "acao": "Cancelar agendamento",
        "quando_usar": "Material reservado incompatível com o modelo/serviço solicitado.",
        "exemplos": [],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 13) Falta de Material
    {
        "id": "falta_material",
        "titulo": "Falta de Material",
        "acao": "Cancelar agendamento",
        "quando_usar": "Não há material/insumo necessário para o atendimento.",
        "exemplos": [],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 14) Falta do Item Principal
    {
        "id": "falta_principal",
        "titulo": "Falta do Item Principal",
        "acao": "Cancelar agendamento",
        "quando_usar": "Item principal indisponível impede o atendimento.",
        "exemplos": [],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 20) Ocorrência – Sem tempo hábil (Não iniciado)
    {
        "id": "oc_tecnico_nao_iniciado",
        "titulo": "Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Não iniciado)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Sem tempo suficiente por erro de agendamento/atraso anterior/roteirização ruim e o atendimento não foi iniciado.",
        "exemplos": ["Atendimento anterior demorou mais que o previsto e inviabilizou o próximo."],
        "campos": campos("Motivo", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Motivo: [MOTIVO]. Cliente [NOME] informado do reagendamento."
        }]
    },

    # 23) Outras ocorrências (fallback)
    {
        "id": "outras",
        "titulo": "Outras ocorrências",
        "acao": "Registrar conforme orientação",
        "quando_usar": "",
        "exemplos": [],
        "campos": campos("Motivo", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Motivo: [MOTIVO]. Cliente [NOME]."
        }]
    },
]

# (Se precisar de todos os outros motivos do seu catálogo original, você pode colá-los aqui seguindo o mesmo padrão.)

# =========================
# Estado
# =========================
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []
if "reset_token" not in st.session_state:
    st.session_state.reset_token = 0

# =========================
# UI
# =========================
st.title("Classificação No-show")
st.markdown("Ferramenta para identificar como classificar No-show.")

os_consulta = st.text_input(
    "Número da OS (opcional) — podem deixar em branco",
    key=f"os_consulta_{st.session_state.reset_token}"
).strip()

st.markdown("**1. Motivos – selecionar um aqui:**")
motivos_map = {m["titulo"]: m for m in CATALOGO}
motivo_titulo = st.selectbox(
    "",
    list(motivos_map.keys()),
    key=f"motivo_{st.session_state.reset_token}"
)
motivo = motivos_map[motivo_titulo]

st.markdown("**2. Preencher as informações solicitadas.**")
cA, cB = st.columns([1,1])
with cA:
    st.subheader("O que fazer?")
    st.info(motivo.get("acao", ""))
with cB:
    st.subheader("Quando usar?")
    st.info(motivo.get("quando_usar", ""))

st.subheader("Exemplos")
if motivo.get("exemplos"):
    for ex in motivo["exemplos"]:
        st.success(ex)
else:
    st.caption("Sem exemplos cadastrados.")

# Versões de máscara (se houver mais de uma)
alt_labels = [m["rotulo"] for m in motivo["mascaras"]]
alt_idx = 0
if len(alt_labels) > 1:
    alt_idx = st.radio(
        "Versões de texto",
        options=list(range(len(alt_labels))),
        format_func=lambda i: alt_labels[i],
        key=f"alt_{motivo['id']}_{st.session_state.reset_token}",
        horizontal=True
    )
alternativa = motivo["mascaras"][alt_idx]
obrig_extra = set(alternativa.get("regras_obrig", []))

# --------- Inputs (campos azuis) ----------
valores = {}
erros = []
counts_by_name = {}

for idx, c in enumerate(motivo["campos"]):
    base_name = c["name"]
    label = c["label"]
    req = bool(c.get("required", False)) or (base_name in obrig_extra)

    occ = counts_by_name.get(base_name, 0) + 1
    counts_by_name[base_name] = occ
    eff_name = base_name if occ == 1 else f"{base_name}_{occ}"

    widget_key = f"inp_{motivo['id']}_{idx}_{eff_name}_{st.session_state.reset_token}"

    pretty_label = label  # (aqui daria para customizar rótulos duplicados se precisar)
    val = st.text_input(pretty_label, value="", key=widget_key).strip()

    valores[eff_name] = val
    if req and not valores.get(eff_name, ""):
        erros.append(f"Preencha o campo obrigatório: **{pretty_label}**")
# ------------------------------------------

st.markdown("**3. Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
template = alternativa.get("template", "")

# === NONCE: muda a key do text_area quando motivo/campos mudam ===
nonce_source = {"motivo_id": motivo["id"], "alt": alternativa["id"], "campos": valores}
mask_nonce = hashlib.md5(json.dumps(nonce_source, sort_keys=True).encode("utf-8")).hexdigest()[:8]

mascara = build_mask(template, valores)
mascara_editada = st.text_area(
    "Máscara gerada",
    value=mascara,
    key=f"mask_{mask_nonce}",  # recria o widget a cada mudança => sempre reflete os campos atuais
    height=140,
    label_visibility="collapsed"
).strip()

c1, c2, c3, c4 = st.columns(4)
add = c1.button("Adicionar à tabela")
baixar = c2.button("Baixar Excel")
limpar = c4.button("🧹 Nova consulta (limpar tudo)", type="secondary")

if add:
    if erros:
        for e in erros:
            st.warning(e)
    else:
        registro = {
            "Número OS (consulta)": os_consulta,
            "Motivo": motivo["titulo"],
            "Versão máscara": alternativa["rotulo"],
            "Ação sistêmica": motivo.get("acao", ""),
            "Quando usar": motivo.get("quando_usar", ""),
            "Máscara": mascara_editada,
        }
        # incluir campos digitados
        for k, v in valores.items():
            registro[k.upper()] = v
        st.session_state.LINHAS.append(registro)
        st.success("Linha adicionada.")

if baixar:
    df = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
    if df.empty:
        st.info("Nada para exportar ainda.")
    else:
        engine = None
        try:
            import openpyxl  # noqa
            engine = "openpyxl"
        except Exception:
            try:
                import xlsxwriter  # noqa
                engine = "xlsxwriter"
            except Exception:
                pass

        if engine:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine=engine) as writer:
                df.to_excel(writer, index=False, sheet_name="No-show")
            st.download_button(
                "Baixar Excel",
                data=output.getvalue(),
                file_name=f"classificacao_no_show_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Baixar CSV",
                data=csv,
                file_name=f"classificacao_no_show_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

if limpar:
    st.session_state.LINHAS = []
    st.session_state.reset_token += 1
    st.experimental_rerun()

st.markdown("---")
st.subheader("Prévia da tabela")
df_prev = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
st.dataframe(df_prev, use_container_width=True)
