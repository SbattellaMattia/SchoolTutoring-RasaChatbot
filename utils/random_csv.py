#!/usr/bin/env python3
import csv
import random
import argparse
from typing import Tuple

NOMI = [
    "Mario", "Laura", "Giuseppe", "Anna", "Paolo", "Francesca", "Marco", "Luca",
    "Sara", "Giulia", "Matteo", "Alessia", "Davide", "Chiara", "Simone", "Elena"
]

COGNOMI = [
    "Rossi", "Bianchi", "Verdi", "Neri", "Russo", "Ferrari", "Esposito", "Romano",
    "Colombo", "Ricci", "Marino", "Greco", "Bruno", "Gallo", "Conti", "De Luca"
]

MATERIE = ["matematica", "italiano", "chimica", "fisica", "inglese", "storia", "informatica"]

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]

def minutes_to_hhmm(m: int) -> str:
    h = m // 60
    mm = m % 60
    return f"{h:02d}:{mm:02d}"

def random_time_range() -> str:
    # a volte genera "00:00-24:00" (full day) come nel tuo esempio
    if random.random() < 0.05:
        return "00:00-24:00"

    start = random.randrange(0, 24 * 60, 30)  # step 30 minuti
    duration = random.choice([120, 180, 240, 300, 360, 480])  # 2h..8h
    end = min(start + duration, 24 * 60)

    # Evita intervalli vuoti
    if end <= start:
        end = min(start + 120, 24 * 60)

    return f"{minutes_to_hhmm(start)}-{minutes_to_hhmm(end)}"

def random_row() -> dict:
    nome = random.choice(NOMI)
    cognome = random.choice(COGNOMI)
    materia = random.choice(MATERIE)
    costo_ora = random.randint(12, 30)
    disponibilita_giorno = random.choice(GIORNI)
    disponibilita_ora = random_time_range()

    return {
        "nome": nome,
        "cognome": cognome,
        "materia": materia,
        "costo_ora": costo_ora,
        "disponibilita_giorno": disponibilita_giorno,
        "disponibilita_ora": disponibilita_ora,
    }

def main():
    parser = argparse.ArgumentParser(description="Genera un CSV tutor.csv casuale.")
    parser.add_argument("rows", type=int, help="Numero di righe da generare (es. 100).")
    parser.add_argument("--out", default="tutor.csv", help="Path file output (default: tutor.csv).")
    parser.add_argument("--seed", type=int, default=None, help="Seed per rendere la generazione ripetibile.")
    args = parser.parse_args()

    if args.rows <= 0:
        raise SystemExit("rows deve essere > 0")

    if args.seed is not None:
        random.seed(args.seed)

    fieldnames = [
        "nome", "cognome", "materia", "costo_ora", "disponibilita_giorno", "disponibilita_ora"
    ]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for _ in range(args.rows):
            writer.writerow(random_row())

    print(f"Creato {args.out} con {args.rows} righe.")

if __name__ == "__main__":
    main()
