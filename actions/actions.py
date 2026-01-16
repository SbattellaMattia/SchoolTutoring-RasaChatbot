# actions.py
from typing import Any, Text, Dict, List
from urllib import parse
from flask import json
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, AllSlotsReset
from rasa_sdk.types import DomainDict
import pandas as pd
from dateutil.parser import parse
from datetime import datetime, date, timedelta
import re
import os



ITALIAN_WEEKDAYS = {
    0: "lunedi",
    1: "martedi",
    2: "mercoledi",
    3: "giovedi",
    4: "venerdi",
    5: "sabato",
    6: "domenica",
}

def _time_to_minutes(hhmm: Text) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)

def _parse_ddmmyyyy(date_str: Text) -> datetime.date:
    # es: "17/01/2026"
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()

def _normalize_day(s: Text) -> Text:
    # gestisce "lunedì" vs "lunedi"
    return (
        (s or "")
        .strip()
        .lower()
        .replace("ì", "i")
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ò", "o")
        .replace("ù", "u")
    )

def _split_range(range_str: Text):
    # es: "14:00-18:00"
    start_s, end_s = range_str.split("-")
    return _time_to_minutes(start_s), _time_to_minutes(end_s)




def _tutor_csv_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return os.path.join(project_root, "actions", "csv", "tutor.csv")


