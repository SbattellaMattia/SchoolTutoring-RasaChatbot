# actions.py
from typing import Any, Text, Dict, List
from urllib import parse
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk.types import DomainDict
import pandas as pd
from dateutil.parser import parse
from datetime import datetime, date, timedelta
import re
import os

class ActionGreet(Action):
    def name(self) -> Text:
        return "action_greet"

    def run(self, dispatcher, tracker, domain):
        metadata = tracker.latest_message.get("metadata", {}) or {}
        first_name = metadata.get("first_name")
        last_name = metadata.get("last_name")

        # Salva negli slot
        events = []
        if first_name:
            events.append(SlotSet("user_first_name", first_name))
        if last_name:
            events.append(SlotSet("user_last_name", last_name))

        # Messaggio di saluto
        if first_name:
            dispatcher.utter_message(text=f"Ciao {first_name}! 👋 Come posso aiutarti?")
        else:
            dispatcher.utter_message(text="Ciao! 👋 Come posso aiutarti?")

        return events





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
            message = f"Ho trovato questi tutor disponibili per {materia}. Quale preferisci?\n\n"

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
                button_payload = nome_completo
                
                buttons.append({
                    "title": button_title,
                    "payload": button_payload
                })
            
            # Invia messaggio con bottoni
            dispatcher.utter_message(
                text=message,
                buttons=buttons,
                button_type="vertical"
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
            SlotSet("cellulare", None),
            SlotSet("materia", None),
            SlotSet("data", None),
            SlotSet("ora", None),
            SlotSet("available_tutors", None),
            SlotSet("tutors_list", None),
            SlotSet("tutor_scelto", None),
        ]




#=================== VALIDATE FORM ====================

