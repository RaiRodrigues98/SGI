"""Suíte E2E do inventário ROTATIVO do SGI.

Uso (PowerShell):
  $env:SGI_BASE_URL='http://127.0.0.1:8000'
  $env:SGI_LOGIN='dev'
  $env:SGI_PASSWORD='SUA_SENHA'
  python teste_rotativo_e2e.py

A suíte cria inventários TESTE-E2E-* e usa somente a API pública do SGI.
Não apaga dados e não altera código/configurações do sistema.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

BASE = os.getenv("SGI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LOGIN = os.getenv("SGI_LOGIN", "")
PASSWORD = os.getenv("SGI_PASSWORD", "")
CLIENTE_ID = int(os.getenv("SGI_CLIENTE_ID", "53"))
CLIENTE = os.getenv("SGI_CLIENTE", "endress")
ARMAZEM = os.getenv("SGI_ARMAZEM", "ML007")
LOCALIZACAO = os.getenv("SGI_LOCALIZACAO", "01PLAQUETA").strip().upper()
TIMEOUT = float(os.getenv("SGI_TIMEOUT", "30"))


class ApiError(RuntimeError):
    def __init__(self, status: int, data: Any, method: str, path: str):
        self.status = status
        self.data = data
        self.method = method
        self.path = path
        super().__init__(f"HTTP {status} {method} {path}: {data}")


class API:
    def __init__(self):
        self.token = ""

    def request(self, method: str, path: str, body: Any = None, expected=(200, 201)) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        raw = None
        if body is not None:
            raw = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(BASE + path, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8") or "null")
                if r.status not in expected:
                    raise ApiError(r.status, data, method, path)
                return data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8") or "null")
            except Exception:
                data = str(e)
            if e.code in expected:
                return data
            raise ApiError(e.code, data, method, path)

    def login(self):
        if not LOGIN or not PASSWORD:
            raise RuntimeError("Defina SGI_LOGIN e SGI_PASSWORD antes de executar.")
        r = self.request("POST", "/auth/login", {"login": LOGIN, "senha": PASSWORD})
        self.token = r["access_token"]


api = API()


@dataclass
class Report:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def ok(self, name: str):
        self.passed.append(name)
        print(f"[PASS] {name}")

    def fail(self, name: str, exc: Exception | str):
        msg = f"{name}: {exc}"
        self.failed.append(msg)
        print(f"[FAIL] {msg}")

    def skip(self, name: str, reason: Exception | str):
        msg = f"{name}: {reason}"
        self.skipped.append(msg)
        print(f"[SKIP] {msg}")


class FixtureUnavailable(RuntimeError):
    """Pré-condição externa ausente; não é regressão funcional do SGI."""
    pass


R = Report()


def assert_true(value, msg):
    if not value:
        raise AssertionError(msg)


def expect_error(fn, statuses=(400, 409, 422), contains: str | None = None):
    try:
        fn()
    except ApiError as e:
        assert_true(e.status in statuses, f"status inesperado: {e.status}; retorno={e.data}")
        if contains:
            text = json.dumps(e.data, ensure_ascii=False).upper()
            assert_true(contains.upper() in text, f"mensagem não contém {contains!r}: {e.data}")
        return e
    raise AssertionError("A operação deveria ter sido bloqueada, mas foi aceita.")


def unique_code(tag: str) -> str:
    # CodigoInventario no banco aceita no máximo 30 caracteres.
    # Mantém o identificador legível e ainda suficientemente único para E2E.
    tag_curta = "".join(ch for ch in tag.upper() if ch.isalnum())[:8]
    sufixo = str(int(time.time() * 1000))[-10:]
    return f"E2E-{tag_curta}-{sufixo}"[:30]


def create_inventory(tag: str):
    r = api.request("POST", "/inventarios", {
        "codigo_inventario": unique_code(tag),
        "tipo": "ROTATIVO",
        "cliente_id": CLIENTE_ID,
        "cliente": CLIENTE,
        "descricao": f"E2E automático ROTATIVO - {tag}",
        "armazem": ARMAZEM,
    })
    return r["id_inventario"], r["id_rodada"]


def add_scope(iid: int):
    return api.request("POST", f"/inventarios/{iid}/escopo/localizacoes", {"localizacoes": [LOCALIZACAO]})


def snapshot(iid: int):
    return api.request("POST", f"/inventarios/{iid}/snapshot", {})


def analysis(iid: int):
    return api.request("GET", f"/inventarios/{iid}/analise-rotativo")


def snapshot_items(iid: int):
    a = analysis(iid)
    items = [x for x in a.get("itens", []) if str(x.get("localizacao", "")).strip().upper() == LOCALIZACAO]
    assert_true(items, f"Nenhum item encontrado na análise para {LOCALIZACAO}")
    return items


def start(iid: int, rid: int):
    return api.request("POST", "/localizacoes/iniciar", {"id_inventario": iid, "id_rodada": rid, "localizacao": LOCALIZACAO})


def count(sid: int, item: dict, qty: float):
    return api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "quantidade": qty,
    })


def close(sid: int, empty=False):
    return api.request("POST", "/localizacoes/encerrar", {"id_sessao": sid, "localizacao_vazia": empty})


def next_round(iid: int):
    return api.request("POST", f"/inventarios/{iid}/rodadas/proxima")


def preview(iid: int):
    return api.request("GET", f"/inventarios/{iid}/rodadas/proxima-preview")


def decision(iid: int, rid: int, item: dict, kind: str, justification=None):
    body = {
        "id_rodada": rid,
        "localizacao": LOCALIZACAO,
        "codigo": str(item["codigo"]),
        "lote": item.get("lote") or "",
        "decisao": kind,
    }
    if justification is not None:
        body["justificativa"] = justification
    return api.request("POST", f"/inventarios/{iid}/decisoes-rotativo", body)


def final_result(iid: int):
    return api.request("GET", f"/inventarios/{iid}/resultado-final")


def qty_stock(item: dict) -> float:
    for k in ("qtd_estoque", "quantidade_estoque", "saldo_inventario"):
        if k in item and item[k] is not None:
            return float(item[k])
    raise AssertionError(f"Campo de estoque não localizado no item: {item}")


def count_all_correct(iid: int, rid: int):
    items = snapshot_items(iid)
    s = start(iid, rid)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid, empty=False)
    return items, sid


def prepare(tag: str):
    iid, r1 = create_inventory(tag)
    add_scope(iid)
    s = snapshot(iid)
    assert_true(int(s.get("registros_snapshot", 0)) > 0, "snapshot vazio")
    items = snapshot_items(iid)
    return iid, r1, items



def run(name, fn):
    try:
        fn()
        R.ok(name)
    except FixtureUnavailable as e:
        R.skip(name, str(e))
    except Exception as e:
        R.fail(name, str(e))









# ============================================================
# ESTÁGIO 9 - COBERTURA E CICLO DO INVENTÁRIO ROTATIVO
# ============================================================

from urllib.parse import urlencode

CTX: dict[str, Any] = {}


def norm(v):
    return "" if v is None else str(v).strip().upper()


def qpath(path: str, **params):
    clean = {k: v for k, v in params.items() if v is not None}
    return path + ("?" + urlencode(clean) if clean else "")


def ciclo_atual():
    return api.request(
        "GET",
        qpath(
            "/rotativo/ciclos/atual",
            cliente_id=CLIENTE_ID,
            armazem=ARMAZEM,
        ),
    )


def abrir_ciclo():
    return api.request(
        "POST",
        "/rotativo/ciclos",
        {
            "cliente_id": CLIENTE_ID,
            "armazem": ARMAZEM,
            "criado_por": LOGIN or "e2e",
        },
    )


def consultar_localizacoes_ciclo(id_ciclo: int | None = None, **filtros):
    params = {
        "cliente_id": CLIENTE_ID,
        "armazem": ARMAZEM,
        "id_ciclo": id_ciclo,
    }
    params.update(filtros)
    return api.request(
        "GET",
        qpath("/rotativo/ciclos/localizacoes", **params),
    )


def iniciar_localizacao_ciclo(
    id_ciclo_localizacao: int,
    id_inventario: int,
    id_rodada: int,
):
    return api.request(
        "POST",
        "/rotativo/ciclos/localizacoes/iniciar",
        {
            "id_ciclo_localizacao": id_ciclo_localizacao,
            "id_inventario": id_inventario,
            "id_rodada": id_rodada,
            "usuario": LOGIN or "e2e",
        },
    )


def concluir_localizacao_ciclo(id_sessao: int):
    return api.request(
        "POST",
        "/rotativo/ciclos/localizacoes/concluir",
        {
            "id_sessao": id_sessao,
            "usuario": LOGIN or "e2e",
        },
    )


def add_scope_custom(iid: int, location: str):
    return api.request(
        "POST",
        f"/inventarios/{iid}/escopo/localizacoes",
        {"localizacoes": [location]},
    )


def snapshot_items_location(iid: int, location: str):
    a = analysis(iid)
    itens = [
        x for x in a.get("itens", [])
        if norm(x.get("localizacao")) == norm(location)
    ]
    return itens


def start_custom(iid: int, rid: int, location: str):
    return api.request(
        "POST",
        "/localizacoes/iniciar",
        {
            "id_inventario": iid,
            "id_rodada": rid,
            "localizacao": location,
        },
    )


def criar_inventario_para_localizacao(location: str, tag: str):
    iid, r1 = create_inventory(tag)
    add_scope_custom(iid, location)
    snap = snapshot(iid)
    total = int(
        snap.get(
            "registros_snapshot",
            snap.get("total_registros", snap.get("quantidade_registros", 0))
        )
        or 0
    )
    itens = snapshot_items_location(iid, location)
    return iid, r1, total, itens


def selecionar_localizacao_pendente_com_estoque(id_ciclo: int):
    consulta = consultar_localizacoes_ciclo(
        id_ciclo=id_ciclo,
        status="PENDENTE",
        somente_pendentes=True,
        ordenar_por="PRIORIDADE",
    )

    pendentes = consulta.get("localizacoes", [])
    if not pendentes:
        raise FixtureUnavailable(
            "O ciclo aberto não possui localização PENDENTE; "
            "estado residual do ambiente impede executar os cenários operacionais."
        )

    # Prefere a localização padrão do ambiente, caso esteja pendente.
    pendentes.sort(
        key=lambda x: 0 if norm(x.get("localizacao")) == LOCALIZACAO else 1
    )

    tentativas = []
    for loc in pendentes[:20]:
        location = norm(loc.get("localizacao"))
        if not location:
            continue

        try:
            iid, r1, total, itens = criar_inventario_para_localizacao(
                location,
                "CICLOCOV"
            )
            positivos = [it for it in itens if qty_stock(it) > 0]
            tentativas.append((location, total, len(positivos)))

            if total > 0 and positivos:
                return {
                    "id_ciclo_localizacao": int(loc["id_ciclo_localizacao"]),
                    "id_rotativo_localizacao": loc.get("id_rotativo_localizacao"),
                    "localizacao": location,
                    "id_inventario": iid,
                    "id_rodada": r1,
                    "itens": itens,
                    "positivos": positivos,
                }
        except Exception as e:
            tentativas.append((location, "ERRO", str(e)))

    raise AssertionError(
        "Nenhuma localização PENDENTE do ciclo apresentou estoque utilizável "
        f"para o E2E. Tentativas: {tentativas}"
    )


def localizar_no_retorno(consulta: dict, location: str):
    for loc in consulta.get("localizacoes", []):
        if norm(loc.get("localizacao")) == norm(location):
            return loc
    return None


def test_ciclo_aberto_ou_criado_e_idempotente():
    atual = ciclo_atual()

    if atual.get("possui_ciclo_aberto"):
        ciclo = atual["ciclo"]
    else:
        aberto = abrir_ciclo()
        ciclo = aberto.get("ciclo", {})
        assert_true(ciclo, f"abertura não retornou ciclo: {aberto}")

    assert_true(int(ciclo.get("id_ciclo", 0)) > 0, f"ID de ciclo inválido: {ciclo}")
    assert_true(norm(ciclo.get("status")) == "ABERTO", f"ciclo não está ABERTO: {ciclo}")

    CTX["id_ciclo"] = int(ciclo["id_ciclo"])

    # Abrir novamente deve reutilizar o ciclo atual, não criar outro.
    again = abrir_ciclo()
    ciclo2 = again.get("ciclo", {})
    assert_true(
        int(ciclo2.get("id_ciclo", 0)) == CTX["id_ciclo"],
        f"segunda abertura criou/retornou outro ciclo: {again}"
    )
    assert_true(
        again.get("criado") is False or norm(again.get("motivo")) == "CICLO_JA_ABERTO",
        f"segunda abertura não foi tratada como idempotente: {again}"
    )


def test_consulta_ciclo_e_cobertura_inicial_coerentes():
    cid = CTX["id_ciclo"]
    consulta = consultar_localizacoes_ciclo(id_ciclo=cid)
    ciclo = consulta.get("ciclo", {})

    assert_true(consulta.get("possui_ciclo") is True, f"consulta sem ciclo: {consulta}")
    total = int(ciclo.get("total_localizacoes", 0))
    pend = int(ciclo.get("localizacoes_pendentes", 0))
    em = int(ciclo.get("localizacoes_em_contagem", 0))
    cont = int(ciclo.get("localizacoes_contadas", 0))
    ign = int(ciclo.get("localizacoes_ignoradas", 0))

    assert_true(total > 0, f"ciclo sem localizações: {ciclo}")
    assert_true(
        total == pend + em + cont + ign,
        f"quebra do balanço de cobertura: {ciclo}"
    )

    esperado = round(((cont + ign) / total) * 100, 2)
    recebido = float(ciclo.get("percentual_cobertura", 0) or 0)
    assert_true(
        abs(recebido - esperado) < 0.011,
        f"percentual de cobertura incoerente: esperado={esperado}; recebido={recebido}; ciclo={ciclo}"
    )

    CTX["cobertura_antes"] = recebido
    CTX["contadas_antes"] = cont
    CTX["processadas_antes"] = cont + ign


def test_seleciona_localizacao_pendente_e_inicia_no_ciclo():
    alvo = selecionar_localizacao_pendente_com_estoque(CTX["id_ciclo"])
    CTX.update(alvo)

    r = iniciar_localizacao_ciclo(
        alvo["id_ciclo_localizacao"],
        alvo["id_inventario"],
        alvo["id_rodada"],
    )

    status_inicio = r.get("status_atual", r.get("status"))
    assert_true(
        norm(status_inicio) == "EM_CONTAGEM",
        f"localização não entrou em EM_CONTAGEM: {r}"
    )

    # Segunda chamada deve ser idempotente.
    r2 = iniciar_localizacao_ciclo(
        alvo["id_ciclo_localizacao"],
        alvo["id_inventario"],
        alvo["id_rodada"],
    )
    status_inicio_2 = r2.get("status_atual", r2.get("status"))
    assert_true(
        norm(status_inicio_2) == "EM_CONTAGEM",
        f"segunda inicialização alterou estado incorretamente: {r2}"
    )

    consulta = consultar_localizacoes_ciclo(id_ciclo=CTX["id_ciclo"])
    loc = localizar_no_retorno(consulta, alvo["localizacao"])
    assert_true(loc is not None, f"localização sumiu do ciclo: {consulta}")
    assert_true(
        norm(loc.get("status_ciclo")) == "EM_CONTAGEM",
        f"consulta não refletiu EM_CONTAGEM: {loc}"
    )


def require_operational_context():
    required = ("id_inventario", "id_rodada", "localizacao")
    missing = [k for k in required if k not in CTX]
    if missing:
        raise FixtureUnavailable(
            "Contexto operacional não preparado "
            f"(ausentes: {', '.join(missing)})."
        )


def test_conclusao_operacional_atualiza_cobertura():
    require_operational_context()
    iid = CTX["id_inventario"]
    rid = CTX["id_rodada"]
    location = CTX["localizacao"]
    itens = CTX["itens"]

    s = start_custom(iid, rid, location)
    sid = int(s["id_sessao"])
    CTX["id_sessao"] = sid

    for it in itens:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)

    close(sid)

    concluido = concluir_localizacao_ciclo(sid)
    CTX["retorno_conclusao"] = concluido

    assert_true(
        concluido.get("registrado") is True,
        f"cobertura não foi registrada: {concluido}"
    )
    assert_true(
        norm(concluido.get("motivo")) == "LOCALIZACAO_CONTADA_REGISTRADA",
        f"motivo inesperado na conclusão: {concluido}"
    )

    ciclo_ret = concluido.get("ciclo", {})
    assert_true(
        int(ciclo_ret.get("localizacoes_contadas", 0)) >= CTX["contadas_antes"] + 1,
        f"contador de localizações contadas não avançou: {ciclo_ret}"
    )

    consulta = consultar_localizacoes_ciclo(id_ciclo=CTX["id_ciclo"])
    loc = localizar_no_retorno(consulta, location)
    assert_true(loc is not None, f"localização não encontrada após conclusão: {consulta}")
    assert_true(
        norm(loc.get("status_ciclo")) == "CONTADA",
        f"localização não ficou CONTADA: {loc}"
    )

    ciclo = consulta.get("ciclo", {})
    assert_true(
        int(ciclo.get("localizacoes_contadas", 0)) >= CTX["contadas_antes"] + 1,
        f"consulta não refletiu incremento da cobertura: {ciclo}"
    )
    assert_true(
        float(ciclo.get("percentual_cobertura", 0) or 0) >= CTX["cobertura_antes"],
        f"percentual de cobertura regrediu: antes={CTX['cobertura_antes']}; depois={ciclo}"
    )


def test_conclusao_nao_duplica_cobertura():
    require_operational_context()
    if "id_sessao" not in CTX:
        raise FixtureUnavailable("Sessão operacional não foi criada.")
    sid = CTX["id_sessao"]

    try:
        segunda = concluir_localizacao_ciclo(sid)
        assert_true(
            segunda.get("registrado") is False,
            f"segunda conclusão deveria ser idempotente: {segunda}"
        )
        assert_true(
            norm(segunda.get("motivo")) == "LOCALIZACAO_JA_CONTADA_NO_CICLO",
            f"motivo inesperado na segunda conclusão: {segunda}"
        )
    except ApiError as e:
        # Se a localização era a última pendente, a primeira conclusão pode ter
        # encerrado o ciclo. Nesse caso não existe mais ciclo ABERTO para a
        # rotina operacional localizar, mas a cobertura já está consolidada.
        primeiro = CTX.get("retorno_conclusao", {})
        ciclo = primeiro.get("ciclo", {})
        assert_true(
            ciclo.get("ciclo_concluido") is True and e.status == 400,
            f"segunda conclusão falhou fora do caso de ciclo encerrado: {e}"
        )

    consulta = consultar_localizacoes_ciclo(id_ciclo=CTX["id_ciclo"])
    loc = localizar_no_retorno(consulta, CTX["localizacao"])
    assert_true(
        loc is not None and norm(loc.get("status_ciclo")) == "CONTADA",
        f"estado final da localização foi alterado indevidamente: {loc}"
    )


def test_vinculo_inventario_rodada_e_ultima_contagem():
    require_operational_context()
    if "id_sessao" not in CTX:
        raise FixtureUnavailable("Conclusão operacional não foi executada.")
    consulta = consultar_localizacoes_ciclo(id_ciclo=CTX["id_ciclo"])
    loc = localizar_no_retorno(consulta, CTX["localizacao"])
    assert_true(loc is not None, f"localização não encontrada: {consulta}")

    contagem_ciclo = loc.get("contagem_ciclo", {})

    id_inventario_ciclo = contagem_ciclo.get(
        "id_inventario",
        loc.get("id_inventario")
    )
    id_rodada_ciclo = contagem_ciclo.get(
        "id_rodada",
        loc.get("id_rodada")
    )
    data_conclusao = contagem_ciclo.get(
        "data_conclusao",
        loc.get("data_conclusao")
    )

    assert_true(
        int(id_inventario_ciclo or 0) == int(CTX["id_inventario"]),
        f"ID_Inventario do ciclo não corresponde ao executado: {loc}"
    )
    assert_true(
        int(id_rodada_ciclo or 0) == int(CTX["id_rodada"]),
        f"ID_Rodada do ciclo não corresponde ao executado: {loc}"
    )
    assert_true(
        data_conclusao is not None,
        f"DataConclusao não foi registrada: {loc}"
    )

    # A consulta operacional combina CicloRotativoLocalizacoes com
    # RotativoLocalizacoes, permitindo validar a última contagem consolidada.
    assert_true(
        int(loc.get("id_inventario_ultima_contagem") or 0) == int(CTX["id_inventario"]),
        f"RotativoLocalizacoes não recebeu o último inventário: {loc}"
    )
    assert_true(
        int(loc.get("id_rodada_ultima_contagem") or 0) == int(CTX["id_rodada"]),
        f"RotativoLocalizacoes não recebeu a última rodada: {loc}"
    )
    assert_true(
        loc.get("ultima_contagem") is not None,
        f"UltimaContagem não foi atualizada: {loc}"
    )


def test_filtros_operacionais_respeitam_status():
    require_operational_context()
    cid = CTX["id_ciclo"]

    contadas = consultar_localizacoes_ciclo(
        id_ciclo=cid,
        status="CONTADA",
    )
    lista = contadas.get("localizacoes", [])

    assert_true(
        all(norm(x.get("status_ciclo")) == "CONTADA" for x in lista),
        f"filtro status=CONTADA retornou outro status: {lista}"
    )
    assert_true(
        any(norm(x.get("localizacao")) == norm(CTX["localizacao"]) for x in lista),
        f"localização recém-contada não apareceu no filtro CONTADA: {lista}"
    )

    pendentes = consultar_localizacoes_ciclo(
        id_ciclo=cid,
        somente_pendentes=True,
    )
    assert_true(
        all(norm(x.get("status_ciclo")) == "PENDENTE" for x in pendentes.get("localizacoes", [])),
        f"somente_pendentes retornou status indevido: {pendentes}"
    )


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 9 | COBERTURA E CICLO DO INVENTÁRIO ROTATIVO")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Ciclo aberto/criado e abertura idempotente", test_ciclo_aberto_ou_criado_e_idempotente)
    run("Consulta e cobertura inicial são coerentes", test_consulta_ciclo_e_cobertura_inicial_coerentes)
    run("Localização pendente entra em EM_CONTAGEM", test_seleciona_localizacao_pendente_e_inicia_no_ciclo)
    run("Conclusão operacional atualiza cobertura", test_conclusao_operacional_atualiza_cobertura)
    run("Conclusão repetida não duplica cobertura", test_conclusao_nao_duplica_cobertura)
    run("Vínculo inventário/rodada e última contagem são preservados", test_vinculo_inventario_rodada_e_ultima_contagem)
    run("Filtros operacionais respeitam o status do ciclo", test_filtros_operacionais_respeitam_status)

    print("\n" + "=" * 72)
    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)} | SKIP: {len(R.skipped)}")
    if R.failed:
        print("RESULTADO: REPROVADO")
        for x in R.failed:
            print(" -", x)
        sys.exit(1)

    print("RESULTADO: APROVADO")
    print("=" * 72)


if __name__ == "__main__":
    main()
