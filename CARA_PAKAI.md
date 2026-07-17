# Cara pakai known-path (bahasa sederhana)

## Ini aplikasi apa?

**Masalah:** AI sering salah pilih tabel data karena namanya mirip  
(contoh: `finance.revenue_old` vs `finance.revenue_canonical`).

**known-path** membandingkan 3 cara:

| Tombol | Arti | Yang diharapkan |
|--------|------|------------------|
| ① Cara bodoh | Cari pakai nama saja | Bisa pilih tabel **jebakan** |
| ② Known-path | Ikuti daftar resmi + cek aman | Pilih tabel **benar** |
| ③ Data rusak | Simulasi tabel resmi bermasalah | **Berhenti**, tidak nebak |

---

## Cara jalanin (3 langkah)

### 1. Buka terminal di folder project

```bash
cd known-path
export PYTHONPATH=src
```

### 2. Nyalakan web

```bash
python -m known_path.webapp --port 8090
```

### 3. Buka browser

```
http://127.0.0.1:8090
```

Lalu klik tombol **① → ② → ③** berurutan.

---

## Lihat yang mana di layar?

1. **Kotak hasil berwarna** di bawah tombol  
   - Hijau = benar  
   - Merah muda = salah / dihentikan  
2. **Peta tabel** — mana yang NYALA  
3. **SQL** — query yang dihasilkan  
4. **Batang perbandingan** — berapa kali ambil detail catalog  
5. **Terminal** (opsional) — log teknis, boleh diabaikan

---

## Tanpa web (CLI)

```bash
export PYTHONPATH=src
python -m known_path.cli demo
```

---

## File penting di repo

| Path | Isi |
|------|-----|
| `src/known_path/` | Kode program |
| `datasets/demo-finance/` | Data demo (catalog + CSV) |
| `cards/` | “Daftar resmi” job |
| `examples/` | SQL hasil run |
| `CARA_PAKAI.md` | File ini |

---

## Tidak perlu

- Tidak wajib paham seluruh kode dulu  
- Tidak wajib DataHub online untuk demo lokal  
- Tidak wajib isi terminal agent  

Cukup: **nyalakan web → klik 3 tombol → baca kotak hasil**.
