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
# ESTÁGIO 8 - RESULTADO FINAL E CONSISTÊNCIA GERENCIAL
# ============================================================

def norm(v):
    return "" if v is None else str(v).strip().upper()


def choose_positive(items):
    for it in items:
        if qty_stock(it) > 0:
            return it
    raise AssertionError("Nenhum item com saldo positivo disponível.")


def get_final_items(iid: int):
    rf = final_result(iid)
    itens = rf.get("itens", [])
    assert_true(itens, f"resultado final sem itens: {rf}")
    return rf, itens


def find_final_item(items, location, code, lot):
    for it in items:
        if (
            norm(it.get("localizacao")) == norm(location)
            and norm(it.get("codigo")) == norm(code)
            and norm(it.get("lote")) == norm(lot)
        ):
            return it
    return None


def value_float(item: dict, *keys, default=None):
    for k in keys:
        if k in item and item[k] is not None:
            return float(item[k])
    if default is not None:
        return float(default)
    raise AssertionError(f"Nenhum dos campos {keys} encontrado em: {item}")


def value_text(item: dict, *keys, default=""):
    for k in keys:
        if k in item and item[k] is not None:
            return str(item[k])
    return default


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


def test_r1_sem_divergencia_resultado_final_consistente():
    iid, r1, items = prepare("FINR1OK")

    s = start(iid, r1)
    sid = s["id_sessao"]
    positivos = [it for it in items if qty_stock(it) > 0]

    for it in positivos:
        count(sid, it, qty_stock(it))

    close(sid)
    fin = next_round(iid)
    assert_true(fin["proxima_rodada"].get("status_inventario") == "FINALIZADO", f"não finalizou: {fin}")

    rf, finais = get_final_items(iid)

    for it in positivos:
        f = find_final_item(finais, LOCALIZACAO, it["codigo"], it.get("lote") or "")
        assert_true(f is not None, f"item ausente do resultado final: {it}")

        estoque = qty_stock(it)
        qtd_final = value_float(f, "quantidade_final", "qtd_final", "qtd_contada_final")
        diferenca = value_float(f, "diferenca_final", "diferenca", default=qtd_final - estoque)

        assert_true(abs(qtd_final - estoque) < 1e-9, f"quantidade final incorreta: {f}")
        assert_true(abs(diferenca) < 1e-9, f"item correto ficou divergente: {f}")


def test_r2_resolvida_usa_quantidade_da_r2():
    iid, r1, items, target = make_one_divergence("FINR2OK")

    decision(iid, r1, target, "RECONTAR")
    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    count(sid2, target, qty_stock(target))
    close(sid2)

    fin = next_round(iid)
    assert_true(fin["proxima_rodada"].get("status_inventario") == "FINALIZADO", f"não finalizou: {fin}")

    rf, finais = get_final_items(iid)
    f = find_final_item(finais, LOCALIZACAO, target["codigo"], target.get("lote") or "")
    assert_true(f is not None, f"item recontado ausente do resultado final: {rf}")

    estoque = qty_stock(target)
    qtd_final = value_float(f, "quantidade_final", "qtd_final", "qtd_contada_final")
    diferenca = value_float(f, "diferenca_final", "diferenca", default=qtd_final - estoque)

    assert_true(abs(qtd_final - estoque) < 1e-9, f"resultado final não usou R2 correta: {f}")
    assert_true(abs(diferenca) < 1e-9, f"R2 resolvida permaneceu divergente: {f}")

    rodada_final = value_text(f, "rodada_final", "numero_rodada_final", "rodada_origem")
    if rodada_final:
        assert_true("2" in rodada_final, f"origem final não indica R2: {f}")


def test_r2_persistente_preserva_divergencia_final():
    iid, r1, items, target = make_one_divergence("FINR2NOK")

    decision(iid, r1, target, "RECONTAR")
    nr = next_round(iid)
    r2 = nr["proxima_rodada"]["id_rodada"]

    s2 = start(iid, r2)
    sid2 = s2["id_sessao"]
    qtd_r2 = qty_stock(target) + 1
    count(sid2, target, qtd_r2)
    close(sid2)

    fin = next_round(iid)
    assert_true(fin["proxima_rodada"].get("status_inventario") == "FINALIZADO", f"não finalizou: {fin}")

    rf, finais = get_final_items(iid)
    f = find_final_item(finais, LOCALIZACAO, target["codigo"], target.get("lote") or "")
    assert_true(f is not None, f"item divergente ausente do resultado final: {rf}")

    estoque = qty_stock(target)
    qtd_final = value_float(f, "quantidade_final", "qtd_final", "qtd_contada_final")
    diferenca = value_float(f, "diferenca_final", "diferenca", default=qtd_final - estoque)

    assert_true(abs(qtd_final - qtd_r2) < 1e-9, f"resultado final não preservou quantidade da R2: {f}")
    assert_true(abs(diferenca - (qtd_r2 - estoque)) < 1e-9, f"diferença final incorreta: {f}")
    assert_true(abs(diferenca) > 1e-9, f"divergência persistente desapareceu: {f}")