class ValidateTutoringForm(FormValidationAction):
    """Validazione custom per il form di prenotazione con Duckling"""

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

        # Caso: il form è appena partito, non c'è ancora un valore vero
        if slot_value is None or str(slot_value).strip() == "":
            return {"materia": None}
        
        materia_clean = str(slot_value).lower().strip()
        if materia_clean in materie_valide:
            return {"materia": materia_clean}
        else:
            dispatcher.utter_message(
                text="Mi dispiace, al momento offriamo solo ripetizioni di matematica, italiano e chimica."
            )
            return {"materia": None}

    def validate_data(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """Duckling: normalizza time.value in gg/mm/aaaa, rifiuta passato."""
        if slot_value is None or str(slot_value).strip() == "":
            return {"data": None}

        # Cerca Duckling time entities
        latest_message_entities = tracker.latest_message.get("entities", [])
        duckling_entities = [
            e for e in latest_message_entities 
            if e.get("extractor") == "DucklingEntityExtractor" and e.get("entity") == "time"
        ]
        
        if not duckling_entities:
            dispatcher.utter_message(
                text="Non ho capito la data. Riprova con espressioni come '17 gennaio', 'domani', '15 settembre', 'sabato'."
            )
            return {"data": None}

        # Prendi prima entità Duckling
        entity = duckling_entities[0]
        value = entity["value"]

        # La stringa è: 🐤 Duckling time entity value: 2026-03-04T00:00:00.000+01:00
        print(f"🐤 Duckling time entity value: {value}")
        
        normalized = parse(value).date()
            
        # Rifiuta passato
        if normalized < date.today():
            dispatcher.utter_message(text="La data non può essere passata. Riprova.")
            return {"data": None}
            
        # Normalizza in gg/mm/aaaa
        return {"data": normalized.strftime("%d/%m/%Y")}
            
       

    def validate_ora(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida l'ora nel formato XX:XX o XX (es. 15:00, 15)"""

        if slot_value is None or str(slot_value).strip() == "":
            return {"ora": None}

        ora_str = str(slot_value).strip()
        
        # Cerca entità Duckling time
        latest_message_entities = tracker.latest_message.get("entities", [])
        time_entities = [
            e["value"] for e in latest_message_entities 
            if e.get("extractor") == "DucklingHTTPExtractor" and e.get("entity") == "time"
        ]

        if time_entities:
            # Duckling ha estratto un'ora valida
            return {"ora": time_entities[0]}

        # Regex per validare formato XX:XX o XX
        import re
        pattern_ora = r'^\s*(?:(\d{1,2}):?(\d{0,2})\s*)?$'
        match = re.match(pattern_ora, ora_str)

        if match:
            ore = int(match.group(1))
            minuti = int(match.group(2) or 0)
            
            # Validazione logica: 0-23 ore, 0-59 minuti
            if 0 <= ore <= 23 and 0 <= minuti <= 59:
                formato_ora = f"{ore:02d}:{minuti:02d}"
                return {"ora": formato_ora}
        
        dispatcher.utter_message(
            text="Non ho capito l'ora. Si accetta il formato 'hh:mm' o 'hh'. Prova di nuovo."
        )
        return {"ora": None}
    

#======================================================================================

class ActionChooseTutor(Action):
    """Gestisce la scelta del tutor tramite bottoni OPPURE testo naturale"""

    def name(self) -> Text:
        return "action_choose_tutor"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        tutors_list = tracker.get_slot("tutors_list")
        if not tutors_list:
            dispatcher.utter_message(text="Prima devi cercare i tutor disponibili.")
            return []
        
        last_message = tracker.latest_message.get("text", "").lower().strip()
        tutor_text = None
        
        # 1️⃣ METODO BOTTONI: payload = nome completo
        if last_message in [t["nome"] for t in tutors_list]:
            tutor_text = last_message
            print(f"✅ Tutor selezionato da bottone: {tutor_text}")
        
        # 2️⃣ METODO TESTO + ENTITY: cerca tutor_name estratto
        elif tracker.latest_message.get("entities"):
            tutor_entities = tracker.get_latest_entity_values("tutor_name")
            for tutor_entity in tutor_entities:
                for tutor in tutors_list:
                    if tutor["nome"].lower() in tutor_entity.lower() or tutor_entity.lower() in tutor["nome"].lower():
                        tutor_text = tutor["nome"]
                        print(f"✅ Tutor selezionato da entity: {tutor_text}")
                        break
                if tutor_text:
                    break
        
        if tutor_text:
            return [SlotSet("tutor_scelto", tutor_text)]
        else:
            dispatcher.utter_message(
                text="Non ho capito quale tutor hai scelto. Usa i bottoni qui sopra o dimmi il nome/número."
            )
            return []

class ActionSaveBooking(Action):
    def name(self) -> Text:
        return "action_save_booking"

    def run(self, dispatcher, tracker, domain):

        phone_number = tracker.get_slot("cellulare")
        materia = tracker.get_slot("materia")
        data = tracker.get_slot("data")
        ora = tracker.get_slot("ora")
        tutor_scelto = tracker.get_slot("tutor_scelto")

        # Recupera nome/cognome utente dagli slot
        first_name = tracker.get_slot("user_first_name")
        last_name = tracker.get_slot("user_last_name")

        # Path CSV
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        bookings_path = os.path.join(project_root, "actions", "csv", "bookings.csv")

        from datetime import datetime
        booking_data = {
            "richiedente": [str(first_name)],
            "cellulare": [phone_number],
            "materia": [materia],
            "data_prenotazione": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "data_ripetizione": [data],
            "ora_ripetizione": [ora],
            "tutor_scelto": [tutor_scelto],
        }

        df_new = pd.DataFrame(booking_data)

        if os.path.exists(bookings_path):
            df_new.to_csv(bookings_path, mode="a", header=False, index=False)
        else:
            df_new.to_csv(bookings_path, mode="w", header=True, index=False)

        # Conferma personalizzata
        display_name = first_name if first_name else "utente"
        msg = (
            f"Perfetto {display_name}! "
            f"Ho prenotato la lezione di {materia} con {tutor_scelto} in data: {data} alle {ora}."
        )
        dispatcher.utter_message(text=msg)

        return []


class ActionShowBookings(Action):
    """Mostra le prenotazioni dell'utente filtrate per numero di telefono"""

    def name(self) -> Text:
        return "action_show_bookings"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Recupera il numero di telefono
        phone_number = tracker.get_slot("cellulare")

        if not phone_number:
            dispatcher.utter_message("Per favore, fornisci il tuo numero di telefono")
            return []

        # Path al file prenotazioni
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        bookings_path = os.path.join(project_root, "actions", "csv", "bookings.csv")
        
        # Verifica se il file esiste
        if not os.path.exists(bookings_path):
            dispatcher.utter_message(text="Non ci sono prenotazioni salvate.")
            return []
        
        # Leggi il CSV e filtra per numero di telefono
        df = pd.read_csv(bookings_path)

        try:
            user_bookings = df[df['cellulare'].astype(str) == str(phone_number)]
        except Exception as e:
            dispatcher.utter_message(text="Errore nel leggere le prenotazioni.")
            return []
        
        # Controlla se ci sono prenotazioni
        if user_bookings.empty:
            dispatcher.utter_message(text="Non hai ancora prenotazioni.")
            return []
        
        # Formatta il messaggio con le prenotazioni
        message = f"Ecco le tue prenotazioni:\n\n"
        for idx, row in user_bookings.iterrows():
            message += f"📚 {row['materia']}\n"
            message += f"👨‍🏫 Tutor: {row['tutor_scelto']}\n"
            message += f"📅 Data: {row['data_ripetizione']} alle {row['ora_ripetizione']}\n"
            message += f"---\n"
        
        dispatcher.utter_message(text=message)
        
        return []