#include "com2_uart_tx.h"

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  Serial.println("starting tx");
  com2_uart_setup();
}

void loop() {
  // put your main code here, to run repeatedly:
  char *data = "hello com2!";
  while (*data) {
    com2_uart_send(*data);
    data++;
  }
  Serial.println("sent");
}
