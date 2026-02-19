import socket
import threading
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import json
import os
from colorama import Fore, Style, init
import signal
import platform

# Inizializza colorama per Windows
init(autoreset=True)

# --- COLORI COLORAMA ---
class Colori:
    RESET = Style.RESET_ALL
    ROSSO = Fore.RED
    VERDE = Fore.GREEN
    GIALLO = Fore.YELLOW
    BLU = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    CIANO = Fore.CYAN
    GRIGIO = Fore.LIGHTBLACK_EX
    BOLD = Style.BRIGHT

# Lock per scrittura XML thread-safe
xml_lock = threading.Lock()

def setup_xml_log():
    """Configura il file XML di log"""
    Path("logs").mkdir(exist_ok=True)
    log_filename = f"logs/server_{datetime.now().strftime('%Y-%m-%d')}.xml"
    
    if not os.path.exists(log_filename):
        root = ET.Element("log")
        root.set("server_name", socket.gethostname())
        root.set("date", datetime.now().strftime('%Y-%m-%d'))
        
        session = ET.SubElement(root, "session")
        session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    
    return log_filename

def setup_client_log(username, client_address):
    """
    Configura il file XML di log per un client specifico
    Gestito dal SERVER, non dal client
    """
    Path("logs").mkdir(exist_ok=True)
    log_filename = f"logs/client_{username}_{datetime.now().strftime('%Y-%m-%d')}.xml"
    
    if not os.path.exists(log_filename):
        root = ET.Element("log")
        root.set("client_username", username)
        root.set("client_address", f"{client_address[0]}:{client_address[1]}")
        root.set("date", datetime.now().strftime('%Y-%m-%d'))
        
        session = ET.SubElement(root, "session")
        session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        session.set("login_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    else:
        # Se esiste già, aggiungi una nuova sessione
        with xml_lock:
            tree = ET.parse(log_filename)
            root = tree.getroot()
            
            session = ET.SubElement(root, "session")
            session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            session.set("login_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
    
    return log_filename

def log_to_xml(log_filename, level, log_type, message):
    """Scrive un'entry nel file XML di log in modo thread-safe"""
    with xml_lock:
        try:
            tree = ET.parse(log_filename)
            root = tree.getroot()
            
            sessions = root.findall("session")
            if sessions:
                current_session = sessions[-1]
            else:
                current_session = ET.SubElement(root, "session")
                current_session.set("start_time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            entry = ET.SubElement(current_session, "entry")
            entry.set("timestamp", datetime.now().strftime('%H:%M:%S'))
            entry.set("level", level)
            entry.set("type", log_type)
            
            msg_elem = ET.SubElement(entry, "message")
            msg_elem.text = message
            
            ET.indent(tree, space="  ")
            tree.write(log_filename, encoding='utf-8', xml_declaration=True)
            
            if level == "INFO":
                level_colored = Colori.VERDE + level + Colori.RESET
            elif level == "WARNING":
                level_colored = Colori.GIALLO + level + Colori.RESET
            elif level == "ERROR":
                level_colored = Colori.ROSSO + level + Colori.RESET
            else:
                level_colored = level
                
            if log_type in ["CONNECTION", "ERROR", "DISCONNECTION", "AUTH", "REGISTRATION"]:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level_colored}] {message}")
        except Exception as e:
            print(f"Errore scrittura XML log: {e}")


def converti_xml_in_csv(xml_filename):
    """Converte un file XML di log in formato CSV"""
    csv_filename = xml_filename.replace(".xml", ".csv")
    
    try:
        tree = ET.parse(xml_filename)
        root = tree.getroot()
        
        with open(csv_filename, "w", encoding='utf-8') as f:
            f.write("timestamp,level,type,message\n")
            for session in root.findall("session"):
                for entry in session.findall("entry"):
                    timestamp = entry.get("timestamp", "")
                    level = entry.get("level", "")
                    log_type = entry.get("type", "")
                    message_elem = entry.find("message")
                    message = message_elem.text if message_elem is not None else ""
                    
                    # Escape dei campi che contengono virgole
                    if "," in message:
                        message = f'"{message}"'
                    
                    f.write(f"{timestamp},{level},{log_type},{message}\n")
        
        return csv_filename
    except Exception as e:
        print(f"Errore conversione XML in CSV: {e}")
        return None

def converti_xml_in_txt(xml_filename):
    """Converte un file XML di log in formato TXT leggibile"""
    txt_filename = xml_filename.replace(".xml", ".txt")
    
    try:
        tree = ET.parse(xml_filename)
        root = tree.getroot()
        
        with open(txt_filename, "w", encoding='utf-8') as f:
            for session in root.findall("session"):
                start_time = session.get("start_time", "")
                login_time = session.get("login_time", "")
                f.write(f"Sessione iniziata: {start_time}, Login: {login_time}\n")
                f.write("-" * 50 + "\n")
                
                for entry in session.findall("entry"):
                    timestamp = entry.get("timestamp", "")
                    level = entry.get("level", "")
                    log_type = entry.get("type", "")
                    message_elem = entry.find("message")
                    message = message_elem.text if message_elem is not None else ""
                    
                    f.write(f"[{timestamp}] [{level}] [{log_type}] {message}\n")
                
                f.write("\n")
        
        return txt_filename
    except Exception as e:
        print(f"Errore conversione XML in TXT: {e}")
        return None