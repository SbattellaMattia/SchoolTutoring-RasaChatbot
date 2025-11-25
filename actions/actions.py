from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict
import csv
import re
from datetime import datetime


class ValidateTutoringBookingForm(FormValidationAction):
    """Valida i dati del form prenotazione ripetizioni"""
    
    def name(self) -> Text:
        return "validate_tutoring_booking_form"
    
    def validate_materia(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida la materia"""
        materie_valide = [
            "matematica", "fisica", "chimica", "inglese", 
            "italiano", "latino", "greco", "informatica", "economia"
        ]
        
        materia = slot_value.lower() if slot_value else None
        
        if materia in materie_valide:
            return {"materia": materia}
        else:
            dispatcher.utter_message(
                text=f"Mi dispiace, non offriamo ripetizioni di {slot_value}. "
                     f"Le materie disponibili sono: {', '.join(materie_valide)}"
            )
            return {"materia": None}
    
    def validate_livello(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida il livello scolastico"""
        livelli_validi = ["elementari", "medie", "superiori", "università", "universita"]
        
        livello = slot_value.lower() if slot_value else None
        
        # Normalizza università/universita
        if livello in ["università", "universita", "uni"]:
            livello = "università"
        
        if livello in livelli_validi:
            return {"livello": livello}
        else:
            dispatcher.utter_message(
                text="Per favore specifica: elementari, medie, superiori o università"
            )
            return {"livello": None}
    
    def validate_modalita(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida la modalità (presenza/online)"""
        modalita = slot_value.lower() if slot_value else None
        
        if "onl" in modalita or "remot" in modalita or "distanz" in modalita:
            return {"modalita": "online"}
        elif "pres" in modalita or "persona" in modalita or "casa" in modalita:
            return {"modalita": "presenza"}
        else:
            dispatcher.utter_message(
                text="Preferisci lezioni in presenza o online?"
            )
            return {"modalita": None}
    
    def validate_durata(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida la durata della lezione"""
        durate_valide = ["1 ora", "1.5 ore", "2 ore"]
        
        # Estrai numero dalla stringa
        if "1.5" in slot_value or "90" in slot_value:
            return {"durata": "1.5 ore"}
        elif "2" in slot_value or "due" in slot_value:
            return {"durata": "2 ore"}
        elif "1" in slot_value or "un" in slot_value:
            return {"durata": "1 ora"}
        else:
            dispatcher.utter_message(
                text="Scegli tra: 1 ora, 1.5 ore o 2 ore"
            )
            return {"durata": None}
    
    def validate_email_studente(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida l'email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, slot_value):
            return {"email_studente": slot_value}
        else:
            dispatcher.utter_message(
                text="Email non valida. Inserisci un'email corretta (es. nome@esempio.com)"
            )
            return {"email_studente": None}


class ActionAssignTutor(Action):
    """Assegna un tutor disponibile in base a materia e livello"""
    
    def name(self) -> Text:
        return "action_assign_tutor"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Recupera slot
        materia = tracker.get_slot('materia')
        livello = tracker.get_slot('livello')
        modalita = tracker.get_slot('modalita')
        
        # Cerca tutor nel CSV
        tutor_assegnato = None
        try:
            with open('actions/csv/tutor.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Verifica materia
                    materie_tutor = row['materie'].split(',')
                    materie_tutor = [m.strip().lower() for m in materie_tutor]
                    
                    if materia not in materie_tutor:
                        continue
                    
                    # Verifica livello
                    if livello not in row['livello'].lower():
                        continue
                    
                    # Verifica modalità
                    if modalita not in row['modalita'].lower():
                        continue
                    
                    # Tutor trovato!
                    tutor_assegnato = f"{row['nome']} {row['cognome']}"
                    tariffa = row['tariffa']
                    break
            
            if tutor_assegnato:
                dispatcher.utter_message(
                    text=f"👨‍🏫 Ti ho assegnato il tutor: {tutor_assegnato}\n"
                         f"💰 Tariffa: {tariffa}€/ora"
                )
            else:
                dispatcher.utter_message(
                    text="⚠️ Al momento non abbiamo tutor disponibili per questa combinazione. "
                         "Ti contatteremo appena possibile!"
                )
                tutor_assegnato = "In attesa di assegnazione"
        
        except FileNotFoundError:
            dispatcher.utter_message(
                text="Errore nel sistema. Ti contatteremo via email!"
            )
            tutor_assegnato = "Sistema in manutenzione"
        
        return [SlotSet("tutor_assegnato", tutor_assegnato)]


class ActionShowBookingSummary(Action):
    """Mostra riepilogo prenotazione"""
    
    def name(self) -> Text:
        return "action_show_booking_summary"
    
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        # Recupera tutti gli slot
        materia = tracker.get_slot('materia')
        livello = tracker.get_slot('livello')
        modalita = tracker.get_slot('modalita')
        data_lezione = tracker.get_slot('data_lezione')
        orario_lezione = tracker.get_slot('orario_lezione')
        durata = tracker.get_slot('durata')
        nome_studente = tracker.get_slot('nome_studente')
        email_studente = tracker.get_slot('email_studente')
        tutor_assegnato = tracker.get_slot('tutor_assegnato')
        
        # Calcola prezzo
        prezzo = self._calcola_prezzo(livello, durata)
        
        # Crea messaggio riepilogo
        summary = (
            f"📋 **Riepilogo Prenotazione**\n\n"
            f"👤 Studente: {nome_studente}\n"
            f"📧 Email: {email_studente}\n"
            f"📚 Materia: {materia.capitalize()}\n"
            f"🎓 Livello: {livello.capitalize()}\n"
            f"📍 Modalità: {modalita.capitalize()}\n"
            f"📅 Data: {data_lezione}\n"
            f"🕒 Orario: {orario_lezione}\n"
            f"⏱️ Durata: {durata}\n"
            f"👨‍🏫 Tutor: {tutor_assegnato}\n"
            f"💰 Prezzo: {prezzo}€\n\n"
            f"✅ Riceverai conferma via email!"
        )
        
        dispatcher.utter_message(text=summary)
        
        return []
    
    def _calcola_prezzo(self, livello: str, durata: str) -> float:
        """Calcola il prezzo in base a livello e durata"""
        # Tariffe base per ora
        tariffe = {
            "elementari": 15,
            "medie": 15,
            "superiori": 20,
            "università": 25
        }
        
        tariffa_oraria = tariffe.get(livello, 20)
        
        # Estrai ore dalla durata
        if "1.5" in durata:
            ore = 1.5
        elif "2" in durata:
            ore = 2
        else:
            ore = 1
        
        return tariffa_oraria * ore
