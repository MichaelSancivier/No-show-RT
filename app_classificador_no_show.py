# -*- coding: utf-8 -*-
# app_classificador_no_show.py

import io
import re
from datetime import datetime
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# Aparência (toque azul-amarelo leve via CSS)
# ---------------------------------------------------------
st.set_page_config(page_title="Classificação No-show", layout="wide")
st.markdown("""
<style>
/* caixas info azul */
.stAlert[data-baseweb="notification"] {
  border-left: 6px solid #1e3a8a !important;
}
.stAlert[data-baseweb="notification"] .st-bz {
  color: #0f172a !important;
}

/* exemplos em verde */
.stAlert[data-baseweb="notification"] .st-c0 {
  color: #064e3b !important;
}

/* botões principais */
.stButton>button {
  background: #0b2948 !important;
  color: #fff !important;
  border-radius: 10px !important;
  padding: 0.6rem 1rem !important;
  border: none !important;
}
.stButton>button:hover {
  opacity: .95;
}

/* campo amarelo */
textarea, .stTextArea textarea {
  background: #fffde7 !important;
  border: 1px solid #facc15 !important;
}

/* borda azul */
input, .stTextInput>div>div>input {border: 1px solid #93c5fd;}
</style>
""")

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------
def slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-ZÀ-ÿ/ _-]+", "", str(s or ""))
    s = s.strip().lower()
    s = (s.replace("ç", "c").replace("á","a").replace("à","a").replace("â","a").replace("ã","a")
           .replace("é","e").replace("ê","e").replace("í","i")
           .replace("ó","o").replace("ô","o").replace("õ","o")
           .replace("ú","u").replace("ü","u"))
    s = s.replace("/", "_")
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")

def normalize_token(token: str) -> str:
    """
    Normaliza os [TOKENS] do catálogo para chaves de campos.
    Suporta sufixos numéricos: [DATA 2], [HORA 3], [DATA/HORA 2], etc.
    """
    t = slug(token)

    # Descrever problema
    if ("descr" in t) and ("problem" in t):
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
        "numero": "asm",  # no texto de instabilidade, [NÚMERO] é a ASM

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
        # === aliases adicionados ===
        "erro_de_agendamento_encaixe": "motivo",
        "demanda_excedida": "motivo",
        "descreva_situacao": "item",
        "descreva_situacao": "item",
    }

    if t in ("descreva", "descrever", "descrever_problema", "descrever_o_problema",
             "descreva_o_problema", "descricao_do_problema"):
        return "descreber_o_problema"

    return mapping.get(t, t)

