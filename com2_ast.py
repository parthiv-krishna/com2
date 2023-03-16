from dataclasses import dataclass

import lark
from lark.ast_utils import Ast

from enum import Enum
from providers import *
import typing


STATE_TIME_VAR = "__state_time"
EXIT_LABEL = "__exit"

def mangle_label(label, num):
    return f"{label}_{num}"

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

    def codegen(self, opts, name):
        array_dims = ""
        c_type = ""
        if self.base_type == "bit":
            first_dim = int(self.dims[0]) if len(self.dims) > 0 else 1
            assert (first_dim <= 64)
            for bit_width in (8, 16, 32, 64):
                if first_dim <= bit_width:
                    c_type = f"uint{bit_width}_t"
                    break

            array_dims = "".join(f"[{d}]" for d in reversed(self.dims[1:]))
            
                    
        elif self.base_type == "integer":
            c_type = "long"

        elif self.base_type == "wire":
            c_type = opts.provider.codegen_wire_type()
        return f"{c_type} {name}{array_dims}"

class LValue(Ast):
    def __init__(self, base, *dims) -> None:
        super().__init__()
        self.base = base
        self.dims = dims
    
    def __str__(self) -> str:
        """ For rvalue (exprs are stirings)
        """
        if len(self.dims) == 0:
            return self.base
        s = self.base + "".join(f"[{i}]" for i in self.dims[:-1])
        return f"(({s} >> ({self.dims[-1]})) & 1)"
    
    def codegen_assign(self, _opts, value, deref=False):
        prefix = "*" if deref else ""
        if len(self.dims) == 0:
            return f"{prefix}{self.base} = {value};\n"
        lhs = prefix + self.base + "".join(f"[{i}]" for i in self.dims[:-1])
        code = f"{lhs} &= ~(1UL << {self.dims[-1]});\n"
        code += f"{lhs} |= (!!({value})) << {self.dims[-1]};\n"
        return code


@dataclass
class ParamDeclaration:
    ty: Type
    name: lark.Token
    init: str

    def codegen(self, opts):
        assert(self.init is not None)
        return f"const {self.ty.codegen(opts, self.name)} = {self.init};"

@dataclass
class VarDeclaration(Ast):
    ty: Type
    name: lark.Token

    def codegen(self, opts):
        return f"static {self.ty.codegen(opts, self.name)};"

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

    def codegen(self, opts):
        name = self.name if self.io_ty == "output" else f"(*{self.name})"
        return self.ty.codegen(opts, name)

class Function(Ast):
    def __init__(self, name, arg_list, stmt_list) -> None:
        super().__init__()
        self.name = name
        self.args = arg_list.children
        self.stmts = stmt_list.children

    def codegen_prototype(self, opts):
        params = ", ".join(arg.codegen(opts) for arg in self.args)
        return f"void {self.name}({params})"
    
    def codegen_header(self, opts):
        return f"{self.codegen_prototype(opts)};"
    
    def codegen_source(self, opts, state_map):
        input_vars = set(arg.name for arg in self.args if arg.io_ty == "input")
        source = self.codegen_prototype(opts)
        source += "{\n"
        num = 0
        source += f"{opts.provider.codegen_time_type()} {STATE_TIME_VAR} = {opts.provider.codegen_get_micros()};\n"
        for stmt in self.stmts:
            if isinstance(stmt, VariableAssignment):
                source += stmt.codegen(opts, deref=(stmt.var.base in input_vars))
            else:
                source += stmt.codegen(opts, num, state_map)
                source += f"{mangle_label(EXIT_LABEL, num)}:\n"
                num += 1
        source += "return;\n}\n"

        return source
    
@dataclass
class VariableAssignment(Ast):
    var: LValue
    expr: str

    def codegen(self, opts, deref=False):
        return self.var.codegen_assign(opts, self.expr, deref)

class StatePath(Ast):
    def __init__(self, start, end) -> None:
        super().__init__()
        self.start = start and lark.Token('LABEL', start.value)
        self.end = lark.Token('LABEL', end.value)

    def codegen(self, opts, num, state_map):
        if self.start is None:
            return state_map[self.end].codegen(opts, num, start=True, end=True)
        code = ""
        completed = set()
        start_state = state_map[self.start]
        code += start_state.codegen(opts, num, start=True)
        frontier = start_state.get_next_states()
        while len(frontier) > 0:
            state_name = frontier.pop()
            state = state_map[state_name]
            end = (state_name == self.end)
            code += state.codegen(opts, num, start=False, end=end)
            completed.add(state_name)
            if not end:
                frontier.update(state.get_next_states() - completed)
            
        return code


