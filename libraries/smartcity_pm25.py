import time
from machine import UART

class HT5102:
    def __init__(self, uart_id=2, baudrate=9600, rx_pin=16, tx_pin=17):
        self.uart = UART(
            uart_id,
            baudrate=baudrate,
            rx=rx_pin,
            tx=tx_pin,
            timeout=1000,  # Timeout để đợi dữ liệu (ms)
        )

    def read_pm_data(self, retries=5):
        for attempt in range(retries):
            # Try to find a valid packet
            if self.uart.any():  # Optional: this may still be unreliable
                byte = self.uart.read(1)
                if byte and byte[0] == 0xA5:
                    data = self.uart.read(3)
                    if data and len(data) == 3:
                        dataH, dataL, checksum = data
                        sum_check = (0xA5 + dataH + dataL) & 0x7F

                        if checksum == sum_check:
                            concentration = dataH * 128 + dataL
                            return concentration
                        else:
                            print("Dữ liệu sai checksum!")
            time.sleep(0.5)
        
        print("Không đọc được dữ liệu hợp lệ sau", retries, "lần thử")
        return None  # Return None if all attempts fail