def build_mask(template: str, values: dict) -> str:
    """
    Substitui [TOKENS] do template pelos valores digitados.
    - [DATA/HORA]    -> data + hora (par 1)
    - [DATA/HORA 2]  -> data_2 + hora_2 (par 2)
    - [DATA/HORA 3]  -> data_3 + hora_3 (par 3)
    - [DATA], [DATA 2], [HORA], [HORA 3] etc. também funcionam.
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
            rep = (f"{d} - {h}" if d and h else (d or h or ""))
            text = text.replace(f"[{tok}]", rep)
            continue

        # chave normalizada direta
        if norm in values and values.get(norm, "") != "":
            text = text.replace(f"[{tok}]", values.get(norm, "").strip())
            continue

        # fallback por slug literal
        s = slug(tok)
        if s in values and values.get(s, "") != "":
            text = text.replace(f"[{tok}]", values.get(s, "").strip())
            continue

        # se não encontrou, apaga o token
        text = text.replace(f"[{tok}]", "")

    # limpeza de espaços duplos
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

# =========================================================
# Catálogo de 23 MOTIVOS (idêntico ao aprovado, com ajustes de máscaras)
# =========================================================
CATALOGO = [
    # 1) Alteração do tipo de serviço – De assistência para reinstalação
    {
        "id": "alteracao_tipo_servico",
        "titulo": "Alteração do tipo de serviço  – De assistência para reinstalação",
        "acao": "Inserir ação no histórico da OS e entrar em contato com a central para cancelamento",
        "quando_usar": "Quando houve alteração no tipo de serviço d...ealizado, e será necessário uma reinstalação completa.",
        "exemplos": [
            "1) O cliente trouxe o veículo para assistên... mas será necessário fazer uma Reinstalação. Cliente voltará no dia seguinte.",
            "2) Necessário uma reinstalação completa, sem tempo hábil para realizar o atendimento."
        ],
        "campos": campos("Descreber o Problema", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] compareceu para atendimento..., mas por [DESCREVER O PROBLEMA], será necessário realizar Reinstalação."
        }]
    },

    # 2) Atendimento Improdutivo – Ponto Fixo/Móvel
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
            "template": "Veículo compareceu para atendimento, porém por [DESCREVER O PROBLEMA], não foi possível realizar o serviço."
        }]
    },

    # 3) Cancelada a Pedido do Cliente
    {
        "id": "pedido_cliente",
        "titulo": "Cancelada a Pedido do Cliente",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o cliente solicita o cancelamento do agendamento.",
        "exemplos": [],
        "campos": campos("Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] solicitou cancelamento d... agendamento no dia [DATA/HORA]."
        }]
    },

    # 4) Cliente não enviou veículo – Operação especial (sem envio)
    {
        "id": "sem_envio_veiculo",
        "titulo": "Cliente não enviou veículo – Operação especial (sem envio de veículo)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o atendimento era operação especial...nviou veículo e precisa cancelar.",
        "exemplos": [],
        "campos": campos(),
        "mascaras": [{
            "id": "sem_os",
            "rotulo": "Operação especial (sem envio de veículo)",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente não enviou veículo para atendimento."
        }]
    },

    # 6) Erro De Agendamento - Cliente desconhecia o agendamento
    {
        "id": "erro_cliente_desconhecia",
        "titulo": "Erro De Agendamento - Cliente desconhecia o agendamento",
        "acao": "Cancelar agendamento",
        "quando_usar": "OS foi agendada sem que o cliente tivesse ciência. Neste caso deve ser incluído canal de cancelamento e canal de contato (preferencialmente canal que seja possível confirmar o cancelamento).",
        "exemplos": [],
        "campos": campos("Canal", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] desconhecia o agendamento. Cancelamento realizado pelo canal [CANAL] no dia [DATA/HORA]."
        }]
    },

    # 7) Erro de Agendamento – Sem intervalo mínimo
    {
        "id": "erro_sem_intervalo",
        "titulo": "Erro de Agendamento – Sem intervalo mínimo entre OS/instalação",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando houve erro e não respeitou o interva...o para teste/reinstalação.",
        "exemplos": [],
        "campos": campos("Tipo erro", "Explique", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "OS agendada apresentou erro de [TIPO] e. ... Realizado o contato com o cliente [NOME], no dia [DATA/HORA]."
        }]
    },

    # 9) Erro de Agendamento – O.S. agendada incorretamente
    {
        "id": "erro_os_incorreta",
        "titulo": "Erro de Agendamento – O.S. agendada incorretamente (tipo/motivo/produto)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando a OS foi agendada com tipo, motivo... serviço não condizente com o solicitado.",
        "exemplos": [],
        "campos": campos("Tipo erro", "Explique", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "OS agendada com erro de [TIPO]. Explicaç... Realizado contato com [NOME] no dia [DATA/HORA]."
        }]
    },

    # 10) Erro de Roteirização – Ponto Móvel
    {
        "id": "erro_roteirizacao_movel",
        "titulo": "Erro de Roteirização – Ponto Móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Roteirização inadequada do atendimento móvel.",
        "exemplos": [],
        "campos": campos("Descreber o Problema", "Especialista", "Data", "Hora", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento ... agendamento. Especialista [ESPECIALISTA] informado às [DATA/HORA 2]."
        }]
    },

    # 11) Falta De Equipamento - Acessórios Imobilizado
    {
        "id": "falta_acessorios_imobilizado",
        "titulo": "Falta De Equipamento - Acessórios Imobilizado",
        "acao": "Cancelar agendamento",
        "quando_usar": "Falta de acessórios que estão alocados (i...atendimento, impedindo a realização do serviço agendado.",
        "exemplos": ["Agendamento precisara ser cancelado, pois ... o mesmo foi pedido para a distribuição mas ainda não chegou."],
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
        "quando_usar": "Material reservado está incompatível com o modelo ou serviço solicitado, mesmo estando disponível no estoque.",
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
        "quando_usar": "Quando não há material/insumo necessário ... atendimento.",
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
        "quando_usar": "Quando o principal item/equipamento não e... atendimento.",
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

    # 15) Instabilidade de Equipamento/Sistema (3 datas/horas)
    {
        "id": "instabilidade_sistema",
        "titulo": "Instabilidade de Equipamento/Sistema",
        "acao": "Contatar a central para conclusão; se não possível, registrar ação com nº da ASM.",
        "quando_usar": "Quando deu problema no sistema ou no equip...tendimentos e necessidade de reagendamento.",
        "exemplos": [],
        "campos": campos("Equipamento/Sistema", "Número", "Data", "Hora", "Data", "Hora", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento ... equipamento/sistema [EQUIPAMENTO/SISTEMA], ASM nº [ASM]."
        }]
    },

    # 16) Cliente ausente
    {
        "id": "cliente_ausente",
        "titulo": "Cliente Ausente",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o cliente não comparece no horário e local combinados.",
        "exemplos": [],
        "campos": campos("Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] ausente no local/horário c...aviso no dia [DATA/HORA]."
        }]
    },

    # 17) Cliente cancelou no local
    {
        "id": "cliente_cancelou_local",
        "titulo": "Cliente cancelou no local",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o cliente cancela no local do atendimento.",
        "exemplos": [],
        "campos": campos("Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] cancelou no local em [DATA/HORA]."
        }]
    },

    # 18) Local não adequado
    {
        "id": "local_inadequado",
        "titulo": "Local não adequado",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o local não oferece condições mínimas para executar o serviço.",
        "exemplos": [],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por [DESCREVER O PROBLEMA]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 19) Ocorrência – Atendimento interrompido (não concluído)
    {
        "id": "oc_tecnico_nao_concluido",
        "titulo": "Ocorrência - Atendimento Interrompido (não concluído)",
        "acao": "Cancelar agendamento",
        "quando_usar": " Quando houve interrupção do atendimento (c...nte por outro motivo) e a OS não foi concluída.",
        "exemplos": [],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento. ... [DATA/HORA] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 20) Ocorrência – Sem tempo hábil (Não iniciado)
    {
        "id": "oc_tecnico_nao_iniciado",
        "titulo": "Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Não iniciado)",
        "acao": "Cancelar agendamento",
        "quando_usar": " Quando não houve tempo suficiente por erro ... atraso em OS anterior ou roteirização ruim e o atendimento não foi iniciado.",
        "exemplos": [" Atendimento anterior demorou muito mais que o previsto e inviabilizou o próximo."],
        "campos": campos("Motivo", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Motivo: [MOTIVO]. Cliente [NOME] informado do reagendamento."
        }]
    },

    # 21) Técnico sem habilidade
    {
        "id": "oc_tecnico_sem_habilidade",
        "titulo": "Ocorrência Com Técnico - Técnico Sem Habilidade Para Realizar Serviço",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o representante técnico identifica...realizado, devido a falta de habilidade específica do técnico.",
        "exemplos": ["Atendimento roteirizado na agenda do técni...or sem a habilidade necessária para a realização do serviço"],
        "campos": campos("Descreber o Problema", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado devido a [DESCREVER O PROBLEMA]. Cliente [NOME] informado."
        }]
    },

    # 22) Cliente direcionado para Loja
    {
        "id": "direcionado_loja",
        "titulo": "Cliente Direcionado para Loja",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o cliente é redirecionado para retirar o equipamento na loja.",
        "exemplos": [],
        "campos": campos("Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME] direcionado para loja em [DATA/HORA]."
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

# ---------------------------------------------------------
# Estado e cache de linhas
# ---------------------------------------------------------
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []
if "reset_token" not in st.session_state:
    st.session_state.reset_token = 0

# =========================================================
# UI principal
# =========================================================
st.markdown("**Ferramenta para identificar como classificar No-show.**")

# Campo opcional de OS (antes do seletor de motivos)
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
# Bloquinho com Ação, Quando usar, Exemplos
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

# Alternativas de máscara (se houver)
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

# --------- BLOCO DE INPUTS (com chaves únicas e numeradas) ----------
valores = {}
erros = []
counts_by_name = {}
counts_by_label = {}

for idx, c in enumerate(motivo["campos"]):
    base_name = c["name"]
    label = c["label"]
    req = bool(c.get("required", False)) or (base_name in obrig_extra)

    occ = counts_by_name.get(base_name, 0) + 1
    counts_by_name[base_name] = occ
    eff_name = base_name if occ == 1 else f"{base_name}_{occ}"

    widget_key = f"inp_{motivo['id']}_{idx}_{eff_name}_{st.session_state.reset_token}"

    # rótulos explícitos para campos repetidos (quando fizer sentido)
    pretty_label = label
    if label.lower().startswith("data") or label.lower().startswith("hora"):
        # exemplos de rotulagem mais clara por motivo
        if motivo["id"] == "instabilidade_sistema":
            explicitos = {
                1: ("Data do fim do atendimento", "Hora do fim do atendimento"),
                2: ("Data do teste/reinstalação", None),
                3: ("Data do contato com a central", "Hora do contato com a central")
            }
            pair = explicitos.get(occ, (None, None))
            if label.lower().startswith("data") and pair[0]:
                pretty_label = pair[0]
            if label.lower().startswith("hora") and pair[1]:
                pretty_label = pair[1]
        elif motivo["id"] == "erro_roteirizacao_movel":
            explicitos = {
                1: ("Data do contato com o cliente", "Hora do contato com o cliente"),
                2: (None, "Hora do contato com o especialista")
            }
            pair = explicitos.get(occ, (None, None))
            if label.lower().startswith("data") and pair[0]:
                pretty_label = pair[0]
            if label.lower().startswith("hora") and pair[1]:
                pretty_label = pair[1]

    val = st.text_input(
        pretty_label,
        value="",
        placeholder=c.get("placeholder", ""),
        key=widget_key
    ).strip()

    valores[eff_name] = val
    if req and not valores.get(eff_name, ""):
        erros.append(f"Preencha o campo obrigatório: **{pretty_label}**")
# --------------------------------------------------------------------

st.markdown("**3. Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
template = alternativa.get("template", "")
mascara = build_mask(template, valores)
mascara_editada = st.text_area(
    "Máscara gerada",
    value=mascara,
    key=f"mask_{motivo['id']}_{st.session_state.reset_token}",
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

        # incluir todos os campos preenchidos (com rótulos numerados quando repetem)
        counts_by_name = {}
        counts_by_label = {}
        for idx, c in enumerate(motivo["campos"]):
            base_name = c["name"]
            label = c["label"]
            occ = counts_by_name.get(base_name, 0) + 1
            counts_by_name[base_name] = occ
            eff_name = base_name if occ == 1 else f"{base_name}_{occ}"

            occ_label = counts_by_label.get(label, 0) + 1
            counts_by_label[label] = occ_label
            col_label = label if occ_label == 1 else f"{label} {occ_label}"

            registro[col_label] = valores.get(eff_name, "")

        st.session_state.LINHAS.append(registro)
        st.success("Linha adicionada.")

if baixar:
    df = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
    if df.empty:
        st.info("Nada para exportar ainda.")
    else:
        # Fallback esperto: openpyxl -> xlsxwriter -> CSV
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
