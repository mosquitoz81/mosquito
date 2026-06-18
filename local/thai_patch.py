#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
thai_patch.py - Translate Indonesian game text to Thai/English.

Scans game configuration and resource files, replaces Indonesian text
with Thai or English equivalents. Creates backups before modifying.

Usage:
  python thai_patch.py --game-root ../work/Pockie --mode scan     # preview changes
  python thai_patch.py --game-root ../work/Pockie --mode apply    # apply changes
  python thai_patch.py --game-root ../work/Pockie --mode revert   # revert from backup

Supports: .ini, .properties, .xml, .txt, .html, .js, .json, .cfg files
"""

import os
import sys
import shutil
import re
import argparse
import time
import json
import glob

# ---------------------------------------------------------------------------
# Indonesian -> Thai / English translation dictionary
# Game UI, menus, messages, system text
# ---------------------------------------------------------------------------
TRANSLATIONS = {
    # --- Common UI ---
    "Masuk": "Login",  # เข้าสู่ระบบ
    "Keluar": "Logout",  # ออกจากระบบ
    "Daftar": "Register",  # สมัคร
    "Mulai": "Start",  # เริ่ม
    "Bermain": "Play",  # เล่น
    "Kembali": "Back",  # กลับ
    "Batal": "Cancel",  # ยกเลิก
    "Simpan": "Save",  # บันทึก
    "Hapus": "Delete",  # ลบ
    "Tutup": "Close",  # ปิด
    "Buka": "Open",  # เปิด
    "Ya": "Yes",  # ใช่
    "Tidak": "No",  # ไม่
    "Lanjut": "Continue",  # ดำเนินการต่อ
    "Selesai": "Done",  # เสร็จ
    "Kirim": "Send",  # ส่ง
    "Terima": "Accept",  # รับ
    "Tolak": "Reject",  # ปฏิเสธ
    "Cari": "Search",  # ค้นหา
    "Pilih": "Select",  # เลือก
    "Ubah": "Change",  # เปลี่ยน
    "Konfirmasi": "Confirm",  # ยืนยัน
    "Bantuan": "Help",  # ช่วยเหลือ
    "Pengaturan": "Settings",  # ตั้งค่า

    # --- Game terms ---
    "Pertarungan": "Battle",  # การต่อสู้
    "Misi": "Mission",  # ภารกิจ
    "Petualangan": "Adventure",  # การผจญภัย
    "Toko": "Shop",  # ร้านค้า
    "Tas": "Bag",  # กระเป๋า
    "Senjata": "Weapon",  # อาวุธ
    "Baju": "Armor",  # เกราะ
    "Pelindung": "Shield",  # โล่
    "Cincin": "Ring",  # แหวน
    "Kalung": "Necklace",  # สร้อยคอ
    "Helm": "Helmet",  # หมวก
    "Sepatu": "Shoes",  # รองเท้า
    "Ramuan": "Potion",  # ยา
    "Gulungan": "Scroll",  # ม้วนกระดาษ
    "Keterampilan": "Skill",  # ทักษะ
    "Jurus": "Jutsu",  # จุทสึ
    "Serangan": "Attack",  # โจมตี
    "Pertahanan": "Defense",  # ป้องกัน
    "Kecepatan": "Speed",  # ความเร็ว
    "Kekuatan": "Strength",  # พลัง
    "Kesehatan": "Health",  # สุขภาพ
    "Chakra": "Chakra",  # จักระ
    "Pengalaman": "Experience",  # ประสบการณ์
    "Tingkat": "Level",  # ระดับ
    "Emas": "Gold",  # ทอง
    "Koin": "Coin",  # เหรียญ
    "Berlian": "Diamond",  # เพชร
    "Perak": "Silver",  # เงิน
    "Teman": "Friend",  # เพื่อน
    "Clan": "Clan",  # แคลน
    "Guild": "Guild",  # กิลด์
    "Peringkat": "Ranking",  # อันดับ
    "Arena": "Arena",  # สนามประลอง
    "Ruang bawah tanah": "Dungeon",  # ดันเจี้ยน
    "Bos": "Boss",  # บอส
    "Pahlawan": "Hero",  # ฮีโร่
    "Ninja": "Ninja",  # นินจา
    "Desa": "Village",  # หมู่บ้าน

    # --- System messages ---
    "Koneksi terputus": "Connection lost",
    "Sedang memuat": "Loading",
    "Mohon tunggu": "Please wait",
    "Koneksi gagal": "Connection failed",
    "Server sedang pemeliharaan": "Server maintenance",
    "Kata sandi salah": "Wrong password",
    "Akun tidak ditemukan": "Account not found",
    "Berhasil": "Success",
    "Gagal": "Failed",
    "Tidak cukup": "Not enough",
    "Penuh": "Full",
    "Kosong": "Empty",
    "Tersedia": "Available",
    "Tidak tersedia": "Unavailable",
    "Undangan": "Invitation",
    "Pesan": "Message",
    "Pemberitahuan": "Notification",
    "Hadiah": "Reward",
    "Selamat": "Congratulations",

    # --- Server/Login page ---
    "Nama pengguna": "Username",
    "Kata sandi": "Password",
    "Ingat saya": "Remember me",
    "Lupa kata sandi": "Forgot password",
    "Buat akun baru": "Create new account",
    "Pilih server": "Select server",
    "Server penuh": "Server full",
    "Server baru": "New server",
    "Pemeliharaan": "Maintenance",
    "Online": "Online",
    "Offline": "Offline",
}

# File extensions to scan
SCAN_EXTENSIONS = {
    ".ini", ".properties", ".xml", ".txt", ".html", ".htm",
    ".js", ".json", ".cfg", ".conf", ".csv", ".lang",
}

# Directories to skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", "backupdb",
    "movieclip", "sound", "music",
}

BACKUP_SUFFIX = ".bak_indo"

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------
def scan_file(filepath):
    """Scan a file for Indonesian text. Returns list of (line_no, original, replacement)."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []

    matches = []
    for i, line in enumerate(lines, 1):
        for indo, eng in TRANSLATIONS.items():
            if indo in line:
                matches.append((i, indo, eng, line.strip()))
    return matches


