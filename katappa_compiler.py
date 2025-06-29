import sys
import argparse
import re

# ==============================================================================
# 0. COMMON DATA STRUCTURES AND ERROR CLASSES
# ==============================================================================

class CompilationError(Exception):
    def __init__(self, message, line=None):
        self.message = message
        self.line = line
        super().__init__(self.formatted_message())

    def formatted_message(self):
        return f"[Error on line {self.line}] {self.message}" if self.line else f"[Error] {self.message}"

class PstRow:
    def __init__(self, lexeme, category, line):
        self.lexeme = lexeme
        self.category = category
        self.line = line
        self.mem_location = None

    def __repr__(self):
        return f"PST(L{self.line}, {self.category}, '{self.lexeme}')"

# ==============================================================================
# 1. LANGUAGE DEFINITION ("Sivagami" v1.2 Spec)
# ==============================================================================

class LanguageSpec:
    KEYWORDS = {
        "num": 'Type', "let": 'Mutability', "fix": 'Mutability',
        "when": 'Control', "other": 'Control', "loop": 'Control', "stop": 'Control',
        "print": 'Io',
        ":": 'Delimiter', "=": 'Operator', "+": 'Operator', "-": 'Operator',
        "*": 'Operator', "/": 'Operator', "==": 'Operator', "!=": 'Operator',
        ">": 'Operator', "<": 'Operator', ">=": 'Operator', "<=": 'Operator',
        "{": 'Delimiter', "}": 'Delimiter', ";": 'Delimiter',
    }

# ==============================================================================
# 2. COMPILER CLASS - WRAPS THE ENTIRE PIPELINE
# ==============================================================================

