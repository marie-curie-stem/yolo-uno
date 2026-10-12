# ============================================================
#  THU VIEN CAM BIEN TDS/EC - Yolo:Uno (ESP32-S3, MicroPython)
# ============================================================
#  Dung cho extension "Cam bien TDS" (khoi lenh keo-tha).
#  - Doc dien ap chan analog (loc nhieu: trung binh cat + EMA).
#  - Cong thuc DFRobot bac 3 (co bu nhiet) -> EC_tho.
#  - Hieu chinh (calib) nhieu diem -> hoi quy least-squares (EC_tho -> ppm).
#  - Luu diem calib vao flash (file JSON) -> khong mat khi tat nguon.
#  KHONG phu thuoc man hinh OLED.
# ============================================================

import json
import time
from machine import Pin, ADC

# --- He so du phong khi KHONG co ca diem calib LAN duong mac dinh ---
# ppm = EC_tho * K_DEFAULT * 0.5
K_DEFAULT = 1.0

# --- GIOI HAN DAI DO (ppm) ---
# Ket qua luon bi kep trong [PPM_MIN, PPM_MAX]. Tren diem calib cao nhat
# thu vien ngoai suy tuyen tinh, nen khong kep thi no se tra ra so lon
# vo han - vo nghia vi chua he do kiem chung o vung do.
#
# Dai do 0-1000 ppm, phu boi 5 diem calib (xem DEFAULT_CALIB ben duoi).
#
# >>> CANH BAO ve DO CHINH XAC o doan tren cung (690-1000 ppm).
# Do nhay tren tung doan giua hai coc lien ke (bu nhiet 27 C):
#     but   89 ->   92 ppm :  dV=0.008 V  ->   388 ppm/V
#     but   92 ->  371 ppm :  dV=0.578 V  ->   483 ppm/V
#     but  371 ->  690 ppm :  dV=0.327 V  ->   975 ppm/V
#     but  690 -> 1000 ppm :  dV=0.071 V  ->  4369 ppm/V   <- gap 4.5x
# Doan cuoi doc gap 4.5 lan doan truoc: dien ap chi nhich 0.071 V trong
# khi nong do nhay 310 ppm. Hau qua:
#   - trong CUNG mot phien do (on dinh 0.28%): sai so o 1000 ppm ~ +/-14 ppm
#     -> dung duoc.
#   - GIUA cac phien: da tung quan sat cung 1 coc troi 6.8% (EC 754.4 roi
#     805.8). Voi do doc doan cuoi, 6.8% thanh ~+/-330 ppm o muc 1000 ppm.
# Nen o vung >690 ppm phai dat DUNG nhiet do nuoc va do lai calib neu
# doi phien/doi ngay. Vung <690 ppm khong bi anh huong nay.
#
# Nguyen nhan goc: cong thuc DFRobot trong ec_tho() duoc thiet ke cho dai
# ra 0-2.3V khi cap 5V (V=2.3 -> ~1120 ppm). Cap 3V3 chi len toi ~1.17V nen
# ca dai 0-1000 ppm bi nen vao nua duoi -> doan tren cung mat do phan giai.
# Doi sang 5V se giai quyet, nhung PHAI CALIB LAI toan bo.
PPM_MIN = 0.0
PPM_MAX = 1000.0

