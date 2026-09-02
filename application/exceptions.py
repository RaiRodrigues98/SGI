class ApplicationError(Exception):
    """Base para erros da camada de aplicação."""
    pass


class TechnicalConfigurationError(ApplicationError):
    """Falha técnica/configuração que impede execução segura."""
    pass
