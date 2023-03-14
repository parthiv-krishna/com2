from dataclasses import dataclass

import lark
from lark.ast_utils import Ast

class Type(Ast):
    def __init__(self, base_type, *dims) -> None:
        super().__init__()
        if base_type == "byte":
            base_type = "bit"
            dims = (8, *dims)
        assert (base_type == "bit" or len(dims) == 0)
        self.base_type = base_type
        self.dims = dims

    def __repr__(self):
        return str(self.base_type) + "".join(f"[{d}]" for d in self.dims)

    def codegen(self, name):
        array_dims = ""
        c_type = ""
        if self.base_type == "bit":
            first_dim = int(self.dims[0])
            assert (first_dim <= 64)
            for bit_width in (8, 16, 32, 64):
                if first_dim <= bit_width:
                    c_type = f"uint{bit_width}_t"
                    break

            array_dims = "".join(f"[{d}]" for d in reversed(self.dims[1:]))
            
                    
        elif self.base_type == "integer":
            c_type = "long"
        return f"{c_type} {name}{array_dims}"



@dataclass
class ParamDeclaration:
    ty: Type
    name: lark.Token
    init: str

    def codegen(self):
        assert(self.init is not None)
        return f"const {self.ty.codegen(self.name)} = {self.init};"

@dataclass
class VarDeclaration(Ast):
    ty: Type
    name: lark.Token

    def codegen(self):
        return f"static {self.ty.codegen(self.name)};"

@dataclass
class Duration(Ast):
    val: str
    unit: lark.Token

class State(Ast):
    def __init__(self, label, duration, actions, transitions) -> None:
        super().__init__()
        self.label = label
        self.duration = duration
        self.actions = actions
        self.transitions = transitions

# class Function(Ast):


# class States(Ast):
#     def __init__(self, *states) -> None:
#         super().__init__()

#         self.states = states

#     def __repr__(self):
#         return "\n".join(str(s) for s in self.states)

