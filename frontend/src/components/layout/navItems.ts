import {
  Home,
  ClipboardList,
  Boxes,
  Activity,
  BarChart3,
  RefreshCcw,
  PieChart,
  History,
  ShieldCheck,
  Layers,
  Map,
  Settings2,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  nome: string;
  icone: LucideIcon;
  to?: string;
  permissao?: string;
  secao?: "PRINCIPAL" | "ADMINISTRACAO";
}

/**
 * Estrutura completa do menu.
 *
 * Sem permissao:
 * qualquer usuario autenticado.
 *
 * Com permissao:
 * exibido somente quando a permissao estiver presente
 * nas permissoes efetivas do usuario.
 */
export const navItems: NavItem[] = [
  {
    nome: "Tela Inicial",
    icone: Home,
    to: "/",
  },
  {
    nome: "Central de Invent\u00e1rios",
    icone: Boxes,
    to: "/inventarios",
    permissao: "INVENTARIO_CRIAR",
  },
  {
    nome: "Contagem",
    icone: ClipboardList,
    to: "/contagem",
    permissao: "CONTAGEM_EXECUTAR",
  },
  {
    nome: "Acompanhamento da Contagem",
    icone: Activity,
    to: "/acompanhamento-contagem",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Análise de Estoque",
    icone: BarChart3,
    to: "/analise-estoque",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Análise Cíclica",
    icone: Layers,
    to: "/analise-ciclica",
    permissao: "INVENTARIO_ROTATIVO_DECIDIR",
  },
  {
    nome: "Análise Oficial",
    icone: PieChart,
    to: "/analise-oficial",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Recontagem",
    icone: RefreshCcw,
    to: "/recontagem",
    permissao: "RODADA_GERAR",
  },
  {
    nome: "Indicadores",
    icone: BarChart3,
    to: "/indicadores",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Histórico",
    icone: History,
    to: "/historico",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Auditoria",
    icone: ShieldCheck,
    to: "/auditoria",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Mapa de Estoque 3D",
    icone: Map,
    to: "/mapa-estoque-3d",
    permissao: "ANALISE_VISUALIZAR",
  },
  {
    nome: "Usuários",
    icone: Users,
    to: "/usuarios",
    permissao: "USUARIO_GERENCIAR",
    secao: "ADMINISTRACAO",
  },
  {
    nome: "Configurações",
    icone: Settings2,
    to: "/configuracoes-inventario",
    permissao: "CONFIGURACAO_VISUALIZAR",
    secao: "ADMINISTRACAO",
  },
];
