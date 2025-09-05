import io
import re
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Classificação No-show", layout="wide")
st.title("Classificação No-show")

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def slug(s: str) -> str:
    s = re.sub(r"[^0-9a-zA-ZÀ-ÿ/ _-]+", "", str(s or ""))
    s = s.strip().lower()
    s = s.replace("ç", "c").replace("á","a").replace("à","a").replace("â","a").replace("ã","a")\
         .replace("é","e").replace("ê","e").replace("í","i").replace("ó","o").replace("ô","o")\
         .replace("õ","o").replace("ú","u").replace("ü","u")
    s = re.sub(r"[^\w/]+", "_", s)
    s = s.replace("/", "_")
    s = re.sub(r"_+", "_", s)
    return s.strip("_")

def normalize_token(token: str) -> str:
    """normaliza o texto entre colchetes do catálogo para comparar com labels dos campos."""
    t = slug(token)
    # mapeamentos comuns
    m = {
        "nome_cliente": "nome",
        "nome_tecnico": "nome_tecnico",
        "cliente": "cliente",
        "tipo": "tipo_erro",
        "tipo_erro": "tipo_erro",
        "descreva": "descreva",
        "descrever_problema": "descreber_o_problema",
        "descrever_o_problema": "descreber_o_problema",
        "descrever_situacao": "descreva",
        "descrever_situacao": "descreva",
        "equipamento_sistema": "equipamento_sistema",
        "numero_ordem_de_servico": "numero_os",
        "numero_os": "numero_os",
        "hora": "hora",
        "data": "data",
        "motivo": "motivo",
        "especialista": "especialista",
        "asm": "asm",
        "canal": "canal",
        "erro_de_agendamento_enxace": "motivo",
    }
    if t in m:
        return m[t]
    # data/hora
    if "data_hora" in t or "datahora" in t:
        return "__DATAHORA__"
    return t

def build_mask(template: str, values: dict, fields_slug_map: set) -> str:
    """Substitui tokens [X] por valores digitados. [DATA/HORA] usa data + hora."""
    text = str(template or "")
    # encontra tokens [TEXTO]
    tokens = re.findall(r"\[([^\]]+)\]", text)
    for tok in tokens:
        norm = normalize_token(tok)
        if norm == "__DATAHORA__":
            val = ""
            d = values.get("data","").strip()
            h = values.get("hora","").strip()
            if d and h:
                val = f"{d} - {h}"
            else:
                # se um dos dois faltar, insere o que houver
                val = (d or h)
        else:
            # se o token normalizado bate com o slug de algum campo, usa
            if norm in values:
                val = values.get(norm, "")
            else:
                # última tentativa: token slug puro
                val = values.get(slug(tok), "")
        text = text.replace(f"[{tok}]", val)
    return text.strip()

def limpar_tudo():
    st.session_state.LINHAS = []
    st.session_state.reset_token += 1
    for k in list(st.session_state.keys()):
        if k.startswith("inp_") or k.startswith("alt_") or k.startswith("motivo_sel"):
            del st.session_state[k]

# ------------------------------------------------------------
# Catálogo embutido
#  - Cada motivo tem:
#    id, titulo, acao, quando_usar, exemplos(list), campos(list[{name,label,placeholder,required}]),
#    mascaras(list[{id,rotulo,descricao,template,regras_obrig(list names)}])
# ------------------------------------------------------------

