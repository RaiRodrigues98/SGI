import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Save, Settings2, Trash2 } from "lucide-react";

import { ApiError } from "@/services/apiClient";

import {
  atualizarConfiguracaoInventario,
  atualizarRodadasConfiguracaoInventario,
  consultarConfiguracaoInventario,
  criarConfiguracaoInventario,
  listarClientesDisponiveis,
} from "@/services/inventarioService";

import type {
  ClienteDisponivelInventario,
  ConfiguracaoInventario,
  ConfiguracaoInventarioEntrada,
  ConfiguracaoRodadaEntrada,
  TipoInventario,
  TipoRodadaConfigurada,
} from "@/types/inventory";

export const Route = createFileRoute("/configuracoes-inventario")({
  head: () => ({
    meta: [
      {
        title: "Configura\u00e7\u00f5es Padr\u00e3o de Invent\u00e1rio \u2014 SGI",
      },
    ],
  }),
  component: ConfiguracoesInventarioPage,
});

const inputClass =
  "h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-60";

const buttonClass =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md border px-4 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

const primaryButtonClass =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50";

function criarModeloConfiguracao(tipo: TipoInventario): {
  form: ConfiguracaoInventarioEntrada;
  rodadas: ConfiguracaoRodadaEntrada[];
} {
  const oficial = tipo === "OFICIAL";

  const rodadas: ConfiguracaoRodadaEntrada[] = oficial
    ? [
        { numero_rodada: 1, tipo_rodada: "COMPLETA" },
        { numero_rodada: 2, tipo_rodada: "COMPLETA" },
        { numero_rodada: 3, tipo_rodada: "DIVERGENCIAS" },
        { numero_rodada: 4, tipo_rodada: "DIVERGENCIAS" },
        { numero_rodada: 5, tipo_rodada: "DIVERGENCIAS" },
        { numero_rodada: 6, tipo_rodada: "GESTOR" },
      ]
    : [
        { numero_rodada: 1, tipo_rodada: "COMPLETA" },
        { numero_rodada: 2, tipo_rodada: "DIVERGENCIAS" },
      ];

  return {
    form: {
      validar_localizacao_escopo: true,
      permitir_localizacao_vazia: true,
      permitir_reabertura_localizacao: false,
      permitir_alteracao_escopo_apos_snapshot: false,

      codigo_livre: false,
      permitir_codigo_nao_cadastrado: false,
      permitir_item_fora_localizacao: false,

      lote_obrigatorio_se_existir: true,
      validar_lote_codigo: true,
      validar_lote_localizacao: true,

      quantidade_minima: 1,
      quantidade_maxima: 999,

      contagem_cega: true,
      considera_localizacao_conciliacao: !oficial,

      recontagem_por_localizacao: true,
      rodadas_iniciais: oficial ? 2 : 1,
      max_rodadas: oficial ? 6 : 2,

      permitir_gestor_antecipado: false,
      limite_itens_gestor_antecipado: oficial ? 5 : 0,

      divergencia_bloqueia_finalizacao: true,
      ativa: true,
    },
    rodadas,
  };
}

