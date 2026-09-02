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
# ESTÁGIO 5 - CLASSIFICAÇÃO DAS DIVERGÊNCIAS
# ============================================================

def session_analysis(sid: int):
    return api.request("GET", f"/sessoes/{sid}/analise")


def count_raw(sid: int, codigo: str, lote: str, qty: float):
    return api.request("POST", "/contagens", {
        "id_sessao": sid,
        "codigo": str(codigo),
        "lote": lote or "",
        "quantidade": qty,
    })


def norm(v):
    return "" if v is None else str(v).strip().upper()


def find_item(items, codigo, lote):
    for it in items:
        if norm(it.get("codigo")) == norm(codigo) and norm(it.get("lote")) == norm(lote):
            return it
    return None


def assert_class(item, status=None, subtype=None):
    assert_true(item is not None, "item esperado não encontrado na análise")
    if status is not None:
        assert_true(
            norm(item.get("status")) == norm(status),
            f"status incorreto. esperado={status}; recebido={item.get('status')}; item={item}"
        )
    if subtype is not None:
        assert_true(
            norm(item.get("subtipo_divergencia")) == norm(subtype),
            f"subtipo incorreto. esperado={subtype}; recebido={item.get('subtipo_divergencia')}; item={item}"
        )


def choose_positive_item(items):
    for it in items:
        if qty_stock(it) > 0:
            return it
    raise AssertionError("Nenhum item com saldo positivo disponível para o teste.")


def choose_code_with_two_lots(items):
    groups = {}
    for it in items:
        if qty_stock(it) <= 0:
            continue
        groups.setdefault(norm(it.get("codigo")), []).append(it)

    for code, group in groups.items():
        lots = {norm(x.get("lote")) for x in group}
        if len(lots) >= 2:
            # Retorna dois lotes distintos.
            first = group[0]
            for second in group[1:]:
                if norm(first.get("lote")) != norm(second.get("lote")):
                    return first, second

    raise AssertionError(
        "O endereço de teste não possui um código com pelo menos dois lotes positivos; "
        "não é possível validar LOTE_INCORRETO de forma determinística."
    )


def count_other_items_correct(sid, items, excluded_keys):
    for it in items:
        key = (norm(it.get("codigo")), norm(it.get("lote")))
        if key in excluded_keys:
            continue
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)


def test_quantidade_sobra():
    iid, r1, items = prepare("QTYPLUS")
    target = choose_positive_item(items)

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)
    a = session_analysis(sid)

    found = find_item(a.get("itens", []), target["codigo"], target.get("lote"))
    assert_class(found, "DIVERGÊNCIA", "QUANTIDADE")
    assert_true(float(found.get("diferenca", 0)) > 0, f"diferença deveria ser positiva: {found}")


def test_quantidade_falta():
    iid, r1, items = prepare("QTYMISS")
    target = choose_positive_item(items)

    s = start(iid, r1)
    sid = s["id_sessao"]

    excluded = {(norm(target.get("codigo")), norm(target.get("lote")))}
    count_other_items_correct(sid, items, excluded)
    close(sid)

    a = session_analysis(sid)
    found = find_item(a.get("itens", []), target["codigo"], target.get("lote"))

    assert_class(found, "FALTA", "QUANTIDADE")
    assert_true(float(found.get("qtd_contada", 0)) == 0, f"falta deveria ter contagem zero: {found}")
    assert_true(float(found.get("diferenca", 0)) < 0, f"diferença deveria ser negativa: {found}")


def test_item_nao_previsto():
    iid, r1, items = prepare("UNEXP")
    fake_code = "E2E999999"
    fake_lot = "LOTE-E2E-NAO-PREVISTO"

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)

    count_raw(sid, fake_code, fake_lot, 1)
    close(sid)

    a = session_analysis(sid)
    found = find_item(a.get("itens", []), fake_code, fake_lot)

    assert_class(found, "SOBRA", "ITEM_NAO_PREVISTO")
    assert_true(float(found.get("qtd_estoque", 0)) == 0, f"item não previsto deveria ter estoque zero: {found}")
    assert_true(float(found.get("qtd_contada", 0)) == 1, f"contagem inesperada: {found}")


