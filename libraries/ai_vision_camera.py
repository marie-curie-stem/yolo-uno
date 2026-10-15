"""
ai_vision_camera.py - Thu vien MicroPython cho AI VISION CAMERA (Yolo UNO, app.ohstem.vn)
Doc ket qua NHAN DANG tu Camera AI qua UART: khuon mat / mau sac / lop (Teachable) / QR.

LUU Y: 2 chuc nang Object tracking va Line tracking KHONG con o extension nay -
       chung da nam trong muc "AI CAMERA" cua thu vien ROBOTICS.
"""

import time
import machine

# Bien toan cuc UART
_uart = None
_last_recv_time = 0

# Cac nhan goi tu Camera AI (giao thuc "tu mo ta"): "NHAN:du_lieu"
_KNOWN_TAGS = ('FACE', 'COLOR', 'CLASS', 'QR')


def _split_tag(text):
    # Tach "NHAN:du_lieu" -> (nhan, du_lieu). Khong co nhan hop le -> ('', text).
    i = text.find(':')
    if i > 0:
        tag = text[:i].strip().upper()
        if tag in _KNOWN_TAGS:
            return tag, text[i + 1:].strip()
    return '', text


def camera_ai_init(rx_pin, tx_pin, baudrate=115200):
    # Khoi tao UART noi Camera AI tren Yolo UNO.
    # rx_pin / tx_pin la chan GPIO cua Yolo UNO (vd D3_PIN, D4_PIN do block truyen vao).
    # Gop tat ca tham so vao 1 lan goi -> tranh .init() lam reset chan tren ESP32-S3.
    global _uart, _last_recv_time
    _uart = machine.UART(1, baudrate=baudrate, rx=rx_pin, tx=tx_pin,
                         bits=8, parity=None, stop=1)
    _last_recv_time = time.ticks_ms()
    return _uart


def camera_ai_uart():
    # Tra ve UART thu vien (do 'camera_ai_init' tao theo chan RX/TX da chon).
    # Tren Yolo UNO PHAI goi camera_ai_init(rx, tx) truoc; chua init -> tra None.
    return _uart


# ================================================================
# NHAN DANG KHUON MAT + MAU SAC + LOP (Teachable) + QR (doc UART)
# Camera gui: "FACE:<id>" (id>=1 da luu / 0 nguoi la / -1 khong co mat)
#             "COLOR:<TEN>" (RED, GREEN, BLUE, ... mau dang thay o tam)
#             "CLASS:<ten lop>,<conf%>"   |   "QR:<noi dung>"
# Cac block tu goi camera_ai_vision_update() de luon co du lieu moi nhat.
# ================================================================
_face_id = -1
_face_time = 0       # moc thoi gian nhan FACE gan nhat
_color_name = ''
_color_time = 0      # moc thoi gian nhan COLOR gan nhat
_class_name = ''     # ten lop Stream video (Teachable Machine)
_class_conf = 0      # do tin cay (%) cua lop dang nhan
_class_time = 0      # moc thoi gian nhan CLASS gan nhat
_qr_text = ''        # noi dung ma QR doc duoc gan nhat
_qr_time = 0         # thoi diem (ms) nhan QR gan nhat (de biet con dang detect khong)

# Khong nhan du lieu nhan dang moi trong ngan nay (ms) -> coi nhu MAT/RONG (tra rong),
# tranh giu ket qua cu mai khi mat vat / mat ket noi -> dieu khien dung.
_VISION_HOLD_MS = 200


def _vision_fresh(t):
    # True neu moc thoi gian t con moi (trong _VISION_HOLD_MS). t==0 -> chua tung nhan.
    return t != 0 and time.ticks_diff(time.ticks_ms(), t) <= _VISION_HOLD_MS


