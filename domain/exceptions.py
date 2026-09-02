"""Exceções independentes da camada HTTP."""


class DomainError(Exception):
    """Base para erros semânticos do domínio/aplicação."""


class BusinessRuleViolation(DomainError):
    """Regra de negócio ou validação semântica não atendida."""


class InvalidStateError(BusinessRuleViolation):
    """Operação incompatível com o estado atual da entidade."""


class NotFoundError(DomainError):
    """Entidade ou recurso de domínio não encontrado."""


class ConflictError(DomainError):
    """Conflito semântico com estado ou recurso já existente."""


class AuthenticationError(DomainError):
    """Falha de autenticacao (credenciais invalidas ou token ausente/expirado) -> HTTP 401."""

    pass


class AuthorizationError(DomainError):
    """Usuario autenticado sem permissao para a acao -> HTTP 403."""

    pass
