/**
 * Tipos do domínio de inventário (SGI).
 * Mantidos independentes da UI para facilitar a integração com a API.
 */

export type TipoInventario = "ROTATIVO" | "OFICIAL";

export type Rodada = 1 | 2 | 3 | 4 | number;

export interface Localizacao {
  idSessao: number;
  codigo: string;
  iniciadaEm: string;
  tipoInventario?: TipoInventario;
  rodada?: Rodada;
}

export interface NovaContagem {
  idSessao: number;
  localizacao: string;
  codigo: string;
  lote: string;
  quantidade: number;
}

export interface ContagemItem extends NovaContagem {
  id: string;
  descricao?: string;
  registradoEm: string;
}

export interface ResumoContagem {
  itensRegistrados: number;
  quantidadeTotal: number;
}

export type StatusAnalise = "OK" | "DIVERGÊNCIA" | "FALTA" | "SOBRA";

export interface AnaliseItem {
  chave: string;
  localizacao: string;
  codigo: string;
  lote: string;
  descricao: string | null;
  qtd_estoque: number;
  qtd_contada: number;
  diferenca: number;
  status: StatusAnalise;
}

export interface AnaliseSessao {
  id_sessao: number;
  localizacao: string;
  status_sessao: string;
  total_registros: number;
  itens: AnaliseItem[];
}

export interface SessaoContagem {
  id_sessao: number;
  localizacao: string;
  status: "ABERTA" | "ENCERRADA";
  data_hora_inicio: string;
  data_hora_fim: string | null;
  itens_registrados: number;
  quantidade_total: number;
}

export interface InventarioResumo {
  id_inventario: number;
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente: string;
  cliente_id: number;
  descricao: string | null;
  armazem: string;
  rodada_atual: number;
  status: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  criado_por: string | null;
  finalizado_por: string | null;
  total_rodadas: number;

  id_rodada_atual: number | null;
  status_rodada: string | null;

  total_localizacoes: number;
  localizacoes_pendentes: number;
  localizacoes_em_contagem: number;
  localizacoes_concluidas: number;
  percentual_progresso: number;

  fase_operacional: string;
  proxima_acao: string;

  analise_disponivel: boolean;
  total_divergencias: number;
  divergencias_sem_decisao: number;
  recontagens_pendentes: number;
  divergencias_justificadas: number;
  divergencias_resolvidas: number;
  pode_finalizar: boolean;
  pode_gerar_recontagem: boolean;

  em_analise_gestor: boolean;
  data_hora_encaminhamento_gestor: string | null;
  encaminhado_gestor_por: string | null;
}

export interface EscopoLocalizacaoInventario {
  id_escopo_localizacao: number;
  localizacao: string;
  selecionado: boolean;
  motivo_exclusao: string | null;
  data_hora_inclusao: string | null;
  data_hora_alteracao: string | null;
  criado_por: string | null;
  alterado_por: string | null;
}

export interface EscopoInventarioResumo {
  total_localizacoes: number;
  selecionadas: number;
  excluidas: number;
}

export interface EscopoInventario {
  id_inventario: number;
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente: string;
  cliente_id: number;
  c_armazem: string;
  status: string;
  resumo: EscopoInventarioResumo;
  localizacoes: EscopoLocalizacaoInventario[];
}

export interface EscopoLocalizacoesEntrada {
  localizacoes: string[];
  criado_por: string;
}

export interface AtualizacaoEscopoResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  localizacoes_recebidas: number;
  adicionadas: string[];
  reativadas: string[];
  ja_existentes: string[];
  mensagem: string;
}

export interface EstoqueCandidatoItem {
  id_origem: number;
  c_armazem: string;
  localizacao: string;
  codigo: string;
  lote: string | null;
  cliente_id: number;
  descricao: string;
  unidade: string | null;
  categoria: string | null;
  validade: string | null;

  valor_unitario: number | null;
  valor_total: number | null;

  q_armazenado: number;
  q_reservado: number;
  q_separando: number;
  q_bloqueado: number | null;
  q_recebimento: number | null;
  saldo_inventario: number;

  status_estoque: number | null;
  tipo_localizacao: string | null;
}

export interface EstoqueCandidatosInventario {
  id_inventario: number;
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente: string;
  cliente_id: number;
  c_armazem: string;
  total: number;
  itens: EstoqueCandidatoItem[];
}