# ============================================================
#  DUONG CALIB MAC DINH  (>>> DIEN SAU KHI DO BANG BUT CHUAN <<<)
#
#  Moi diem la [EC_tho, ppm]. Lay EC_tho bang cach nhung dau do vao coc
#  chuan roi chay khoi "hieu chinh TDS: them diem" - add_calib_point_now()
#  in cap [EC_tho -> ppm] ra Serial.
#  De trong [] neu chua co -> se dung duong K_DEFAULT tho.
#
#  >>> QUAN TRONG: cac diem nay CHI dung de khop san duong mac dinh
#      MOT LAN luc import. Chung KHONG BAO GIO duoc dua vao self.pts.
#      Vi vay ngay khi nguoi dung tu calib 1 diem, duong mac dinh
#      MAT TAC DUNG hoan toan - khong con tron lan nhu truoc.
#      (Giong cach ph_meter.py dung PH_SLOPE_DEFAULT / PH_OFFSET_DEFAULT.)
#
#  Do ngay 2026-08-04. Dien ap la trung binh cac mau doc tu Serial;
#  nhiet do bu dat DUNG theo but tai tung coc, nen EC_tho (da quy ve 25 C)
#  so sanh duoc voi nhau du tung coc do o nhiet do khac:
#    #1 EC_tho =  70.3  ->   32 ppm  (V=0.082371 @24C)  ty le 0.455
#    #2 EC_tho = 149.4  ->   92 ppm  (V=0.190607 @27C)  ty le 0.616
#    #3 EC_tho = 547.6  ->  371 ppm  (V=0.768304 @27C)  ty le 0.678
#    #4 EC_tho = 775.1  ->  690 ppm  (V=1.095434 @27C)  ty le 0.890
#    #5 EC_tho = 828.0  -> 1000 ppm  (V=1.166393 @27C)  ty le 1.208
#  Ca EC_tho va ppm deu tang deu qua 5 diem -> du lieu la MOT HAM,
#  phu tron dai 0-1000 ppm.
#
#  Coc 32 ppm da BAT DUOC MOT LOI THAT: truoc do diem thap nhat la
#  EC 143.6 (89 ppm) va vung duoi no chi duoc NOI THANG VE GOC voi ty le
#  0.620. Do that cho ty le 0.455 -> duong cu doc 43.6 ppm o coc 32 ppm,
#  tuc cao hon +36%. Gio doan 0-32 ppm moi la phan phai ngoai suy.
#
#  Da BO diem cu EC 143.6 -> 89 ppm: no chi cach #2 co 5.8 don vi EC,
#  duoi muc nhieu cua cam bien, va tao mot cho TUT do doc (0.778 -> 0.517
#  -> 0.701). Bo no lam do doc muot hon: 0.759 -> 0.701 -> 1.402 -> 5.860.
#
#  MO HINH: da thuc KHONG khop duoc bo nay. Doan cuoi doc gap ~4 lan doan
#  truoc, nen da thuc (bi ep phai muot) vong len qua roi bu lai bang cach
#  TUT XUONG o giua:
#     bac 3 qua 5 diem : sai lech 14.8 ppm, do doc AM tai EC 340-600
#     bac 2            : sai lech 99.5 ppm
#     bac 4 (chinh xac): van uon nguoc tai EC 500-565
#  Vi vay _fit_poly() tu dong chuyen sang NOI SUY TUYEN TINH TUNG DOAN:
#  khop chinh xac 0.00 ppm ca 5 diem, don dieu tang, khong vong len.
#  Day cung la cach may do thuc te van dung.
#
#  LUU Y 1: khoang 92-371 ppm hien chi co hai dau neo (EC 149.4 va 547.6).
#  Mot coc quang 200 ppm se lam chac them doan dai nhat nay.
#
#  LUU Y 2: doan 690-1000 ppm co do phan giai kem nhat - xem canh bao o
#  phan GIOI HAN DAI DO phia tren truoc khi tin so doc trong vung do.
#
#  LUU Y 3: hai diem calib phai cach nhau > max(15, 8%*EC) moi cung ton
#  tai; gan hon thi add_calib_point() se ghi de. O vung thap 15 EC ~ 7 ppm.
DEFAULT_CALIB = [[70.3, 32.0], [149.4, 92.0], [547.6, 371.0],
                 [775.1, 690.0], [828.0, 1000.0]]
# ============================================================


#  Bac toi da cua duong hoi quy theo so diem calib:
#    1 diem  -> qua goc      2 diem -> duong thang
#    3 diem  -> parabol      >=4 diem -> bac 3
#  Bac 3 khop chinh xac 4 diem, nhung voi nhieu diem co nhieu thi de UON
#  LUON. Vi vay sau khi khop luon kiem tra don dieu tang (_is_safe);
#  neu that bai thi TU DONG ha bac.
_MAX_DEG = 3

#  Nguong "khop sat": da thuc chi duoc uu tien khi sai lech lon nhat cua no
#  <= max(_FIT_TOL_MIN, _FIT_TOL_PCT * ppm cao nhat). Vuot nguong -> chuyen
#  sang noi suy tuyen tinh tung doan (khop chinh xac). Khi so diem = bac+1
#  da thuc khop chinh xac nen luon duoi nguong -> van duoc uu tien.
_FIT_TOL_PCT = 0.015
_FIT_TOL_MIN = 2.0


def _poly_at(c, ec):
    """c = [c0, c1, c2, c3] -> gia tri tai ec."""
    return c[0] + c[1] * ec + c[2] * ec * ec + c[3] * ec * ec * ec


def _slope_at(c, ec):
    """Dao ham d(ppm)/d(ec) tai ec."""
    return c[1] + 2.0 * c[2] * ec + 3.0 * c[3] * ec * ec


