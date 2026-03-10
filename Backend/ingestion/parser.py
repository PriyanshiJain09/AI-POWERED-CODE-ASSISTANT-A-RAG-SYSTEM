# ingestion/parser.py — Parse source files into function-level chunks

import re
from dataclasses import dataclass

@dataclass
class CodeChunk:
    content: str          # raw source of the function/class
    file_path: str
    name: str             # function or class name
    start_line: int
    end_line: int
    chunk_type: str       # "function" | "class" | "file"
    language: str


# File extensions we support
SUPPORTED_EXTENSIONS = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".jsx":  "javascript",
    ".go":   "go",
    ".java": "java",
    ".rb":   "ruby",
    ".rs":   "rust",
}

# Max chars per chunk to avoid overflowing LLM context
MAX_CHUNK_CHARS = 3000


def get_language(file_path: str) -> str | None:
    for ext, lang in SUPPORTED_EXTENSIONS.items():
        if file_path.endswith(ext):
            return lang
    return None


def parse_file(file_path: str, source: str) -> list[CodeChunk]:
    """
    Parse a source file into function/class level chunks.
    Falls back to regex-based parsing if tree-sitter is unavailable.
    """
    language = get_language(file_path)
    if not language:
        return []

    try:
        return _parse_with_treesitter(file_path, source, language)
    except Exception:
        # Graceful fallback to regex-based splitting
        return _parse_with_regex(file_path, source, language)


def _parse_with_treesitter(file_path: str, source: str, language: str) -> list[CodeChunk]:
    """Use tree-sitter for accurate AST-based parsing."""
    chunks = []

    if language == "python":
        import tree_sitter_python as ts_lang
        from tree_sitter import Language, Parser
        LANG = Language(ts_lang.language())
        node_types = ("function_definition", "async_function_definition", "class_definition")

    elif language in ("javascript", "typescript"):
        try:
            import tree_sitter_javascript as ts_lang
        except ImportError:
            raise
        from tree_sitter import Language, Parser
        LANG = Language(ts_lang.language())
        node_types = (
            "function_declaration", "function_expression",
            "arrow_function", "method_definition", "class_declaration",
        )
    else:
        raise ImportError(f"No tree-sitter grammar for {language}")

    from tree_sitter import Parser
    parser = Parser(LANG)
    tree = parser.parse(bytes(source, "utf-8"))
    lines = source.splitlines()

    def walk(node, depth=0):
        if node.type in node_types:
            start = node.start_point[0]
            end   = node.end_point[0]
            content = source[node.start_byte:node.end_byte]

            # Get name
            name = "anonymous"
            for child in node.children:
                if child.type in ("identifier", "property_identifier"):
                    name = child.text.decode()
                    break

            # Trim oversized chunks
            if len(content) > MAX_CHUNK_CHARS:
                content = content[:MAX_CHUNK_CHARS] + "\n# ... (truncated)"

            chunks.append(CodeChunk(
                content=content,
                file_path=file_path,
                name=name,
                start_line=start + 1,
                end_line=end + 1,
                chunk_type="class" if "class" in node.type else "function",
                language=language,
            ))

        for child in node.children:
            walk(child, depth + 1)

    walk(tree.root_node)

    # If no functions found, treat entire file as one chunk
    if not chunks:
        chunks.append(_whole_file_chunk(file_path, source, language))

    return chunks


def _parse_with_regex(file_path: str, source: str, language: str) -> list[CodeChunk]:
    """Regex fallback — handles Python and JS/TS reasonably well."""
    chunks = []
    lines = source.splitlines()

    if language == "python":
        pattern = re.compile(r"^(async\s+)?def\s+(\w+)|^class\s+(\w+)", re.MULTILINE)
    elif language in ("javascript", "typescript"):
        pattern = re.compile(
            r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)|"
            r"^(?:export\s+)?class\s+(\w+)|"
            r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(",
            re.MULTILINE,
        )
    else:
        # For unsupported languages just chunk by ~50 lines
        return _chunk_by_lines(file_path, source, language)

    matches = list(pattern.finditer(source))
    for i, match in enumerate(matches):
        start_char = match.start()
        end_char   = matches[i + 1].start() if i + 1 < len(matches) else len(source)
        content    = source[start_char:end_char].strip()

        name = next((g for g in match.groups() if g), "unknown")
        start_line = source[:start_char].count("\n") + 1
        end_line   = source[:end_char].count("\n") + 1

        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS] + "\n# ... (truncated)"

        chunks.append(CodeChunk(
            content=content,
            file_path=file_path,
            name=name,
            start_line=start_line,
            end_line=end_line,
            chunk_type="function",
            language=language,
        ))

    if not chunks:
        chunks.append(_whole_file_chunk(file_path, source, language))

    return chunks


def _chunk_by_lines(file_path: str, source: str, language: str, chunk_size=60) -> list[CodeChunk]:
    """Last-resort chunker: split file into N-line windows."""
    lines = source.splitlines()
    chunks = []
    for i in range(0, len(lines), chunk_size):
        block = "\n".join(lines[i:i + chunk_size])
        chunks.append(CodeChunk(
            content=block,
            file_path=file_path,
            name=f"lines_{i+1}_{i+chunk_size}",
            start_line=i + 1,
            end_line=min(i + chunk_size, len(lines)),
            chunk_type="file",
            language=language,
        ))
    return chunks


def _whole_file_chunk(file_path: str, source: str, language: str) -> CodeChunk:
    content = source[:MAX_CHUNK_CHARS] + ("\n# ...(truncated)" if len(source) > MAX_CHUNK_CHARS else "")
    return CodeChunk(
        content=content,
        file_path=file_path,
        name=file_path.split("/")[-1],
        start_line=1,
        end_line=source.count("\n") + 1,
        chunk_type="file",
        language=language,
    )
