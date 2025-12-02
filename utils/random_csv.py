import csv
import os

def crea_csv_iniziali():
    """Crea CSV iniziali con dati di esempio"""
    
    # Crea directory
    os.makedirs('actions/csv', exist_ok=True)
    
    # Tutor
    with open('actions/csv/tutor.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['nome', 'cognome', 'materie', 'tariffa', 'disponibilita_giorni', 'disponibilita_inizio', 'disponibilita_fine'])
        writer.writerow(['Marco', 'Rossi', 'matematica;fisica', '25', 'lunedi;martedi;mercoledi;giovedi;venerdi', '10', '19'])
        writer.writerow(['Laura', 'Bianchi', 'inglese;italiano', '20', 'lunedi;mercoledi;venerdi', '14', '20'])
        writer.writerow(['Giuseppe', 'Verdi', 'chimica;fisica', '28', 'martedi;giovedi', '16', '19'])
    
    # Prenotazioni (vuoto)
    with open('actions/csv/prenotazioni.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['tutor_nome', 'tutor_cognome', 'data', 'ora_inizio', 'ora_fine', 'materia', 'email_studente'])
    
    print("✅ CSV creati!")

if __name__ == "__main__":
    crea_csv_iniziali()