def test_lote_incorreto():
    iid, r1, items = prepare("BADLOT")
    lot_missing, lot_over = choose_code_with_two_lots(items)

    qa = qty_stock(lot_missing)
    qb = qty_stock(lot_over)

    s = start(iid, r1)
    sid = s["id_sessao"]

    excluded = {
        (norm(lot_missing.get("codigo")), norm(lot_missing.get("lote"))),
        (norm(lot_over.get("codigo")), norm(lot_over.get("lote"))),
    }
    count_other_items_correct(sid, items, excluded)

    # O saldo total do código continua correto, mas foi informado no lote errado.
    count_raw(
        sid,
        lot_over["codigo"],
        lot_over.get("lote") or "",
        qa + qb
    )
    close(sid)

    a = session_analysis(sid)
    ai = a.get("itens", [])

    missing = find_item(ai, lot_missing["codigo"], lot_missing.get("lote"))
    over = find_item(ai, lot_over["codigo"], lot_over.get("lote"))

    assert_class(missing, None, "LOTE_INCORRETO")
    assert_class(over, None, "LOTE_INCORRETO")
    assert_true(float(missing.get("diferenca", 0)) < 0, f"lote faltante deveria ser negativo: {missing}")
    assert_true(float(over.get("diferenca", 0)) > 0, f"lote excedente deveria ser positivo: {over}")


def test_lote_e_quantidade():
    iid, r1, items = prepare("LOTQTY")
    lot_missing, lot_over = choose_code_with_two_lots(items)

    qa = qty_stock(lot_missing)
    qb = qty_stock(lot_over)

    s = start(iid, r1)
    sid = s["id_sessao"]

    excluded = {
        (norm(lot_missing.get("codigo")), norm(lot_missing.get("lote"))),
        (norm(lot_over.get("codigo")), norm(lot_over.get("lote"))),
    }
    count_other_items_correct(sid, items, excluded)

    # Transfere o saldo para outro lote E adiciona +1, gerando erro de lote + quantidade.
    count_raw(
        sid,
        lot_over["codigo"],
        lot_over.get("lote") or "",
        qa + qb + 1
    )
    close(sid)

    a = session_analysis(sid)
    ai = a.get("itens", [])

    missing = find_item(ai, lot_missing["codigo"], lot_missing.get("lote"))
    over = find_item(ai, lot_over["codigo"], lot_over.get("lote"))

    assert_class(missing, None, "LOTE_E_QUANTIDADE")
    assert_class(over, None, "LOTE_E_QUANTIDADE")


def test_resumo_classificacao_quantidade():
    iid, r1, items = prepare("SUMQTY")
    target = choose_positive_item(items)

    s = start(iid, r1)
    sid = s["id_sessao"]

    for it in items:
        q = qty_stock(it)
        if q <= 0:
            continue
        count(sid, it, q + 1 if it is target else q)

    close(sid)

    a = analysis(iid)
    resumo = a.get("resumo", {})

    assert_true(
        int(resumo.get("divergencias_quantidade", 0)) >= 1,
        f"resumo não contabilizou divergência de quantidade: {resumo}"
    )
    assert_true(
        int(resumo.get("itens_requerem_decisao", 0)) >= 1,
        f"divergência não foi marcada como requerendo decisão: {resumo}"
    )


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 5 | CLASSIFICAÇÃO DAS DIVERGÊNCIAS ROTATIVAS")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("Sobra de quantidade = QUANTIDADE", test_quantidade_sobra)
    run("Falta de item = FALTA / QUANTIDADE", test_quantidade_falta)
    run("Item inexistente no snapshot = ITEM_NAO_PREVISTO", test_item_nao_previsto)
    run("Troca de lote com total correto = LOTE_INCORRETO", test_lote_incorreto)
    run("Troca de lote com total incorreto = LOTE_E_QUANTIDADE", test_lote_e_quantidade)
    run("Resumo contabiliza divergência de quantidade", test_resumo_classificacao_quantidade)

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
