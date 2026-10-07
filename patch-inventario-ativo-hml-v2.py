from pathlib import Path
from datetime import datetime
import hashlib
import re
import shutil

ROOT = Path.cwd()

EXPECTED = {
    "frontend/src/services/indicadoresService.ts":
        "490D2A29FE16DF3306B2BCCDDD06D9A24ED75A3595699170ABB04865AE893200",
    "frontend/src/services/rotativoService.ts":
        "D88AA146011A150822406791571C50010445539C478BC8DAF30DDC9C68E4C820",
    "frontend/src/routes/analise-ciclica.tsx":
        "0569579EA186B16EC554661B271FD1D9DCCC17AB4DECE92AC22299EB6B08C61D",
    "frontend/src/routes/recontagem.tsx":
        "E994300DB8E8A18EB1676D21D2BAC7896D7B983F566D92EF8D52FE3A1969E23B",
    "frontend/src/routes/analise-estoque.tsx":
        "E4883BD79B2ECC2ED753CF8687C2D163060C2AC1A1070E9E4C5119F0C8BB3437",
    "frontend/src/routes/acompanhamento-contagem.tsx":
        "74C33A475CDBBBDF9479C1943C5CB1F462D20BCD4370CF71A7E1FA0B8F1F3C9C",
    "frontend/src/routes/indicadores.tsx":
        "D14444841A50C6F148CBD263DCA505F5551363D3D4C6CC18CB1F3DA481B8D1DA",
    "frontend/src/routes/auditoria.tsx":
        "F9FEB0332D06191497B925AB106BDF27479F9E670416701E919DAC3DFBF107A2",
}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def replace_once(text, old, new, nome):
    qtd = text.count(old)

    if qtd != 1:
        raise RuntimeError(
            f"[ERRO] {nome}: esperado 1 bloco, encontrado {qtd}."
        )

    return text.replace(old, new, 1)

def remover_trava_sem_id(text, nome):
    pattern = re.compile(
        r"\n(?P<i>[ \t]+)if \(!idInventario\) \{\n"
        r"(?P=i)  throw new Error\(\n"
        r"(?:[^\n]*\n){1,6}?"
        r"(?P=i)  \);\n"
        r"(?P=i)\}\n"
    )

    encontrados = list(pattern.finditer(text))

    if len(encontrados) != 1:
        raise RuntimeError(
            f"[ERRO] {nome}: bloco !idInventario esperado 1 vez; "
            f"encontrado {len(encontrados)}."
        )

    return pattern.sub("\n", text, count=1)


print("============================================================")
print("PRE-CHECK")
print("============================================================")

originais = {}

for relativo, esperado in EXPECTED.items():
    path = ROOT / relativo

    if not path.exists():
        raise RuntimeError(
            f"[ERRO] Arquivo não encontrado: {relativo}"
        )

    atual = sha256(path)

    if atual != esperado:
        raise RuntimeError(
            f"[ERRO] Hash divergente: {relativo}\n"
            f"Esperado: {esperado}\n"
            f"Atual:    {atual}\n"
            "PATCH NÃO APLICADO."
        )

    originais[relativo] = path.read_text(
        encoding="utf-8"
    )

    print(f"[OK] {relativo}")

novos = dict(originais)


# ============================================================
# 1. SERVIÇO DE INDICADORES
# Mantém a API atual e filtra ABERTO no frontend.
# ============================================================

rel = "frontend/src/services/indicadoresService.ts"

antigo = '''export async function listarInventariosIndicadores() {
  return apiRequest<InventarioIndicadores[]>("/inventarios");
}'''

