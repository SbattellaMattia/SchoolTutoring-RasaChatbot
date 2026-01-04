# actions.py
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk.types import DomainDict
import pandas as pd
from datetime import datetime, timedelta
import os


class ActionSearchTutors(Action):
    """Action per cercare tutor disponibili nel database CSV"""

    def name(self) -> Text:
        return "action_search_tutors"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Recupera gli slot
        materia = tracker.get_slot("materia")
        data = tracker.get_slot("data")
        ora = tracker.get_slot("ora")
    
        # Ottieni la directory dove si trova actions.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Vai alla cartella parent (la root del progetto)
        project_root = os.path.dirname(current_dir)
        
        # Costruisci il path al CSV
        csv_path = os.path.join(project_root, "actions", "csv", "tutor.csv")
        
        # DEBUG
        print(f"🔍 Cercando CSV in: {csv_path}")
        print(f"📁 File esiste? {os.path.exists(csv_path)}")

        if not os.path.exists(csv_path):
            dispatcher.utter_message(text="Errore: database tutor non trovato.")
            return [SlotSet("available_tutors", False)]

        try:
            # Carica il database
            df = pd.read_csv(csv_path)

            # Filtra per materia
            tutors = df[df['materia'].str.lower() == materia.lower()]

            if tutors.empty:
                dispatcher.utter_message(
                    text=f"Mi dispiace, non ci sono tutor disponibili per {materia}."
                )
                return [
                    SlotSet("available_tutors", False),     
                    SlotSet("tutors_list", None)         
                ]

            # TODO: Qui dovresti implementare logica più sofisticata per 
            # verificare disponibilità in base a data/ora
            # Per ora mostriamo tutti i tutor della materia

            # Prepara il messaggio con i tutor trovati
            message = f"Ho trovato questi tutor disponibili per {materia}:\nQuale preferisci?\n\n"

            buttons = []
            tutors_list = []
            
            for idx, tutor in tutors.iterrows():
                nome_completo = f"{tutor['nome']} {tutor['cognome']}"
                costo = tutor['costo_ora']
                
                tutors_list.append({
                    'nome': nome_completo,
                    'costo': costo
                })
                
                # Crea bottone per ogni tutor
                button_title = f"👤 {nome_completo} - {costo}€/ora"
                button_payload = f"/choose_tutor{{\"tutor_name\":\"{nome_completo}\"}}"
                
                buttons.append({
                    "title": button_title,
                    "payload": button_payload
                })
            
            # Invia messaggio con bottoni
            dispatcher.utter_message(
                text=message,
                buttons=buttons
            )

            return [
                SlotSet("available_tutors", True),      # ← Per il flusso conversazionale
                SlotSet("tutors_list", tutors_list)     # ← Per memorizzare i dati
            ]

        except Exception as e:
            dispatcher.utter_message(
                text=f"Si è verificato un errore durante la ricerca: {str(e)}"
            )
            return [
                SlotSet("available_tutors", False),
                SlotSet("tutors_list", None)
            ]


class ActionResetSlots(Action):
    """Action per resettare gli slot e ricominciare"""

    def name(self) -> Text:
        return "action_reset_slots"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        return [
            SlotSet("materia", None),
            SlotSet("data", None),
            SlotSet("ora", None),
            SlotSet("available_tutors", None),
            SlotSet("tutors_list", None),
            SlotSet("tutor_scelto", None),
        ]


