import re
from dataclasses import dataclass
from typing import List


@dataclass
class ValidationIssue:
    """Représente une erreur ou un avertissement détecté par le validateur Lua."""

    severity: str  # "ERROR" | "WARNING"
    line: int
    message: str


class LuaValidator:
    """Validateur statique et syntaxique du code Lua généré ou modifié pour Luanti."""

    BLOCK_OPENERS = re.compile(r"\b(function|if|for|while|repeat)\b")
    BLOCK_CLOSERS = re.compile(r"\b(end|until)\b")
    PRIVATE_KEY_PATTERN = re.compile(r"(api_key|secret_key|private_token|bearer\s+[a-zA-Z0-9_\-\.]{12,})", re.IGNORECASE)

    @classmethod
    def validate_lua_code(cls, lua_source: str) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        lines = lua_source.splitlines()

        open_blocks = 0
        paren_balance = 0
        brace_balance = 0

        for idx, raw_line in enumerate(lines, start=1):
            # Retirer les commentaires de fin de ligne
            code_line = raw_line.split("--", 1)[0]

            # Vérification de sécurité : pas de clés API privées en dur
            if cls.PRIVATE_KEY_PATTERN.search(code_line):
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        line=idx,
                        message="Sécurité : Clé API ou secret détecté en clair dans le script Lua.",
                    )
                )

            # Suppression des chaînes littérales avant comptage des délimiteurs
            stripped_strings = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', code_line)

            paren_balance += stripped_strings.count("(") - stripped_strings.count(")")
            brace_balance += stripped_strings.count("{") - stripped_strings.count("}")

            open_blocks += len(cls.BLOCK_OPENERS.findall(stripped_strings))
            # 'do' autonome (hors 'while ... do' et 'for ... do') ouvre aussi un bloc
            if re.search(r"\bdo\b", stripped_strings) and not re.search(r"\b(while|for)\b", stripped_strings):
                open_blocks += 1

            open_blocks -= len(cls.BLOCK_CLOSERS.findall(stripped_strings))

        if paren_balance != 0:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    line=len(lines),
                    message=f"Parenthèses '(' et ')' déséquilibrées (delta = {paren_balance}).",
                )
            )

        if brace_balance != 0:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    line=len(lines),
                    message=f"Accolades '{{' et '}}' déséquilibrées (delta = {brace_balance}).",
                )
            )

        if open_blocks != 0:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    line=len(lines),
                    message=f"Blocs Lua 'function/if/do' et 'end' déséquilibrés (delta = {open_blocks}).",
                )
            )

        return issues