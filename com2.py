import sys
from argparse import ArgumentParser
from lark import Lark

def main(file: str, grammar_file: str):
    com2_parser = Lark.open(grammar_file, rel_to=__file__, parser="lalr", debug=True)
    with open(file, 'r') as f:
        ast = com2_parser.parse(f.read())
        print(ast.pretty())

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--grammar_file", default="com2.lark")
    args = parser.parse_args()
    main(args.file, args.grammar_file)