class ValidateTutoringForm(FormValidationAction):
    """Validazione custom per il form di prenotazione"""

    def name(self) -> Text:
        return "validate_tutoring_form"

    def validate_materia(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida che la materia sia tra quelle disponibili"""

        materie_valide = ["matematica", "italiano", "chimica"]

        if slot_value and slot_value.lower() in materie_valide:
            return {"materia": slot_value.lower()}
        else:
            dispatcher.utter_message(
                text=f"Mi dispiace, al momento offriamo solo ripetizioni di matematica, italiano e chimica."
            )
            return {"materia": None}

    def validate_data(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida la data inserita"""

        # Qui potresti aggiungere logica per parsare e validare la data
        # Per ora accettiamo qualsiasi valore
        if slot_value:
            return {"data": slot_value}
        else:
            return {"data": None}

    def validate_ora(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida l'ora inserita"""

        # Qui potresti aggiungere logica per validare il formato dell'ora
        # Per ora accettiamo qualsiasi valore
        if slot_value:
            return {"ora": slot_value}
        else:
            return {"ora": None}

class ActionConfirmBooking(Action):
    """Action per confermare la prenotazione"""

    def name(self) -> Text:
        return "action_confirm_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Recupera gli slot
        materia = tracker.get_slot("materia")
        data = tracker.get_slot("data")
        ora = tracker.get_slot("ora")
        tutors_list = tracker.get_slot("tutors_list")
        
        # Gestisci la scelta del tutor
        last_message = tracker.latest_message.get('text', '').lower()
        
        tutor_scelto = None
        
        if tutors_list:
            if "primo" in last_message or "1" in last_message:
                tutor_scelto = tutors_list[0]['nome']
            elif "secondo" in last_message or "2" in last_message:
                tutor_scelto = tutors_list[1]['nome'] if len(tutors_list) > 1 else tutors_list[0]['nome']
            elif "terzo" in last_message or "3" in last_message:
                tutor_scelto = tutors_list[2]['nome'] if len(tutors_list) > 2 else tutors_list[0]['nome']
            else:
                # Cerca il nome del tutor nel messaggio
                for tutor in tutors_list:
                    if tutor['nome'].lower() in last_message:
                        tutor_scelto = tutor['nome']
                        break
                
                # Se non trovato, prendi il primo
                if not tutor_scelto:
                    tutor_scelto = tutors_list[0]['nome']
        
        # Messaggio di conferma
        message = f"Perfetto! Ho prenotato la ripetizione di {materia} con {tutor_scelto} per il {data} alle {ora}."
        
        dispatcher.utter_message(text=message)
        
        return [SlotSet("tutor_scelto", tutor_scelto)]
    

class ActionConfirmTutor(Action):
    """Gestisce la scelta del tutor e salva la prenotazione"""

    def name(self) -> Text:
        return "action_confirm_tutor"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Estrai il nome del tutor dall'entity
        tutor_name = next(tracker.get_latest_entity_values("tutor_name"), None)
        
        if tutor_name:
            # Salva la prenotazione
            return [SlotSet("tutor_scelto", tutor_name)]
        else:
            dispatcher.utter_message(
                text="Non ho capito quale tutor hai scelto. Riprova."
            )
            return []
        

class ActionSaveBooking(Action):
    """Salva la prenotazione nel file bookings.csv"""

    def name(self) -> Text:
        return "action_save_booking"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Recupera i dati della prenotazione
        materia = tracker.get_slot("materia")
        data = tracker.get_slot("data")
        ora = tracker.get_slot("ora")
        tutor_scelto = tracker.get_slot("tutor_scelto")
        
        # Path al file prenotazioni
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        bookings_path = os.path.join(project_root, "csv", "bookings.csv")
        
        # Crea i dati della prenotazione
        from datetime import datetime
        booking_data = {
            'data_prenotazione': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            'materia': [materia],
            'data_ripetizione': [data],
            'ora_ripetizione': [ora],
            'tutor': [tutor_scelto],
            'user_id': [tracker.sender_id]
        }
        
        df_new = pd.DataFrame(booking_data)
        
        # Salva nel CSV (append se esiste, crea se non esiste)
        if os.path.exists(bookings_path):
            df_new.to_csv(bookings_path, mode='a', header=False, index=False)
        else:
            df_new.to_csv(bookings_path, mode='w', header=True, index=False)
        
        print(f"✅ Prenotazione salvata: {tutor_scelto} - {materia} - {data} {ora}")
        
        # Messaggio di conferma
        message = f"Perfetto! Ho prenotato la ripetizione di {materia} con {tutor_scelto} per il {data} alle {ora}."
        dispatcher.utter_message(text=message)
        
        return []