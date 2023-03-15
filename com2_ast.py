from dataclasses import dataclass

import lark
from lark.ast_utils import Ast

from enum import Enum

STATE_TIME_VAR = "__state_time"

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

    def codegen(self, compiler_options, name):
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

    def codegen(self, compiler_options):
        assert(self.init is not None)
        return f"const {self.ty.codegen(compiler_options, self.name)} = {self.init};"

@dataclass
class VarDeclaration(Ast):
    ty: Type
    name: lark.Token

    def codegen(self, compiler_options):
        return f"static {self.ty.codegen(compiler_options, self.name)};"

@dataclass
class Duration(Ast):
    val: str
    unit: lark.Token

    def get_us(self):
        suffix = ""
        if self.unit == "s":
            suffix = "* 1000000"
        elif self.unit == "ms":
            suffix = "* 1000"
        elif self.unit == "ns":
            suffix = "/ 1000"
        return f"({self.val}) {suffix}"
    
    def get_half_us(self):
        return f"({self.get_us()}) / 2"

@dataclass
class Argument(Ast):
    io_ty: lark.Token
    ty: Type
    name: lark.Token

    def codegen(self, compiler_options):
        name = self.name if self.io_ty == "output" else f"(*{self.name})"
        return self.ty.codegen(compiler_options, name)

class Function(Ast):
    def __init__(self, name, arg_list, stmt_list) -> None:
        super().__init__()
        self.name = name
        self.args = arg_list.children
        self.stmts = stmt_list.children

    def codegen_prototype(self, compiler_options):
        params = ", ".join(arg.codegen(compiler_options) for arg in self.args)
        return f"void {self.name}({params})"
    
    def codegen_header(self, compiler_options):
        return f"{self.codegen_prototype(compiler_options)};"
    
    def codegen_source(self, compiler_options):
        input_vars = set(arg.name for arg in self.args if arg.io_ty == "input")
        source = self.codegen_prototype(compiler_options)
        source += "{\n"
        for stmt in self.stmts:
            if isinstance(stmt, VariableAssignment):
                source += f"    {stmt.codegen(compiler_options, deref=(stmt.var in input_vars))}\n"
            else:
                source += f"{stmt.codegen(compiler_options)}\n"
        source += "}"

        return source
    
@dataclass
class VariableAssignment(Ast):
    var: lark.Token
    expr: str

    def codegen(self, compiler_options, deref=False):
        prefix = "*" if deref else ""
        return f"{prefix}{self.var} = {self.expr};"

@dataclass
class StatePath(Ast):
    start: lark.Token
    end: lark.Token

    def codegen(self, compiler_options, num, state_map):
        code = ""
        completed = set()
        start_state = state_map[self.start]
        code += start_state.codegen(compiler_options, num, start=True)
        frontier = start_state.get_next_states()
        while len(frontier) > 0:
            state_name = frontier.pop()
            state = state_map[state_name]
            end = (state_name == self.end)
            code += state.codegen(compiler_options, num, start=False, end=end)
            completed.add(state_name)
            if not end:
                frontier |= state.get_next_states() - completed
            
        return code



# class States(Ast):
#     def __init__(self, *states) -> None:
#         super().__init__()

#         self.states = states

#     def __repr__(self):
#         return "\n".join(str(s) for s in self.states)


class Driver(Enum):
    LEFT = "_LEFT"
    RIGHT = "RIGHT"

class WireActionType(Enum):
    TRANFER = "TRANSFER"
    SEND = "SEND"

class _WireAction(Ast):
    DRIVER = None
    ACTION = None

@dataclass
class _ToRight(_WireAction):
    wire: lark.Token
    val: str
    DRIVER = Driver.LEFT

class TransferToRight(_ToRight):
    ACTION = WireActionType.TRANFER

class SendToRight(_ToRight):
    ACTION = WireActionType.SEND
    
@dataclass
class _ToLeft(_WireAction):
    val: str
    wire: lark.Token
    DRIVER = Driver.RIGHT

class TransferToLeft(_ToLeft):
    ACTION = WireActionType.TRANFER

class SendToLeft(_ToLeft):
    ACTION = WireActionType.SEND

@dataclass
class Transition(Ast):
    predicate: str
    target: lark.Token
    
class State(Ast):
    def __init__(self, label, cond_list, actions, transitions) -> None:
        super().__init__()
        self.label = label
        self.left_driven_wires = set()
        self.right_driven_wires = set()
        for action in actions:
            if isinstance(action, _WireAction):
                if action.DIRECTION == Direction.TO_RIGHT:
                    self.left_driven_wires.add(action.wire)
                else:
                    self.right_driven_wires.add(action.wire)
        assert len(self.left_driven_wires & self.right_driven_wires) == 0
        self.actions = actions
        self.next_state_label = None
        self.conds = cond_list
        self.transitions = transitions

    def set_next(self, next_label):
        self.next_state_label = next_label

    def mangle(self, label, num):
        return f"{label}_{num}"

    def get_next_states(self) -> set[str]:
        can_fall_through = True
        next_states = set()
        for transition in self.transitions:
            next_states.add(transition.target)
            if transition.predicate is None:
                can_fall_through = False
        if can_fall_through and self.next_state_label is not None:
            next_states.add(self.next_state_label)
        return next_states
    
    def codegen(self, compiler_options, num, start=False, end=False):
        code = ""
        if not start:
            code += f"{self.mangle(self.label, num)}:\n"
        reads = set()
        assertions = set()
        for action in self.actions:
            if isinstance(action, VariableAssignment) or action.DRIVER == compiler_options.codegen_side:
                # set to write mode
                code += action.codegen(compiler_options) + "\n"
            elif action.wire in self.conds:
                assert (action.ACTION == WireActionType.SEND)
                assertions.add(action)
            elif action.ACTION == WireActionType.TRANFER:
                # set to read mode
                reads.add(action)
        if len(assertions) == 0:
            try:
                assertions = next(filter(lambda c: isinstance(c, Duration), self.conds))
            except StopIteration:
                assertions = None
        if isinstance(assertions, Duration):
            self.codegen_delay_until(compiler_options, assertions.get_half_us())
            self.codegen_reads(compiler_options, reads)
            self.codegen_delay_until(compiler_options, assertions.get_us())
            self.codegen_update_state_time(compiler_options, assertions.get_us())
        else:
              
    def codegen_delay_until(self, compiler_options, delta_us):
        get_us = compiler_options.provider.codegen_get_micros() # get time
        return f"while ({get_us} - {STATE_TIME_VAR} < {delta_us}) {{}}\n"
    
    def codegen_update_state_time(self, compiler_options, change_us=None):
        get_us = compiler_options.provider.codegen_get_micros() # get time
        expr = get_us if change_us is None else f"{STATE_TIME_VAR} + {change_us}"
        return f"{STATE_TIME_VAR} = {expr};\n"
    
    def codegen_reads(self, compiler_options, reads):
        return "".join(r.codegen() + "\n" for r in reads)
    
    def codegen_asertions(self, assertions):
        pass
        

    