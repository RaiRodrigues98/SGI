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
    return f"TESTE-E2E-{tag}-{int(time.time()*1000)}"[-60:]


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



# ============================================================
# ESTÁGIO 2 - PROTEÇÕES E INTEGRIDADE DO ROTATIVO
# ============================================================

def test_decisao_duplicada_mesma_divergencia():
    iid, r1, items = prepare("DUPDEC")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)

    d1 = decision(iid, r1, target, "RECONTAR")
    assert_true(d1.get("status") == "ATIVA", f"primeira decisão inválida: {d1}")

    # Segunda decisão para a mesma chave.
    try:
        d2 = decision(iid, r1, target, "RECONTAR")
        # Se aceitar, o preview deve continuar com um único candidato lógico.
        pv = preview(iid)
        cand = pv.get("preview", {}).get("itens_candidatos", [])
        assert_true(len(cand) == 1, f"duplicou candidato lógico na R2: {cand}")

        ids = cand[0].get("ids_decisao_rotativo", [])
        assert_true(len(ids) >= 1, f"candidato sem decisão vinculada: {cand}")

        # Aceitar repetição só é tolerável se não quebrar o fluxo.
        nr = next_round(iid)
        r2 = nr["proxima_rodada"]["id_rodada"]

        s2 = start(iid, r2)
        sid2 = s2["id_sessao"]
        count(sid2, target, qty_stock(target))
        close(sid2)

        fin = next_round(iid)
        pr = fin["proxima_rodada"]
        assert_true(pr.get("status_inventario") == "FINALIZADO", f"duplicidade de decisão corrompeu finalização: {fin}")

        rf = pr.get("resultado_final", {})
        fech = rf.get("fechamento_recontagens", {})
        assert_true(
            int(fech.get("divergencias_confirmadas", 0)) == 0,
            f"decisão duplicada deixou divergência residual: {fech}"
        )

    except ApiError as e:
        # Bloquear a segunda decisão também é comportamento válido de proteção.
        assert_true(e.status in (400, 409), f"status inesperado para decisão duplicada: {e.status} - {e.data}")


def test_troca_recontar_para_justificar():
    iid, r1, items = prepare("RECONTAR_JUST")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)

    decision(iid, r1, target, "RECONTAR")

    try:
        d2 = decision(
            iid,
            r1,
            target,
            "JUSTIFICAR_DIVERGENCIA",
            "E2E - divergência confirmada após revisão"
        )

        pv = preview(iid)
        p = pv.get("preview", {})

        # Se a troca for aceita, a divergência não deve permanecer simultaneamente
        # como RECONTAR e JUSTIFICAR.
        cand = p.get("itens_candidatos", [])
        assert_true(
            len(cand) == 0 or all(c.get("motivo") != "DECISAO_ROTATIVO_RECONTAR" for c in cand),
            f"troca de decisão deixou RECONTAR ativo indevidamente: {cand}"
        )

        # Com todas as divergências justificadas, o fluxo deve encerrar sem R2.
        fin = next_round(iid)
        pr = fin["proxima_rodada"]
        assert_true(pr.get("status_inventario") == "FINALIZADO", f"troca para JUSTIFICAR não finalizou: {fin}")

    except ApiError as e:
        # Também é aceitável a API proibir alteração de decisão já registrada.
        assert_true(e.status in (400, 409), f"status inesperado na troca RECONTAR -> JUSTIFICAR: {e.status} - {e.data}")


def test_troca_justificar_para_recontar():
    iid, r1, items = prepare("JUST_RECONTAR")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)

    decision(
        iid,
        r1,
        target,
        "JUSTIFICAR_DIVERGENCIA",
        "E2E - justificativa inicial"
    )

    try:
        d2 = decision(iid, r1, target, "RECONTAR")
        pv = preview(iid)
        cand = pv.get("preview", {}).get("itens_candidatos", [])
        assert_true(len(cand) == 1, f"troca para RECONTAR não produziu candidato único: {cand}")

        nr = next_round(iid)
        r2 = nr["proxima_rodada"]["id_rodada"]

        s2 = start(iid, r2)
        sid2 = s2["id_sessao"]
        count(sid2, target, qty_stock(target))
        close(sid2)

        fin = next_round(iid)
        assert_true(
            fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
            f"troca JUSTIFICAR -> RECONTAR quebrou finalização: {fin}"
        )

    except ApiError as e:
        assert_true(e.status in (400, 409), f"status inesperado na troca JUSTIFICAR -> RECONTAR: {e.status} - {e.data}")


def test_duplo_post_criacao_r2():
    iid, r1, items = prepare("DUPR2")
    target = items[0]

    s = start(iid, r1)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)
    close(sid)

    decision(iid, r1, target, "RECONTAR")

    first = next_round(iid)
    r2 = first["proxima_rodada"]["id_rodada"]
    assert_true(first["proxima_rodada"].get("numero_rodada") == 2, f"primeira R2 inválida: {first}")

    try:
        second = next_round(iid)
        pr = second.get("proxima_rodada", {})
        assert_true(
            int(pr.get("numero_rodada", 2)) <= 2,
            f"duplo POST criou rodada acima de R2: {second}"
        )
        if pr.get("id_rodada") is not None:
            assert_true(
                pr.get("id_rodada") == r2 or pr.get("criada") is False,
                f"duplo POST criou outra R2 física: primeira={r2}; retorno={second}"
            )
    except ApiError as e:
        assert_true(e.status in (400, 409), f"status inesperado no duplo POST R2: {e.status} - {e.data}")


def test_item_nao_autorizado_na_r2():
    iid, r1, items = prepare("R2_ITEM_FORA")
    assert_true(len(items) >= 2, "teste requer pelo menos 2 itens no snapshot")
    target = items[0]
    fora = items[1]

    s = start(iid, r1)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)
    close(sid)

    decision(iid, r1, target, "RECONTAR")
    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]

    # Item fora da R2 não deve ser aceito.
    expect_error(
        lambda: count(sid2, fora, max(1, qty_stock(fora))),
        statuses=(400, 409, 422)
    )

    # O item autorizado continua funcionando.
    count(sid2, target, qty_stock(target))
    close(sid2)
    fin = next_round(iid)
    assert_true(fin["proxima_rodada"].get("status_inventario") == "FINALIZADO", f"finalização falhou: {fin}")


def test_operacao_apos_finalizado():
    iid, r1, items = prepare("POSFINAL")
    count_all_correct(iid, r1)
    fin = next_round(iid)

    assert_true(
        fin["proxima_rodada"].get("status_inventario") == "FINALIZADO",
        f"inventário não finalizou: {fin}"
    )

    # Não deve permitir nova abertura operacional após finalização.
    expect_error(
        lambda: start(iid, r1),
        statuses=(400, 409)
    )



def run(name, fn):
    """Executa um cenário sem interromper os demais testes da suíte."""
    try:
        fn()
        R.ok(name)
    except Exception as e:
        R.fail(name, e)


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 2 | PROTEÇÕES E INTEGRIDADE DO INVENTÁRIO ROTATIVO")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Decisão duplicada para a mesma divergência", test_decisao_duplicada_mesma_divergencia)
    run("Troca RECONTAR -> JUSTIFICAR", test_troca_recontar_para_justificar)
    run("Troca JUSTIFICAR -> RECONTAR", test_troca_justificar_para_recontar)
    run("Duplo POST de criação da R2", test_duplo_post_criacao_r2)
    run("Item não autorizado não pode ser contado na R2", test_item_nao_autorizado_na_r2)
    run("Operação após inventário finalizado", test_operacao_apos_finalizado)

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
