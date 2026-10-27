"""MCP-сервер diff-guard. Запуск из корня практики: .venv/bin/python -m mcp_server.diff_guard"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from mcp_server.diffscan import DiffError, inspect

server = MCPServer(
    "diff-guard",
    instructions="Проверяет unified diff до передачи в модель или отчёт: лимит 20 000 "
                 "символов и секреты. Значения секретов никогда не возвращаются.",
)


@server.tool()
def inspect_diff(diff: str) -> dict:
    """Проверить unified diff по правилам API-1 и SEC-1.

    Возвращает число символов, файлы с количеством добавленных/удалённых строк,
    найденные секреты (вид, файл, строка, сторона diff — без значения) и redacted_diff,
    где секреты заменены на [REDACTED] с сохранением строк.
    Ошибки: invalid_request (пусто), diff_too_large (> 20 000), not_a_diff.
    """
    try:
        return inspect(diff)
    except DiffError as e:
        raise ToolError(f"{e.code}: {e}") from None


if __name__ == "__main__":
    server.run()
