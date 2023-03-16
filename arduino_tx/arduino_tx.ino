#include "com2_uart_tx.h"

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  Serial.println("starting tx");
  com2_uart_setup();
}

void loop() {
  // put your main code here, to run repeatedly:
  char *str = "hello com2!\n";
  while (*str) {
    com2_uart_send(*str);
    str++;
  }
  Serial.println("sent");
  delay(1000);
}
