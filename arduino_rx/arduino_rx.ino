#include "com2_uart_rx.h"

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  Serial.println("rx starting");
  com2_uart_setup();
}

void loop() {
  // put your main code here, to run repeatedly:
  char str[128];
  for (int i = 0; i < 128; i++) {
    com2_uart_recv(str + i);
    if (str[i] == '\n') {
      str[i + 1] = 0;
      break;
    }
  }
  Serial.print(str);
}
