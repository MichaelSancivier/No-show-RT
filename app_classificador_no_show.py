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
        if n == "2":
            return "__DATAHORA2__"
        if n == "3":
            return "__DATAHORA3__"
        return f"__DATAHORA{n}__"

    # DATA 1..N
    m = re.match(r"^data(?:_(\d+))?$", t)
    if m:
        n = m.group(1)
        return f"data_{n}" if n and n != "1" else "data"

    # HORA 1..N
    m = re.match(r"^hora(?:_(\d+))?$", t)
    if m:
        n = m.group(1)
        return f"hora_{n}" if n and n != "1" else "hora"

    # Mapeamentos diretos / sinônimos
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
        "item": "item",        "erro_de_agendamento_encaixe": "motivo",
        "demanda_excedida": "motivo",
        "descreva_situacao": "item",
        "descreva_situação": "item",

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
                n = re.findall(r"__DATAHORA(\d+)__", norm)
                n = n[0] if n else "1"
                d_key, h_key = f"data_{n}", f"hora_{n}"
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

    text = re.sub(r"\s+\.", ".", text)
    return text.strip()

def limpar_tudo():
    """Limpa todos os inputs e força recarregar a tela."""
    if "LINHAS" in st.session_state:
        st.session_state.LINHAS = []
    st.session_state.reset_token = st.session_state.get("reset_token", 0) + 1
    for k in list(st.session_state.keys()):
        if k.startswith(("inp_", "alt_", "mot_sel_", "os_consulta_", "mask_")):
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
# Catálogo de 23 MOTIVOS (idêntico ao aprovado, com ajustes de máscaras)
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
        "quando_usar": "Quando o veículo está presente mas não foi possível atender (problema mecânico, elétrico ou condição do veículo). Se ponto móvel, considere também quando o atendimento em campo não pôde ser feito por fatores externos (chuva ou local sem condição).",
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
        "quando_usar": "Quando o próprio cliente solicita o cancelamento do atendimento.",
        "exemplos": [
            "1) Cliente ligou pedindo para remarcar porque o motorista estaria em viagem, ou porque não chegaria a tempo, ou veículo está na oficina.",
            "2) Entramos em contato com o cliente para confirmar o atendimento ele disse que o veículo estará em viagem ou indisponível."
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

    # 4) Cancelamento a pedido da RT
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
        "quando_usar": "OS foi agendada sem que o cliente tivesse sido informado previamente, resultando em ausência ou recusa no momento do atendimento técnico. Obrigatório informar: Nome do cliente que entrou em contato, horário do cancelamento e canal de contato (preferencialmente canal que seja possível a futura comprovação).",
        "exemplos": [
            "1) Técnico chegou e o cliente disse não ter solicitado nenhum serviço ou foi entrado em contato com o cliente e o mesmo informou que desconhecia o agendamento.​",
            "2) Realizamos contato com o cliente ele informou que desconhecia o agendamento."
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
        "quando_usar": "Endereço informado na OS está incorreto ou incompleto, inviabilizando a chegada ao local para execução do serviço.",
        "exemplos": ["Técnico direcionado para rua X, mas cliente está na rua Y, inviabilizando o atendimento."],
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
        "quando_usar": "OS criada com informações incompletas, como ausência de dados do cliente, tipo de serviço ou outros campos obrigatórios que inviabilizam o atendimento.",
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
        "quando_usar": "Erro na categorização do serviço ao agendar a OS (ex: tipo de atendimento ou produto incorreto), levando à impossibilidade de execução correta.",
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
        "quando_usar": "Quando houver uma falha no agendamento, e permite que o cliente consiga fazer agendamento no portal do cliente de um dia para o outro ou no mesmo dia, sem considerar o deslocamento.",
        "exemplos": ["Deslocamento de retorno não considerado, técnico sem tempo hábil para execução, comercial informado."],
        "campos": campos("Descreber o Problema", "Cliente", "Data", "Hora", "Especialista", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às [DATA/HORA] foi informado sobre a necessidade de reagendamento. Especialista [ESPECIALISTA] informado às [DATA/HORA 2]."
        }]
    },

    # 11) Falta De Equipamento - Acessórios Imobilizado
    {
        "id": "falta_acessorios_imobilizado",
        "titulo": "Falta De Equipamento - Acessórios Imobilizado",
        "acao": "Cancelar agendamento",
        "quando_usar": "Falta de acessórios que estão alocados (imobilizados) em outro atendimento, impedindo a realização do serviço agendado.",
        "exemplos": ["Agendamento precisara ser cancelado, pois estamos sem o sensor temperatura NTC 10K , o mesmo foi pedido para a distribuição mas ainda não chegou."],
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
        "quando_usar": "Material reservado está incompatível com o veículo ou serviço solicitado, mesmo estando disponível no estoque.",
        "exemplos": ["Instalação não concluída por falta de rastreador compatível."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 13) Falta De Equipamento - Material
    {
        "id": "falta_material",
        "titulo": "Falta De Equipamento - Material",
        "acao": "Cancelar agendamento",
        "quando_usar": "Ausência total de material necessário para a execução da OS, mesmo após verificação de estoque.",
        "exemplos": ["Falta equipamento ADPLUS."],
        "campos": campos("Item", "Cliente", "Data", "Hora"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": "Atendimento não realizado por falta de [ITEM]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 14) Falta De Equipamento - Principal
    {
        "id": "falta_principal",
        "titulo": "Falta De Equipamento - Principal",
        "acao": "Cancelar agendamento",
        "quando_usar": "Atendimento foi marcado, mas o técnico não tinha consigo o equipamento principal necessário, mesmo estando previsto para o serviço.",
        "exemplos": [
            "1) RT Com falta de equipamento LMU4233.​",
            "2) Aguardando o equipamento RFID."
        ],
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
        "quando_usar": "Quando deu problema no sistema ou no equipamento e não foi possível terminar o serviço.",
        "exemplos": ["Rastreador não iniciou comunicação com a plataforma."],
        "campos": campos("Data", "Hora", "Equipamento/Sistema", "Data", "Data", "Hora", "ASM"),
        "mascaras": [{
            "id": "padrao",
            "rotulo": "Padrão",
            "descricao": "",
            "regras_obrig": [],
            "template": (
                "Atendimento finalizado em [DATA/HORA] não concluído devido à instabilidade de "
                "[EQUIPAMENTO/SISTEMA]. Registrado teste/reinstalação em [DATA 2]. "
                "Realizado contato com a central [DATA/HORA 3] e foi gerada a ASM [NÚMERO]."
            )
        }]
    },

    # 16) No-show Cliente – Ponto Fixo/Móvel
    {
        "id": "no_show_cliente",
        "titulo": "No-show Cliente – Ponto Fixo/Móvel",
        "acao": "Cancelar agendamento",
        "quando_usar": "Quando o cliente não aparece no local/empresa (fixo) ou não está disponível no ponto móvel.",
        "exemplos": ["O técnico chegou ao cliente, mas o caminhão estava em rota de viagem, o veículo não compareceu no ponto de atendimento, o veículo chegou com atraso superior a 15 minutos."],
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
        "quando_usar": "Quando o técnico não comparece no horário/local.",
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
        "quando_usar": "Quando o técnico não consegue realizar o atendimento por questões pessoais ou operacionais, como: Problemas de saúde e pessoais; Problemas no veículo do técnico ou acidentes, ou outras impossibilidades de comparecer ao local. Deve ser informar horário, nome do cliente e canal de contato (voz, e-mail, whatsapp) que foi informado o cliente sobre a impossibilidade de atendimento.",
        "exemplos": ["Técnico não se sentiu bem e teve que se ausentar na tarde de hoje."],
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
        "quando_usar": "Quando iniciado o atendimento, porém foi identificado que não será possível concluir o serviço.",
        "exemplos": ["Técnico começou a realizar o serviço e não conseguiu finalizar o atendimento no mesmo dia."],
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
        "quando_usar": " Quando não houve tempo suficiente por erro de agendamento, encaixe, atraso em OS anterior ou roteirização ruim e o atendimento não foi iniciado.",
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
        "quando_usar": "Quando o representante técnico identifica que o atendimento não pode ser realizado, devido a falta de habilidade específica do técnico.",
        "exemplos": ["Atendimento roteirizado na agenda do técnico instalador sem a habilidade necessária para a realização do serviço"],
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
        "quando_usar": "Quando o técnico identifica que o equipamento/acessório não está mais no veículo ou por falta de condições de mau uso não é possível realizar o atendimento, e o cliente se recusa a assinar o termo de cobrança.",
        "exemplos": ["Veículo esta no local mas não tem todos os equipamentos, novo proprietário não aceitou assinar o termo de Mau Uso."],
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
        "quando_usar": "Quando iniciado o atendimento, porém foi identificado que o equipamento/material separado não atende as necessidades para conclusão do serviço.",
        "exemplos": ["Técnico foi para atendimento, porém identificou que é necessário utilizar outro equipamento do que foi descrito como problema."],
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

# Campo opcional de OS (antes do seletor de motivos)
os_consulta = st.text_input(
    "Número da OS (opcional) — podem deixar em branco",
    key=f"os_consulta_{st.session_state.reset_token}"
).strip()

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
            # exemplos de rotulagem mais clara por motivo (ponto opcional)
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

    # máscara gerada
    template = alternativa.get("template", "")
    mascara = build_mask(template, valores)

    st.markdown("**3. Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
    # <<< O atendente pode editar/ acrescenter texto; isso vai para a tabela
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
                # guarda exatamente o que está na caixa 3
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
                import openpyxl  # noqa: F401
                engine = "openpyxl"
            except Exception:
                try:
                    import xlsxwriter  # noqa: F401
                    engine = "xlsxwriter"
                except Exception:
                    engine = None

            if engine:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine=engine) as w:
                    df.to_excel(w, index=False, sheet_name="No-show")
                st.download_button(
                    "Baixar Excel (No-show)",
                    data=buf.getvalue(),
                    file_name=f"no_show_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.caption(f"Arquivo gerado com engine **{engine}**.")
            else:
                csv = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Baixar CSV (fallback)",
                    data=csv,
                    file_name=f"no_show_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                st.warning("Nenhum engine Excel disponível. Exporte em CSV ou inclua `openpyxl`/`xlsxwriter` no requirements.")

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