def campos(*labels):
    # gera lista de campos a partir dos rótulos (todos vazios por padrão)
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
        "campos": campos("Descreber o Problema","Cliente"),
        "mascaras": [{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template": "Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [CLIENTE] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 2) Atendimento Improdutivo – Ponto Fixo/Móvel
    {
        "id":"improdutivo_ponto_fixo_movel",
        "titulo":"Atendimento Improdutivo – Ponto Fixo/Móvel",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o veículo está presente mas não foi possível atender (problema mecânico, elétrico ou condição do veículo). Se ponto móvel, considere também quando o atendimento em campo não pôde ser feito por fatores externos (chuva ou local sem condição).",
        "exemplos":[
            "1) O cliente trouxe o veículo, ele compareceu para atendimento, mas o veículo apresentou falhas elétrica.",
            "2) O local para atendimento não possuía cobertura para atendimento."
        ],
        "campos": campos("Descreber o Problema"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Veículo compareceu para atendimento, porém por [DESCREVER O PROBLEMA], não foi possível realizar o serviço."
        }]
    },

    # 3) Cancelada a Pedido do Cliente
    {
        "id":"pedido_cliente",
        "titulo":"Cancelada a Pedido do Cliente",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o próprio cliente solicita o cancelamento do atendimento.",
        "exemplos":[
            "1) Cliente ligou pedindo para remarcar porque o motorista estaria em viagem, ou porque não chegaria a tempo, ou veículo está na oficina.",
            "2) Entramos em contato com o cliente para confirmar o atendimento ele disse que o veículo estará em viagem ou indisponível."
        ],
        "campos": campos("Nome","Canal","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Cliente [NOME], contato via [CANAL] em [DATA/HORA], informou indisponibilidade para o atendimento."
        }]
    },

    # 4) Cancelamento a pedido da RT
    {
        "id":"pedido_rt",
        "titulo":"Cancelamento a pedido da RT",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando houver necessidade de cancelamento do agendamento por parte do representante técnico.",
        "exemplos":["Devido a situações de atendimento, precisamos cancelar com o cliente."],
        "campos": campos("Descreber o Problema","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [CLIENTE] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 5) Cronograma ... (2 alternativas)
    {
        "id":"cronograma_substituicao_placa",
        "titulo":"Cronograma de Instalação/Substituição de Placa",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o atendimento faz parte de um cronograma especial pré-acordado com o cliente e a execução segue o planejamento acordado ou como operação especial. A substituição só poderá ser feito para o mesmo serviço.",
        "exemplos":[
            "1) Cliente substituiu por essa OS 462270287.",
            "2) Operação especial, não foi atendido veículo como substituição."
        ],
        "campos": campos("Número OS"),
        "mascaras":[
            {
                "id":"com_os",
                "rotulo":"Substituição com OS",
                "descricao":"Quando o cliente enviou veículo para atendimento (há OS de substituição).",
                "regras_obrig":["numero_os"],
                "template":"Realizado atendimento com substituição de placa. Foi realizado a alteração pela OS [NÚMERO ORDEM DE SERVIÇO]."
            },
            {
                "id":"sem_os",
                "rotulo":"Operação especial (sem envio do veículo)",
                "descricao":"Quando o cliente não enviou o veículo para atendimento.",
                "regras_obrig":[],
                "template":"Cliente não enviou veículo para atendimento."
            }
        ]
    },

    # 6) Erro De Agendamento - Cliente desconhecia ...
    {
        "id":"erro_cliente_desconhecia",
        "titulo":"Erro De Agendamento - Cliente desconhecia o agendamento",
        "acao":"Cancelar agendamento",
        "quando_usar":"OS foi agendada sem que o cliente tivesse sido informado previamente...",
        "exemplos":[
            "1) Técnico chegou e o cliente disse não ter solicitado nenhum serviço...",
            "2) Realizamos contato com o cliente e ele informou que desconhecia o agendamento."
        ],
        "campos": campos("Nome Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Em contato com o cliente o mesmo informou que desconhecia o agendamento. Nome cliente:  [NOME CLIENTE] / Data contato:  [DATA/HORA] ."
        }]
    },

    # 7) Erro de Agendamento – Endereço incorreto
    {
        "id":"erro_endereco_incorreto",
        "titulo":"Erro de Agendamento – Endereço incorreto",
        "acao":"Cancelar agendamento",
        "quando_usar":"Endereço informado na OS está incorreto ou incompleto, inviabilizando a chegada ao local para execução do serviço.",
        "exemplos":["Técnico direcionado para rua X, mas cliente está na rua Y, inviabilizando o atendimento."],
        "campos": campos("Tipo erro","Descreva","Nome","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Erro identificado no agendamento: [TIPO]. Situação: [DESCREVA]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 8) Falta de informações na OS
    {
        "id":"erro_falta_info_os",
        "titulo":"Erro de Agendamento – Falta de informações na O.S.",
        "acao":"Cancelar agendamento",
        "quando_usar":"OS criada com informações incompletas...",
        "exemplos":["Não há solução cadastrada no sistema."],
        "campos": campos("Tipo erro","Explique","Nome","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"OS agendada apresentou erro de [TIPO] e foi identificado através de [EXPLIQUE A SITUAÇÃO]\nRealizado o contato com o cliente [NOME], no dia [DATA/HORA]."
        }]
    },

    # 9) OS agendada incorretamente
    {
        "id":"erro_os_incorreta",
        "titulo":"Erro de Agendamento – O.S. agendada incorretamente (tipo/motivo/produto)",
        "acao":"Cancelar agendamento",
        "quando_usar":"Erro na categorização do serviço ao agendar a OS...",
        "exemplos":[
            "1) Cliente pediu assistência e foi agendado instalação por engano.",
            "2) Agendamento realizado no mesmo dia do agendamento sem autorização."
        ],
        "campos": campos("Tipo erro","Explique","Nome","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"OS agendada apresentou erro de [TIPO] e foi identificado através de [EXPLIQUE A SITUAÇÃO]\nRealizado o contato com o cliente [NOME], no dia [DATA/HORA]."
        }]
    },

    # 10) Roteirização móvel
    {
        "id":"erro_roteirizacao_movel",
        "titulo":"Erro de roteirização do agendamento - Atendimento móvel",
        "acao":"Cancelar agendamento",
        "quando_usar":"Falha de agendamento que permite agendar sem considerar deslocamento.",
        "exemplos":["Deslocamento de retorno não considerado, técnico sem tempo hábil para execução, comercial informado."],
        "campos": campos("Descreber o Problema","Cliente","Data","Hora","Especialista","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às [DATA/HORA] foi informado sobre a necessidade de reagendamento. Especialista [ESPECIALISTA] informado às [DATA/HORA]."
        }]
    },

    # 11 a 14) Falta de equipamento (várias)
    {
        "id":"falta_acessorios_imobilizado",
        "titulo":"Falta De Equipamento - Acessórios Imobilizado",
        "acao":"Cancelar agendamento",
        "quando_usar":"Falta de acessórios imobilizados...",
        "exemplos":["Agendamento precisara ser cancelado, pois estamos sem o sensor temperatura NTC 10K ..."],
        "campos": campos("Item","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"",
            "regras_obrig":[],
            "template":"Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },
    {
        "id":"falta_item_reservado_incompativel",
        "titulo":"Falta De Equipamento - Item Reservado Não Compatível",
        "acao":"Cancelar agendamento",
        "quando_usar":"Material reservado incompatível.",
        "exemplos":["Atendimento de instalação não concluído por falta de rastreador compatível."],
        "campos": campos("Item","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },
    {
        "id":"falta_material",
        "titulo":"Falta De Equipamento - Material",
        "acao":"Cancelar agendamento",
        "quando_usar":"Ausência total de material necessário.",
        "exemplos":["Falta de equipamento ADPLUS."],
        "campos": campos("Item","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },
    {
        "id":"falta_principal",
        "titulo":"Falta De Equipamento - Principal",
        "acao":"Cancelar agendamento",
        "quando_usar":"Técnico sem o equipamento principal.",
        "exemplos":["1) RT Com falta de equipamento LMU4233.","2) Aguardando o equipamento RFID."],
        "campos": campos("Item","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Atendimento não realizado por falta de [DESCREVA SITUAÇÃO]. Cliente [NOME] informado em [DATA/HORA]."
        }]
    },

    # 15) Instabilidade de Equipamento/Sistema
    {
        "id":"instabilidade_sistema",
        "titulo":"Instabilidade de Equipamento/Sistema",
        "acao":"Entrar em contato com a central para conclusão, e se não for possível incluir ação no histórico da OS com o nº da ASM",
        "quando_usar":"Quando deu problema no sistema ou no equipamento e não foi possível terminar o serviço.",
        "exemplos":["O rastreador não iniciou comunicação com a plataforma."],
        "campos": campos("Data","Hora","Equipamento/Sistema","Data","Data","Hora","ASM"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Atendimento finalizado em [DATA/HORA] não concluído devido à instabilidade de [EQUIPAMENTO/SISTEMA].\nRegistrado teste/reinstalação em [DATA]. Realizado contato com a central [DATA/HORA]  e foi gerada a ASM [NÚMERO]."
        }]
    },

    # 16) No-show Cliente
    {
        "id":"no_show_cliente",
        "titulo":"No-show Cliente – Ponto Fixo/Móvel",
        "acao":"Cancelar agendamento",
        "quando_usar":"Cliente não aparece no local/empresa ou ponto móvel.",
        "exemplos":["O técnico chegou ao cliente, mas o caminhão estava em rota ..."],
        "campos": campos("Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Cliente não compareceu para atendimento até às [HORA]."
        }]
    },

    # 17) No-show Técnico
    {
        "id":"no_show_tecnico",
        "titulo":"No-show Técnico",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o técnico não comparece no horário/local.",
        "exemplos":["Técnico não realizou atendimento."],
        "campos": campos("Nome Técnico","Data","Hora","Motivo"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Técnico [NOME TÉCNICO], em [DATA/HORA], não realizou o atendimento por motivo de [MOTIVO]."
        }]
    },

    # 18) Ocorrência com Técnico – Não foi possível realizar atendimento
    {
        "id":"oc_tecnico_impossivel",
        "titulo":"Ocorrência com Técnico – Não foi possível realizar atendimento",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o técnico não consegue realizar o atendimento por questões pessoais/operacionais.",
        "exemplos":["Técnico não se sentiu bem e teve que se ausentar ..."],
        "campos": campos("Nome Técnico","Data","Hora","Motivo"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 19) Ocorrência com Técnico – Sem Tempo Hábil (Atendimento Parcial)
    {
        "id":"oc_tecnico_parcial",
        "titulo":"Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Atendimento Parcial)",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando iniciado o atendimento, porém não será possível concluir.",
        "exemplos":["Técnico começou a realizar o serviço e não conseguiu finalizar ..."],
        "campos": campos("Descreber o Problema","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às DATA/HORA] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 20) Ocorrência com Técnico – Sem Tempo Hábil (Não iniciado)
    {
        "id":"oc_tecnico_nao_iniciado",
        "titulo":"Ocorrência Com Técnico - Sem Tempo Hábil Para Realizar O Serviço (Não iniciado)",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando não houve tempo suficiente por erro de agendamento/encaixe/atraso etc.",
        "exemplos":["Atendimento anterior demorou muito mais que o previsto e inviabilizou o próximo."],
        "campos": campos("Motivo","Cliente"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Motivo: [ERRO DE AGENDAMENTO/ENCAIXE] ou [DEMANDA EXCEDIDA]. Cliente [NOME] informado do reagendamento."
        }]
    },

    # 21) Técnico sem habilidade
    {
        "id":"oc_tecnico_sem_habilidade",
        "titulo":"Ocorrência Com Técnico - Técnico Sem Habilidade Para Realizar Serviço",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando o RT identifica que o atendimento não pode ser realizado por falta de habilidade.",
        "exemplos":["Atendimento roteirizado na agenda do técnico instalador sem a habilidade necessária."],
        "campos": campos("Descreber o Problema","Cliente"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Não foi possível realizar o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] foi informado sobre a necessidade de reagendamento."
        }]
    },

    # 22) Perda/Extravio/Falta/Defeito
    {
        "id":"perda_extravio_defeito",
        "titulo":"Perda/Extravio/Falta Do Equipamento/Equipamento Com Defeito",
        "acao":"Cancelar agendamento",
        "quando_usar":"Quando não é possível realizar o atendimento por perda/extravio/defeito e o cliente recusa termo.",
        "exemplos":["Veículo no local mas sem todos os equipamentos; novo proprietário não aceitou assinar o termo de Mau Uso."],
        "campos": campos("Descreber o Problema"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Não foi possível realizar o atendimento, pois [DESCREVER PROBLEMA]. Cliente se recusou assinar termo."
        }]
    },

    # 23) Serviço incompatível com a OS aberta
    {
        "id":"servico_incompativel_os",
        "titulo":"Serviço incompatível com a OS aberta",
        "acao":"Cancelar agendamento",
        "quando_usar":"Iniciado atendimento, identificou-se que o material separado não atende as necessidades.",
        "exemplos":["Técnico foi para atendimento, porém identificou que é necessário utilizar outro equipamento do que foi descrito como problema."],
        "campos": campos("Descreber o Problema","Cliente","Data","Hora"),
        "mascaras":[{
            "id":"padrao","rotulo":"Padrão","descricao":"", "regras_obrig":[],
            "template":"Não foi possível concluir o atendimento devido [DESCREVA O PROBLEMA]. Cliente [NOME] às DATA/HORA] foi informado sobre a necessidade de reagendamento."
        }]
    },
]

