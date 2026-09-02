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


def test_snapshot_duplicate():
    iid, _, _ = prepare("SNAP")
    expect_error(lambda: snapshot(iid), statuses=(400, 409))


def test_all_ok_and_finalization_idempotency():
    iid, r1, _ = prepare("OK")
    count_all_correct(iid, r1)
    out = next_round(iid)
    assert_true(out.get("proxima_rodada", {}).get("encerrado") is True, f"não finalizou na R1: {out}")
    before = final_result(iid)
    # Repetir a finalização deve ser segura: pode responder erro de estado ou retorno finalizado,
    # mas jamais deve alterar/duplicar o resultado final.
    try:
        next_round(iid)
    except ApiError as e:
        assert_true(e.status in (400, 409), f"status inesperado na repetição: {e.status}")
    after = final_result(iid)
    assert_true(before == after, "resultado final mudou após repetir finalização")


def test_recount_resolves_and_protections():
    iid, r1, items = prepare("R2OK")
    target = items[0]
    s = start(iid, r1); sid = s["id_sessao"]
    # todos corretos, exceto alvo +1
    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)
    close(sid)

    # sessão encerrada não aceita nova contagem
    expect_error(lambda: count(sid, target, max(1, qty_stock(target))), statuses=(400, 409))
    # divergência sem decisão bloqueia avanço
    expect_error(lambda: next_round(iid), statuses=(400, 409), contains="SEM TRATAMENTO")
    # RECONTAR sem justificativa deve aceitar
    d1 = decision(iid, r1, target, "RECONTAR")
    assert_true(d1.get("justificativa") is None, "RECONTAR ganhou justificativa indevida")
    # Valida o preview com uma única decisão ativa.
    # O teste de decisão repetida deve ser isolado: substituir uma decisão pode
    # também alterar ocorrências vinculadas e não deve contaminar o cenário
    # cujo objetivo é provar a resolução normal da R2.
    pv = preview(iid)
    cand = pv.get("preview", {}).get("itens_candidatos", [])
    assert_true(len(cand) == 1, f"R2 deveria ter exatamente 1 candidato: {cand}")
    ids = cand[0].get("ids_decisao_rotativo", [])
    assert_true(d1["id_decisao_rotativo"] in ids, f"preview não usa a decisão RECONTAR ativa: {ids}")

    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]
    assert_true(nr["proxima_rodada"].get("itens_gerados") == 1, "R2 não ficou restrita ao RECONTAR")
    # POST repetido não pode criar outra R2.
    # Com a R2 ainda aberta, a API atual responde 400 informando que a R2
    # ainda não foi concluída operacionalmente; isso é uma proteção válida.
    try:
        again = next_round(iid)
    except ApiError as e:
        assert_true(e.status in (400, 409), f"status inesperado no POST repetido da R2: {e.status}")
        again = None

    # Se a implementação responder 2xx, também é aceitável desde que
    # não crie uma rodada além da R2.
    if isinstance(again, dict):
        pr = again.get("proxima_rodada", {})
        assert_true(pr.get("numero_rodada", 2) <= 2, f"criou rodada indevida: {again}")

    s2 = start(iid, r2); sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)
    fin = next_round(iid)
    pr = fin["proxima_rodada"]
    assert_true(pr.get("status_inventario") == "FINALIZADO", f"inventário não finalizado: {fin}")
    assert_true(pr.get("resumo_r2", {}).get("resolvidos_r2") == 1, f"R2 não resolveu: {fin}")
    assert_true(pr.get("resultado_final", {}).get("fechamento_recontagens", {}).get("ocorrencias_resolvidas") == 1, "ocorrência não resolvida")


def test_justify_required_and_r1_terminal():
    iid, r1, items = prepare("JUST")
    target = items[0]
    s = start(iid, r1); sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q + 1 if it is target else q)
    close(sid)
    expect_error(lambda: decision(iid, r1, target, "JUSTIFICAR_DIVERGENCIA"), statuses=(400, 409, 422), contains="JUSTIFIC")
    d = decision(iid, r1, target, "JUSTIFICAR_DIVERGENCIA", "Divergência real - teste E2E automático")
    assert_true(bool(d.get("divergencia_justificada")), f"não marcou justificada: {d}")
    out = next_round(iid)
    pr = out.get("proxima_rodada", {})
    assert_true(pr.get("encerrado") is True, f"não encerrou após R1 justificada: {out}")
    assert_true(pr.get("numero_rodada") == 1, f"criou R2 indevidamente: {out}")


def test_recount_persistent_divergence():
    iid, r1, items = prepare("R2NOK")
    target = items[0]
    q0 = qty_stock(target)
    s = start(iid, r1); sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q + 1 if it is target else q)
    close(sid)
    decision(iid, r1, target, "RECONTAR")
    nr = next_round(iid); r2 = nr["proxima_rodada"]["id_rodada"]
    s2 = start(iid, r2); sid2 = s2["id_sessao"]
    count(sid2, target, q0 + 1)  # mantém a divergência
    close(sid2)
    fin = next_round(iid); pr = fin["proxima_rodada"]
    assert_true(pr.get("status_inventario") == "FINALIZADO", "R2 divergente não finalizou")
    assert_true(pr.get("resumo_r2", {}).get("divergencias_confirmadas") == 1, f"não confirmou divergência: {fin}")
    assert_true(pr.get("resultado_final", {}).get("fechamento_recontagens", {}).get("divergencias_confirmadas") == 1, "fechamento não confirmou divergência")


def run(name, fn):
    try:
        fn(); R.ok(name)
    except Exception as e:
        R.fail(name, e)


def main():
    print("=" * 68)
    print("SGI - SUÍTE E2E AUTOMÁTICA DO INVENTÁRIO ROTATIVO")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 68)
    api.login()
    R.ok("Autenticação")

    run("Snapshot não pode ser gerado duas vezes", test_snapshot_duplicate)
    run("R1 sem divergência + finalização idempotente", test_all_ok_and_finalization_idempotency)
    run("Proteções + RECONTAR sem justificativa + R2 resolvida", test_recount_resolves_and_protections)
    run("JUSTIFICAR exige texto + encerra na R1 sem R2", test_justify_required_and_r1_terminal)
    run("R2 persistente finaliza como divergência confirmada", test_recount_persistent_divergence)

    print("\n" + "=" * 68)
    print(f"PASS: {len(R.passed)} | FAIL: {len(R.failed)}")
    if R.failed:
        print("RESULTADO: REPROVADO")
        for x in R.failed:
            print(" -", x)
        sys.exit(1)
    print("RESULTADO: APROVADO")
    print("=" * 68)


if __name__ == "__main__":
    main()