novo = '''export async function listarInventariosIndicadores() {
  const inventarios =
    await apiRequest<InventarioIndicadores[]>("/inventarios");

  return inventarios.filter(
    (item) => item.status === "ABERTO",
  );
}'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 2. SERVIÇO ROTATIVO
# ============================================================

rel = "frontend/src/services/rotativoService.ts"

antigo = '''export async function listarInventariosRotativos() {
  return apiRequest<InventarioRotativo[]>("/inventarios?tipo=ROTATIVO");
}'''

novo = '''export async function listarInventariosRotativos() {
  const inventarios =
    await apiRequest<InventarioRotativo[]>(
      "/inventarios?tipo=ROTATIVO",
    );

  return inventarios.filter(
    (item) => item.status === "ABERTO",
  );
}'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 3. IMPORT limparInventarioAtual
# ============================================================

import_antigo = '''import {
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";'''

import_novo = '''import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";'''

rotas = [
    "frontend/src/routes/analise-ciclica.tsx",
    "frontend/src/routes/recontagem.tsx",
    "frontend/src/routes/analise-estoque.tsx",
    "frontend/src/routes/acompanhamento-contagem.tsx",
    "frontend/src/routes/indicadores.tsx",
]

for rel in rotas:
    novos[rel] = replace_once(
        novos[rel],
        import_antigo,
        import_novo,
        f"{rel} / import",
    )


# ============================================================
# 4. ANÁLISE CÍCLICA
# ============================================================

rel = "frontend/src/routes/analise-ciclica.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

antigo = '''      const lista =
        await listarInventariosRotativos();

      const inventarioEncontrado =
        lista.find(
          (item) =>
            item.id_inventario ===
            idInventario,
        );'''

novo = '''      const lista =
        await listarInventariosRotativos();

      if (lista.length === 0) {
        limparInventarioAtual();
        setAnalise(null);
        setErro(null);
        return;
      }

      const inventarioEncontrado =
        lista.find(
          (item) =>
            item.id_inventario ===
            idInventario,
        ) ??
        (!idInventarioUrl
          ? lista[0] ?? null
          : null);'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 5. RECONTAGEM
# ============================================================

rel = "frontend/src/routes/recontagem.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

antigo = '''      const inventarios = await listarInventariosIndicadores();
      const encontrado = inventarios.find(
        (item) => item.id_inventario === idInventario,
      );'''

novo = '''      const inventarios = await listarInventariosIndicadores();

      if (inventarios.length === 0) {
        limparInventarioAtual();
        setInventario(null);
        setRodada(null);
        setDados(null);
        setModo("SEM_RECONTAGEM");
        setErro(null);
        return;
      }

      const encontrado =
        inventarios.find(
          (item) =>
            item.id_inventario === idInventario,
        ) ??
        (!idInventarioUrl
          ? inventarios[0] ?? null
          : null);'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 6. ANÁLISE DE ESTOQUE
# ============================================================

rel = "frontend/src/routes/analise-estoque.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

antigo = '''        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );'''