def camera_ai_vision_update():
    # Doc goi UART moi nhat: cap nhat ket qua FACE / COLOR / CLASS / QR.
    global _uart, _last_recv_time, _face_id, _color_name, _class_name, _class_conf, _qr_text, _qr_time
    global _face_time, _color_time, _class_time
    while _uart and _uart.any():
        ln = _uart.readline()
        if not ln:
            break
        try:
            text = ln.decode('utf-8').strip()
        except Exception:
            continue
        _last_recv_time = time.ticks_ms()
        tag, payload = _split_tag(text)   # tag tu dong chuan hoa HOA -> nhan ca face:/FACE:
        if tag == 'FACE':
            try:
                _face_id = int(payload)
                _face_time = time.ticks_ms()
            except Exception:
                pass
        elif tag == 'COLOR':
            _color_name = payload.strip().upper()   # chuan hoa HOA de camera_ai_is_color so khop dung
            _color_time = time.ticks_ms()
        elif tag == 'CLASS':
            # payload = "<ten lop>,<conf%>"  (vd "meo,87")
            i = payload.rfind(',')
            if i >= 0:
                _class_name = payload[:i].strip()
                try:
                    _class_conf = int(payload[i + 1:])
                except Exception:
                    _class_conf = 0
            else:
                _class_name = payload.strip()
                _class_conf = 0
            _class_time = time.ticks_ms()
        elif tag == 'QR':
            _qr_text = payload   # noi dung ma QR (giu nguyen, khong viet hoa)
            _qr_time = time.ticks_ms()


def camera_ai_face_known(face_id=0):
    # True neu DANG nhan ra nguoi DA LUU. Mat/cu -> False.
    # face_id > 0: chi dung khi nhan dung ID do. face_id == 0: bat ky ID da luu (>=1).
    camera_ai_vision_update()
    if not _vision_fresh(_face_time):
        return False
    if face_id and face_id >= 1:
        return _face_id == int(face_id)
    return _face_id >= 1


def camera_ai_face_unknown():
    # True neu DANG thay mat nhung CHUA LUU (id == 0). Mat/cu -> False.
    camera_ai_vision_update()
    return _vision_fresh(_face_time) and _face_id == 0


def camera_ai_color_name():
    # Ten mau dang thay o tam ('RED','GREEN',...). '' neu khong thay / mat ket noi.
    camera_ai_vision_update()
    return _color_name if _vision_fresh(_color_time) else ''


def camera_ai_is_color(name):
    # True neu DANG thay mau dung bang 'name' (vd 'RED'). Mat/cu -> False.
    camera_ai_vision_update()
    return _vision_fresh(_color_time) and _color_name == str(name).upper()


def camera_ai_class():
    # Ten lop nhan dang (Stream video / Teachable Machine). '' neu khong nhan duoc /
    # mat ket noi (khong giu ket qua cu mai) -> dieu khien dung.
    camera_ai_vision_update()
    return _class_name if _vision_fresh(_class_time) else ''


def camera_ai_class_conf():
    # Do tin cay (%) cua lop dang nhan: 0..100. 0 neu khong nhan duoc / mat ket noi.
    camera_ai_vision_update()
    return _class_conf if _vision_fresh(_class_time) else 0


def camera_ai_is_class(name, min_conf=0):
    # True neu DANG nhan lop == 'name' VA tin cay >= min_conf (%). Mat/cu -> False.
    camera_ai_vision_update()
    if not _vision_fresh(_class_time):
        return False
    n = str(name)
    return (_class_name == n or _class_name.upper() == n.upper()) and _class_conf >= min_conf


def camera_ai_qr(hold_ms=1500):
    # Noi dung ma QR khi DANG detect (chuoi). Tra '' (rong) neu khong thay QR
    # trong hold_ms gan day -> chi hien khi co ma trong khung, het thi de trong.
    camera_ai_vision_update()
    if _qr_time != 0 and time.ticks_diff(time.ticks_ms(), _qr_time) <= hold_ms:
        return _qr_text
    return ''