export interface LocalizacaoCandidataInventario {
  localizacao: string;
  registros: number;
  itens_distintos: number;
  lotes_distintos: number;
  quantidade_total: number;
}

export interface LocalizacoesCandidatasInventario {
  id_inventario: number;
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente: string;
  cliente_id: number;
  c_armazem: string;
  total_localizacoes: number;
  localizacoes: LocalizacaoCandidataInventario[];
}

export interface InventarioDetalhe {
  id_inventario: number;
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente: string;
  cliente_id: number;
  descricao: string | null;
  armazem: string;
  rodada_atual: number;
  status: string;
  data_hora_inicio: string | null;
  data_hora_fim: string | null;
  criado_por: string | null;
  data_hora_criacao: string | null;
  finalizado_por: string | null;
  em_analise_gestor: boolean;
  data_hora_encaminhamento_gestor: string | null;
  encaminhado_gestor_por: string | null;

  fase_operacional: string;
  proxima_acao: string;
  analise_disponivel: boolean;
  pode_finalizar: boolean;
  pode_gerar_recontagem: boolean;

  total_localizacoes: number;
  localizacoes_pendentes: number;
  localizacoes_em_contagem: number;
  total_divergencias: number;
  divergencias_sem_decisao: number;
  recontagens_pendentes: number;
  localizacoes_concluidas: number;
  percentual_progresso: number;
}

export interface InventarioCancelamentoEntrada {
  motivo: string;
}

export interface InventarioCancelamentoResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  status: string;
  cancelado_por: string | null;
  motivo_cancelamento: string | null;
  data_hora_cancelamento: string | null;
  mensagem: string;
}

export interface InventarioCriacaoResposta {
  id_inventario: number;
  codigo_inventario: string;
  status: string;
}

export interface InventarioCriacaoEntrada {
  codigo_inventario: string;
  tipo: TipoInventario;
  cliente_id: number;
  cliente: string;
  descricao: string | null;
  armazem: string;
}

export interface RodadaAtualOperacional {
  id_inventario: number;
  codigo_inventario: string;
  tipo_inventario: TipoInventario;
  rodada_atual: number;
  id_rodada: number;
  numero_rodada: number;
  status: string;
  data_hora_inicio: string | null;
}

export interface ContextoContagem {
  idInventario: number;
  codigoInventario: string;
  idRodada: number;
  numeroRodada: number;
  tipoInventario: TipoInventario;
  statusRodada: string;
}
export type TipoRodadaConfigurada = "COMPLETA" | "DIVERGENCIAS" | "GESTOR";

export interface ConfiguracaoRodada {
  id_configuracao_rodada: number;
  numero_rodada: number;
  tipo_rodada: TipoRodadaConfigurada;
  ativa: boolean;
}

export interface StatusEscopoInventario {
  id_inventario: number;
  snapshot_gerado: boolean;
  registros_snapshot: number;
  permitir_alteracao_apos_snapshot: boolean;
  contagem_iniciada: boolean;
  total_sessoes_contagem: number;
  pode_alterar_escopo: boolean;
  motivo_bloqueio: "CONTAGEM_INICIADA" | "SNAPSHOT_GERADO" | null;
}

export interface ConfiguracaoInventario {
  id_configuracao: number;
  cliente_id: number;
  tipo_inventario: TipoInventario;

  validar_localizacao_escopo: boolean;
  permitir_localizacao_vazia: boolean;
  permitir_reabertura_localizacao: boolean;
  permitir_alteracao_escopo_apos_snapshot: boolean;

  codigo_livre: boolean;
  permitir_codigo_nao_cadastrado: boolean;
  permitir_item_fora_localizacao: boolean;

  lote_obrigatorio_se_existir: boolean;
  validar_lote_codigo: boolean;
  validar_lote_localizacao: boolean;

  quantidade_minima: number;
  quantidade_maxima: number;

  contagem_cega: boolean;
  considera_localizacao_conciliacao: boolean;

  recontagem_por_localizacao: boolean;
  rodadas_iniciais: number;
  max_rodadas: number;

  permitir_gestor_antecipado: boolean;
  limite_itens_gestor_antecipado: number;

  divergencia_bloqueia_finalizacao: boolean;
  ativa: boolean;

  criado_por: string | null;
  data_hora_criacao: string | null;
  alterado_por: string | null;
  data_hora_alteracao: string | null;