function ConfiguracoesInventarioPage() {
  const [clientes, setClientes] = useState<ClienteDisponivelInventario[]>([]);

  const [clienteId, setClienteId] = useState("");
  const [tipo, setTipo] = useState<TipoInventario>("ROTATIVO");

  const [configuracao, setConfiguracao] = useState<ConfiguracaoInventario | null>(null);

  const [form, setForm] = useState<ConfiguracaoInventarioEntrada | null>(null);

  const [rodadas, setRodadas] = useState<ConfiguracaoRodadaEntrada[]>([]);

  const [carregandoClientes, setCarregandoClientes] = useState(true);

  const [consultando, setConsultando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [salvandoRodadas, setSalvandoRodadas] = useState(false);

  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    void carregarClientes();
  }, []);

  const clienteSelecionado = useMemo(
    () => clientes.find((item) => item.cliente_id === Number(clienteId)) ?? null,
    [clientes, clienteId],
  );

  async function carregarClientes() {
    setCarregandoClientes(true);
    setErro(null);

    try {
      const dados = await listarClientesDisponiveis();
      setClientes(dados);
    } catch (e) {
      const mensagem = mensagemErro(e);
      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setCarregandoClientes(false);
    }
  }

  async function consultar() {
    const id = Number(clienteId);

    if (!Number.isInteger(id) || id <= 0) {
      setErro("Selecione um cliente.");
      return;
    }

    setConsultando(true);
    setErro(null);

    try {
      const dados = await consultarConfiguracaoInventario(id, tipo);

      aplicarConfiguracao(dados);
    } catch (e) {
      const mensagem = mensagemErro(e);

      const configuracaoInexistente =
        (e instanceof ApiError && e.status === 404) ||
        mensagem.includes("Não existe configuração ativa") ||
        mensagem.includes("Nao existe configuracao ativa");

      if (configuracaoInexistente) {
        const modeloNovo = criarModeloConfiguracao(tipo);

        setConfiguracao(null);
        setForm(modeloNovo.form);
        setRodadas(modeloNovo.rodadas);
        setErro(null);

        toast.info("Nenhuma configuração encontrada. Ajuste as regras e crie a configuração.");
      } else {
        setConfiguracao(null);
        setForm(null);
        setRodadas([]);
        setErro(mensagem);
      }
    } finally {
      setConsultando(false);
    }
  }

  function aplicarConfiguracao(dados: ConfiguracaoInventario) {
    setConfiguracao(dados);

    setForm({
      validar_localizacao_escopo: dados.validar_localizacao_escopo,
      permitir_localizacao_vazia: dados.permitir_localizacao_vazia,
      permitir_reabertura_localizacao: dados.permitir_reabertura_localizacao,
      permitir_alteracao_escopo_apos_snapshot: dados.permitir_alteracao_escopo_apos_snapshot,

      codigo_livre: dados.codigo_livre,
      permitir_codigo_nao_cadastrado: dados.permitir_codigo_nao_cadastrado,
      permitir_item_fora_localizacao: dados.permitir_item_fora_localizacao,

      lote_obrigatorio_se_existir: dados.lote_obrigatorio_se_existir,
      validar_lote_codigo: dados.validar_lote_codigo,
      validar_lote_localizacao: dados.validar_lote_localizacao,

      quantidade_minima: dados.quantidade_minima,
      quantidade_maxima: dados.quantidade_maxima,

      contagem_cega: dados.contagem_cega,
      considera_localizacao_conciliacao: dados.considera_localizacao_conciliacao,

      recontagem_por_localizacao: dados.recontagem_por_localizacao,
      rodadas_iniciais: dados.rodadas_iniciais,
      max_rodadas: dados.max_rodadas,

      permitir_gestor_antecipado: dados.permitir_gestor_antecipado,
      limite_itens_gestor_antecipado: dados.limite_itens_gestor_antecipado,

      divergencia_bloqueia_finalizacao: dados.divergencia_bloqueia_finalizacao,
      ativa: dados.ativa,
    });

    setRodadas(
      dados.rodadas.map((rodada) => ({
        numero_rodada: rodada.numero_rodada,
        tipo_rodada: rodada.tipo_rodada,
      })),
    );
  }

  function alterarBooleano(campo: keyof ConfiguracaoInventarioEntrada, valor: boolean) {
    setForm((atual) =>
      atual
        ? {
            ...atual,
            [campo]: valor,
          }
        : atual,
    );
  }

  function alterarNumero(
    campo:
      | "quantidade_minima"
      | "quantidade_maxima"
      | "rodadas_iniciais"
      | "max_rodadas"
      | "limite_itens_gestor_antecipado",
    valor: string,
  ) {
    const numero = Number(valor);

    setForm((atual) =>
      atual
        ? {
            ...atual,
            [campo]: Number.isFinite(numero) ? numero : 0,
          }
        : atual,
    );
  }

  async function salvarConfiguracao() {
    if (!form || !clienteId) {
      return;
    }

    if (form.quantidade_minima > form.quantidade_maxima) {
      setErro("A quantidade mínima não pode ser maior que a quantidade máxima.");
      return;
    }

    if (form.rodadas_iniciais > form.max_rodadas) {
      setErro("Rodadas iniciais não pode ser maior que o máximo de rodadas.");
      return;
    }

    setSalvando(true);
    setErro(null);

    try {
      const criando = configuracao === null;

      if (criando && rodadas.length !== form.max_rodadas) {
        throw new Error("A quantidade de rodadas deve ser igual ao máximo de rodadas.");
      }

      const resposta = criando
        ? await criarConfiguracaoInventario(Number(clienteId), tipo, {
            ...form,
            rodadas,
          })
        : await atualizarConfiguracaoInventario(Number(clienteId), tipo, form);

      aplicarConfiguracao(resposta.configuracao);

      toast.success(
        resposta.mensagem ||
          (configuracao
            ? "Configuração atualizada com sucesso."
            : "Configuração criada com sucesso."),
      );
    } catch (e) {
      const mensagem = mensagemErro(e);
      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setSalvando(false);
    }
  }

  function adicionarRodada() {
    const maiorNumero = rodadas.reduce((maior, item) => Math.max(maior, item.numero_rodada), 0);

    setRodadas((atual) => [
      ...atual,
      {
        numero_rodada: maiorNumero + 1,
        tipo_rodada: "DIVERGENCIAS",
      },
    ]);
  }

  function removerRodada(indice: number) {
    setRodadas((atual) => atual.filter((_, i) => i !== indice));
  }

  function alterarTipoRodada(indice: number, valor: TipoRodadaConfigurada) {
    setRodadas((atual) =>
      atual.map((item, i) =>
        i === indice
          ? {
              ...item,
              tipo_rodada: valor,
            }
          : item,
      ),
    );
  }

  async function salvarRodadas() {
    if (!form || !clienteId) {
      return;
    }

    if (rodadas.length === 0) {
      setErro("Informe ao menos uma rodada.");
      return;
    }

    setSalvandoRodadas(true);
    setErro(null);

    try {
      const resposta = await atualizarRodadasConfiguracaoInventario(Number(clienteId), tipo, {
        rodadas_iniciais: form.rodadas_iniciais,
        max_rodadas: form.max_rodadas,
        rodadas,
      });

      aplicarConfiguracao(resposta.configuracao);

      toast.success(resposta.mensagem || "Configuração de rodadas atualizada com sucesso.");
    } catch (e) {
      const mensagem = mensagemErro(e);
      setErro(mensagem);
      toast.error(mensagem);
    } finally {
      setSalvandoRodadas(false);
    }
  }

  return (
    <main className="space-y-6 p-4 sm:p-6">
      <header className="flex items-start gap-3">
        <Settings2 className="mt-0.5 size-7 shrink-0 text-primary" aria-hidden="true" />

        <div>
          <h1 className="text-xl font-bold tracking-tight text-primary">
            Configurações padrão de inventário
          </h1>

          <p className="mt-1 text-sm text-muted-foreground">
            Defina as regras que serão copiadas para novos inventários de cada cliente e tipo.
          </p>
        </div>
      </header>

      {erro && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {erro}
        </div>
      )}

      <section className="rounded-lg border bg-card p-5 shadow-xs">
        <h2 className="font-semibold">Consultar configuração padrão</h2>

        <p className="mt-1 text-sm text-muted-foreground">
          Selecione o cliente e o tipo de inventário. O armazém abaixo é apenas uma referência do cadastro do cliente e não faz parte da chave desta configuração.
        </p>

        <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr_auto]">
          <Campo titulo="Cliente">
            <select
              className={inputClass}
              value={clienteId}
              disabled={carregandoClientes}
              onChange={(e) => {
                setClienteId(e.target.value);
                setConfiguracao(null);
                setForm(null);
                setRodadas([]);
                setErro(null);
              }}
            >
              <option value="">
                {carregandoClientes ? "Carregando clientes..." : "Selecione um cliente"}
              </option>

              {clientes.map((cliente) => (
                <option key={cliente.cliente_id} value={cliente.cliente_id}>
                  {cliente.cliente} · {cliente.armazem}
                </option>
              ))}
            </select>
          </Campo>

          <Campo titulo="Tipo de inventário">
            <select
              className={inputClass}
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value as TipoInventario);
                setConfiguracao(null);
                setForm(null);
                setRodadas([]);
                setErro(null);
              }}
            >
              <option value="ROTATIVO">Rotativo</option>
              <option value="OFICIAL">Oficial</option>
            </select>
          </Campo>

          <div className="flex items-end">
            <button
              type="button"
              className={primaryButtonClass}
              disabled={consultando || !clienteId}
              onClick={() => void consultar()}
            >
              {consultando ? <Loader2 className="size-4 animate-spin" /> : null}
              Consultar
            </button>
          </div>
        </div>

        {clienteSelecionado && (
          <div className="mt-4 rounded-md bg-muted/50 p-3 text-sm">
            <strong>Escopo do padrão:</strong> {clienteSelecionado.cliente}
            {" · "}
            <strong>Tipo:</strong> {tipo === "OFICIAL" ? "Oficial" : "Rotativo"}
            {" · "}
            <strong>Armazém de referência:</strong> {clienteSelecionado.armazem}
          </div>
        )}
      </section>

      {form && !configuracao ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
          Nenhuma configuração padrão está cadastrada para este cliente e tipo. Ajuste as regras
          abaixo e clique em Criar configuração. O padrão será utilizado na criação de novos
          inventários.
        </div>
      ) : null}

      {form && (
        <>
          <section className="space-y-5 rounded-lg border bg-card p-5 shadow-xs">
            <div>
              <h2 className="font-semibold">Regras operacionais padrão</h2>

              <p className="mt-1 text-sm text-muted-foreground">
                Estas regras serão copiadas para cada novo inventário. Inventários existentes mantêm
                sua própria configuração aplicada.
              </p>
            </div>

            <Grupo titulo="Localização">
              <Opcao
                titulo="Validar localização no escopo"
                descricao="Impede contagem de localização que não pertence ao escopo do inventário."
                marcado={form.validar_localizacao_escopo}
                onChange={(valor) => alterarBooleano("validar_localizacao_escopo", valor)}
              />

              <Opcao
                titulo="Permitir localização vazia"
                descricao="Permite registrar contagem mesmo quando não houver itens previstos na localização."
                marcado={form.permitir_localizacao_vazia}
                onChange={(valor) => alterarBooleano("permitir_localizacao_vazia", valor)}
              />

              <Opcao
                titulo="Permitir reabertura de localização"
                descricao="Permite voltar a contar uma localização já encerrada."
                marcado={form.permitir_reabertura_localizacao}
                onChange={(valor) => alterarBooleano("permitir_reabertura_localizacao", valor)}
              />
              <Opcao
                titulo="Permitir alteração do escopo após snapshot"
                descricao="Permite incluir novas localizações no escopo após gerar o snapshot, desde que a contagem ainda não tenha sido iniciada. Ao alterar o escopo, o snapshot anterior será invalidado e deverá ser gerado novamente."
                marcado={form.permitir_alteracao_escopo_apos_snapshot}
                onChange={(valor) =>
                  alterarBooleano("permitir_alteracao_escopo_apos_snapshot", valor)
                }
              />
            </Grupo>

            <Grupo titulo="Código do item">
              <Opcao
                titulo="Código livre"
                descricao="Permite informar o código manualmente."
                marcado={form.codigo_livre}
                onChange={(valor) => alterarBooleano("codigo_livre", valor)}
              />

              <Opcao
                titulo="Permitir código não cadastrado"
                descricao="Aceita código que não esteja presente na base de estoque."
                marcado={form.permitir_codigo_nao_cadastrado}
                onChange={(valor) => alterarBooleano("permitir_codigo_nao_cadastrado", valor)}
              />

              <Opcao
                titulo="Permitir item fora da localização"
                descricao="Permite contar um item em localização diferente da prevista."
                marcado={form.permitir_item_fora_localizacao}
                onChange={(valor) => alterarBooleano("permitir_item_fora_localizacao", valor)}
              />
            </Grupo>

            <Grupo titulo="Lote">
              <Opcao
                titulo="Lote obrigatório quando existir"
                descricao="Exige lote para itens controlados por lote."
                marcado={form.lote_obrigatorio_se_existir}
                onChange={(valor) => alterarBooleano("lote_obrigatorio_se_existir", valor)}
              />

              <Opcao
                titulo="Validar lote x código"
                descricao="Confere se o lote informado pertence ao item contado."
                marcado={form.validar_lote_codigo}
                onChange={(valor) => alterarBooleano("validar_lote_codigo", valor)}
              />

              <Opcao
                titulo="Validar lote x localização"
                descricao="Confere se o lote está previsto para a localização."
                marcado={form.validar_lote_localizacao}
                onChange={(valor) => alterarBooleano("validar_lote_localizacao", valor)}
              />
            </Grupo>

            <Grupo titulo="Contagem e conciliação">
              <Opcao
                titulo="Contagem cega"
                descricao="O operador não visualiza a quantidade esperada no estoque."
                marcado={form.contagem_cega}
                onChange={(valor) => alterarBooleano("contagem_cega", valor)}
              />

              <Opcao
                titulo="Considerar localização na conciliação"
                descricao="A conciliação considera também a localização do item."
                marcado={form.considera_localizacao_conciliacao}
                onChange={(valor) => alterarBooleano("considera_localizacao_conciliacao", valor)}
              />

              <div className="grid gap-4 md:grid-cols-2">
                <Campo titulo="Quantidade mínima">
                  <input
                    type="number"
                    className={inputClass}
                    value={form.quantidade_minima}
                    onChange={(e) => alterarNumero("quantidade_minima", e.target.value)}
                  />
                </Campo>

                <Campo titulo="Quantidade máxima">
                  <input
                    type="number"
                    className={inputClass}
                    value={form.quantidade_maxima}
                    onChange={(e) => alterarNumero("quantidade_maxima", e.target.value)}
                  />
                </Campo>
              </div>
            </Grupo>

            <Grupo titulo="Recontagem e gestor">
              <Opcao
                titulo="Recontagem por localização"
                descricao="A recontagem é tratada por localização divergente."
                marcado={form.recontagem_por_localizacao}
                onChange={(valor) => alterarBooleano("recontagem_por_localizacao", valor)}
              />

              <Opcao
                titulo="Permitir gestor antecipado"
                descricao="Permite encaminhar divergências ao gestor antes de atingir o máximo de rodadas."
                marcado={form.permitir_gestor_antecipado}
                onChange={(valor) => alterarBooleano("permitir_gestor_antecipado", valor)}
              />

              <Opcao
                titulo="Divergência bloqueia finalização"
                descricao="Impede finalizar o inventário enquanto existirem divergências pendentes."
                marcado={form.divergencia_bloqueia_finalizacao}
                onChange={(valor) => alterarBooleano("divergencia_bloqueia_finalizacao", valor)}
              />

              <div className="grid gap-4 md:grid-cols-3">
                <Campo titulo="Rodadas iniciais">
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    value={form.rodadas_iniciais}
                    onChange={(e) => alterarNumero("rodadas_iniciais", e.target.value)}
                  />
                </Campo>

                <Campo titulo="Máximo de rodadas">
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    value={form.max_rodadas}
                    onChange={(e) => alterarNumero("max_rodadas", e.target.value)}
                  />
                </Campo>

                <Campo titulo="Limite de itens para gestor antecipado">
                  <input
                    type="number"
                    min={0}
                    className={inputClass}
                    value={form.limite_itens_gestor_antecipado}
                    disabled={!form.permitir_gestor_antecipado}
                    onChange={(e) =>
                      alterarNumero("limite_itens_gestor_antecipado", e.target.value)
                    }
                  />
                </Campo>
              </div>
            </Grupo>

            <Grupo titulo="Status">
              <Opcao
                titulo="Configuração ativa"
                descricao="Define se esta configuração está disponível para utilização."
                marcado={form.ativa}
                onChange={(valor) => alterarBooleano("ativa", valor)}
              />
            </Grupo>

            <div className="flex justify-end border-t pt-5">
              <button
                type="button"
                className={primaryButtonClass}
                disabled={salvando}
                onClick={() => void salvarConfiguracao()}
              >
                {salvando ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Save className="size-4" />
                )}
                {configuracao ? "Salvar configuração" : "Criar configuração"}
              </button>
            </div>
          </section>

          <section className="space-y-5 rounded-lg border bg-card p-5 shadow-xs">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="font-semibold">Rodadas padrão</h2>

                <p className="mt-1 text-sm text-muted-foreground">
                  Defina a sequência inicial que será copiada para novos inventários.
                </p>
              </div>

              <button type="button" className={buttonClass} onClick={adicionarRodada}>
                <Plus className="size-4" />
                Adicionar rodada
              </button>
            </div>

            <div className="space-y-3">
              {rodadas.length === 0 && (
                <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                  Nenhuma rodada configurada.
                </div>
              )}

              {rodadas.map((rodada, indice) => (
                <div
                  key={`${rodada.numero_rodada}-${indice}`}
                  className="grid gap-3 rounded-md border p-4 md:grid-cols-[140px_1fr_auto]"
                >
                  <Campo titulo="Rodada">
                    <input className={inputClass} value={rodada.numero_rodada} disabled />
                  </Campo>

                  <Campo titulo="Tipo">
                    <select
                      className={inputClass}
                      value={rodada.tipo_rodada}
                      onChange={(e) =>
                        alterarTipoRodada(indice, e.target.value as TipoRodadaConfigurada)
                      }
                    >
                      <option value="COMPLETA">Completa</option>
                      <option value="DIVERGENCIAS">Divergências</option>
                      <option value="GESTOR">Gestor</option>
                    </select>
                  </Campo>

                  <div className="flex items-end">
                    <button
                      type="button"
                      className={buttonClass}
                      onClick={() => removerRodada(indice)}
                    >
                      <Trash2 className="size-4" />
                      Remover
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end border-t pt-5">
              <button
                type="button"
                className={primaryButtonClass}
                disabled={salvandoRodadas}
                onClick={() => void salvarRodadas()}
              >
                {salvandoRodadas ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Save className="size-4" />
                )}
                Salvar rodadas
              </button>
            </div>
          </section>

          {configuracao ? (
            <section className="rounded-lg border bg-card p-5 text-sm shadow-xs">
              <h2 className="font-semibold">Dados da configuração padrão</h2>

              <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Info titulo="Configuração" valor={`#${configuracao.id_configuracao}`} />

                <Info titulo="Criado por" valor={configuracao.criado_por ?? "-"} />

                <Info titulo="Criado em" valor={formatarData(configuracao.data_hora_criacao)} />

                <Info
                  titulo="Última alteração"
                  valor={formatarData(configuracao.data_hora_alteracao)}
                />
              </div>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4 rounded-lg border p-4">
      <h3 className="font-medium">{titulo}</h3>
      {children}
    </div>
  );
}

function Campo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-muted-foreground">{titulo}</span>

      {children}
    </label>
  );
}

function Opcao({
  titulo,
  descricao,
  marcado,
  onChange,
}: {
  titulo: string;
  descricao: string;
  marcado: boolean;
  onChange: (valor: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md border p-3">
      <input
        type="checkbox"
        className="mt-1 size-4"
        checked={marcado}
        onChange={(e) => onChange(e.target.checked)}
      />

      <span>
        <span className="block text-sm font-medium">{titulo}</span>

        <span className="mt-0.5 block text-xs text-muted-foreground">{descricao}</span>
      </span>
    </label>
  );
}

function Info({ titulo, valor }: { titulo: string; valor: string | number }) {
  return (
    <div>
      <div className="text-xs uppercase text-muted-foreground">{titulo}</div>

      <div className="mt-1 font-medium">{valor}</div>
    </div>
  );
}

function formatarData(valor: string | null | undefined) {
  if (!valor) {
    return "-";
  }

  const data = new Date(valor);

  return Number.isNaN(data.getTime()) ? valor : data.toLocaleString("pt-BR");
}

function mensagemErro(e: unknown) {
  return e instanceof Error ? e.message : "Erro inesperado ao processar a configuração.";
}
