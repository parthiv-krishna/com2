import abc
from enum import Enum
import lark

class WireMode(Enum):
    Input = "INPUT"
    Output = "OUTPUT"

class Provider(abc.ABC):
    @abc.abstractmethod
    def codegen_get_micros(self):
        pass
    
    @abc.abstractmethod
    def codegen_time_type(self):
        pass

    @abc.abstractmethod
    def codegen_wire_type(self):
        pass

    @abc.abstractmethod
    def codegen_wire_set_mode(self, wire_id: lark.Token, mode: WireMode):
        pass

    @abc.abstractmethod
    def codegen_wire_write_bit(self, wire_id: lark.Token, expr: str):
        pass
    
    @abc.abstractmethod
    def codegen_wire_read_bit(self, wire_id: lark.Token, expr: str):
        pass

class ArduinoProvider(Provider):
    def codegen_get_micros(self):
        return "micros()"
    
    def codegen_time_type(self):
        return "unsigned long"
    
    def codegen_wire_type(self):
        return "int"
    
    def codegen_wire_set_mode(self, wire_id: lark.Token, mode: WireMode):
        return f"pinMode({wire_id}, {mode})"
    
    def codegen_wire_write_bit(self, wire_id: lark.Token, expr: str):
        return f"digitalWrite({wire_id}, {expr})"
    
    def codegen_wire_read_bit(self, wire_id: lark.Token, expr: str):
        return f"{expr} = digitalRead({wire_id})"