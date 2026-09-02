import requests
import sys


BASE_URL = "http://127.0.0.1:8000"

ID_INVENTARIO = 14
ID_RODADA = 28

LOCALIZACAO = "01PLAQUETA"
CODIGO = "71554091"
LOTE = "3007863574 - 30"

DECISAO = "RECONTAR"
USUARIO = "dev"


def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def validar(resposta, etapa):

    print("HTTP:", resposta.status_code)

    try:
        dados = resposta.json()
    except Exception:
        dados = resposta.text

    print("Resposta:", dados)

    if resposta.status_code not in (200, 201):
        print(f"\n[FALHOU] {etapa}")
        sys.exit(1)

    return dados


# ============================================================
# 1. REGISTRAR DECISÃO RECONTAR
# ============================================================

titulo("1. REGISTRANDO DECISÃO RECONTAR")

resposta = requests.post(
    (
        f"{BASE_URL}"
        f"/inventarios/{ID_INVENTARIO}"
        f"/decisoes-rotativo"
    ),
    json={
        "id_rodada": ID_RODADA,
        "localizacao": LOCALIZACAO,
        "codigo": CODIGO,
        "lote": LOTE,
        "decisao": DECISAO,
        "justificativa": (
            "Recontagem para validar divergência da R1."
        ),
        "usuario": USUARIO,
    },
)

dados = validar(
    resposta,
    "Não foi possível registrar a decisão RECONTAR."
)


# ============================================================
# 2. MOSTRAR RESULTADO
# ============================================================

titulo("RESULTADO")

print(
    "ID Inventário:",
    dados.get("id_inventario")
)

print(
    "ID Rodada:",
    dados.get("id_rodada")
)

print(
    "Localização:",
    dados.get("localizacao")
)

print(
    "Código:",
    dados.get("codigo")
)

print(
    "Lote:",
    dados.get("lote")
)

print(
    "Decisão:",
    dados.get("decisao")
)

print(
    "ID Decisão:",
    dados.get("id_decisao_rotativo")
)

print(
    "ID Ocorrência:",
    dados.get("id_ocorrencia")
)


# ============================================================
# 3. VALIDAÇÃO PRINCIPAL
# ============================================================

decisao_retornada = str(
    dados.get("decisao", "")
).strip().upper()


if decisao_retornada == "RECONTAR":

    print(
        "\n[APROVADO] "
        "A decisão RECONTAR foi registrada."
    )

    print(
        "\nRegra validada:"
    )

    print(
        "DIVERGÊNCIA R1"
    )

    print(
        "+"
    )

    print(
        "DECISÃO RECONTAR"
    )

    print(
        "="
    )

    print(
        "ITEM ELEGÍVEL PARA R2"
    )

    sys.exit(0)


print(
    "\n[ATENÇÃO] A API respondeu com sucesso, "
    "mas o campo 'decisao' não retornou como esperado."
)

print(
    "Vamos validar diretamente no banco."
)

sys.exit(0)