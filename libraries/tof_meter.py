# ============================================================
#  THU VIEN CAM BIEN KHOANG CACH ToF VL53L0X - Yolo:Uno (ESP32-S3)
# ============================================================
#  Dung cho extension "Cam bien khoang cach ToF" (khoi lenh keo-tha).
#  - Giao tiep I2C (mac dinh SDA=IO11, SCL=IO12 - cong I2C cua Yolo:Uno).
#  - Doi che do do: mac dinh / chinh xac cao / toc do cao / tam xa.
#  KHONG phu thuoc man hinh: phan hien thi do khoi lenh khac lo.
#
#  DOC THO: tra ve DUNG so cam bien do duoc.
#    khong median, khong lam muot EMA, khong kep gioi han, khong bu offset.
#
#  Driver cap thap nam trong vl53l0x.py (ban port MIT tu Adafruit/pololu).
# ============================================================

from machine import Pin, I2C, SoftI2C

from vl53l0x import VL53L0X

# --- Cau hinh mac dinh ---
TOF_SDA_DEFAULT = 11          # cong I2C cua Yolo:Uno
TOF_SCL_DEFAULT = 12
TOF_ADDR_DEFAULT = 0x29       # dia chi I2C mac dinh cua VL53L0X

OUT_OF_RANGE = -1             # khong doc duoc cam bien (loi I2C)

# --- Bu sai so o CU LY GAN ---
#  VL53L0X do dua tren thoi gian bay cua chum laser. O cu ly gan, anh sang
#  phan xa qua manh va co them phan xa cheo qua lop kinh phu, lam chip do
#  DAI hon thuc te. Do khong phai nhieu (so do rat on dinh) nen loc EMA
#  khong sua duoc; phai bu bang bang so do duoc.
#  Do thuc te: duoi 10cm lech +2cm, tu 10cm tro len gan nhu chuan.
#
#  Bu HET 25mm khi so do <= 120mm, roi giam dan ve 0 khi len 140mm.
#  Giam dan chu khong cat dot ngot, de so do khong bi nhay bac thang.
NEAR_FIX_MM = 25              # luong bu toi da (mm)
NEAR_FIX_FULL_MM = 120        # tu day tro xuong: bu het NEAR_FIX_MM
NEAR_FIX_NONE_MM = 140        # tu day tro len : khong bu nua

# --- Gioi han duoi cua so do tra ve: 4 cm ---
#  VL53L0X khong do noi duoi ~4cm (datasheet ghi tam do tu ~3-5cm tro len):
#  o cu ly do chum laser doi ve qua som, chip khong phan giai duoc nua.
#  Nen KEP ve dung bien thay vi tra so bay.
MIN_VALID_MM = 40             # 4 cm

# --- Gioi han tren cua so do tra ve: 200 cm ---
#  Xa hon 200cm thi VL53L0X do khong con dang tin, nen KEP ve dung bien.
MAX_VALID_MM = 2000           # 200 cm

#  Cam bien bao "khong thay vat" bang mot so rat lon (thuong 8190/8191).
#  Hang so nay dung de nhan biet truong hop do, truoc khi kep gioi han.
NO_TARGET_MM = 8000

# --- Che do do: ten -> (signal_rate MCPS, timing budget us, pre VCSEL, final VCSEL) ---
#  signal_rate_limit CANG NHO  -> chap nhan tin hieu yeu -> do XA hon (nhieu hon)
#  timing budget      CANG LON -> do lau hon nhung ON DINH & XA hon
#  VCSEL pulse period CANG LON -> tam do XA hon. DAY MOI LA YEU TO QUYET DINH:
#     mac dinh 14/10 -> tran ~1.2m du co ha signal rate va tang budget.
#     tam xa    18/14 -> len duoc ~2m.
#  CAC CHE DO DUOI DAY LAY DUNG THEO HO SO CHINH HANG cua ST, giong het
#  Adafruit_VL53L0X::VL53L0X_SENSE_* ma ban test Arduino dung:
#     default       -> 0.25 MCPS, 33ms,  14/10   (~1.2m)
#     long range    -> 0.10 MCPS, 33ms,  18/14   (~2m)
#     high speed    -> 0.25 MCPS, 20ms,  14/10
#     high accuracy -> 0.25 MCPS, 200ms, 14/10
#  Truoc day 'long' dung budget 200ms - KHONG khop ho so goc; nay da sua.
MODES = {
    "default": (0.25, 33000, 14, 10),    # ~1.2m, 33ms/lan do
    "accurate": (0.25, 200000, 14, 10),  # chinh xac cao, 200ms/lan do
    "fast": (0.25, 20000, 14, 10),       # nhanh 20ms/lan do, nhieu hon
    "long": (0.10, 33000, 18, 14),       # tam xa ~2m - GIONG BAN C++ hien tai
}


