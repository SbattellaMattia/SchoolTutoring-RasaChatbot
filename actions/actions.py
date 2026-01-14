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







#=================== VALIDATE FORM ====================

class ValidateTutoringForm(FormValidationAction):
    """Validazione custom per il form di prenotazione con Duckling"""

    def name(self) -> Text:
        return "validate_tutoring_form"
    
    def validate_cellulare(self, slot_value, dispatcher, tracker, domain):
        if slot_value is None:
            return {"cellulare": None}

        latest_message_entities = tracker.latest_message.get("entities", [])
        phone_entities = [
            e for e in latest_message_entities 
            if e.get("extractor") == "DucklingEntityExtractor" and e.get("entity") == "phone-number"
        ]

        if phone_entities:
            phone_value = phone_entities[0].get("value")
            print(f"📞 Phone: {phone_value}")
            return {"cellulare": phone_value}
    
        dispatcher.utter_message("Numero non riconosciuto. Inserisci un numero italiano valido (10 cifre): 3451234567 o +393451234567.")
        return {"cellulare": None}


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
            
       

 

    def validate_ora(self, slot_value, dispatcher, tracker, domain):
        """Duckling: estrai ora da time.value -> HH:MM"""
        if slot_value is None or str(slot_value).strip() == "":
            return {"ora": None}

        latest_message_entities = tracker.latest_message.get("entities", [])
        duckling_entities = [
            e for e in latest_message_entities 
            if e.get("extractor") == "DucklingEntityExtractor" and e.get("entity") == "time"]
        
        if not duckling_entities:
            dispatcher.utter_message(
                text="Non ho capito l'ora. Riprova con '15', 'alle 17', '17:30'."
            )
            return {"ora": None}

        entity = duckling_entities[0]
        value = entity["value"]
        print(f"🐤 Duckling time entity value: {value}")
        
        dt = parse(value)
        ora = dt.strftime("%H:%M") 
        
        return {"ora": ora}

    

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
                text="Non ho capito quale tutor hai scelto. Usa i bottoni qui sopra o dimmi il nome."
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
        message = f"*Ecco le tue prenotazioni:*\n\n"
        for idx, row in user_bookings.iterrows():
            message += f"📚 {row['materia']}\n"
            message += f"👨‍🏫 Tutor: {row['tutor_scelto']}\n"
            message += f"📅 Data: {row['data_ripetizione']} alle {row['ora_ripetizione']}\n"
            message += f"\n\n"
        
        # Invia il messaggio 
        dispatcher.utter_message(
            json_message={
                "text": message,
                "parse_mode": "Markdown"
            }
        )
        
        return []
    


    #===========================================================================
    #                           TUTOR ACTIONS
    #===========================================================================

    class ActionShowSubjects(Action):
        def name(self) -> Text:
            return "action_show_subjects"

        def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:
            
            # Path al file prenotazioni
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            tutor_path = os.path.join(project_root, "actions", "csv", "tutor.csv")
            
            try:
                # Leggi il CSV
                df = pd.read_csv(tutor_path)
                
                # Ottieni le materie uniche
                materie = df['materia'].unique().tolist()
                
                # Crea i bottoni per Telegram
                buttons = []
                for materia in materie:
                    buttons.append({
                        "title": materia.capitalize(),
                        "payload": f"/seleziona_materia{{\"materia\":\"{materia}\"}}"
                    })
                
                # Invia il messaggio con i bottoni
                dispatcher.utter_message(
                    text="📚 Seleziona la materia per vedere i tutor disponibili:",
                    buttons=buttons,
                    button_type="vertical"
                )
                
            except Exception as e:
                dispatcher.utter_message(
                    text=f"Mi dispiace, si è verificato un errore nel caricare le materie."
                )
                print(f"Errore: {e}")
            
            return []


    class ActionShowTutorPerSubject(Action):
        def name(self) -> Text:
            return "action_show_tutor_per_subject"

        def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:
            
            # Ottieni la materia dallo slot
            materia = tracker.get_slot("materia")
            
            if not materia:
                dispatcher.utter_message(
                    text="Non ho capito quale materia ti interessa. Riprova."
                )
                return []
            
            # Path al file prenotazioni
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            tutor_path = os.path.join(project_root, "actions", "csv", "tutor.csv")
            
            try:
                # Leggi il CSV
                df = pd.read_csv(tutor_path)
                
                # Filtra per materia
                tutor_materia = df[df['materia'].str.lower() == materia.lower()]
                
                if tutor_materia.empty:
                    dispatcher.utter_message(
                        text=f"Non ho trovato tutor disponibili per {materia}."
                    )
                    return [SlotSet("materia", None)]
                
                # Raggruppa per tutor (nome + cognome)
                tutor_gruppi = tutor_materia.groupby(['nome', 'cognome', 'costo_ora'])
                
                messaggio = f"🎓 *Tutor disponibili per {materia.upper()}:*\n\n"
                
                for (nome, cognome, costo), gruppo in tutor_gruppi:
                    messaggio += f"👨‍🏫 *{nome} {cognome}*\n"
                    messaggio += f"💰 Costo: €{costo}/ora\n"
                    messaggio += f"📅 Disponibilità:\n"
                    
                    for _, riga in gruppo.iterrows():
                        giorno = riga['disponibilita_giorno'].capitalize()
                        ora = riga['disponibilita_ora']
                        messaggio += f"   • {giorno}: {ora}\n"
                    
                    messaggio += "\n"
                
                # Invia il messaggio 
                dispatcher.utter_message(
                    json_message={
                        "text": messaggio,
                        "parse_mode": "Markdown"
                    }
                )
                
            except Exception as e:
                dispatcher.utter_message(
                    text=f"Mi dispiace, si è verificato un errore."
                )
                print(f"Errore: {e}")
            
            return []
        


    #===========================================================================
    #                           RESET ACTIONS
    #===========================================================================

    class ActionResetSlots(Action):
        """Action per resettare tutti gli slot della conversazione"""

        def name(self) -> Text:
            return "action_reset_slots"

        def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:
            
            # Reset di tutti gli slot
            return [
                AllSlotsReset(),
                SlotSet("cellulare", None),
                SlotSet("materia", None),
                SlotSet("data", None),
                SlotSet("ora", None),
                SlotSet("available_tutors", None),
                SlotSet("tutors_list", None),
                SlotSet("tutor_scelto", None),
            ]