namespace Dpaa.Core;

/// <summary>
/// Протокол UART (1 Мбит/с): запрос A5 A1 A0 D2 D1 D0 CHK, CHK = A1^A0^D2^D1^D0^5A;
/// старший бит A1 = 1 — чтение. Ответ на чтение: 5A A1 A0 D2 D1 D0 CHK.
/// </summary>
public static class Protocol
{
    public const int FrameLen = 7;

    public static byte[] EncodeWrite(int addr, long data)
    {
        addr &= 0x7FFF;
        data &= 0xFFFFFF;
        var f = new byte[FrameLen];
        f[0] = Hw.SyncCmd;
        f[1] = (byte)(addr >> 8);
        f[2] = (byte)addr;
        f[3] = (byte)(data >> 16);
        f[4] = (byte)(data >> 8);
        f[5] = (byte)data;
        f[6] = Checksum(f);
        return f;
    }

    public static byte[] EncodeRead(int addr)
    {
        var f = EncodeWrite(addr, 0);
        f[1] |= 0x80;
        f[6] ^= 0x80;
        return f;
    }

    public static (int Addr, int Data) DecodeResponse(ReadOnlySpan<byte> f)
    {
        if (f.Length != FrameLen || f[0] != Hw.SyncRsp)
            throw new FormatException("неверный кадр ответа");
        if (Checksum(f) != f[6])
            throw new FormatException("неверная контрольная сумма ответа");
        return (((f[1] & 0x7F) << 8) | f[2], (f[3] << 16) | (f[4] << 8) | f[5]);
    }

    /// <summary>Ответ так, как его формирует ПЛИС (нужен симулятору и тестам).</summary>
    public static byte[] EncodeResponse(int addr, int data)
    {
        var f = EncodeRead(addr);
        f[0] = Hw.SyncRsp;
        f[3] = (byte)(data >> 16);
        f[4] = (byte)(data >> 8);
        f[5] = (byte)data;
        f[6] = Checksum(f);
        return f;
    }

    static byte Checksum(ReadOnlySpan<byte> f)
    {
        byte c = 0x5A;
        for (int i = 1; i < 6; i++) c ^= f[i];
        return c;
    }

    /// <summary>Разбор кадра запроса (для симулятора): адрес, данные, признак чтения.</summary>
    public static bool TryDecodeRequest(ReadOnlySpan<byte> f, out int addr, out int data, out bool read)
    {
        addr = data = 0;
        read = false;
        if (f.Length != FrameLen || f[0] != Hw.SyncCmd || Checksum(f) != f[6]) return false;
        read = (f[1] & 0x80) != 0;
        addr = ((f[1] & 0x7F) << 8) | f[2];
        data = (f[3] << 16) | (f[4] << 8) | f[5];
        return true;
    }

    public static string Hex(byte[] frame) => Convert.ToHexString(frame).ToLowerInvariant();
}