class Compiler:
    def __init__(self, source_code):
        self.source_code = source_code
        self.tokens = []
        self.pst = []
        self.symbol_table = {}
        self.string_literals = {}
        self.stack_size = 0
        self.label_count = 0
        self.loop_end_stack = []

    def compile(self):
        self._stage1_tokenize()
        self._stage2_categorize()
        self._stage3_analyze()
        return self._generate_toplevel_assembly()

    def _get_unique_label(self, prefix):
        self.label_count += 1
        return f".L_{prefix}_{self.label_count}"

    def _tokenize(self):
        print("[1] Tokenization Stage: Reading source...")
        token_spec = [
            ('StringLiteral', r'"[^"]*"'), ('Variable', r'\.[a-zA-Z0-9_]+'),
            ('NumericLiteral',r'-?\d+'), ('Keyword', r'[a-zA-Z]+'),
            ('Operator', r'==|!=|>=|<=|[=+\-*/><]'), ('Delimiter', r'[:{};]'),
            ('Whitespace', r'\s+'), ('Comment', r'##.*'), ('Mismatch', r'.'),
        ]
        tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in token_spec)
        line_num = 1
        for mo in re.finditer(tok_regex, self.source_code):
            kind, value = mo.lastgroup, mo.group()
            if kind in ['Whitespace', 'Comment']:
                line_num += value.count('\n')
                continue
            elif kind == 'Mismatch':
                raise CompilationError(f"Unexpected character: '{value}'", line_num)
            
            # This is a slightly more robust way to track line numbers with regex
            current_line_num = line_num
            line_num += value.count('\n')
            self.tokens.append((value, current_line_num))
    
    def _stage1_tokenize(self): self._tokenize()

    def _stage2_categorize(self):
        print("[2] Categorization Stage: Identifying tokens...")
        for lexeme, line in self.tokens:
            category = "Unknown"
            if lexeme.startswith('.'): category = "Variable"
            elif lexeme.isdigit() or (lexeme.startswith('-') and lexeme[1:].isdigit()): category = "NumericLiteral"
            elif lexeme.startswith('"'): category = "StringLiteral"
            elif lexeme in LanguageSpec.KEYWORDS: category = LanguageSpec.KEYWORDS[lexeme]
            else: raise CompilationError(f"Unknown symbol '{lexeme}'", line)
            self.pst.append(PstRow(lexeme, category, line))
        print("    - Generated Initial PST")

    def _stage3_analyze(self):
        print("[3] Analysis Stage: Building Symbol Table...")
        i = 0
        while i < len(self.pst):
            row = self.pst[i]
            if row.category == 'Mutability':
                try:
                    var, colon, type_kw, semi = self.pst[i+1:i+5]
                    if not (var.category == 'Variable' and colon.lexeme == ':' and type_kw.category == 'Type' and semi.lexeme == ';'):
                        raise CompilationError("Invalid variable declaration.", row.line)
                    if var.lexeme in self.symbol_table:
                        raise CompilationError(f"Variable '{var.lexeme}' already declared.", var.line)
                    self.stack_size += 8
                    var.mem_location = f"-{self.stack_size}(%rbp)"
                    self.symbol_table[var.lexeme] = var
                    i += 4
                except (IndexError, ValueError): raise CompilationError("Incomplete variable declaration.", row.line)
            elif row.category == 'StringLiteral':
                if row.lexeme not in self.string_literals:
                    self.string_literals[row.lexeme] = self._get_unique_label("STR")
            elif row.category == 'Variable':
                if row.lexeme not in self.symbol_table:
                    raise CompilationError(f"Use of undeclared variable '{row.lexeme}'", row.line)
                row.mem_location = self.symbol_table[row.lexeme].mem_location
            i += 1
        if self.stack_size % 16 != 0: self.stack_size += 16 - (self.stack_size % 16)
        symbol_table_repr = {k: v.mem_location for k, v in self.symbol_table.items()}
        print(f"    - Symbol Table: {symbol_table_repr}")
        print(f"    - String Literals: {self.string_literals}")
        print(f"    - Reserved Stack Size: {self.stack_size} bytes")

    def _generate_toplevel_assembly(self):
        """Generates the full assembly file including boilerplate."""
        print("[4] Code Generation Stage: Translating PST to Assembly...")
        
        data_section = []
        if self.string_literals:
            data_section.append(".section .rodata")
            for literal, label in self.string_literals.items():
                data_section.append(f'{label}: .string {literal}')
        data_section.append('.LC_NUM_FMT: .string "%lld\\n"')
        
        text_section = self._generate_assembly_for_block(self.pst)

        main_prologue = [
            ".section .text", ".globl main", "\nmain:", "    pushq   %rbp",
            "    movq    %rsp, %rbp",
            f"    subq    ${self.stack_size}, %rsp" if self.stack_size > 0 else ""
        ]
        main_epilogue = [
            "\n    movq    $0, %rax", "    leave", "    ret"
        ]
        
        full_assembly = "\n".join(data_section + main_prologue + text_section + main_epilogue)
        return full_assembly + "\n"

    def _generate_assembly_for_block(self, block_pst):
        """Recursively generates assembly for a given block of PST rows."""
        asm = []
        i = 0
        while i < len(block_pst):
            row = block_pst[i]
            
            if row.category == 'Mutability':
                i += 5
                continue

            if row.category == 'Variable' and i + 1 < len(block_pst) and block_pst[i+1].lexeme == '=':
                val = block_pst[i+2]
                asm.append(f"\n    # Katappa: {row.lexeme} = ...")
                
                if val.category == "NumericLiteral":
                    asm.append(f"    movq    ${val.lexeme}, {row.mem_location}")
                    i += 3
                elif val.category == 'Variable' and i + 3 < len(block_pst) and block_pst[i+3].category == 'Operator':
                    op, operand2 = block_pst[i+3], block_pst[i+4]
                    asm.extend([f"    movq    {val.mem_location}, %rax"])
                    
                    if operand2.category == 'Variable':
                        asm.append(f"    movq    {operand2.mem_location}, %rbx")
                        reg_or_imm = "%rbx"
                    elif operand2.category == 'NumericLiteral':
                        reg_or_imm = f"${operand2.lexeme}"
                    else:
                        raise CompilationError("Invalid right-hand side in arithmetic expression.", op.line)

                    op_map = {'+': "addq", '-': "subq", '*': "imulq"}
                    if op.lexeme in op_map:
                        asm.append(f"    {op_map[op.lexeme]}   {reg_or_imm}, %rax")
                    elif op.lexeme == '/':
                        if operand2.category == 'NumericLiteral':
                            asm.append(f"    movq ${operand2.lexeme}, %rbx")
                        asm.extend(["    cqto", "    idivq   %rbx"])
                    
                    asm.append(f"    movq    %rax, {row.mem_location}")
                    i += 5
                else: 
                    raise CompilationError("Invalid assignment expression.", row.line)
                continue

            elif row.lexeme == 'print':
                val = block_pst[i+1]
                asm.append(f"\n    # Katappa: print {val.lexeme};")
                if val.category == 'Variable':
                    ## WIN64 FIX: Use Windows ABI registers (RCX, RDX) for printf arguments
                    asm.extend([f"    leaq    .LC_NUM_FMT(%rip), %rcx", f"    movq    {val.mem_location}, %rdx"])
                elif val.category == 'StringLiteral':
                    ## WIN64 FIX: Use Windows ABI register (RCX) for the first argument
                    asm.append(f"    leaq    {self.string_literals[val.lexeme]}(%rip), %rcx")
                
                ## WIN64 FIX: Call the plain 'printf' symbol and manage the 32-byte shadow space on the stack.
                asm.extend(["    subq    $32, %rsp",
                            "    movq    $0, %rax",
                            "    call    printf",
                            "    addq    $32, %rsp"])
                i += 2
                continue

            elif row.lexeme == 'when':
                else_label, end_label = self._get_unique_label("ELSE"), self._get_unique_label("END_WHEN")
                var1, op, operand2 = block_pst[i+1], block_pst[i+2], block_pst[i+3]
                
                asm.append(f"\n    # Katappa: when {var1.lexeme} {op.lexeme} {operand2.lexeme} {{...}}")
                asm.append(f"    movq    {var1.mem_location}, %rax")

                if operand2.category == 'Variable':
                    asm.append(f"    cmpq    {operand2.mem_location}, %rax")
                elif operand2.category == 'NumericLiteral':
                    asm.append(f"    cmpq    ${operand2.lexeme}, %rax")
                else:
                    raise CompilationError("Invalid right-hand side in when condition.", op.line)

                jump_map = {"==": "jne", "!=": "je", ">": "jle", "<": "jge", ">=": "jl", "<=": "jg"}
                asm.append(f"    {jump_map[op.lexeme]} {else_label}")
                
                i += 5
                block_start = i
                brace_count = 1
                while brace_count > 0:
                    if i >= len(block_pst): raise CompilationError("Unmatched '{' bracket.", block_pst[block_start-1].line)
                    if block_pst[i].lexeme == '{': brace_count += 1
                    elif block_pst[i].lexeme == '}': brace_count -= 1
                    i += 1
                when_block = block_pst[block_start:i-1]
                asm.extend(self._generate_assembly_for_block(when_block))
                
                asm.append(f"    jmp {end_label}")
                
                asm.append(f"{else_label}:")
                
                if i < len(block_pst) and block_pst[i].lexeme == 'other':
                    i += 2
                    block_start = i
                    brace_count = 1
                    while brace_count > 0:
                        if i >= len(block_pst): raise CompilationError("Unmatched '{' bracket.", block_pst[block_start-1].line)
                        if block_pst[i].lexeme == '{': brace_count += 1
                        elif block_pst[i].lexeme == '}': brace_count -= 1
                        i += 1
                    other_block = block_pst[block_start:i-1]
                    asm.extend(self._generate_assembly_for_block(other_block))
                
                asm.append(f"{end_label}:")
                continue
            
            elif row.lexeme == 'loop':
                start_label, end_label = self._get_unique_label("LOOP_START"), self._get_unique_label("LOOP_END")
                self.loop_end_stack.append(end_label)
                asm.append(f"\n{start_label}:")
                
                i += 2
                block_start = i
                brace_count = 1
                while brace_count > 0:
                    if i >= len(block_pst): raise CompilationError("Unmatched '{' bracket.", block_pst[block_start-1].line)
                    if block_pst[i].lexeme == '{': brace_count += 1
                    elif block_pst[i].lexeme == '}': brace_count -= 1
                    i += 1
                loop_block = block_pst[block_start:i-1]
                asm.extend(self._generate_assembly_for_block(loop_block))
                
                asm.append(f"    jmp {start_label}")
                asm.append(f"{end_label}:")
                self.loop_end_stack.pop()
                continue
            
            elif row.lexeme == 'stop':
                if not self.loop_end_stack: raise CompilationError("'stop' can only be used inside a loop.", row.line)
                asm.append(f"    jmp {self.loop_end_stack[-1]}")
                i += 2
                continue
            
            i += 1
        return asm

def main():
    parser = argparse.ArgumentParser(description="The Katappa Language Compiler (v3.0 Final)")
    parser.add_argument("filepath", help="Path to the Katappa source file (.katp)")
    args = parser.parse_args()
    
    input_path = args.filepath
    output_asm_path = input_path.replace('.katp', '.s')
    output_exe_path = input_path.replace('.katp', '')

    try:
        with open(input_path, 'r') as f: source_code = f.read()
        compiler = Compiler(source_code)
        assembly_code = compiler.compile()
        with open(output_asm_path, 'w') as f: f.write(assembly_code)
        
        print("\n✅ Compilation Successful!")
        print(f"   Assembly code written to: {output_asm_path}")
        print("\nTo create a final executable, run:")
        print(f"  gcc -o {output_exe_path} {output_asm_path}")

    except (FileNotFoundError, CompilationError, IndexError) as e:
        print(f"\n❌ Compilation Failed!")
        if isinstance(e, CompilationError): print(e.formatted_message())
        else: print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()