def _is_safe(c, lo, hi):
    """Duong chi dung duoc khi TANG DAN tren [lo, hi] va duong tai lo.
    Chan truong hop bac 3 uon nguoc -> ppm giam khi nuoc dac hon."""
    if _poly_at(c, lo) <= 0.0:
        return False
    if hi <= lo:                          # chi 1 diem -> khong co gi de kiem
        return _slope_at(c, lo) > 0.0
    step = (hi - lo) / 32.0
    ec = lo
    for _ in range(33):
        if _slope_at(c, ec) <= 0.0:
            return False
        ec += step
    return True


def _lsq(pts, deg):
    """Khop least-squares bac 'deg' -> [c0, c1, c2, c3] (dem 0 cho bac thieu).
    Tra None neu he suy bien."""
    size = deg + 1
    # ma tran mo rong size x (size+1) cua he phuong trinh chuan
    A = [[0.0] * (size + 1) for _ in range(size)]
    for r in range(size):
        for c in range(size):
            s = 0.0
            for ec, ppm in pts:
                s += ec ** (r + c)
            A[r][c] = s
        s = 0.0
        for ec, ppm in pts:
            s += ppm * (ec ** r)
        A[r][size] = s
    # khu Gauss co chon tru
    for i in range(size):
        piv = i
        for k in range(i + 1, size):
            if abs(A[k][i]) > abs(A[piv][i]):
                piv = k
        A[i], A[piv] = A[piv], A[i]
        d = A[i][i]
        if abs(d) < 1e-12:
            return None
        for c in range(size + 1):
            A[i][c] /= d
        for k in range(size):
            if k != i:
                f = A[k][i]
                for c in range(size + 1):
                    A[k][c] -= f * A[i][c]
    out = [0.0, 0.0, 0.0, 0.0]
    for i in range(size):
        out[i] = A[i][size]
    return out


def _pw_at(pts, ec):
    """Noi suy tuyen tinh tung doan qua 'pts' (da sap tang theo ec).
    Ngoai [pts[0], pts[-1]] tra ve gia tri tai dau mut - phan ngoai
    khoang calib do calc_ppm() xu ly rieng."""
    if ec <= pts[0][0]:
        return pts[0][1]
    for i in range(1, len(pts)):
        x1, y1 = pts[i]
        if ec <= x1:
            x0, y0 = pts[i - 1]
            if x1 <= x0:
                return y1
            return y0 + (y1 - y0) * (ec - x0) / (x1 - x0)
    return pts[-1][1]


def _pts_monotone(pts):
    """True khi ca ec VA ppm deu tang dan qua tung diem. Day la dieu kien
    de noi suy tuyen tinh tung doan chac chan khong uon nguoc."""
    for i in range(1, len(pts)):
        if pts[i][0] <= pts[i - 1][0] or pts[i][1] <= pts[i - 1][1]:
            return False
    return True


def _fit_poly(pts):
    """Khop 'pts' (da sap tang theo ec) -> (c0, c1, c2, c3, deg).
    Chon bac CAO NHAT ma duong con tang dan; neu uon nguoc thi ha bac.
    deg=0: khong co diem nao.  deg=-1: da thuc that bai, dung LINEAR
    (noi suy tuyen tinh tung doan) - xem _model_at() trong class."""
    n = len(pts)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, 0
    if n == 1:
        ec, ppm = pts[0]
        return 0.0, (ppm / ec) if ec > 0 else 0.0, 0.0, 0.0, 1   # qua goc
    lo = pts[0][0]
    hi = pts[-1][0]
    deg_max = n - 1
    if deg_max > _MAX_DEG:
        deg_max = _MAX_DEG

    # Bac cao nhat con TANG DAN. Bac thap hon chi khop te hon nen khong thu tiep.
    best = None
    for deg in range(deg_max, 1, -1):
        c = _lsq(pts, deg)
        if c is not None and _is_safe(c, lo, hi):
            best = (c, deg)
            break

    # Da thuc chi duoc chon khi no THUC SU di sat cac diem. Mot da thuc van
    # tang dan nhung khop te (khi so diem nhieu hon bac+1, least-squares chi
    # la trung hoa) thi te hon noi suy tung doan - vi tung doan khop CHINH XAC.
    if best is not None:
        c, deg = best
        tol = _FIT_TOL_PCT * pts[-1][1]
        if tol < _FIT_TOL_MIN:
            tol = _FIT_TOL_MIN
        if _fit_error(c, deg, pts) <= tol:
            return c[0], c[1], c[2], c[3], deg

    # Khong co da thuc nao vua tang dan vua khop sat -> NOI SUY TUYEN TINH
    # TUNG DOAN, mien la ban than cac diem da tang dan. Khop chinh xac moi
    # diem, khong bao gio vong len roi tut xuong. Day cung la cach may do
    # thuc te van dung.
    if n >= 3 and _pts_monotone(pts):
        return 0.0, 0.0, 0.0, 0.0, -1

    # Cac diem khong tang dan (du lieu tu chong nhau): danh phai dung da thuc
    # tang dan neu co, du no khop khong sat.
    if best is not None:
        c, deg = best
        return c[0], c[1], c[2], c[3], deg
    # bac 1: duong thang least-squares; neu van khong tang -> qua goc
    c = _lsq(pts, 1)
    if c is not None and _is_safe(c, lo, hi):
        return c[0], c[1], 0.0, 0.0, 1
    return 0.0, (pts[-1][1] / hi) if hi > 0 else 0.0, 0.0, 0.0, 1