# ------------------------------------------------------------
# Estado
# ------------------------------------------------------------
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []
if "reset_token" not in st.session_state:
    st.session_state.reset_token = 0

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.markdown("**Ferramenta para identificar como classificar No-show.**")
st.markdown("1) **Motivos – selecionar um aqui:**")

motivos_map = {m["titulo"]: m for m in CATALOGO}
motivo_titulo = st.selectbox(
    "Motivo",
    list(motivos_map.keys()),
    index=0,
    key=f"motivo_sel_{st.session_state.reset_token}",
    label_visibility="collapsed"
)
motivo = motivos_map[motivo_titulo]

st.markdown("2) **Preencher as informações solicitadas.**")
col_esq, col_dir = st.columns([1.05, 1])

with col_esq:
    st.subheader("Dados")
    valores = {}
    erros = []

    # Alternativas de máscara (quando houver)
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

    # Campos para digitar
    for c in motivo["campos"]:
        name = c["name"]
        label = c["label"]
        req_base = bool(c.get("required", False))
        req = req_base or (name in obrig_extra)
        val = st.text_input(
            label,
            value="",
            placeholder=c.get("placeholder",""),
            key=f"inp_{motivo['id']}_{name}_{st.session_state.reset_token}"
        ).strip()
        valores[name] = val
        if req and not val:
            erros.append(f"Preencha o campo obrigatório: **{label}**")

    # 3) Gera máscara (substitui tokens [X] pelos valores)
    template = alternativa.get("template","")
    mascara = build_mask(template, valores, {f["name"] for f in motivo["campos"]})
    st.markdown("3) **Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
    st.text_area("Máscara gerada", value=mascara, height=120, label_visibility="collapsed")

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
                "Ação sistêmica": motivo.get("acao",""),
                "Quando usar": motivo.get("quando_usar",""),
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
        st.experimental_rerun()

with col_dir:
    st.subheader("O que fazer?")
    st.info(motivo.get("acao",""))
    st.subheader("Quando usar?")
    st.info(motivo.get("quando_usar",""))
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