def apply_file(filepath, dry_run=False):
    """Apply translations to a file. Returns count of replacements."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return 0

    new_content = content
    count = 0
    for indo, eng in TRANSLATIONS.items():
        if indo in new_content:
            occurrences = new_content.count(indo)
            new_content = new_content.replace(indo, eng)
            count += occurrences

    if count > 0 and not dry_run:
        backup = filepath + BACKUP_SUFFIX
        if not os.path.exists(backup):
            shutil.copy2(filepath, backup)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return count


def revert_file(filepath):
    """Revert a file from its backup."""
    backup = filepath + BACKUP_SUFFIX
    if os.path.exists(backup):
        shutil.copy2(backup, filepath)
        os.remove(backup)
        return True
    return False


def walk_game_files(game_root):
    """Yield all translatable files in the game directory."""
    for root, dirs, files in os.walk(game_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SCAN_EXTENSIONS:
                yield os.path.join(root, f)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pockie Ninja Indonesian -> English/Thai translator")
    parser.add_argument("--game-root", required=True, help="Path to work/Pockie directory")
    parser.add_argument("--mode", choices=["scan", "apply", "revert"], default="scan",
                        help="scan=preview, apply=patch files, revert=restore backups")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    game_root = os.path.abspath(args.game_root)
    if not os.path.isdir(game_root):
        print(f"ERROR: Game root not found: {game_root}")
        sys.exit(1)

    print(f"Mode: {args.mode}")
    print(f"Game root: {game_root}")
    print(f"Translations: {len(TRANSLATIONS)} entries")
    print()

    if args.mode == "scan":
        total_files = 0
        total_matches = 0
        for fpath in walk_game_files(game_root):
            matches = scan_file(fpath)
            if matches:
                total_files += 1
                total_matches += len(matches)
                rel = os.path.relpath(fpath, game_root)
                print(f"  {rel}: {len(matches)} match(es)")
                if args.verbose:
                    for line_no, indo, eng, context in matches:
                        print(f"    L{line_no}: '{indo}' -> '{eng}'")
                        print(f"           {context[:80]}")
        print()
        print(f"Summary: {total_matches} matches in {total_files} files")
        if total_matches > 0:
            print("Run with --mode apply to patch these files (backups will be created)")

    elif args.mode == "apply":
        total_files = 0
        total_replacements = 0
        for fpath in walk_game_files(game_root):
            count = apply_file(fpath)
            if count > 0:
                total_files += 1
                total_replacements += count
                rel = os.path.relpath(fpath, game_root)
                print(f"  Patched {rel}: {count} replacement(s)")
        print()
        print(f"Summary: {total_replacements} replacements in {total_files} files")
        print("Backups saved with .bak_indo extension")
        print("Run with --mode revert to undo all changes")

    elif args.mode == "revert":
        reverted = 0
        for fpath in walk_game_files(game_root):
            backup = fpath + BACKUP_SUFFIX
            if os.path.exists(backup):
                revert_file(fpath)
                rel = os.path.relpath(fpath, game_root)
                print(f"  Reverted {rel}")
                reverted += 1
        # Also check for backups of files not in current walk
        for root, dirs, files in os.walk(game_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith(BACKUP_SUFFIX):
                    original = os.path.join(root, f[:-len(BACKUP_SUFFIX)])
                    if not os.path.exists(original + BACKUP_SUFFIX):
                        shutil.copy2(os.path.join(root, f), original)
                        os.remove(os.path.join(root, f))
                        reverted += 1
        print()
        print(f"Summary: Reverted {reverted} files")


if __name__ == "__main__":
    main()
