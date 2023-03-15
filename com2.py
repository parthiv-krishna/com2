from argparse import ArgumentParser
import lark
import lark.ast_utils
import com2_ast
from com2_ast import *
from providers import *

class CompilerOptions:
    params_dict = {
        "tx": 8, 
        "baud": 115200
    }

    provider = ArduinoProvider()

    codegen_side = com2_ast.Driver.LEFT

COMPILER_OPTIONS = CompilerOptions()

class AstTransformer(lark.Transformer):
    expr = " ".join

    def __init__(self, compiler_options: CompilerOptions) -> None:
        super().__init__()
        self.provided_params = compiler_options.params_dict

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
    
    def states(self, states: list[State]):
        state_map = {}
        anonymous_label_cnt = 0
        prev = None
        for state in states:
            if state.label is None:
                state.label = f"anonymous{anonymous_label_cnt}"
                anonymous_label_cnt += 1
            state_map[state.label] = state
            if prev is not None:
                prev.set_next(state.label)
            prev = state
        return state_map
             
class CodeGen(lark.visitors.Interpreter):
    def __init__(self, side) -> None:
        super().__init__()
        self.side = side

    def start(self, start):
        source = ""
        for section_type in ("parameters", "variables"):
            for section in start.children:
                if section.data == section_type:
                    source += self.visit(section) + "\n"
        return source
    
    def parameters(self, section):
        return "\n".join(d.codegen(COMPILER_OPTIONS) for d in section.children)
    variables = parameters

    def functions(self, section):
        return "\n".join(f.codegen_source(COMPILER_OPTIONS) for f in section.children)

def main(file: str, grammar_file: str):
    to_ast = lark.ast_utils.create_transformer(com2_ast, AstTransformer(COMPILER_OPTIONS))
    com2_parser = lark.Lark.open(grammar_file, rel_to=__file__, parser="lalr", debug=True, transformer=to_ast)
    with open(file, 'r') as f:
        ast = com2_parser.parse(f.read())

    # params_dict = populate_parameters({"tx": 8, "baud": 115200}, ast)
    # print(params_dict)

    # vars_dict = create_variables(ast)
    # print(vars_dict)
    
    print(ast.pretty())
    print(CodeGen("functions").visit(ast))

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file", default="uart.com2")
    parser.add_argument("--grammar_file", default="com2.lark")
    args = parser.parse_args()
    main(args.file, args.grammar_file)
