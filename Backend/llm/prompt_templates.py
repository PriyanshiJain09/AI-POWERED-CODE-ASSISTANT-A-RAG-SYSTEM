# llm/prompt_templates.py — All prompts in one place


def qa_prompt(question: str, chunks: list[dict]) -> str:
    context_blocks = []
    for i, c in enumerate(chunks):
        context_blocks.append(
            f"[{i+1}] File: {c['file_path']} | Function: {c['name']} "
            f"(lines {c.get('start_line','?')}–{c.get('end_line','?')})\n"
            f"```{c.get('language','')}\n{c['content']}\n```"
        )
    context = "\n\n".join(context_blocks)

    return f"""You are RepoMind, a helpful code assistant. A developer is asking about a codebase.

Use the code context below to inform your answer. You can also use your general knowledge about the libraries and patterns you recognize in the code. Be conversational, helpful and clear — like a senior engineer explaining to a teammate.

If the context shows relevant code, reference it with [1], [2] etc.
If the context is not enough, still try to give a helpful answer based on what you can see.

Code Context:
{context}

Developer's Question: {question}

Answer:"""


def explain_file_prompt(file_path: str, content: str) -> str:
    """For the /explain-file endpoint."""
    # Truncate very large files
    if len(content) > 6000:
        content = content[:6000] + "\n# ... (file truncated for brevity)"

    return f"""You are a senior software engineer. Explain the following source file clearly for a developer who is new to this codebase.

File: {file_path}

Include:
1. What this file does (1-2 sentences)
2. Key functions/classes and their purpose
3. Important dependencies or patterns used
4. Any notable implementation details

```
{content}
```

Explanation:"""


def explain_pr_prompt(pr_number: int, diff: str) -> str:
    """For the /explain-pr endpoint."""
    if len(diff) > 8000:
        diff = diff[:8000] + "\n# ... (diff truncated)"

    return f"""You are a code reviewer. Summarise this pull request diff for a developer.

PR #{pr_number}

Include:
1. What problem this PR solves (1-2 sentences)
2. Files changed and what changed in each
3. Any potential issues or things reviewers should focus on
4. Overall risk level (low / medium / high)

Diff:
{diff}

Summary:"""


def patch_prompt(repo_full: str, issue_description: str, context_chunks: list[dict]) -> str:
    """For the /generate-patch endpoint."""
    context = "\n\n".join([
        f"File: {c['file_path']}\n```{c.get('language','')}\n{c['content']}\n```"
        for c in context_chunks
    ])

    return f"""You are an expert software engineer working on the repo: {repo_full}

Task: {issue_description}

Relevant code context:
{context}

Generate a minimal, correct code patch to accomplish the task.
Respond ONLY with a unified diff format (like `git diff`), nothing else.
Use this exact format:
--- a/path/to/file
+++ b/path/to/file
@@ -line,count +line,count @@
 context line
-removed line
+added line

Patch:"""
