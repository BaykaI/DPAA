namespace Dpaa.Core;

/// <summary>
/// Константы аппаратуры: тактирование, решётка, форматы и карта регистров ПЛИС.
/// Всё совпадает с dpaa/hw.py и прошивкой gateware/rtl/ (проверяется тестами по эталонам).
/// </summary>
public static class Hw
{
    // --- тактирование ---
    public const double FClk = 50_000_000;          // системная частота ПЛИС (PLL 25 -> 50 МГц)
    public const int FrameClks = 1024;               // 64 такта BCLK на кадр I2S
    public const double Fs = FClk / FrameClks;       // 48 828.125 Гц
    public const double SoundSpeed = 343.0;          // м/с при ~20 °C

    // --- решётка ---
    public const int NElem = 16;
    public const int NMics = 16;
    public const double Pitch = 0.04;                // шаг 40 мм
    /// <summary>Микрофон стоит на 29.8 мм выше центра динамика (ось z решётки).</summary>
    public static readonly Vec3 MicOffset = new(0, 0, 0.0298);

    // --- ядро дробной задержки ---
    public const int W = 18;                         // разрядность отсчётов и коэффициентов
    public const int Taps = 8;
    public const int TapCenter = 3;                  // минимальная целая задержка
    public const int PhaseBits = 5;
    public const int Phases = 1 << PhaseBits;        // шаг 1/32 отсчёта
    public const int CoefFrac = 16;                  // Q2.16
    public const int Depth = 256;
    public const int MaxDelay = Depth - Taps;
    public const int Unity = 1 << CoefFrac;

    // --- карта регистров (адрес 15 бит, данные 24 бита) ---
    public const int RegId = 0x0000;                 // R: идентификатор
    public const int RegFrames = 0x0001;             // R: счётчик кадров
    public const int RegCtrl = 0x0002;               // W: бит 0 — передача, бит 1 — приём
    public const int RegCommit = 0x0003;             // W: бит 0 — таблицы TX, бит 1 — таблицы RX
    public static readonly int[] GenBase = { 0x0010, 0x0020 };
    public const int RegPeak = 0x0100;               // R: пик микрофона i (0x0100 + i), сброс при чтении
    public const int TxDelay = 0x1000, TxGain = 0x1080;
    public const int RxDelay = 0x2000, RxGain = 0x2080;
    public const int IdValue = 0xDAA001;

    // смещения регистров генератора
    public const int GenMode = 0, GenIncLo = 1, GenIncHi = 2, GenAmp = 3;
    public const int GenRateLo = 4, GenRateHi = 5, GenChirpLen = 6, GenPeriod = 7;
    public const int GenOnLen = 8, GenEnvStep = 9, GenB0 = 10, GenB1 = 11, GenB2 = 12;
    public const int GenA1 = 13, GenA2 = 14, GenFilt = 15;

    public const int TxBeams = 2;
    public const int RxBeams = 2;

    public const byte SyncCmd = 0xA5, SyncRsp = 0x5A;

    /// <summary>Потолок громкости генератора (безопасность слуха и динамиков), доля шкалы.</summary>
    public const double MaxAmp = 0.5;
    /// <summary>Максимальный вес элемента на передачу.</summary>
    public const double TxLevel = 0.5;
}

public enum GenMode { Off = 0, Sine = 1, Noise = 2, Chirp = 3 }