def _fit_error(c, deg, pts):
    """Sai lech LON NHAT giua mo hinh da khop va cac diem calib (ppm).
    Lon = du lieu calib khong nhat quan (do sai / cam bien bao hoa /
    chua on dinh), KHONG phai loi cua duong. _is_safe() khong bat duoc
    truong hop nay vi duong van co the tang dan ma van khop rat te.
    deg=-1 (tuyen tinh tung doan) luon 0 vi no khop chinh xac moi diem."""
    if deg == -1:
        return 0.0
    err = 0.0
    for ec, ppm in pts:
        d = _poly_at(c, ec) - ppm
        if d < 0.0:
            d = -d
        if d > err:
            err = d
    return err


# Khop san duong mac dinh MOT LAN luc import -> chi con la he so.
_DEF_PTS = [[float(a), float(b)] for a, b in DEFAULT_CALIB]
_DEF_PTS.sort(key=lambda q: q[0])
_DEF_C0, _DEF_C1, _DEF_C2, _DEF_C3, _DEF_DEG = _fit_poly(_DEF_PTS)
_DEF_EC_MIN = _DEF_PTS[0][0] if _DEF_PTS else 0.0
_DEF_EC_MAX = _DEF_PTS[-1][0] if _DEF_PTS else 0.0


class TDSMeter:
    """Doc & hieu chinh cam bien TDS/EC analog."""

    def __init__(self, tds_pin, temperature=25.0, sample_count=30,
                 calib_file="tds_calib.json", max_pts=8,
                 ema_alpha=0.25, ema_jump_v=0.3, sample_gap_us=700):
        self.temperature = temperature       # nhiet do nuoc (C) de bu nhiet
        self.sample_count = sample_count      # so mau moi lan doc
        self.sample_gap_us = sample_gap_us    # gian cach giua cac mau (us)
        self.calib_file = calib_file          # file luu diem calib
        self.max_pts = max_pts                # so diem calib toi da

        # --- Loc lam muot EMA tren dien ap ---
        self.ema_alpha = ema_alpha
        self.ema_jump_v = ema_jump_v
        self._v_ema = None

        # ADC: dai do 0..3.3V (ATTN_11DB)
        self.adc = ADC(Pin(tds_pin, Pin.IN))
        try:
            self.adc.atten(ADC.ATTN_11DB)
        except AttributeError:
            pass

        # He so duong dang dung: ppm = c0 + c1*ec + c2*ec^2 + c3*ec^3
        # deg:  0 = chua co du lieu   1..3 = bac da thuc
        #      -1 = noi suy tuyen tinh tung doan (dung model_pts)
        self.c0 = 0.0
        self.c1 = 0.0
        self.c2 = 0.0
        self.c3 = 0.0
        self.deg = 0
        self.ec_min = 0.0            # bien duoi/tren cua duong dang dung
        self.ec_max = 0.0
        self.model_pts = []          # cac diem hau thuan mo hinh dang dung
        self.using_default = True    # True = dang dung duong mac dinh

        # Diem calib CUA NGUOI DUNG (khong bao gio chua DEFAULT_CALIB),
        # danh sach [ec_tho, ppm], sap tang dan theo ec
        self.pts = []
        self.load_calib()

    # ------------------------------------------------------------
    #  NHIET DO (de bu nhiet)
    # ------------------------------------------------------------
    def set_temperature(self, t):
        """Dat nhiet do nuoc thuc te (C) de bu nhiet ve moc 25C."""
        try:
            self.temperature = float(t)
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------
    #  DOC DIEN AP (V)
    # ------------------------------------------------------------
    def read_voltage(self):
        """Doc dien ap: lay 'sample_count' mau, bo 1 min & 1 max (chong gai)
        roi lay TRUNG BINH -> khu nhieu dot bien."""
        buf = []
        for i in range(self.sample_count):
            buf.append(self._read_uv())
            if i < self.sample_count - 1:
                time.sleep_us(self.sample_gap_us)
        if len(buf) >= 4:
            buf.sort()
            buf = buf[1:-1]              # bo min & max
        uv = sum(buf) / len(buf)         # trung binh
        return uv / 1_000_000.0          # microvolt -> V

    def read_voltage_smooth(self):
        """Doc dien ap (V) da lam muot bang EMA. Neu doi > ema_jump_v
        (nhac ra / nhung vao) thi nhay theo ngay de phan ung nhanh."""
        v = self.read_voltage()
        if self._v_ema is None or abs(v - self._v_ema) > self.ema_jump_v:
            self._v_ema = v
        else:
            a = self.ema_alpha
            self._v_ema = (1.0 - a) * self._v_ema + a * v
        return self._v_ema

    def _read_uv(self):
        # Uu tien read_uv() (da hieu chinh eFuse); neu khong co -> quy doi tho.
        try:
            return self.adc.read_uv()
        except AttributeError:
            try:
                return int(self.adc.read_u16() * 3.3 / 65535 * 1_000_000)
            except AttributeError:
                return int(self.adc.read() * 3.3 / 4095 * 1_000_000)

    # ------------------------------------------------------------
    #  EC_tho (cong thuc DFRobot bac 3, da bu nhiet)
    # ------------------------------------------------------------
    def ec_tho(self, v):
        """Doi dien ap (V) -> EC tho (uS/cm), co bu nhiet ve 25C."""
        comp = 1.0 + 0.02 * (self.temperature - 25.0)
        vv = v / comp
        ec = 133.42 * vv * vv * vv - 255.86 * vv * vv + 857.39 * vv
        return ec if ec > 0 else 0.0

    # ------------------------------------------------------------
    #  QUY DOI EC_tho -> ppm theo duong hoi quy
    # ------------------------------------------------------------
    def _model_at(self, ec):
        """Gia tri THO cua mo hinh dang dung, chua kep dai do va chua
        xu ly phan ngoai khoang calib. deg=-1 -> tuyen tinh tung doan."""
        if self.deg == -1:
            return _pw_at(self.model_pts, ec)
        return self.c0 + self.c1 * ec + self.c2 * ec * ec + self.c3 * ec * ec * ec

    def _slope_hi(self):
        """Do doc tai diem calib cao nhat, dung de ngoai suy len tren."""
        if self.deg == -1:
            p = self.model_pts
            x0, y0 = p[-2]
            x1, y1 = p[-1]
            return (y1 - y0) / (x1 - x0) if x1 > x0 else 0.0
        hi = self.ec_max
        return self.c1 + 2.0 * self.c2 * hi + 3.0 * self.c3 * hi * hi

    def calc_ppm(self, ec):
        """Ap dung duong dang dung (mac dinh HOAC calib cua nguoi dung)."""
        if self.deg == 0:
            # khong co diem calib va DEFAULT_CALIB de trong -> duong K tho
            ppm = ec * K_DEFAULT * 0.5
        else:
            lo = self.ec_min
            hi = self.ec_max
            if ec <= lo:
                # duoi diem thap nhat: noi thang ve goc -> khong khi doc ~0
                # (truong hop 1 diem duy nhat lo==hi cung roi vao day -> qua goc)
                p_lo = self._model_at(lo)
                ppm = p_lo * (ec / lo) if lo > 0.1 else 0.0
            elif ec >= hi:
                # tren diem cao nhat: ngoai suy tuyen tinh theo do doc cuoi
                # (tranh parabol/bac 3 cong nguoc ngoai khoang da calib)
                ppm = self._model_at(hi) + self._slope_hi() * (ec - hi)
            else:
                ppm = self._model_at(ec)
        # kep vao dai do da khai bao
        if ppm < PPM_MIN:
            return PPM_MIN
        if ppm > PPM_MAX:
            return PPM_MAX
        return ppm

    # ------------------------------------------------------------
    #  CAC HAM DOC CHINH
    # ------------------------------------------------------------
    def read_tds(self):
        """Doc TDS (ppm) - da loc nhieu, bu nhiet, ap dung hieu chinh."""
        return round(self.calc_ppm(self.ec_tho(self.read_voltage_smooth())))

    # ------------------------------------------------------------
    #  HOI QUY least-squares (EC_tho -> ppm)
    # ------------------------------------------------------------
    def update_regression(self):
        """Chon duong dang dung:
          - KHONG co diem calib nao -> he so duong MAC DINH (_DEF_*).
          - CO it nhat 1 diem calib -> khop rieng tu cac diem do;
            duong mac dinh MAT TAC DUNG hoan toan."""
        if not self.pts:
            self.c0, self.c1, self.c2, self.c3, self.deg = (
                _DEF_C0, _DEF_C1, _DEF_C2, _DEF_C3, _DEF_DEG)
            self.ec_min, self.ec_max = _DEF_EC_MIN, _DEF_EC_MAX
            self.model_pts = _DEF_PTS          # dung cho deg = -1
            self.using_default = True
            return
        self.c0, self.c1, self.c2, self.c3, self.deg = _fit_poly(self.pts)
        self.ec_min = self.pts[0][0]
        self.ec_max = self.pts[-1][0]
        self.model_pts = self.pts
        self.using_default = False

    # ------------------------------------------------------------
    #  HIEU CHINH (CALIB)
    # ------------------------------------------------------------
    def add_calib_point(self, ec, ppm):
        """Them 1 diem calib (ec_tho, ppm). Ghi de neu da co diem rat gan (theo ec).
        Neu day -> thay diem gan nhat. Sau do sap xep & luu flash."""
        # Nguong gop phai TI LE theo EC: calib lai cung 1 coc o EC cao co the
        # lech 50-60 don vi (do nhiet do / troi cam bien). Neu dung nguong
        # tuyet doi 15 thi se sinh ra 2 diem trung lap chong nhau -> hoi quy
        # bac 2 cong nguoc va sai nang o khoang giua.
        tol = 15.0 if ec * 0.08 < 15.0 else ec * 0.08
        for p in self.pts:
            if abs(p[0] - ec) < tol:
                p[0] = ec
                p[1] = ppm
                self._finish_calib()
                return
        if len(self.pts) >= self.max_pts:
            nearest = min(self.pts, key=lambda q: abs(q[0] - ec))
            nearest[0] = ec
            nearest[1] = ppm
        else:
            self.pts.append([ec, ppm])
        self._finish_calib()

    def add_calib_point_now(self, ppm):
        """Doc EC_tho hien tai va them lam 1 diem calib voi TDS chuan 'ppm'.
        (Nhung dau do vao dung dich chuan roi goi ham nay.)

        IN ra Serial cap [EC_tho -> ppm] vua luu: day la cach DUY NHAT lay
        so EC_tho de dien vao DEFAULT_CALIB, nen dung bo dong print nay."""
        v = self.read_voltage()
        ec = self.ec_tho(v)
        self.add_calib_point(ec, ppm)
        print("TDS calib: V={:.6f} @{:.1f}C -> EC_tho={:.1f} -> {:.1f} ppm ({} diem)".format(
            v, self.temperature, ec, ppm, len(self.pts)))
        return ec

    def _finish_calib(self):
        self.pts.sort(key=lambda q: q[0])
        self.save_calib()
        self.update_regression()     # tu dong tat duong mac dinh

    def reset_calib(self):
        """Xoa toan bo diem calib cua nguoi dung -> quay ve DUONG MAC DINH.
        Ghi [] vao flash nen sau khi tat/mo nguon van la duong mac dinh."""
        self.pts = []
        self.save_calib()
        self.update_regression()

    # ------------------------------------------------------------
    #  LUU / NAP FLASH (file JSON)
    # ------------------------------------------------------------
    def save_calib(self):
        try:
            with open(self.calib_file, "w") as f:
                json.dump(self.pts, f)
        except OSError as e:
            print("!! Loi luu calib TDS:", e)

    def load_calib(self):
        """Nap diem calib CUA NGUOI DUNG tu flash.
        Chua co file / file rong / file loi -> pts = [] -> dung duong MAC DINH.
        DEFAULT_CALIB khong bao gio duoc nap vao pts."""
        try:
            with open(self.calib_file, "r") as f:
                pts = json.load(f)
            self.pts = [[float(a), float(b)] for a, b in pts][: self.max_pts]
            self.pts.sort(key=lambda q: q[0])
        except (OSError, ValueError, TypeError):
            self.pts = []
        self.update_regression()