class ToFSensor:
    """Doc cam bien khoang cach ToF VL53L0X qua I2C."""

    def __init__(self, sda=TOF_SDA_DEFAULT, scl=TOF_SCL_DEFAULT, freq=400000,
                 address=TOF_ADDR_DEFAULT, mode="long", io_timeout_ms=300,
                 ema_alpha=0.3, ema_jump_mm=80, near_fix=True):
        # Bat/tat viec bu sai so cu ly gan (xem NEAR_FIX_MM o dau file).
        self.near_fix = near_fix

        # --- Loc lam muot EMA (trung binh truot mu) ---
        # Moi so do moi duoc tron voi ket qua truoc do:
        #     ket_qua = (1 - alpha) * ket_qua_cu + alpha * so_do_moi
        # alpha cang NHO -> cang muot nhung phan ung cham hon.
        # Neu khoang cach doi lon hon ema_jump_mm (vat di chuyen that) thi
        # NHAY THEO NGAY, khong lam muot - de khong bi tre khi vat chay.
        self.ema_alpha = ema_alpha
        self.ema_jump_mm = ema_jump_mm
        self._mm_ema = None               # None = chua co so do nao

        # --- Mo bus I2C: uu tien I2C phan cung, khong duoc thi dung SoftI2C ---
        try:
            self.i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=freq)
        except Exception:
            self.i2c = SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=freq)

        self.sensor = VL53L0X(self.i2c, address=address, io_timeout_ms=io_timeout_ms)

        self.mode = "default"
        self.set_mode(mode)

    # ------------------------------------------------------------
    #  CHE DO DO
    # ------------------------------------------------------------
    def set_mode(self, mode):
        """Doi che do do: 'default' | 'accurate' | 'fast' | 'long'."""
        rate, budget, pre_pclks, final_pclks = MODES.get(mode, MODES["default"])
        self.sensor.signal_rate_limit = rate
        # Noi rong timing budget TRUOC khi doi VCSEL: moi lan doi VCSEL, driver
        # ap dung lai budget dang co; budget qua nho se bao "Requested timeout too big".
        self.sensor.measurement_timing_budget = 200000
        self.sensor.set_pre_range_vcsel_period(pre_pclks)
        self.sensor.set_final_range_vcsel_period(final_pclks)
        # Dat budget that su sau khi VCSEL da xong.
        self.sensor.measurement_timing_budget = budget
        self.mode = mode if mode in MODES else "default"
        self.reset_smooth()           # cau hinh doi -> so do cu khong con hop
        return self.mode

    # ------------------------------------------------------------
    #  DOC KHOANG CACH
    # ------------------------------------------------------------
    def read_raw_mm(self):
        """Doc khoang cach (mm) - DUNG so cam bien tra ve, khong kep gioi han.

        Khong thay vat thi cam bien tra so rat lon (8190/8191) va so do vao
        van duoc tra ra nguyen ven. Loi I2C -> OUT_OF_RANGE (-1)."""
        try:
            return self.sensor.range
        except Exception:
            return OUT_OF_RANGE

    def _bu_cu_ly_gan(self, mm):
        """Tru bot phan do dai them o cu ly gan.

        <= 120mm : tru het 20mm
        120-140mm: tru giam dan 20mm -> 0mm
        >  140mm : giu nguyen
        Cach giam dan nay giu so do luon tang deu, khong nhay bac thang."""
        if not self.near_fix or mm > NEAR_FIX_NONE_MM:
            return mm
        if mm <= NEAR_FIX_FULL_MM:
            bu = NEAR_FIX_MM
        else:
            phan_con_lai = (NEAR_FIX_NONE_MM - mm) / float(
                NEAR_FIX_NONE_MM - NEAR_FIX_FULL_MM)
            bu = NEAR_FIX_MM * phan_con_lai
        return int(mm - bu + 0.5)

    def read_mm(self):
        """Doc khoang cach (mm): da BU SAI SO CU LY GAN, loc nhieu EMA,
        va kep trong khoang 4cm .. 200cm.

        Ngoai khoang do VL53L0X do khong con dang tin, nen tra ve dung bien
        thay vi so bay. Muon so tho chua qua xu ly thi dung read_raw_mm()."""
        mm = self.read_raw_mm()
        if mm == OUT_OF_RANGE:
            self._mm_ema = None           # mat tin hieu -> xoa trang thai loc
            return OUT_OF_RANGE
        if mm > MAX_VALID_MM:
            mm = MAX_VALID_MM
        mm = self._bu_cu_ly_gan(mm)
        if mm < MIN_VALID_MM:
            mm = MIN_VALID_MM             # vat qua gan -> kep ve 4cm

        if self._mm_ema is None or abs(mm - self._mm_ema) > self.ema_jump_mm:
            self._mm_ema = float(mm)      # lan dau, hoac vat vua doi cho that
        else:
            a = self.ema_alpha
            self._mm_ema = (1.0 - a) * self._mm_ema + a * mm
        return int(self._mm_ema + 0.5)

    def reset_smooth(self):
        """Xoa trang thai loc - lan doc ke tiep bat dau lai tu dau."""
        self._mm_ema = None

    def read_cm(self):
        """Doc khoang cach (cm, 1 chu so thap phan: 12.2, 29.1 ...), da loc nhieu.

        Toi da 200.0 cm."""
        mm = self.read_mm()
        if mm == OUT_OF_RANGE:
            return OUT_OF_RANGE
        return round(mm / 10.0, 1)

    def read_raw_cm(self):
        """Doc khoang cach (cm) tho, KHONG kep gioi han."""
        mm = self.read_raw_mm()
        if mm == OUT_OF_RANGE:
            return OUT_OF_RANGE
        return round(mm / 10.0, 1)

    def read_status(self):
        """Ma trang thai cua phep do gan nhat (goi SAU read_mm/read_cm).

        11 = phep do hoan tat, so do dang tin. Cac ma khac = do that bai.
        Day la thu ma ban test Arduino in o cot 'status'."""
        return self.sensor.last_range_status

    # ------------------------------------------------------------
    #  HIEU CHUAN OFFSET (nam trong chip, moi che do do deu duoc bu)
    # ------------------------------------------------------------
    def get_offset_mm(self):
        """Doc offset hieu chuan dang nam trong chip (mm)."""
        return self.sensor.get_offset_mm()

    def set_offset_mm(self, offset_mm):
        """Ghi offset hieu chuan vao chip (mm). Mat dien la mat, phai ghi lai."""
        return self.sensor.set_offset_mm(offset_mm)

    def calibrate_offset(self, actual_mm, samples=20):
        """Hieu chuan theo dung quy trinh cua ST.

        Dat bia phang MAU TRANG, vuong goc, cach mat kinh dung 'actual_mm'
        (ST khuyen nghi 100mm), roi goi ham nay. No do nhieu lan, tinh phan
        lech roi ghi thang vao chip.

        Tra ve (offset_moi_mm, so_do_trung_binh_mm)."""
        self.sensor.set_offset_mm(0)          # xoa offset cu truoc khi do
        tong = 0
        dem = 0
        for _ in range(samples):
            mm = self.read_raw_mm()
            if mm != OUT_OF_RANGE and self.read_status() == self.sensor.RANGE_OK:
                tong += mm
                dem += 1
        if dem == 0:
            raise RuntimeError("Khong do duoc mau nao hop le - kiem tra vat/anh sang")
        trung_binh = tong / dem
        offset = actual_mm - trung_binh
        self.sensor.set_offset_mm(offset)
        return (self.sensor.get_offset_mm(), trung_binh)

    # ------------------------------------------------------------
    #  TIEN ICH CHO KHOI LENH
    # ------------------------------------------------------------
    def is_valid(self):
        """True neu phep do vua roi HOP LE (dua vao ma trang thai, giong ban C++).

        Dung so THO - neu dung read_mm() thi truong hop 'khong thay vat' da bi
        kep ve 2000 nen khong con nhan ra duoc."""
        mm = self.read_raw_mm()
        if mm == OUT_OF_RANGE or mm >= NO_TARGET_MM:
            return False
        return self.read_status() == self.sensor.RANGE_OK

    def closer_than(self, limit_cm):
        """True neu co vat that va vat gan hon 'limit_cm' cm."""
        mm = self.read_raw_mm()
        if mm == OUT_OF_RANGE or mm >= NO_TARGET_MM:
            return False
        if self.read_status() != self.sensor.RANGE_OK:
            return False
        return mm / 10.0 <= limit_cm

    def describe(self):
        """In thong tin cam bien ra Serial (de kiem tra / debug)."""
        print("--- THONG TIN CAM BIEN ToF VL53L0X ---")
        print("  Dia chi I2C   : 0x{:02X}".format(self.sensor._address))
        print("  Che do do     : {}".format(self.mode))
        print("  Signal rate   : {:.2f} MCPS".format(self.sensor.signal_rate_limit))
        print("  Timing budget : {} us".format(self.sensor.measurement_timing_budget))
        print("  VCSEL pre/fin : {} / {}".format(
            self.sensor._get_vcsel_pulse_period(0),
            self.sensor._get_vcsel_pulse_period(1)))
        print("  Offset trong chip: {} mm".format(self.get_offset_mm()))
        mm = self.read_mm()
        if mm == OUT_OF_RANGE:
            print("  Do thu        : loi doc cam bien")
        else:
            print("  Do thu        : {} mm ({} cm), status {}{}".format(
                mm, round(mm / 10.0, 1), self.read_status(),
                "" if self.read_status() == self.sensor.RANGE_OK else " (KHONG dang tin)"))
        print("--------------------------------------")
