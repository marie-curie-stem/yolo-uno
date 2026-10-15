# 2. Làm việc với module - Working with modules

Sau khi đã làm quen với bo mạch Yolo UNO và môi trường lập trình ở chương đầu, trong chương này chúng ta sẽ bắt đầu kết nối và điều khiển các module phần cứng thực tế. Mỗi dự án nhỏ giới thiệu một loại module cơ bản: từ **đèn thông minh** (điều khiển đèn LED và đọc cảm biến ánh sáng), **màn hình LCD1602** (hiển thị chữ và số), **giám sát nhiệt độ phòng** (đọc cảm biến nhiệt độ - độ ẩm), **quạt thông minh** (điều khiển động cơ theo nhiệt độ), cho đến **động cơ Servo** (điều khiển góc quay chính xác). Ở mỗi bài, bạn sẽ học cách đấu nối module, viết chương trình điều khiển và quan sát kết quả ngay trên mạch. Các kiến thức này là nền tảng để kết hợp nhiều module lại với nhau trong những dự án hoàn chỉnh ở các chương sau.

- [Đèn thông minh](Đèn thông minh) - Smart Light
- [Màn hình LCD1602](Màn hình LCD1602) - LCD1602 Display
- [Giám sát nhiệt độ phòng](Giám sát nhiệt độ phòng) - Room Temperature Monitoring
- [Quạt thông minh](Quạt thông minh) - Smart Fan
- [Động cơ Servo](Động cơ Servo) - Servo Motor

Now that you are familiar with the Yolo UNO board and the programming environment from the first chapter, this chapter starts connecting and controlling real hardware modules. Each small project introduces one basic type of module: a **smart light** (controlling an LED and reading a light sensor), the **LCD1602 display** (showing text and numbers), **room temperature monitoring** (reading a temperature and humidity sensor), a **smart fan** (driving a motor based on temperature), and finally the **servo motor** (controlling a precise rotation angle). In every lesson you will learn how to wire the module, write the control program, and see the result directly on your board. This knowledge is the foundation for combining several modules into complete projects in later chapters.

The regular 1602 display from OhStem works on address 0x21 where others use 0x27. But you can adjust this with the [lcd_fix.py](../hardware/lcd_fix.py) script. It then looks like this:

![1602 LCD](./Màn%20hình%20LCD1602/lcd1602_0x27.jpg)
