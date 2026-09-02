"""
Unit of Work SQL Server.

Fase 9A da refatoração do SGI.

Responsabilidade:
- abrir conexão e cursor;
- expor commit/rollback explícitos;
- fechar cursor e conexão.

Decisão arquitetural importante:
- o Unit of Work NÃO decide quando fazer commit ou rollback;
- essa decisão continua no router nesta fase;
- não existe auto-commit;
- não existe auto-rollback em __exit__.

Isso preserva exatamente a fronteira transacional validada e mantém
locks com LockOwner='Transaction' ativos até o commit/rollback do router.
"""

from database import get_connection


class SqlServerUnitOfWork:

    def __init__(
        self,
        connection_factory=get_connection
    ):

        self._connection_factory = (
            connection_factory
        )

        self.connection = None
        self.cursor = None

    @property
    def aberto(self) -> bool:

        return (
            self.connection is not None
            and
            self.cursor is not None
        )

    def open(self):

        if self.aberto:

            raise RuntimeError(
                "Unit of Work já está aberto."
            )

        self.connection = (
            self._connection_factory()
        )

        try:

            self.cursor = (
                self.connection.cursor()
            )

        except Exception:

            self.connection.close()
            self.connection = None

            raise

        return self

    def commit(self):

        if self.connection is None:

            raise RuntimeError(
                "Unit of Work não está aberto."
            )

        self.connection.commit()

    def rollback(self):

        if self.connection is None:
            return

        self.connection.rollback()

    def close(self):

        if self.cursor is not None:

            self.cursor.close()
            self.cursor = None

        if self.connection is not None:

            self.connection.close()
            self.connection = None

    def __enter__(self):

        return self.open()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        # A decisão transacional permanece explícita
        # no chamador nesta fase.
        self.close()

        return False
