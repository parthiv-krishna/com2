from argparse import ArgumentParser
import lark
from class_transformer import *

class State:
    pass

class Type:
    dimensions: list[int]

    def __init__(self, tree: lark.Tree):
        pass

def populate_parameters(defined_params, ast: lark.Tree):
    params_dict = {}
    param_sections = ast.find_data("parameters")
    for param_section in param_sections:
        declaration: DeclarationNode
        for declaration in param_section.children:
            name = declaration.name.value
            init = declaration.init
            if init is None:
                init = defined_params[name]
            params_dict[name] = init

    return params_dict

def create_variables(ast: lark.Tree):
    vars_dict = {}
    var_sections = ast.find_data("variables")
    for var_section in var_sections:
        declaration: DeclarationNode
        for declaration in var_section.children:
            vars_dict[declaration.name.value] = declaration.ty.children

    return vars_dict

def main(file: str, grammar_file: str):
    com2_parser = lark.Lark.open(grammar_file, rel_to=__file__, parser="lalr", debug=True, transformer=ToClassTransformer())
    with open(file, 'r') as f:
        ast = com2_parser.parse(f.read())
        
        tct = ToClassTransformer()
        ast = tct.transform(ast)

        params_dict = populate_parameters({"tx": 8, "baud": 115200}, ast)
        print(params_dict)

        vars_dict = create_variables(ast)
        print(vars_dict)
        
            
    

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--grammar_file", default="com2.lark")
    args = parser.parse_args()
    main(args.file, args.grammar_file)