novo = '''        const dados =
          await listarInventariosIndicadores();

        if (dados.length === 0) {
          limparInventarioAtual();
          setInventarioSelecionado(null);
          setAnaliseRotativo(null);
          setAnaliseOficial(null);
          setUltimaAtualizacao(null);
          setErro(null);
          return;
        }

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          ) ??
          (!idInventarioUrl
            ? dados[0] ?? null
            : null);'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 7. INDICADORES
# ============================================================

rel = "frontend/src/routes/indicadores.tsx"

novos[rel] = remover_trava_sem_id(
    novos[rel],
    rel,
)

antigo = '''        const dados =
          await listarInventariosIndicadores();

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          );'''

novo = '''        const dados =
          await listarInventariosIndicadores();

        if (dados.length === 0) {
          limparInventarioAtual();
          setInventarioSelecionado(null);
          setAcompanhamento(null);
          setProdutividade(null);
          setResultadoFinal(null);
          setRisco(null);
          setPainel(null);
          setTendencias(null);
          setErro(null);
          return;
        }

        const inventarioEncontrado =
          dados.find(
            (item) =>
              item.id_inventario ===
              idInventario,
          ) ??
          (!idInventarioUrl
            ? dados[0] ?? null
            : null);'''

novos[rel] = replace_once(
    novos[rel],
    antigo,
    novo,
    rel,
)


# ============================================================
# 8. ACOMPANHAMENTO
#
# Não depende mais do bloco exato entre as linhas 211 e 222.
# ============================================================

rel = "frontend/src/routes/acompanhamento-contagem.tsx"
texto = novos[rel]

ancora_inicio = '''    setInventarios(inventariosOrdenados);
'''
ancora_fim = '''    const idInventarioPreferido ='''

if texto.count(ancora_inicio) != 1:
    raise RuntimeError(
        "[ERRO] Acompanhamento: "
        "setInventarios(inventariosOrdenados) não é único."
    )

if texto.count(ancora_fim) != 1:
    raise RuntimeError(
        "[ERRO] Acompanhamento: "
        "idInventarioPreferido não é único."
    )

pos_inicio = texto.index(ancora_inicio)
pos_fim = texto.index(
    ancora_fim,
    pos_inicio + len(ancora_inicio),
)

segmento = texto[
    pos_inicio + len(ancora_inicio):
    pos_fim
]

padrao_guard = re.compile(
    r'(?P<linha>[ \t]*)if\s*\(\s*'
    r'(?:inventariosOrdenados\.length\s*===\s*0|'
    r'!inventariosOrdenados\.length)'
    r'\s*\)\s*\{\n'
)

match = padrao_guard.search(segmento)

if match:
    if "limparInventarioAtual();" not in segmento:
        insercao = (
            match.group(0)
            + match.group("linha")
            + "  limparInventarioAtual();\n"
        )

        segmento = (
            segmento[:match.start()]
            + insercao
            + segmento[match.end():]
        )

        print(
            "[OK] Acompanhamento: "
            "limpeza adicionada à guarda existente."
        )
else:
    guarda = '''    if (inventariosOrdenados.length === 0) {
      limparInventarioAtual();
      setIdInventarioContexto(null);
      setAcompanhamento(null);
      setProdutividade(null);
      setErro(null);
      return;
    }

'''

    segmento = guarda + segmento

    print(
        "[OK] Acompanhamento: "
        "guarda de lista vazia criada."
    )

texto = (
    texto[:pos_inicio + len(ancora_inicio)]
    + segmento
    + texto[pos_fim:]
)

novos[rel] = texto


# ============================================================
# 9. AUDITORIA
#
# Sem ?inventario:
#   somente inventário operacional ABERTO.
#
# Com ?inventario=1654:
#   histórico continua acessível.
#
# Consulta histórica NÃO altera inventário operacional.
# ============================================================

rel = "frontend/src/routes/auditoria.tsx"

novos[rel] = replace_once(
    novos[rel],
    '''import { obterInventarioAtual, salvarInventarioAtual } from "@/lib/inventarioAtual";''',
    '''import {
  limparInventarioAtual,
  obterInventarioAtual,
  salvarInventarioAtual,
} from "@/lib/inventarioAtual";''',
    f"{rel} / contexto",
)

novos[rel] = replace_once(
    novos[rel],
    '''} from "../services/auditoriaService";''',
    '''} from "../services/auditoriaService";
