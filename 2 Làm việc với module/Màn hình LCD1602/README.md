# Màn hình LCD1602

Viết tên dự án của em ở đây.

## 1. Ảnh chương trình Scratch

![code](code.png)

## 2. Mã nguồn Python

Viết mã nguồn Python của em ở đây.

```python
from lcd1602 import *
from yolo_uno import *

lcd1602 = LCD1602()

async def setup():

  print('App started')
  lcd1602.show(str('Hello'), 1 - 1, 1 - 1)
  lcd1602.show(str('OhStem Education'), 2 - 1, 1 - 1)

async def main():
  await setup()
  while True:
    await asleep_ms(100)

run_loop(main())
```

![1602 LCD](./lcd1602_0x27.jpg)

## 3. Hướng dẫn lắp đặt và kết nối

Mô tả cách lắp đặt các thiết bị và kết nối với bo mạch.

* **Thiết bị:** Liệt kê các thiết bị được sử dụng.
* **Cổng kết nối:** Ghi rõ mỗi thiết bị được kết nối với cổng nào trên bo mạch.
* **Cách lắp đặt:** Mô tả cách kết nối các thiết bị với nhau.

Ví dụ:


| Thiết bị | Chân kết nối | Chức năng |
|---|---|---|
| Màn hình LCD I²C | GPIO11 (SDA) | Gửi và nhận dữ liệu |
| Màn hình LCD I²C | GPIO12 (SCL) | Cung cấp tín hiệu xung nhịp |

Or

| Device | Connection Pin | Function |
|---|---|---|
| I²C LCD | GPIO11 (SDA) | Sends and receives data |
| I²C LCD | GPIO12 (SCL) | Provides the clock signal |

![connection](./circuit_1602_crop.png)

## 4. Những điều em đã học được

Viết những điều em đã học được khi thực hiện dự án.

* Em đã học được gì?
* Em đã gặp khó khăn gì và giải quyết như thế nào?
* Nếu thực hiện lại dự án, em muốn cải thiện điều gì?