class Driver(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"

class WireActionType(Enum):
    TRANSFER = "TRANSFER"
    SEND = "SEND"

class _WireAction(Ast):
    DRIVER = None
    ACTION = None

class _Transfer(_WireAction):
    ACTION = WireActionType.TRANSFER

    def codegen(self, opts):
        if opts.codegen_side == self.DRIVER:
            write = opts.provider.codegen_wire_write_bit(self.wire, self.val)
            return f"{write};\n"

        read = opts.provider.codegen_wire_read_bit(self.wire)
        return self.val.codegen_assign(opts, read)
        
    
class _Send(_WireAction):
    ACTION = WireActionType.SEND

    def codegen(self, opts):
        if opts.codegen_side == self.DRIVER:        
            write = opts.provider.codegen_wire_write_bit(self.wire, self.val)
            return f"{write};"
        
        return ""

@dataclass
class _ToLeft(_WireAction):
    DRIVER = Driver.RIGHT
    val: typing.Union[str, LValue]
    wire: lark.Token

@dataclass
class _ToRight(_WireAction):
    DRIVER = Driver.LEFT
    wire: lark.Token
    val: typing.Union[str, LValue]


class TransferToRight(_ToRight, _Transfer):
    pass
class TransferToLeft(_ToLeft, _Transfer):
    pass
    
class SendToRight(_ToRight, _Send):
    pass

class SendToLeft(_ToLeft, _Send):
    pass


@dataclass
class Transition(Ast):
    predicate: str
    target: lark.Token
    
class State(Ast):
    def __init__(self, label, cond_list, actions, transitions) -> None:
        super().__init__()
        self.label = label
        self.actions = actions.children
        self.next_state_label = None
        self.conds = cond_list.children
        self.transitions = transitions.children if transitions is not None else []

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
    
    def codegen(self, opts, num, start=False, end=False):
        code = ""
        if not start:
            code += f"{mangle_label(self.label, num)}:\n"
        reads = []
        assertions = []
        for action in self.actions:
            if isinstance(action, VariableAssignment) or action.DRIVER == opts.codegen_side:
                if isinstance(action, _WireAction):
                    code += f"{opts.provider.codegen_wire_set_mode(action.wire, WireMode.Output)};\n"
                code += action.codegen(opts)
            elif action.wire in self.conds:
                assert (action.ACTION == WireActionType.SEND)
                code += f"{opts.provider.codegen_wire_set_mode(action.wire, WireMode.Input)};\n"
                assertions.append(action)
            elif action.ACTION == WireActionType.TRANSFER:
                code += f"{opts.provider.codegen_wire_set_mode(action.wire, WireMode.Input)};\n"
                reads.append(action)
        if end:
            return code + f"goto {mangle_label(EXIT_LABEL, num)};\n"
        if len(assertions) == 0:
            try:
                assertions = next(filter(lambda c: isinstance(c, Duration), self.conds))
            except StopIteration:
                assertions = None
        if isinstance(assertions, Duration):
            code += self.codegen_delay_until(opts, assertions.get_half_us())
            code += self.codegen_reads(opts, reads)
            code += self.codegen_delay_until(opts, assertions.get_us())
            code += self.codegen_update_state_time(opts, assertions.get_us())
        else:
            code += self.codegen_wait_for_assertions(opts, assertions)
            code += self.codegen_update_state_time(opts)
            code += self.codegen_reads(opts, reads)
        code += self.codegen_branches(opts, num)
        return code
              
    def codegen_delay_until(self, opts, delta_us):
        get_us = opts.provider.codegen_get_micros() # get time
        return f"while ({get_us} - {STATE_TIME_VAR} < {delta_us}) {{}}\n"
    
    def codegen_update_state_time(self, opts, change_us=None):
        get_us = opts.provider.codegen_get_micros() # get time
        expr = get_us if change_us is None else f"{STATE_TIME_VAR} + {change_us}"
        return f"{STATE_TIME_VAR} = {expr};\n"
    
    def codegen_reads(self, opts, reads):
        return "".join(r.codegen(opts) for r in reads)
    
    def codegen_wait_for_assertions(self, opts, assertions):
        code = "while (1) {\n"
        for assertion in assertions:
            read_value = opts.provider.codegen_wire_read_bit(assertion.wire)
            code += f"if ({read_value} != {assertion.val}) {{\n"
            code += "    break;\n"
            code += "}\n"
        code += "}\n"
        return code
        
    def codegen_branches(self, _opts, num):
        code = ""
        add_fallthrough = True
        for transition in self.transitions:
            assert add_fallthrough # if we don't need fallthrough, we have a dead transition
            goto = f"goto {mangle_label(transition.target, num)};\n"
            if transition.predicate is not None:
                code += f"if ({transition.predicate}) {{\n    {goto}}}\n"
            else:
                code += goto
                add_fallthrough = False
        if add_fallthrough and self.next_state_label is not None:
            code += f"goto {mangle_label(self.next_state_label, num)};\n"
        return code
