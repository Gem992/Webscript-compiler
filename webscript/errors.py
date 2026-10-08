class CompileError(Exception):
    """An error found in any compiler phase (Lexical / Syntax / Semantic)."""

    def __init__(self, phase, message, line=0, col=0, category=None):
        super().__init__(message)
        self.phase = phase
        self.message = message
        self.line = line
        self.col = col
        self.category = category

    def to_dict(self):
        return {"phase": self.phase, "message": self.message,
                "line": self.line, "col": self.col}

    def __str__(self):
        loc = f" at line {self.line}, col {self.col}" if self.line else ""
        return f"{self.phase} Error{loc}: {self.message}"