def test_justificada_preserva_quantidade_e_divergencia_r1():
    iid, r1, items, target = make_one_divergence("FINJUST")

    decision(
        iid,
        r1,
        target,
        "JUSTIFICAR_DIVERGENCIA",
        "E2E - divergência confirmada para validar resultado final"
    )

    fin = next_round(iid)
    assert_true(fin["proxima_rodada"].get("status_inventario") == "FINALIZADO", f"não finalizou: {fin}")

    rf, finais = get_final_items(iid)
    f = find_final_item(finais, LOCALIZACAO, target["codigo"], target.get("lote") or "")
    assert_true(f is not None, f"item justificado ausente do resultado final: {rf}")

    estoque = qty_stock(target)
    esperado = estoque + 1
    qtd_final = value_float(f, "quantidade_final", "qtd_final", "qtd_contada_final")
    diferenca = value_float(f, "diferenca_final", "diferenca", default=qtd_final - estoque)

    assert_true(abs(qtd_final - esperado) < 1e-9, f"quantidade justificada não foi preservada: {f}")
    assert_true(abs(diferenca - 1) < 1e-9, f"diferença justificada incorreta: {f}")


def test_resultado_final_sem_duplicidade_logica():
    iid, r1, items = prepare("FINDUP")

    s = start(iid, r1)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid)

    next_round(iid)

    rf, finais = get_final_items(iid)
    chaves = [
        (
            norm(it.get("localizacao")),
            norm(it.get("codigo")),
            norm(it.get("lote")),
        )
        for it in finais
    ]

    assert_true(
        len(chaves) == len(set(chaves)),
        f"resultado final possui duplicidade lógica: total={len(chaves)} únicos={len(set(chaves))}"
    )


def test_resultado_final_idempotente():
    iid, r1, items = prepare("FINIDEMP")

    s = start(iid, r1)
    sid = s["id_sessao"]
    for it in items:
        q = qty_stock(it)
        if q > 0:
            count(sid, it, q)
    close(sid)

    next_round(iid)
    rf1, itens1 = get_final_items(iid)

    # Repetir finalização não pode alterar nem duplicar resultado.
    try:
        next_round(iid)
    except ApiError as e:
        assert_true(e.status in (400, 409, 422), f"status inesperado na repetição: {e}")

    rf2, itens2 = get_final_items(iid)

    ch1 = sorted(
        (
            norm(x.get("localizacao")),
            norm(x.get("codigo")),
            norm(x.get("lote")),
            value_float(x, "quantidade_final", "qtd_final", "qtd_contada_final"),
        )
        for x in itens1
    )
    ch2 = sorted(
        (
            norm(x.get("localizacao")),
            norm(x.get("codigo")),
            norm(x.get("lote")),
            value_float(x, "quantidade_final", "qtd_final", "qtd_contada_final"),
        )
        for x in itens2
    )

    assert_true(ch1 == ch2, "resultado final mudou após tentativa de finalização repetida")


def main():
    print("=" * 72)
    print("SGI - ESTÁGIO 8 | RESULTADO FINAL E CONSISTÊNCIA GERENCIAL")
    print(f"API: {BASE} | Cliente: {CLIENTE_ID} | Armazém: {ARMAZEM} | Local: {LOCALIZACAO}")
    print("=" * 72)

    api.login()
    R.ok("Autenticação")

    run("R1 sem divergência gera resultado final consistente", test_r1_sem_divergencia_resultado_final_consistente)
    run("R2 resolvida usa a quantidade correta da R2", test_r2_resolvida_usa_quantidade_da_r2)
    run("R2 persistente preserva a divergência final", test_r2_persistente_preserva_divergencia_final)
    run("JUSTIFICAR preserva quantidade e divergência da R1", test_justificada_preserva_quantidade_e_divergencia_r1)
    run("Resultado final não possui duplicidade lógica", test_resultado_final_sem_duplicidade_logica)
    run("Resultado final permanece idempotente", test_resultado_final_idempotente)

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
