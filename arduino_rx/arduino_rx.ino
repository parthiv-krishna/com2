#include "com2_uart_rx.h"

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  Serial.println("rx starting");
  uart_setup();
}

#include "com2_uart_rx.c"

void loop() {
  // put your main code here, to run repeatedly:
  char data[128];
  for (int i = 0; i < 128; i++) {
    uart_recv(data + i);
    if (data[i] == '\n') {
      data[i + 1] = 0;
      break;
    }
  }
  Serial.print(data);
}
