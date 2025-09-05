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
.block-container {padding-top: 1.2rem;}
.stAlert > div {border-left: 0.35rem solid #0ea5e9;}
/* títulos */
h1, h2, h3 {color: #1e3a8a;}
/* cards à direita azuis */
div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"] > div:nth-child(2) .stAlert > div {
  background: #0f3a5d !important; color: #e5f2ff !important; border-radius: 10px;
}
/* área da máscara com borda amarela */
textarea {border: 1.5px solid #fcd34d !important;}
/* labels amarelas */
label {color:#fbbf24;}
/* inputs com borda azul */
input, .stTextInput>div>div>input {border: 1px solid #38bdf8 !important;}
</style>
""", unsafe_allow_html=True)

st.title("Classificação No-show")

# =========================================================
# Helpers
# =========================================================
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
    Faz o mapeamento de sinônimos e ortografias diferentes.
    """
    t = slug(token)

    # ---- Regras especiais amplas para "descrever/descrição do problema"
    # Qualquer token que contenha "descr" e "problem" vira a chave usada no formulário
    if ("descr" in t) and ("problem" in t):
        # nosso campo padrão (mesmo que esteja escrito "Descreber o Problema")
        return "descreber_o_problema"

    # Mapeamentos diretos de sinônimos comuns
    mapping = {
        # nomes
        "nome": "nome",
        "cliente": "nome",
        "nome_cliente": "nome",
        "nome_tecnico": "nome_tecnico",
        "tecnico": "nome_tecnico",

        # data/hora
        "data": "data",
        "hora": "hora",
        "data_hora": "__DATAHORA__",
        "data___hora": "__DATAHORA__",   # variações que aparecem do slug

        # canais / papéis
        "canal": "canal",
        "especialista": "especialista",

        # numerações
        "numero_ordem_de_servico": "numero_os",
        "numero_os": "numero_os",
        "numero": "asm",  # no texto de instabilidade, [NÚMERO] refere-se ao nº da ASM

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
    }

    # variações típicas do "descrever/descrição" que não caíram no if acima
    if t in ("descreva", "descrever", "descrever_problema", "descrever_o_problema",
             "descreva_o_problema", "descricao_do_problema"):
        return "descreber_o_problema"

    return mapping.get(t, t)

def build_mask(template: str, values: dict) -> str:
    """
    Substitui [TOKENS] do template pelos valores digitados.
    [DATA/HORA] é montado a partir de Data + Hora (se existirem).
    Tokens desconhecidos permanecem entre colchetes.
    """
    text = str(template or "")
    tokens = re.findall(r"\[([^\]]+)\]", text)
    for tok in tokens:
        norm = normalize_token(tok)

        if norm == "__DATAHORA__":
            d = values.get("data", "").strip()
            h = values.get("hora", "").strip()
            rep = (f"{d} - {h}" if d and h else (d or h or ""))
            text = text.replace(f"[{tok}]", rep)
            continue

        # tenta por chave normalizada
        if norm in values and values.get(norm, "") != "":
            text = text.replace(f"[{tok}]", values.get(norm, "").strip())
            continue

        # fallback: tenta por slug literal do token
        s = slug(tok)
        if s in values and values.get(s, "") != "":
            text = text.replace(f"[{tok}]", values.get(s, "").strip())
            continue

        # se ainda não substituiu, deixa o token como está

    # pequenos ajustes: remover duplos espaços antes de pontos, etc.
    text = re.sub(r"\s+\.", ".", text)
    return text.strip()

def limpar_tudo():
    """Limpa todos os inputs e força recarregar a tela."""
    if "LINHAS" in st.session_state:
        st.session_state.LINHAS = []
    st.session_state.reset_token = st.session_state.get("reset_token", 0) + 1
    for k in list(st.session_state.keys()):
        if k.startswith(("inp_", "alt_", "mot_sel_")):
            del st.session_state[k]

# =========================================================
# Utilitário para construir lista de campos
# =========================================================
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
# Catálogo de 23 MOTIVOS (regras + campos + máscaras)
# (idênticos ao que combinamos; ajustes mínimos em pontuação)
# =========================================================
CATALOGO = [
    # 1) Alteração do tipo de serviço – De assistência para reinstalação
    {
        "id": "alteracao_tipo_servico",
        "titulo": "Alteração do tipo de serviço  – De assistência para reinstalação",
        "acao": "Inserir ação no histórico da OS e entrar em contato com a central para cancelamento",
        "quando_usar": "Quando durante a prestação de serviço o técnico identificar a necessidade de realizar outro tipo de execução.",
        "exemplos": [
            "1) A OS está como assistência, mas será necessário fazer uma Reinstalação. Cliente voltará no dia seguinte.",
            "2) Necessário uma reinstalação completa, sem tempo hábil para realizar o atendimento."
        ],
        "campos": campos("Descreber o Problema", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [CLIENTE] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 2) Atendimento Improdutivo – Ponto Fixo/Móvel
    {
        "id": "improdutivo_ponto_fixo_movel",
        "titulo": "Atendimento Improdutivo – Ponto Fixo/Móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o veículo está presente mas não foi possível atender (mecânico, elétrico ou condição do veículo). Em móvel, incluir fatores externos.",
        "exemplos": [
            "1) O cliente trouxe o veículo, ele compareceu para atendimento, mas o veículo apresentou falhas elétrica",
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
        "quando_usar": "Quando o próprio cliente solicita o cancelamento do atendimento.",
        "exemplos": [
            "1) Cliente ligou pedindo para remarcar.",
            "2) Ao confirmar, cliente informou indisponibilidade."
        ],
        "campos": campos("Nome", "Canal", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente [NOME], contato via [CANAL] em [DATA/HORA], informou indisponibilidade para o atendimento."
        }]
    },

    # 4) Cancelamento a pedido da RT  (MÁSCARA AJUSTADA)
    {
        "id": "pedido_rt",
        "titulo": "Cancelamento a pedido da RT",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando houver necessidade de cancelamento por parte do representante técnico.",
        "exemplos": ["Devido a situações de atendimento, precisamos cancelar com o cliente."],
        "campos": campos("Descreber o Problema", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] em [DATA/HORA], foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 5) Cronograma de Instalação/Substituição de Placa (2 opções)
    {
        "id": "cronograma_substituicao_placa",
        "titulo": "Cronograma de Instalação/Substituição de Placa",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o atendimento faz parte de cronograma especial pré-acordado / operação especial.",
        "exemplos": [
            "1) Cliente substituiu por essa OS 462270287.",
            "2) Operação especial, sem envio de veículo como substituição."
        ],
        "campos": campos("Número OS"),
        "mascaras": [
            {
                "id": "com_os",
                "rotulo": "Substituição com OS",
                "descricao": "",
                "regras_obrig": ["numero_os"],
                "template": "Realizado atendimento com substituição de placa. Foi realizado a alteração pela OS [NÚMERO ORDEM DE SERVIÇO]."
            },
            {
                "id": "sem_os",
                "rotulo": "Operação especial (sem envio de veículo)",
                "descricao": "",
                "regras_obrig": [],
                "template": "Cliente não enviou veículo para atendimento."
            }
        ]
    },

    # 6) Erro De Agendamento - Cliente desconhecia o agendamento
    {
        "id": "erro_cliente_desconhecia",
        "titulo": "Erro De Agendamento - Cliente desconhecia o agendamento",
        "acao": "Cancelar agendamento",
        "quando_usar": "OS agendada sem o cliente saber previamente.",
        "exemplos": [
            "1) Técnico chegou e cliente disse não ter solicitado.",
            "2) Contato com cliente: desconhecia o agendamento."
        ],
        "campos": campos("Nome Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Em contato com o cliente o mesmo informou que desconhecia o agendamento. Nome cliente: [NOME CLIENTE] / Data contato: [DATA/HORA]."
        }]
    },

    # 7) Erro de Agendamento – Endereço incorreto
    {
        "id": "erro_endereco_incorreto",
        "titulo": "Erro de Agendamento – Endereço incorreto",
        "acao": "Cancelar agendamento",
        "quando_usar": "Endereço incorreto/incompleto inviabilizando chegada.",
        "exemplos": ["Técnico foi para rua X, cliente na rua Y."],
        "campos": campos("Tipo erro", "Descreva", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Erro identificado no agendamento: [TIPO]. Situação: [DESCREVA]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 8) Erro de Agendamento – Falta de informações na O.S.
    {
        "id": "erro_falta_info_os",
        "titulo": "Erro de Agendamento – Falta de informações na O.S.",
        "acao": "Cancelar agendamento",
        "quando_usar": "OS com dados incompletos inviabilizando atendimento.",
        "exemplos": ["Não há solução cadastrada no sistema."],
        "campos": campos("Tipo erro", "Explique", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "OS agendada apresentou erro de [TIPO] e foi identificado através de [EXPLIQUE A SITUAÇÃO]. Realizado o contato com o cliente [NOME], no dia [DATA/HORA]."
        }]
    },

    # 9) Erro de Agendamento – O.S. agendada incorretamente
    {
        "id": "erro_os_incorreta",
        "titulo": "Erro de Agendamento – O.S. agendada incorretamente (tipo/motivo/produto)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Categorização incorreta (tipo/serviço/produto), inviabilizando execução.",
        "exemplos": [
            "1) Cliente pediu assistência e foi agendada instalação por engano.",
            "2) Agendamento no mesmo dia sem autorização."
        ],
        "campos": campos("Tipo erro", "Explique", "Nome", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "OS agendada apresentou erro de [TIPO] e foi identificado através de [EXPLIQUE A SITUAÇÃO]. Realizado o contato com o cliente [NOME], no dia [DATA/HORA]."
        }]
    },

    # 10) Erro de roteirização - Atendimento móvel
    {
        "id": "erro_roteirizacao_movel",
        "titulo": "Erro de roteirização do agendamento - Atendimento móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Falha permitindo agendamento sem considerar deslocamento.",
        "exemplos": ["Técnico sem tempo hábil; comercial informado."],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora", "Especialista", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às [DATA/HORA] foi informado sobre a necessidade de reagendamento. Especialista [ESPECIALISTA] informado às [DATA/HORA]."
        }]
    },

    # 11) Falta De Equipamento - Acessórios Imobilizado
    {
        "id": "falta_acessorios_imobilizado",
        "titulo": "Falta De Equipamento - Acessórios Imobilizado",
        "acao": "Cancelar agendamento",
        "quando_usar": "Acessórios imobilizados em outro atendimento.",
        "exemplos": ["Sem o sensor temperatura NTC 10K; aguardando distribuição."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 12) Falta De Equipamento - Item Reservado Não Compatível
    {
        "id": "falta_item_reservado_incompativel",
        "titulo": "Falta De Equipamento - Item Reservado Não Compatível",
        "acao": "Cancelar agendamento",
        "quando_usar": "Item reservado incompatível com veículo/serviço.",
        "exemplos": ["Instalação não concluída por falta de rastreador compatível."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 13) Falta De Equipamento - Material
    {
        "id": "falta_material",
        "titulo": "Falta De Equipamento - Material",
        "acao": "Cancelar agendamento",
        "quando_usar": "Ausência total de material necessário.",
        "exemplos": ["Falta equipamento ADPLUS."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 14) Falta De Equipamento - Principal
    {
        "id": "falta_principal",
        "titulo": "Falta De Equipamento - Principal",
        "acao": "Cancelar agendamento",
        "quando_usar": "Técnico sem o equipamento principal necessário.",
        "exemplos": ["1) Falta LMU4233. 2) Aguardando RFID."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 15) Instabilidade de Equipamento/Sistema
    {
        "id": "instabilidade_sistema",
        "titulo": "Instabilidade de Equipamento/Sistema",
        "acao": "Contatar a central para conclusão; se não possível, registrar ação com nº da ASM.",
        "quando_usar": "Problema no sistema/equipamento impediu concluir.",
        "exemplos": ["Rastreador não iniciou comunicação com a plataforma."],
        "campos": campos("Data", "Hora", "Equipamento/Sistema", "Data", "Data", "Hora", "ASM"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento finalizado em [DATA/HORA] não concluído devido à instabilidade de [EQUIPAMENTO/SISTEMA]. Registrado teste/reinstalação em [DATA]. Realizado contato com a central [DATA/HORA] e foi gerada a ASM [NÚMERO]."
        }]
    },

    # 16) No-show Cliente – Ponto Fixo/Móvel
    {
        "id": "no_show_cliente",
        "titulo": "No-show Cliente – Ponto Fixo/Móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Cliente não aparece no local (fixo) / indisponível no ponto móvel.",
        "exemplos": ["Veículo em rota; chegou com atraso > 15min."],
        "campos": campos("Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Cliente não compareceu para atendimento até às [HORA]."
        }]
    },

    # 17) No-show Técnico
    {
        "id": "no_show_tecnico",
        "titulo": "No-show Técnico",
        "acao": "Cancelar agendamento",
        "quando_usar": "Técnico não comparece no horário/local.",
        "exemplos": ["Técnico não realizou o atendimento."],
        "campos": campos("Nome Técnico", "Data", "Hora", "Motivo"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Técnico [NOME TÉCNICO], em [DATA/HORA], não realizou o atendimento por motivo de [MOTIVO]."
        }]
    },

    # 18) Ocorrência com Técnico – Não foi possível realizar atendimento
    {
        "id": "oc_tecnico_impossivel",
        "titulo": "Ocorrência com Técnico – Não foi possível realizar atendimento",
        "acao": "Cancelar agendamento",
        "quando_usar": "Questões pessoais/operacionais impediram o atendimento.",
        "exemplos": ["Técnico não se sentiu bem e se ausentou."],
        "campos": campos("Descreber o Problema", "Nome"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 19) Ocorrência – Sem tempo hábil (Atendimento Parcial)
    {
        "id": "oc_tecnico_parcial",
        "titulo": "Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Atendimento Parcial)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Atendimento iniciado, mas não será possível concluir no dia.",
        "exemplos": ["Técnico iniciou o serviço e não finalizou no mesmo dia."],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às [DATA/HORA] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 20) Ocorrência – Sem tempo hábil (Não iniciado)
    {
        "id": "oc_tecnico_nao_iniciado",
        "titulo": "Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Não iniciado)",
        "acao": "Cancelar agendamento",
        "quando_usar": "Sem tempo suficiente por erro de agendamento/encaixe/atraso; atendimento não iniciado.",
        "exemplos": ["Atendimento anterior demorou além do previsto e inviabilizou o próximo."],
        "campos": campos("Motivo", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Motivo: [ERRO DE AGENDAMENTO/ENCAIXE] ou [DEMANDA EXCEDIDA]. Cliente [NOME] informado do reagendamento."
        }]
    },

    # 21) Técnico sem habilidade
    {
        "id": "oc_tecnico_sem_habilidade",
        "titulo": "Ocorrência Com Técnico - Técnico Sem Habilidade Para Realizar Serviço",
        "acao": "Cancelar agendamento",
        "quando_usar": "RT identifica que o técnico não possui a habilidade necessária.",
        "exemplos": ["Atendimento roteirizado para técnico sem a skill exigida."],
        "campos": campos("Descreber o Problema", "Cliente"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 22) Perda/Extravio/Falta/Defeito
    {
        "id": "perda_extravio_defeito",
        "titulo": "Perda/Extravio/Falta Do Equipamento/Equipamento Com Defeito",
        "acao": "Cancelar agendamento",
        "quando_usar": "Equipamento/acessório não está mais no veículo ou defeito/má condição; cliente recusou termo.",
        "exemplos": ["Novo proprietário não aceitou assinar o termo de Mau Uso."],
        "campos": campos("Descreber o Problema"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível realizar o atendimento, pois [DESCREVER PROBLEMA]. Cliente se recusou assinar termo."
        }]
    },

    # 23) Serviço incompatível com a OS aberta
    {
        "id": "servico_incompativel_os",
        "titulo": "Serviço incompatível com a OS aberta",
        "acao": "Cancelar agendamento",
        "quando_usar": "Material separado não atende às necessidades para concluir o serviço.",
        "exemplos": ["Necessidade de outro equipamento que não o descrito."],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às [DATA/HORA] foi informado sobre a necessidade de reagendamento."
        }]
    },
]

