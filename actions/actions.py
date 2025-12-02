from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict
import csv
import re
from datetime import datetime, timedelta
from rasa_sdk.events import SlotSet, FollowupAction


class ValidateTutoringBookingForm(FormValidationAction):
    """Valida i dati inseriti dall'utente"""
    
    def name(self) -> Text:
        return "validate_tutoring_booking_form"
    
    def validate_materia(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida materia e cerca tutor disponibili"""
        materia = slot_value.lower().strip()
        
        # Leggi CSV tutor
        tutor_trovati = []
        try:
            with open('actions/csv/tutor.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    materie_tutor = [m.strip().lower() for m in row['materie'].split(';')]
                    if materia in materie_tutor:
                        tutor_trovati.append(row)
        except FileNotFoundError:
            dispatcher.utter_message(text="Errore nel caricamento dei dati.")
            return {"materia": None}
        
        if not tutor_trovati:
            dispatcher.utter_message(text=f"Non abbiamo tutor disponibili per {materia}.")
            return {"materia": None}
        
        # Prendi il primo tutor disponibile (o logica più complessa)
        tutor = tutor_trovati[0]
        
        return {
            "materia": materia,
            "tutor_selezionato": f"{tutor['nome']} {tutor['cognome']}",
            "tariffa": tutor['tariffa']
        }
    
    def validate_orario_inizio(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida che lo slot scelto sia valido e calcola fine"""
        # slot_value formato: "2025-11-28_15" (data_ora)
        
        try:
            data_ora = slot_value.split('_')
            data = data_ora[0]
            ora = int(data_ora[1])
            
            return {
                "orario_inizio": str(ora),
                "orario_fine": str(ora + 1),
                "data_lezione": data
            }
        except:
            dispatcher.utter_message(text="Formato orario non valido.")
            return {"orario_inizio": None}
    
    def validate_email_studente(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, slot_value):
            return {"email_studente": slot_value}
        else:
            dispatcher.utter_message(text="Email non valida. Riprova:")
            return {"email_studente": None}


class ActionShowAvailableSlots(Action):
    """Mostra gli slot disponibili con buttons"""
    
    def name(self) -> Text:
        return "action_show_available_slots"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        materia = tracker.get_slot('materia')
        tutor_selezionato = tracker.get_slot('tutor_selezionato')
        
        if not tutor_selezionato:
            dispatcher.utter_message(text="Errore: nessun tutor selezionato.")
            return []
        
        # Leggi dati tutor
        tutor_data = None
        try:
            with open('actions/csv/tutor.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if f"{row['nome']} {row['cognome']}" == tutor_selezionato:
                        tutor_data = row
                        break
        except FileNotFoundError:
            dispatcher.utter_message(text="Errore nel caricamento dati tutor.")
            return []
        
        if not tutor_data:
            dispatcher.utter_message(text="Errore nel caricamento tutor.")
            return []
        
        # Genera slot disponibili (prossimi 7 giorni)
        slot_disponibili = self._genera_slot_disponibili(tutor_data)
        
        # Filtra slot già occupati
        slot_liberi = self._filtra_slot_occupati(slot_disponibili, tutor_selezionato)
        
        if not slot_liberi:
            dispatcher.utter_message(text="Nessuno slot disponibile nei prossimi 7 giorni.")
            return []
        
        # Crea buttons (max 10 slot)
        buttons = []
        for slot in slot_liberi[:10]:
            data, ora = slot.split('_')
            # Formato leggibile: "Lun 28/11 ore 15:00"
            dt = datetime.strptime(data, '%Y-%m-%d')
            giorno_nome = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'][dt.weekday()]
            label = f"{giorno_nome} {dt.strftime('%d/%m')} ore {ora}:00"
            
            buttons.append({
                "title": label,
                "payload": f"/inform_slot{{\"orario_inizio\": \"{slot}\"}}"
            })
        
        dispatcher.utter_message(
            text=f"🎓 Perfetto! Ho trovato {tutor_selezionato}\n💰 Tariffa: {tutor_data['tariffa']}€/ora\n\n📅 Scegli uno slot disponibile:",
            buttons=buttons
        )
        
        return [SlotSet("slot_disponibili", slot_liberi)]
    
    def _genera_slot_disponibili(self, tutor_data: Dict) -> List[str]:
        """Genera tutti gli slot possibili per il tutor nei prossimi 7 giorni"""
        slot_list = []
        
        giorni_settimana = {
            'lunedi': 0, 'martedi': 1, 'mercoledi': 2, 
            'giovedi': 3, 'venerdi': 4, 'sabato': 5, 'domenica': 6
        }
        
        giorni_disponibili = [giorni_settimana[g.strip().lower()] 
                             for g in tutor_data['disponibilita_giorni'].split(';')]
        
        ora_inizio = int(tutor_data['disponibilita_inizio'])
        ora_fine = int(tutor_data['disponibilita_fine'])
        
        # Prossimi 7 giorni
        oggi = datetime.now()
        for i in range(7):
            data = oggi + timedelta(days=i)
            
            # Salta se non è un giorno disponibile
            if data.weekday() not in giorni_disponibili:
                continue
            
            # Genera slot orari (ogni ora)
            for ora in range(ora_inizio, ora_fine):
                slot = f"{data.strftime('%Y-%m-%d')}_{ora}"
                slot_list.append(slot)
        
        return slot_list
    
    def _filtra_slot_occupati(self, slot_list: List[str], tutor_nome: str) -> List[str]:
        """Rimuove gli slot già prenotati"""
        try:
            with open('actions/csv/prenotazioni.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                prenotazioni = list(reader)
        except FileNotFoundError:
            # Se il file non esiste, tutti gli slot sono liberi
            return slot_list
        
        slot_occupati = []
        for p in prenotazioni:
            if f"{p['tutor_nome']} {p['tutor_cognome']}" == tutor_nome:
                slot_occupato = f"{p['data']}_{p['ora_inizio']}"
                slot_occupati.append(slot_occupato)
        
        # Rimuovi slot occupati
        slot_liberi = [s for s in slot_list if s not in slot_occupati]
        
        return slot_liberi


class ActionConfirmBooking(Action):
    """Salva prenotazione e mostra riepilogo"""
    
    def name(self) -> Text:
        return "action_confirm_booking"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Recupera tutti gli slot
        materia = tracker.get_slot('materia')
        tutor_selezionato = tracker.get_slot('tutor_selezionato')
        data_lezione = tracker.get_slot('data_lezione')
        orario_inizio = tracker.get_slot('orario_inizio')
        orario_fine = tracker.get_slot('orario_fine')
        email = tracker.get_slot('email_studente')
        tariffa = tracker.get_slot('tariffa')
        
        # Salva prenotazione nel CSV
        tutor_nome, tutor_cognome = tutor_selezionato.split(' ', 1)
        
        try:
            with open('actions/csv/prenotazioni.csv', 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Se file vuoto, scrivi header
                f.seek(0, 2)  # Va alla fine del file
                if f.tell() == 0:
                    writer.writerow(['tutor_nome', 'tutor_cognome', 'data', 'ora_inizio', 'ora_fine', 'materia', 'email_studente'])
                
                writer.writerow([tutor_nome, tutor_cognome, data_lezione, orario_inizio, orario_fine, materia, email])
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel salvare la prenotazione: {e}")
            return []
        
        # Formatta data leggibile
        dt = datetime.strptime(data_lezione, '%Y-%m-%d')
        data_leggibile = dt.strftime('%d/%m/%Y')
        giorno_nome = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'][dt.weekday()]
        
        # Mostra riepilogo
        riepilogo = (
            f"✅ **PRENOTAZIONE CONFERMATA**\n\n"
            f"📚 Materia: {materia.capitalize()}\n"
            f"👨‍🏫 Tutor: {tutor_selezionato}\n"
            f"📅 Data: {giorno_nome} {data_leggibile}\n"
            f"🕒 Orario: {orario_inizio}:00 - {orario_fine}:00\n"
            f"💰 Tariffa: {tariffa}€\n"
            f"📧 Email: {email}\n\n"
            f"Riceverai una conferma via email! 📨"
        )
        
        dispatcher.utter_message(text=riepilogo)
        
        return []
