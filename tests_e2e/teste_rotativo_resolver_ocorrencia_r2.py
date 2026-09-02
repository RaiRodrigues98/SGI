import sys
from pathlib import Path


# ============================================================
# CONFIGURA PYTHON PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR)
    )


from database import get_connection

from services.finalizacao_rotativo import (
    _resolver_recontagens_rotativo,
)


ID_INVENTARIO = 13
ID_RODADA_R1 = 25
ID_RODADA_R2 = 27

ID_OCORRENCIA = 5
ID_DECISAO = 5

def titulo(texto):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


conn = None
cursor = None


try:

    # ============================================================
    # 1. CONEXÃO
    # ============================================================

    titulo("1. CONECTANDO AO BANCO")

    conn = get_connection()
    cursor = conn.cursor()

    print("[OK] Conexão realizada")


    # ============================================================
    # 2. ESTADO ANTES
    # ============================================================

    titulo("2. ESTADO ANTES DA RESOLUÇÃO")

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            StatusResolucao,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ResolvidoPor,
            DataHoraResolucao
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA,
    )

    ocorrencia_antes = cursor.fetchone()

    if not ocorrencia_antes:
        print("[FALHOU] Ocorrência não encontrada.")
        sys.exit(1)

    print("Ocorrência:", ocorrencia_antes.ID_Ocorrencia)
    print("Status:", ocorrencia_antes.StatusResolucao)
    print(
        "Rodada resolução:",
        ocorrencia_antes.ID_RodadaResolucao,
    )

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
            Decisao,
            Status
        FROM dbo.DecisoesRotativo
        WHERE ID_DecisaoRotativo = ?
        """,
        ID_DECISAO,
    )

    decisao_antes = cursor.fetchone()

    if not decisao_antes:
        print("[FALHOU] Decisão não encontrada.")
        sys.exit(1)

    print("\nDecisão:", decisao_antes.ID_DecisaoRotativo)
    print("Tipo:", decisao_antes.Decisao)
    print("Status:", decisao_antes.Status)


    # ============================================================
    # 3. EXECUTAR TRANSIÇÃO
    # ============================================================

    titulo("3. RESOLVENDO RECONTAGEM")

    resultado = _resolver_recontagens_rotativo(
        cursor=cursor,
        id_inventario=ID_INVENTARIO,
        id_rodada_r1=ID_RODADA_R1,
        id_rodada_r2=ID_RODADA_R2,
        usuario="teste_e2e",
    )

    print("Resultado:", resultado)

    conn.commit()

    print("[OK] Commit realizado")


    # ============================================================
    # 4. VALIDAR OCORRÊNCIA
    # ============================================================

    titulo("4. VALIDANDO OCORRÊNCIA")

    cursor.execute(
        """
        SELECT
            ID_Ocorrencia,
            StatusResolucao,
            ID_InventarioResolucao,
            ID_RodadaResolucao,
            TipoResolucao,
            ObservacaoResolucao,
            ResolvidoPor,
            DataHoraResolucao
        FROM dbo.OcorrenciasDivergencia
        WHERE ID_Ocorrencia = ?
        """,
        ID_OCORRENCIA,
    )

    ocorrencia = cursor.fetchone()

    print("ID Ocorrência:", ocorrencia.ID_Ocorrencia)
    print("Status:", ocorrencia.StatusResolucao)
    print(
        "ID Inventário resolução:",
        ocorrencia.ID_InventarioResolucao,
    )
    print(
        "ID Rodada resolução:",
        ocorrencia.ID_RodadaResolucao,
    )
    print("Tipo resolução:", ocorrencia.TipoResolucao)
    print(
        "Observação:",
        ocorrencia.ObservacaoResolucao,
    )
    print("Resolvido por:", ocorrencia.ResolvidoPor)
    print(
        "Data resolução:",
        ocorrencia.DataHoraResolucao,
    )


    # ============================================================
    # 5. VALIDAR DECISÃO
    # ============================================================

    titulo("5. VALIDANDO DECISÃO")

    cursor.execute(
        """
        SELECT
            ID_DecisaoRotativo,
            Decisao,
            Status
        FROM dbo.DecisoesRotativo
        WHERE ID_DecisaoRotativo = ?
        """,
        ID_DECISAO,
    )

    decisao = cursor.fetchone()

    print("ID Decisão:", decisao.ID_DecisaoRotativo)
    print("Decisão:", decisao.Decisao)
    print("Status:", decisao.Status)


    # ============================================================
    # 6. RESULTADO
    # ============================================================

    titulo("RESULTADO")

    ocorrencia_ok = (
        ocorrencia.StatusResolucao
        == "RESOLVIDA_RECONTAGEM"
        and
        ocorrencia.ID_InventarioResolucao
        == ID_INVENTARIO
        and
        ocorrencia.ID_RodadaResolucao
        == ID_RODADA_R2
        and
        ocorrencia.TipoResolucao
        == "RECONTAGEM"
        and
        ocorrencia.DataHoraResolucao
        is not None
    )

    decisao_ok = (
        decisao.Decisao == "RECONTAR"
        and
        decisao.Status == "CONCLUIDA"
    )

    if ocorrencia_ok and decisao_ok:

        print(
            "[APROVADO] A recontagem foi encerrada "
            "corretamente."
        )

        print("\nRegra validada:")

        print(
            "EM_RECONTAGEM"
        )

        print(
            "+"
        )

        print(
            "R2 RESOLVIDA"
        )

        print(
            "="
        )

        print(
            "RESOLVIDA_RECONTAGEM"
        )

        print(
            "+"
        )

        print(
            "DECISÃO RECONTAR = CONCLUIDA"
        )

        sys.exit(0)


    print(
        "[FALHOU] A ocorrência ou a decisão "
        "não foi atualizada corretamente."
    )

    sys.exit(1)


except Exception as erro:

    if conn:
        conn.rollback()

    print("\n[ERRO]")
    print(type(erro).__name__)
    print(str(erro))

    sys.exit(1)


finally:

    if cursor:
        cursor.close()

    if conn:
        conn.close()