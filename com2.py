from argparse import ArgumentParser
import lark
import lark.ast_utils
import com2_ast
from com2_ast import *
from providers import *
import copy

class CompilerOptions:
    params_dict = {
        "tx": 8, 
        "baud": 600
    }

    provider = ArduinoProvider()

    def __init__(self, driver: Driver) -> None:
        self.codegen_side = driver

class Substitute(lark.Transformer):
    def __init__(self, substitution_var: lark.Token, substitution_val: int):
        super().__init__(visit_tokens=True)
        self.var = substitution_var
        self.val = lark.Token('INT', substitution_val)

    @lark.v_args(tree=True)
    def PREPROC_ID(self, token):
        if token == self.var:
            return self.val
        return token
    
    @lark.v_args(tree=True)
    def LABEL(self, token):
        return lark.Token(token.type, token.replace(self.var, self.val))


class Preprocessor(lark.Transformer):
    @lark.v_args(inline=True)
    def for_loop(self, counter, start, stop, states):
        start = int(start)
        stop = int(stop)
        result = []
        for curr in range(start, stop+1):
            sub = Substitute(counter, curr)
            substituted = sub.transform(states)
            result.append(substituted)
        return lark.Tree("state_list", result)
             

class AstTransformer(lark.Transformer):
    def expr(self, children):
        return "".join(str(child) for child in children)

    def __init__(self, opts: CompilerOptions) -> None:
        super().__init__()
        self.provided_params = opts.params_dict
        self.state_map = None

    def subscript(self, children):
        x = children[0]
        x += "".join(f"[{i}]" for i in children[1:-1])
        return f"(({x} >> ({children[-1]})) & 1)"
    
    @lark.v_args(inline=True)
    def array_dim(self, dim):
        return dim
    
    @lark.v_args(inline=True)
    def param_declaration(self, ty, name, init):
        if name.value in self.provided_params:
            init = self.provided_params[name.value]
        return ParamDeclaration(ty, name, init)
    
    def state_list(self, children):
        flat_list = []
        for child in children:
            if isinstance(child, list):
                flat_list.extend(child)
            else:
                flat_list.append(child)

        return flat_list

    @lark.v_args(inline=True)
    def states(self, states: list[State]):
        state_map = {}
        anonymous_label_cnt = 0
        prev = None
        for state in states:
            if state.label is None:
                state.label = f"anonymous{anonymous_label_cnt}"
                anonymous_label_cnt += 1
            assert (state.label not in state_map)
            state_map[state.label] = state
            if prev is not None:
                prev.set_next(state.label)
            prev = state
        self.state_map = state_map
        return lark.Discard
             
class CodeGen(lark.visitors.Interpreter):
    def __init__(self, opts: CompilerOptions, state_map) -> None:
        super().__init__()
        self.opts = opts
        self.state_map = state_map

    def start(self, start):
        source = ""
        fn_type = "left_functions" if self.opts.codegen_side == Driver.LEFT else "right_functions"
        for section_type in ("parameters", "variables", "shared_functions", fn_type):
            for section in start.children:
                if isinstance(section, lark.Tree) and section.data == section_type:
                    source += self.visit(section) + "\n"
        return source
    
    def parameters(self, section):
        return "\n".join(d.codegen(self.opts) for d in section.children)
    variables = parameters

    def left_functions(self, section):
        return "\n".join(f.codegen_source(self.opts, self.state_map) for f in section.children)
    right_functions = left_functions
    shared_functions = left_functions

class HeaderGen(lark.visitors.Interpreter):
    def __init__(self, opts: CompilerOptions) -> None:
        super().__init__()
        self.opts = opts

    def start(self, start):
        source = ""
        fn_type = "left_functions" if self.opts.codegen_side == Driver.LEFT else "right_functions"
        for section in start.children:
            if isinstance(section, lark.Tree) and section.data == fn_type:
                source += self.visit(section) + "\n"
        return source

    def left_functions(self, section):
        return "\n".join(f.codegen_header(self.opts) for f in section.children)
    right_functions = left_functions  

def main(opts: CompilerOptions, file: str, grammar_file: str, output_prefix):
    com2_parser = lark.Lark.open(grammar_file, rel_to=__file__, parser="lalr", debug=True)
    with open(file, 'r') as f:
        ast = com2_parser.parse(f.read())

    preproc = Preprocessor()
    ast = preproc.transform(ast)
    
    to_ast = lark.ast_utils.create_transformer(com2_ast, AstTransformer(opts))
    ast = to_ast.transform(ast)

    with open(f"{output_prefix}.h", 'w') as f:
        f.write(HeaderGen(opts).visit(ast))
    
    with open(f"{output_prefix}.c", 'w') as f:
        f.write(CodeGen(opts, to_ast.state_map).visit(ast))

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file", default="uart.com2")
    parser.add_argument("output_prefix", default="com2_uart")
    parser.add_argument("--grammar_file", default="com2.lark")
    parser.add_argument("--driver", type=Driver, default=Driver.LEFT)
    args = parser.parse_args()
    opts = CompilerOptions(args.driver)
    main(opts, args.file, args.grammar_file, args.output_prefix)