import { listarInventariosIndicadores } from "@/services/indicadoresService";''',
    f"{rel} / indicadores",
)

novos[rel] = replace_once(
    novos[rel],
    '''  const id = idInventarioUrl ?? obterInventarioAtual();''',
    '''  const [
    idInventarioContexto,
    setIdInventarioContexto,
  ] = useState<number | null>(
    idInventarioUrl ?? null,
  );

  const id =
    idInventarioUrl ??
    idInventarioContexto;''',
    f"{rel} / id",
)

marcador_erro = '''  const [erro, setErro] = useState<string | null>(null);'''

resolver = '''  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (idInventarioUrl) {
      setIdInventarioContexto(
        idInventarioUrl,
      );
      return;
    }

    let ativo = true;

    void listarInventariosIndicadores()
      .then((inventarios) => {
        if (!ativo) return;

        const idPersistido =
          obterInventarioAtual();

        const inventarioAtivo =
          inventarios.find(
            (item) =>
              item.id_inventario ===
              idPersistido,
          ) ??
          inventarios[0] ??
          null;

        if (!inventarioAtivo) {
          limparInventarioAtual();
          setIdInventarioContexto(null);
          setResultado(null);
          setErro(null);
          return;
        }

        salvarInventarioAtual(
          inventarioAtivo.id_inventario,
          inventarioAtivo.tipo,
        );

        setIdInventarioContexto(
          inventarioAtivo.id_inventario,
        );
      })
      .catch((falha: unknown) => {
        if (!ativo) return;

        setIdInventarioContexto(null);
        setResultado(null);

        setErro(
          falha instanceof Error
            ? falha.message
            : "Erro ao localizar o inventário ativo.",
        );
      });

    return () => {
      ativo = false;
    };
  }, [idInventarioUrl]);'''

novos[rel] = replace_once(
    novos[rel],
    marcador_erro,
    resolver,
    f"{rel} / resolver",
)

bloco_historico = '''      if (data.inventario) {
        salvarInventarioAtual(data.inventario.id_inventario, data.inventario.tipo);
      }
'''

novos[rel] = replace_once(
    novos[rel],
    bloco_historico,
    "",
    f"{rel} / historico nao altera contexto",
)


# ============================================================
# 10. VALIDAÇÕES ANTES DE GRAVAR
# ============================================================

print("")
print("============================================================")
print("VALIDACAO EM MEMORIA")
print("============================================================")

for relativo in EXPECTED:
    if novos[relativo] == originais[relativo]:
        raise RuntimeError(
            f"[ERRO] Nenhuma alteração produzida: {relativo}"
        )

if 'item.status === "ABERTO"' not in novos[
    "frontend/src/services/indicadoresService.ts"
]:
    raise RuntimeError(
        "[ERRO] Filtro ABERTO ausente em indicadoresService."
    )

if 'item.status === "ABERTO"' not in novos[
    "frontend/src/services/rotativoService.ts"
]:
    raise RuntimeError(
        "[ERRO] Filtro ABERTO ausente em rotativoService."
    )

if (
    'salvarInventarioAtual(data.inventario.id_inventario'
    in novos["frontend/src/routes/auditoria.tsx"]
):
    raise RuntimeError(
        "[ERRO] Auditoria ainda altera contexto operacional."
    )

for relativo in rotas:
    if "limparInventarioAtual" not in novos[relativo]:
        raise RuntimeError(
            f"[ERRO] limparInventarioAtual ausente: {relativo}"
        )

print("[OK] Todas as validações em memória passaram.")
print("[OK] Nenhum arquivo gravado até este ponto.")


# ============================================================
# 11. BACKUP
# ============================================================

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

backup_root = (
    ROOT
    / "_backup_contexto_inventario"
    / stamp
)

for relativo in EXPECTED:
    origem = ROOT / relativo
    destino = backup_root / relativo

    destino.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        origem,
        destino,
    )

print("")
print(f"[OK] Backup: {backup_root}")


# ============================================================
# 12. GRAVAÇÃO
# ============================================================

for relativo, conteudo in novos.items():
    path = ROOT / relativo

    path.write_text(
        conteudo,
        encoding="utf-8",
        newline="\n",
    )

    print(f"[PATCH] {relativo}")


# ============================================================
# 13. POS-CHECK
# ============================================================

print("")
print("============================================================")
print("POS-CHECK")
print("============================================================")

for relativo in EXPECTED:
    path = ROOT / relativo

    print(
        f"[OK] {relativo}\n"
        f"     SHA256={sha256(path)}"
    )

print("")
print("============================================================")
print("PATCH V2 APLICADO COM SUCESSO")
print("============================================================")
print("Backend: NÃO ALTERADO")
print("Banco:   NÃO ALTERADO")
print("Produção: NÃO ALTERADA")
print(f"Backup: {backup_root}")
