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

    def ok(self, name: str):
        self.passed.append(name)
        print(f"[PASS] {name}")

    def fail(self, name: str, exc: Exception | str):
        msg = f"{name}: {exc}"
        self.failed.append(msg)
        print(f"[FAIL] {msg}")


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
    except Exception as e:
        R.fail(name, str(e))







# ============================================================
# ESTÁGIO 7 - DECISÕES, OCORRÊNCIAS E RASTREABILIDADE
# ============================================================

def norm(v):
    return "" if v is None else str(v).strip().upper()


def choose_positive(items):
    for it in items:
        if qty_stock(it) > 0:
            return it
    raise AssertionError("Nenhum item com saldo positivo disponível.")


def make_one_divergence(tag):
    iid, r1, items = prepare(tag)
    target = choose_positive(items)

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)
    return iid, r1, items, target


def test_recontar_cria_decisao_e_ocorrencia_vinculadas():
    iid, r1, items, target = make_one_divergence("OCCLINK")

    d = decision(iid, r1, target, "RECONTAR")

    id_decisao = d.get("id_decisao_rotativo")
    assert_true(id_decisao is not None, f"decisão sem ID: {d}")
    assert_true(d.get("id_ocorrencia") is not None, f"decisão sem ocorrência vinculada: {d}")
    assert_true(norm(d.get("status")) == "ATIVA", f"decisão deveria estar ATIVA: {d}")

    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])
    assert_true(len(cand) == 1, f"preview deveria ter um candidato: {cand}")

    ids = cand[0].get("ids_decisao_rotativo", [])
    assert_true(
        int(id_decisao) in [int(x) for x in ids],
        f"preview não referencia a decisão ativa {id_decisao}: {cand}"
    )


def test_recontagem_resolvida_fecha_ocorrencia():
    iid, r1, items, target = make_one_divergence("OCCRES")
    d = decision(iid, r1, target, "RECONTAR")

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)

    fin = next_round(iid)
    pr = fin["proxima_rodada"]

    assert_true(pr.get("status_inventario") == "FINALIZADO", f"inventário não finalizou: {fin}")

    fechamento = pr.get("resultado_final", {}).get("fechamento_recontagens", {})
    if not fechamento:
        fechamento = pr.get("resumo_r2", {})

    assert_true(
        int(fechamento.get("ocorrencias_resolvidas", 0)) == 1,
        f"ocorrência resolvida não contabilizada: {fechamento}"
    )
    assert_true(
        int(fechamento.get("divergencias_confirmadas", 0)) == 0,
        f"recontagem correta ficou como divergência confirmada: {fechamento}"
    )


def test_recontagem_persistente_confirma_divergencia():
    iid, r1, items, target = make_one_divergence("OCCCONF")
    decision(iid, r1, target, "RECONTAR")

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target) + 1)
    close(sid2)

    fin = next_round(iid)
    pr = fin["proxima_rodada"]

    assert_true(pr.get("status_inventario") == "FINALIZADO", f"inventário não finalizou: {fin}")

    fechamento = pr.get("resultado_final", {}).get("fechamento_recontagens", {})
    if not fechamento:
        fechamento = pr.get("resumo_r2", {})

    assert_true(
        int(fechamento.get("divergencias_confirmadas", 0)) == 1,
        f"divergência persistente não foi confirmada: {fechamento}"
    )
    assert_true(
        int(fechamento.get("ocorrencias_resolvidas", fechamento.get("resolvidos_r2", 0))) == 0,
        f"divergência persistente foi marcada como resolvida: {fechamento}"
    )


def test_justificar_nao_cria_r2_e_preserva_divergencia():
    iid, r1, items, target = make_one_divergence("OCCJUST")

    d = decision(
        iid,
        r1,
        target,
        "JUSTIFICAR_DIVERGENCIA",
        "E2E - divergência física confirmada e justificada"
    )

    assert_true(d.get("id_ocorrencia") is not None, f"justificativa sem ocorrência: {d}")

    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])
    assert_true(len(cand) == 0, f"JUSTIFICAR gerou candidato de R2: {cand}")

    fin = next_round(iid)
    pr = fin["proxima_rodada"]

    assert_true(pr.get("status_inventario") == "FINALIZADO", f"JUSTIFICAR não finalizou na R1: {fin}")
    assert_true(pr.get("criada") is False, f"JUSTIFICAR criou R2 indevidamente: {fin}")

    rf = final_result(iid)
    finais = rf.get("itens", [])

    alvo = None
    for it in finais:
        if norm(it.get("localizacao")) == norm(LOCALIZACAO) \
           and norm(it.get("codigo")) == norm(target.get("codigo")) \
           and norm(it.get("lote")) == norm(target.get("lote")):
            alvo = it
            break

    assert_true(alvo is not None, f"item justificado ausente do resultado final: {rf}")
    assert_true(
        float(alvo.get("diferenca_final", alvo.get("diferenca", 0))) != 0,
        f"divergência justificada desapareceu do resultado final: {alvo}"
    )


def test_substituicao_decisao_nao_duplica_candidato():
    iid, r1, items, target = make_one_divergence("OCCSUB")

    d1 = decision(iid, r1, target, "RECONTAR")
    d2 = decision(iid, r1, target, "RECONTAR")

    assert_true(
        int(d1["id_decisao_rotativo"]) != int(d2["id_decisao_rotativo"]),
        f"segunda decisão não gerou novo registro rastreável: d1={d1}; d2={d2}"
    )

    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])

    assert_true(len(cand) == 1, f"substituição duplicou candidato físico da R2: {cand}")

    ids = [int(x) for x in cand[0].get("ids_decisao_rotativo", [])]
    assert_true(
        int(d2["id_decisao_rotativo"]) in ids,
        f"preview não aponta para a decisão mais recente: d1={d1}; d2={d2}; cand={cand}"
    )

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"substituição de decisão corrompeu encerramento: {fin}"
    )


def test_troca_para_justificar_remove_candidato_r2():
    iid, r1, items, target = make_one_divergence("OCCCHG")

    decision(iid, r1, target, "RECONTAR")
    decision(
        iid,
        r1,
        target,
        "JUSTIFICAR_DIVERGENCIA",
        "E2E - decisão alterada antes da criação da R2"
    )

    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])

    assert_true(
        len(cand) == 0,
        f"RECONTAR substituído permaneceu ativo no preview: {cand}"
    )

    fin = next_round(iid)
    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"troca para JUSTIFICAR não encerrou na R1: {fin}"
    )


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 7 | DECISÕES, OCORRÊNCIAS E RASTREABILIDADE")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("RECONTAR cria decisão e ocorrência vinculadas", test_recontar_cria_decisao_e_ocorrencia_vinculadas)
    run("R2 resolvida fecha corretamente a ocorrência", test_recontagem_resolvida_fecha_ocorrencia)
    run("R2 persistente confirma a divergência", test_recontagem_persistente_confirma_divergencia)
    run("JUSTIFICAR não cria R2 e preserva divergência final", test_justificar_nao_cria_r2_e_preserva_divergencia)
    run("Substituição de decisão não duplica candidato da R2", test_substituicao_decisao_nao_duplica_candidato)
    run("Troca RECONTAR -> JUSTIFICAR remove candidato da R2", test_troca_para_justificar_remove_candidato_r2)

    print("\n" + "=" * 72)
    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")
    if R.failed:
        print("RESULTADO: REPROVADO")
        for x in R.failed:
            print(" -", x)
        sys.exit(1)

    print("RESULTADO: APROVADO")
    print("=" * 72)


if __name__ == "__main__":
    main()
