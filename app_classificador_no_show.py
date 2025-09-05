import io
from datetime import datetime
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Classificação No-show", layout="wide")
st.title("Classificação No-show")

# =========================================================
# Catálogo EMBUTIDO (amplie à vontade)
# - placeholders dentro das máscaras devem bater com os "name" dos campos
# =========================================================
CATALOGO = [
    {
        "id": "cronograma_substituicao_placa",
        "titulo": "Cronograma de Instalação/Substituição de Placa",
        "acao": "Cancelar agendamento",
        "quando_usar": (
            "Quando o atendimento faz parte de um cronograma especial pré-acordado com o cliente "
            "e a execução segue o planejamento acordado ou como operação especial. A substituição "
            "só poderá ser feita para o mesmo serviço."
        ),
        "exemplos": [
            "1) Cliente substituiu por essa OS {os_relacionada}.",
            "2) Operação especial, não foi atendido veículo como substituição."
        ],
        # Campos que SEMPRE aparecem. A obrigatoriedade pode mudar conforme a alternativa.
        "campos": [
            {"name": "os_relacionada", "label": "Número OS (quando houver OS de substituição)", "placeholder": "462270287", "required": False},
            {"name": "complemento", "label": "Complemento (opcional)", "placeholder": "Observações", "required": False},
        ],
        # DUAS ALTERNATIVAS de máscara – o usuário escolhe abaixo
        "mascaras": [
            {
                "id": "substituicao_por_os",
                "rotulo": "Substituição por outra OS",
                "descricao": "Quando existe uma OS relacionada para a substituição.",
                "regras_obrig": ["os_relacionada"],  # estes campos tornam-se obrigatórios nesta alternativa
                "template": "Realizado atendimento com substituição de placa. Alteração feita pela OS {os_relacionada}."
            },
            {
                "id": "operacao_especial",
                "rotulo": "Operação especial (sem OS de substituição)",
                "descricao": "Quando é operação especial sem atendimento do veículo como substituição.",
                "regras_obrig": [],  # nenhum campo passa a ser obrigatório nesta alternativa
                "template": "Operação especial, não foi atendido veículo como substituição."
            }
        ]
    },
    {
        "id": "erro_cliente_desconhecia",
        "titulo": "Erro de Agendamento – Cliente desconhecia",
        "acao": "Cancelar agendamento",
        "quando_usar": "Cliente afirma não ter ciência do agendamento quando contatado.",
        "exemplos": [
            "Em contato com o cliente o mesmo informou que desconhecia o agendamento."
        ],
        "campos": [
            {"name": "nome", "label": "Nome do cliente", "placeholder": "João Silva", "required": True},
            {"name": "data_contato", "label": "Data do contato (DD/MM/AAAA)", "placeholder": "15/05/2025", "required": True},
            {"name": "hora_contato", "label": "Hora do contato (HHhMM)", "placeholder": "13h25", "required": True},
        ],
        "mascaras": [
            {
                "id": "padrao",
                "rotulo": "Padrão",
                "descricao": "",
                "regras_obrig": [],
                "template": "Em contato com o cliente o mesmo informou que desconhecia o agendamento. Nome: {nome} / Data contato: {data_contato} - {hora_contato}"
            }
        ]
    },
    {
        "id": "pedido_cliente",
        "titulo": "Cancelada a Pedido do Cliente",
        "acao": "Cancelar agendamento",
        "quando_usar": "Cliente indisponível e solicita cancelamento/reagendamento.",
        "exemplos": [
            "Cliente {nome} , contato via {canal} em {data} - {hora}, informou indisponibilidade."
        ],
        "campos": [
            {"name": "nome", "label": "Nome do cliente", "placeholder": "Michael Sancivier", "required": True},
            {"name": "canal", "label": "Canal", "placeholder": "Voz/Whatsapp/e-mail", "required": True},
            {"name": "data", "label": "Data (DD/MM/AAAA)", "placeholder": "15/05/2025", "required": True},
            {"name": "hora", "label": "Hora (HHhMM)", "placeholder": "13h25", "required": True},
        ],
        "mascaras": [
            {
                "id": "padrao",
                "rotulo": "Padrão",
                "descricao": "",
                "regras_obrig": [],
                "template": "Cliente {nome} , contato via {canal} em {data} - {hora}, informou indisponibilidade para o atendimento."
            }
        ]
    },
    {
        "id": "improdutivo_ponto_fixo",
        "titulo": "Atendimento Improdutivo – Ponto Fixo",
        "acao": "Cancelar agendamento",
        "quando_usar": "Veículo compareceu, mas não foi possível realizar o serviço por motivo informado.",
        "exemplos": [
            "Veículo compareceu para atendimento, porém por {motivo}, não foi possível realizar o serviço."
        ],
        "campos": [
            {"name": "motivo", "label": "Motivo da improdutividade", "placeholder": "falha elétrica", "required": True},
        ],
        "mascaras": [
            {
                "id": "padrao",
                "rotulo": "Padrão",
                "descricao": "",
                "regras_obrig": [],
                "template": "Veículo compareceu para atendimento, porém por {motivo}, não foi possível realizar o serviço."
            }
        ]
    },
]

# =========================================================
# Estado
# =========================================================
if "LINHAS" not in st.session_state:
    st.session_state.LINHAS = []
if "reset_token" not in st.session_state:
    st.session_state.reset_token = 0  # usado para forçar limpeza dos inputs

def limpar_tudo():
    """Zera todos os inputs e resultados para nova consulta."""
    st.session_state.LINHAS = []
    st.session_state.reset_token += 1
    # remove chaves de campos dinamicamente
    for k in list(st.session_state.keys()):
        if k.startswith("inp_") or k.startswith("alt_") or k.startswith("motivo_sel"):
            del st.session_state[k]

# =========================================================
# UI
# =========================================================
st.markdown("**Ferramenta para identificar como classificar No-show.**")

# 1) Seleção de motivo
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

    # se houver alternativas de máscara, mostre seletor
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

    # campos variam só na obrigatoriedade adicional por alternativa
    for campo in motivo["campos"]:
        name = campo["name"]
        label = campo["label"]
        ph = campo.get("placeholder", "")
        req_base = bool(campo.get("required", False))
        req = req_base or (name in obrig_extra)

        val = st.text_input(
            label,
            value="",
            placeholder=ph,
            key=f"inp_{motivo['id']}_{name}_{st.session_state.reset_token}"
        ).strip()
        valores[name] = val
        if req and not val:
            erros.append(f"Preencha o campo obrigatório: **{label}**")

    # gera máscara substituindo placeholders
    template = alternativa.get("template", "")
    mascara = template
    # substitui {nome} por valor; se algum placeholder não tiver valor, mantém sem quebrar
    for c in motivo["campos"]:
        mascara = mascara.replace("{" + c["name"] + "}", valores.get(c["name"], ""))

    # anexa complemento ao final se existir
    if "complemento" in valores and valores["complemento"]:
        mascara = mascara.rstrip(". ") + ". " + valores["complemento"]

    st.markdown("3) **Texto padrão (Máscara) para incluir na Ordem de Serviço.**")
    st.text_area(
        "Máscara gerada",
        value=mascara,
        height=110,
        key=f"mask_view_{st.session_state.reset_token}",
        label_visibility="collapsed"
    )

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
        st.experimental_rerun()

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