def load_subjects_from_csv(path: str) -> List[str]:
    df = pd.read_csv(path)
    materie = (
        df["materia"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
        .unique()
        .tolist()
    )
    materie.sort()
    return materie








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
    def name(self) -> Text:
        return "action_search_tutors"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        materia = tracker.get_slot("materia")
        data = tracker.get_slot("data")   # atteso "DD/MM/YYYY"
        ora = tracker.get_slot("ora")     # atteso "HH:MM"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        csv_path = os.path.join(project_root, "actions", "csv", "tutor.csv")

        if not os.path.exists(csv_path):
            dispatcher.utter_message(text="Errore: database tutor non trovato.")
            return [SlotSet("available_tutors", False)]

        try:
            df = pd.read_csv(csv_path)

            # Normalizzazioni base
            df["materia_norm"] = df["materia"].astype(str).str.strip().str.lower()
            df["giorno_norm"] = df["disponibilita_giorno"].astype(str).apply(_normalize_day)

            # Filtra per materia
            if not materia:
                dispatcher.utter_message(text="Mi serve la materia per cercare i tutor.")
                return [SlotSet("available_tutors", False)]

            tutors = df[df["materia_norm"] == materia.strip().lower()].copy()

            # Se ho data e ora, filtro anche per disponibilità
            if data and ora:
                requested_date = _parse_ddmmyyyy(data)
                requested_day = ITALIAN_WEEKDAYS[requested_date.weekday()]  # Monday=0 [web:57]
                requested_minutes = _time_to_minutes(ora)

                # tengo solo il giorno giusto
                tutors = tutors[tutors["giorno_norm"] == requested_day].copy()

                # split intervalli e filtro per ora
                start_end = tutors["disponibilita_ora"].astype(str).apply(_split_range)
                tutors["start_min"] = start_end.apply(lambda x: x[0])
                tutors["end_min"] = start_end.apply(lambda x: x[1])

                tutors = tutors[
                    (tutors["start_min"] <= requested_minutes)
                    & (requested_minutes <= tutors["end_min"])
                ].copy()

            if tutors.empty:
                if data and ora:
                    dispatcher.utter_message(
                        text=f"Non ho trovato tutor per {materia} disponibili il {data} alle {ora}."
                    )
                else:
                    dispatcher.utter_message(
                        text=f"Mi dispiace, non ci sono tutor disponibili per {materia}."
                    )
                return [SlotSet("available_tutors", False), SlotSet("tutors_list", None)]

            # Prepara bottoni (raggruppo per tutor, perché nel CSV hai più righe per stesso tutor)
            tutors["nome_completo"] = tutors["nome"].astype(str).str.strip() + " " + tutors["cognome"].astype(str).str.strip()

            # prendo un costo per tutor (se è sempre uguale)
            grouped = tutors.groupby("nome_completo", as_index=False).agg(
                costo_ora=("costo_ora", "first")
            )

            message = f"Ho trovato questi tutor disponibili per {materia} alle {ora} di {data}. Quale preferisci?\n\n"

            buttons = []
            tutors_list = []
            for _, row in grouped.iterrows():
                nome_completo = row["nome_completo"]
                costo = row["costo_ora"]

                tutors_list.append({"nome": nome_completo, "costo": costo})

                buttons.append({
                    "title": f"👤 {nome_completo} - {costo}€/ora",
                    "payload": f'/choose_tutor{{"tutor":"{nome_completo}"}}'
                })

            dispatcher.utter_message(
                text=message,
                buttons=buttons,
                button_type="vertical"
            )

            return [SlotSet("available_tutors", True), SlotSet("tutors_list", tutors_list)]

        except Exception as e:
            dispatcher.utter_message(text="Si è verificato un errore durante la ricerca.")
            raise







#=================== VALIDATE FORM ====================

class ValidateTutoringForm(FormValidationAction):
    """Validazione custom per il form di prenotazione con Duckling"""

    def name(self) -> Text:
        return "validate_tutoring_form"
    
    

    def validate_cellulare(self, slot_value, dispatcher, tracker, domain):
        if slot_value is None:
            return {"cellulare": None}

        raw = str(slot_value)
        normalized = re.sub(r"[^\d+]", "", raw)

        # accetta:
        # - 10 cifre (es 3451234567)
        # - +39 seguito da 10 cifre (es +393451234567)
        if re.fullmatch(r"\d{10}", normalized) or re.fullmatch(r"\+39\d{10}", normalized):
            return {"cellulare": normalized}

        dispatcher.utter_message(
            "Numero non riconosciuto. Inserisci un numero italiano valido (10 cifre): 3451234567 o +393451234567."
        )
        return {"cellulare": None}



    def validate_materia(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Valida che la materia sia tra quelle disponibili"""

        # Caso: il form è appena partito, non c'è ancora un valore vero
        if slot_value is None or str(slot_value).strip() == "":
            return {"materia": None}
        
        materia = (slot_value or "").strip().lower()

        # Path al file prenotazioni
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        tutor_path = os.path.join(project_root, "actions", "csv", "tutor.csv")

        df = pd.read_csv(tutor_path)
        materie_csv = sorted(set(df["materia"].astype(str).str.strip().str.lower()))

        if materia in materie_csv:
            return {"materia": materia}

        dispatcher.utter_message(
            text=f"❌ Materia non disponibile. Scegli tra: {', '.join(materie_csv)}"
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
        
        allowed = [t["nome"].strip() for t in tutors_list]

        # 1) Metodo BOTTONI: leggi entity "tutor" dal payload /choose_tutor{"tutor":"..."}
        tutor_entity = next(tracker.get_latest_entity_values("tutor"), None)
        if tutor_entity:
            tutor_entity = tutor_entity.strip()
            # match esatto o contains
            for name in allowed:
                if tutor_entity.lower() == name.lower():
                    return [SlotSet("tutor_scelto", name)]
            for name in allowed:
                if tutor_entity.lower() in name.lower() or name.lower() in tutor_entity.lower():
                    return [SlotSet("tutor_scelto", name)]

        # 2) Metodo testo libero: l'utente scrive "nome cognome"
        last_text = (tracker.latest_message.get("text") or "").strip()
        if last_text:
            for name in allowed:
                if last_text.lower() == name.lower():
                    return [SlotSet("tutor_scelto", name)]
            for name in allowed:
                if last_text.lower() in name.lower() or name.lower() in last_text.lower():
                    return [SlotSet("tutor_scelto", name)]

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

    class ActionShowSubjectsText(Action):
        def name(self) -> Text:
            return "action_show_subjects_text"

        def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:

            path = _tutor_csv_path()
            if not os.path.exists(path):
                dispatcher.utter_message(text="Non trovo il database dei tutor (tutor.csv).")
                return []

            try:
                materie = load_subjects_from_csv(path)
                if not materie:
                    dispatcher.utter_message(text="Al momento non ci sono materie disponibili.")
                    return []

                pretty = "Le materie disponibili sono:\n" + "\n".join(f"📚 *{m.capitalize()}*" for m in materie) + "\n\nPresto ne saranno disponibili di nuove!"
                dispatcher.utter_message(
                    json_message={
                        "text": pretty,
                        "parse_mode": "Markdown"
                    }
                )
                return []
            
            

            except Exception:
                dispatcher.utter_message(text="Errore nel caricare le materie.")
                raise


class ActionShowSubjectsButtons(Action):
    def name(self) -> Text:
        return "action_show_subjects_buttons"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        path = _tutor_csv_path()
        if not os.path.exists(path):
            dispatcher.utter_message(text="Non trovo il database dei tutor (tutor.csv).")
            return []

        try:
            materie = load_subjects_from_csv(path)
            if not materie:
                dispatcher.utter_message(text="Al momento non ci sono materie disponibili.")
                return []

            buttons = []
            for materia in materie:
                # json.dumps evita problemi con le graffe nelle f-string
                payload = "/inform_slot" + json.dumps({"materia": materia}, ensure_ascii=False)
                buttons.append({"title": materia.capitalize(), "payload": payload})

            dispatcher.utter_message(
                text="📚 Seleziona la materia per vedere i tutor disponibili:",
                buttons=buttons,
                button_type="vertical",
            )
            return []

        except Exception:
            dispatcher.utter_message(text="Errore nel caricare le materie.")
            raise


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
                #AllSlotsReset(),
                SlotSet("materia", None),
                SlotSet("data", None),
                SlotSet("ora", None),
                SlotSet("available_tutors", None),
                SlotSet("tutors_list", None),
                SlotSet("tutor", None),
            ]