  rodadas: ConfiguracaoRodada[];
}

export interface ConfiguracaoInventarioEntrada {
  validar_localizacao_escopo: boolean;
  permitir_localizacao_vazia: boolean;
  permitir_reabertura_localizacao: boolean;
  permitir_alteracao_escopo_apos_snapshot: boolean;

  codigo_livre: boolean;
  permitir_codigo_nao_cadastrado: boolean;
  permitir_item_fora_localizacao: boolean;

  lote_obrigatorio_se_existir: boolean;
  validar_lote_codigo: boolean;
  validar_lote_localizacao: boolean;

  quantidade_minima: number;
  quantidade_maxima: number;

  contagem_cega: boolean;
  considera_localizacao_conciliacao: boolean;

  recontagem_por_localizacao: boolean;
  rodadas_iniciais: number;
  max_rodadas: number;

  permitir_gestor_antecipado: boolean;
  limite_itens_gestor_antecipado: number;

  divergencia_bloqueia_finalizacao: boolean;
  ativa: boolean;
}

export interface ConfiguracaoRodadaEntrada {
  numero_rodada: number;
  tipo_rodada: TipoRodadaConfigurada;
}

export interface ConfiguracoesRodadasEntrada {
  rodadas_iniciais: number;
  max_rodadas: number;
  rodadas: ConfiguracaoRodadaEntrada[];
}

export interface AtualizacaoConfiguracaoResposta {
  sucesso: boolean;
  mensagem: string;
  configuracao: ConfiguracaoInventario;
}

export interface AtualizacaoRodadasResposta {
  sucesso: boolean;
  mensagem?: string;
  configuracao: ConfiguracaoInventario;
}

export interface ClienteDisponivelInventario {
  cliente_id: number;
  cliente: string;
  armazem: string;
}

export interface StatusSnapshotInventario {
  id_inventario: number;
  snapshot_gerado: boolean;
  registros_snapshot: number;
  localizacoes_snapshot: number;
}

export interface GerarSnapshotResposta {
  sucesso: boolean;
  id_inventario: number;
  codigo_inventario: string;
  cliente_id: number;
  armazem: string;
  localizacoes_escopo: number;
  registros_snapshot: number;
  gerado_por: string;
  mensagem: string;
}


export interface ConfiguracaoInventarioAplicada
  extends ConfiguracaoInventario {
  id_configuracao_aplicada: number;
  id_configuracao_origem: number | null;
  id_configuracao_operacional_origem: number | null;
  id_inventario: number;
  origem: "INVENTARIO";
  versao: number;

  localizacao_obrigatoria: boolean;
  localizacao_validar_estoque: boolean;

  codigo_obrigatorio: boolean;
  codigo_validar_estoque: boolean;

  lote_obrigatorio_quando_existir: boolean;
  lote_validar_codigo: boolean;

  quantidade_obrigatoria: boolean;
  quantidade_operacional_minima: number;
  quantidade_operacional_maxima: number;

  motivo_ultima_alteracao: string | null;
}

export interface AtualizarConfiguracaoInventarioAplicadaEntrada
  extends ConfiguracaoInventarioEntrada {
  versao_esperada: number;
  motivo: string;

  localizacao_obrigatoria: boolean;
  localizacao_validar_estoque: boolean;

  codigo_obrigatorio: boolean;
  codigo_validar_estoque: boolean;

  lote_obrigatorio_quando_existir: boolean;
  lote_validar_codigo: boolean;

  quantidade_obrigatoria: boolean;
  quantidade_operacional_minima: number;
  quantidade_operacional_maxima: number;

  rodadas: ConfiguracaoRodadaEntrada[];
}

export interface AtualizacaoConfiguracaoInventarioAplicadaResposta {
  sucesso: boolean;
  mensagem: string;
  configuracao: ConfiguracaoInventarioAplicada;
}

export interface HistoricoConfiguracaoInventarioItem {
  id_historico_configuracao: number;
  id_configuracao_aplicada: number;
  id_inventario: number;
  versao_anterior: number | null;
  versao_nova: number;
  tipo_alteracao: string;
  motivo: string;
  alterado_por: string;
  data_hora_alteracao: string;
}

export interface HistoricoConfiguracaoInventarioResposta {
  id_inventario: number;
  total: number;
  historico: HistoricoConfiguracaoInventarioItem[];
}
