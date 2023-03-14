from dataclasses import dataclass

import lark

@dataclass
class DeclarationNode:
    ty: lark.Tree
    name: lark.Token
    init: lark.Tree


@lark.v_args(inline=True)
class ToClassTransformer(lark.Transformer):
    declaration = DeclarationNode
