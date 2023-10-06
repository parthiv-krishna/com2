# com2
com2 (short for **com**municaions **com**piler) is a domain specific language and associated compiler for defining new and existing digital communication protocols. With com2, one can write a single unified definition of a communication protocol and generate code for both sides of the protocol (reader/writer, controller/peripheral). In principle com2 could generate code for many different backends, although so far we have only implemented code generation for polling-based code for Arduino. Future backends could include polling-based and interrupt-based implementations, or even hardware implementations by generating Verilog.

### Slides
The slides for our presentation can be found [here](https://docs.google.com/presentation/d/1wd-cLTV7zk-6ha02cgiNSGKHZyAGYPovaxa3Yg2ryUU/edit?usp=sharing).

## Example
Our implementation of [UART](https://en.wikipedia.org/wiki/Universal_asynchronous_receiver-transmitter) is shown below:

[`uart.com2`](/uart.com2)
```
parameters {
    wire tx;
    integer baud;
    integer bit_period = 1000000/baud;
    integer stop_bits = 1;
}

variables {
    byte data;
}

states {
    IDLE: (tx){
        tx --> 1;
    }

    START: (bit_period us){
        tx --> 0;   
    }

    for $i from 0 to 7 {
        (bit_period us){
            tx ==> data[$i];
        }        
    }

    STOP: (bit_period * stop_bits us){
        tx --> 1;
    }[=> IDLE]

}

shared {
    fn com2_uart_setup() {
        ...IDLE;
    }
}

left {
    fn com2_uart_send(output byte x) {
        data = x;
        START...IDLE;
    }
}

right {
    fn com2_uart_recv(input byte x) {
        IDLE...IDLE;
        x = data;
    }
}
```

The program is composed of 6 sections:
* `parameters`: These are compile time contants that parameterize a pair of devices. These include baud rate and a pin identifier for the transmission wire.
* `variables`: This section defines variables that are accessible by the state machine. Available datatypes are `bit` and nested arrays of `bit` (e.g. `bit[8][8]`). `byte` is shorthand for `bit[8]`
* `states`: This section defines the shared state machine of the protocol. More details on state definitions below.
* `shared/left/right`: These sections define API functions that will be callable from C. `shared` functions are defined for both devices, while `left`/`right` functions are only defined for the respective device.

### States
com2 models digital communication protocols as state machines that are shared between a "left" device and "right" device. The states and transitions are defined in the `states` section using the following format:
```
LABEL: (transition_criteria) {
    state_actions
}[transitions]
```
`LABEL` gives the state a name, although this is optional because states flow sequentially by default. `transition_criteria` deteremines when the state should finish. These can be defined by time durations and/or wires. `state_actions` defines what occcurs during the state. `transitions` specifies transitions to the next state. These may be conditional on variable values. If `transitions` is absent the state implicitly transitions to the next state defined in the `states` section.

The following actions are allowed in a state:
* Variable assignment (`x = y`)
* Wire hold (`tx --> 1`): This tells the device to hold the wire at a value for the duration of the state. If this wire is included in the `transition_criteria`, then the state will transition when this hold no longer applies. Wire hold can be driven by the left device (`wire --> v`) or the right device (`v <-- wire`).
* Sync value (`tx ==> x`): This sends a bit value from a variable on one device to the same variable on the other device. This can be driven by the left device (`wire ==> var`) or the right device (`var <== wire`)

## Usage
```
python com2.py uart.com2 com2_uart_tx --driver=LEFT
```
This command compiles the com2 to C code for the left device, in this case the UART writer. It will produce `com2_uart_tx.h` and `com2_uart_tx.c`.
```
python com2.py uart.com2 com2_uart_rx --driver=RIGHT
```
This command compiles the com2 to C code for the right device, in this case the UART reader. It will produce `com2_uart_rx.h` and `com2_uart_rx.c`.
