from argparse import ArgumentParser
import lark
import lark.ast_utils
import com2_ast
from com2_ast import *

class AstTransformer(lark.Transformer):
    expr = " ".join

    def __init__(self, provided_params) -> None:
        super().__init__()
        self.provided_params = provided_params

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
    
class CodeGen(lark.visitors.Interpreter):
    def __init__(self, side) -> None:
        super().__init__()
        self.side = side

    def start(self, *sections):
        source = ""
        for section_type in ("parameters", "variables", self.side):
            for section in sections:
                if section.data == section_type:
                    source += self.visit(section) + "\n"
        return source
    
    def parameters(declarations): 
        return "\n".join(d.codegen() for d in declarations)
    variables = source

def main(file: str, grammar_file: str):
    params_dict = {"tx": 8, "baud": 115200}
    to_ast = lark.ast_utils.create_transformer(com2_ast, AstTransformer(params_dict))
    com2_parser = lark.Lark.open(grammar_file, rel_to=__file__, parser="lalr", debug=True, transformer=to_ast)
    with open(file, 'r') as f:
        ast = com2_parser.parse(f.read())

    # params_dict = populate_parameters({"tx": 8, "baud": 115200}, ast)
    # print(params_dict)

    # vars_dict = create_variables(ast)
    # print(vars_dict)
    
    print(ast.pretty())

    
     __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--grammar_file", default="com2.lark")
    args = parser.parse_args()
    main(args.file, args.grammar_file)