# =========================================================
# Estado
# =========================================================
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []
if "reset_token" not in st.session_state:
    st.session_state.reset_token = 0

# =========================================================
# UI principal
# =========================================================
st.markdown("**Ferramenta para identificar como classificar No-show.**")

st.markdown("**1. Motivos – selecionar um aqui:**")
motivos_map = {m["titulo"]: m for m in CATALOGO}
motivo_titulo = st.selectbox(
    "Motivo",
    list(motivos_map.keys()),
    index=0,
    key=f"mot_sel_{st.session_state.reset_token}",
    label_visibility="collapsed"
)
motivo = motivos_map[motivo_titulo]

st.markdown("**2. Preencher as informações solicitadas.**")
col_esq, col_dir = st.columns([1.05, 1])

with col_esq:
    st.subheader("Dados")
    valores = {}
    erros = []

    # opções de máscara
    alt_labels = [a["rotulo"] for a in motivo["mascaras"]]
    alt_idx = 0
    if len(motivo["mascaras"]) > 1:
        alt_idx = st.radio(
            "Versão da máscara",
            options=list(range(len(alt_labels))),
            format_func=lambda i: alt_labels[i],
            key=f"alt_{motivo['id']}_{st.session_state.reset_token}",
            horizontal=True
        )
    alternativa = motivo["mascaras"][alt_idx]
    obrig_extra = set(alternativa.get("regras_obrig", []))

    # inputs
    for c in motivo["campos"]:
        name = c["name"]
        label = c["label"]
        req = bool(c.get("required", False)) or (name in obrig_extra)
        val = st.text_input(
            label,
            value="",
            placeholder=c.get("placeholder", ""),
            key=f"inp_{motivo['id']}_{name}_{st.session_state.reset_token}"
        ).strip()
        valores[name] = val
        if req and not val:
            erros.append(f"Preencha o campo obrigatório: **{label}**")

    # máscara gerada
    template = alternativa.get("template", "")
    mascara = build_mask(template, valores)

    st.markdown("**3. Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
    st.text_area("Máscara gerada", value=mascara, height=140, label_visibility="collapsed")

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
                "Motivo": motivo["titulo"],
                "Versão máscara": alternativa["rotulo"],
                "Ação sistêmica": motivo.get("acao", ""),
                "Quando usar": motivo.get("quando_usar", ""),
                "Máscara": mascara,
            }
            for c in motivo["campos"]:
                registro[c["label"]] = valores.get(c["name"], "")
            st.session_state.LINHAS.append(registro)
            st.success("Linha adicionada.")

    if baixar:
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

    if limpar:
        limpar_tudo()
        st.rerun()

with col_dir:
    st.subheader("O que fazer?")
    st.info(motivo.get("acao", ""))
    st.subheader("Quando usar?")
    st.info(motivo.get("quando_usar", ""))
    st.subheader("Exemplos")
    if motivo.get("exemplos"):
        for ex in motivo["exemplos"]:
            st.success(ex)
    else:
        st.caption("Sem exemplos cadastrados.")

st.markdown("---")
st.subheader("Prévia da tabela")
df_prev = pd.DataFrame(st.session_state.LINHAS) if st.session_state.LINHAS else pd.DataFrame()
st.dataframe(df_prev, use_container_width=True)
