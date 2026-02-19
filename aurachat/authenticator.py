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
import logger

# File configurazione utenti (dentro la cartella `config`)
CONFIG_FILE = 'config/users.json'
config_lock = threading.Lock()

# Mappa utenti connessi {username: (socket, address)}
utenti_connessi = {}
utenti_lock = threading.Lock()


def setup_config():
    """Crea la cartella config e il file users.json se non esistono"""
    Path("config").mkdir(exist_ok=True)
    # Se il file non esiste, crealo vuoto con struttura base
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"users": []}, f, indent=2)

def carica_utenti():
    """Carica gli utenti dal file JSON"""
    with config_lock:
        try:
            # Assicura che la cartella e il file esistano
            setup_config()
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"users": []}

def salva_utenti(data):
    """Salva gli utenti nel file JSON"""
    with config_lock:
        # Assicura che la cartella esista prima di salvare
        Path(os.path.dirname(CONFIG_FILE) or '.').mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

def verifica_credenziali(username, password):
    """Verifica se username e password sono corretti"""
    data = carica_utenti()    
    for user in data['users']:
        if user['username'] == username and user['password'] == password:
            return True
    return False

def username_esiste(username):
    """Controlla se un username esiste già"""
    data = carica_utenti()
    for user in data['users']:
        if user['username'] == username:
            return True
    return False

def registra_utente(username, password, ip, porta):
    """Registra un nuovo utente"""
    data = carica_utenti()
    
    nuovo_utente = {
        "username": username,
        "password": password,
        "ip": ip,
        "porta": porta,
        "data_registrazione": datetime.now().isoformat(),
        "ultimo_accesso": datetime.now().isoformat()
    }
    
    data['users'].append(nuovo_utente)
    salva_utenti(data)
    return True

def aggiorna_ultimo_accesso(username):
    """Aggiorna la data di ultimo accesso"""
    data = carica_utenti()
    for user in data['users']:
        if user['username'] == username:
            user['ultimo_accesso'] = datetime.now().isoformat()
            break
    salva_utenti(data)


def autenticazione(mio_socket, client_address, log_filename):
    """
    Gestisce l'autenticazione del client
    Restituisce: (True, username) se successo, (False, None) altrimenti
    """
    try:
        # Chiedi se ha già un account
        mio_socket.send("AUTH_REQUEST|Hai già un account? (SI/NO): ".encode('utf-8'))
        risposta = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip().upper()
        
        if risposta == "SI":
            # LOGIN
            for tentativo in range(3):
                mio_socket.send("AUTH_USERNAME|Username: ".encode('utf-8'))
                username = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                mio_socket.send("AUTH_PASSWORD|Password: ".encode('utf-8'))
                password = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                if verifica_credenziali(username, password):
                    # Verifica se utente già connesso
                    with utenti_lock:
                        if username in utenti_connessi:
                            mio_socket.send("AUTH_FAIL|Utente già connesso da un altro client!".encode('utf-8'))
                            logger.log_to_xml(log_filename, "WARNING", "AUTH", f"Tentativo login con utente già connesso: {username}")
                            return False, None
                    
                    aggiorna_ultimo_accesso(username)
                    mio_socket.send(f"AUTH_SUCCESS|Benvenuto {username}!".encode('utf-8'))
                    
                    logger.log_to_xml(log_filename, "INFO", "AUTH", f"Login effettuato: {username}")
                    
                    return True, username
                else:
                    tentativi_rimasti = 2 - tentativo
                    if tentativi_rimasti > 0:
                        mio_socket.send(f"AUTH_RETRY|Credenziali errate! {tentativi_rimasti} tentativi rimasti".encode('utf-8'))
                    else:
                        mio_socket.send("AUTH_FAIL|Credenziali errate! Accesso negato".encode('utf-8'))
                    
                    logger.log_to_xml(log_filename, "WARNING", "AUTH", f"Tentativo login fallito per username: {username}")
            
            return False, None
            
        elif risposta == "NO":
            # REGISTRAZIONE
            while True:
                mio_socket.send("REG_USERNAME|Scegli un username (univoco lunghezza min. 3): ".encode('utf-8'))
                username = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
                
                if not username or len(username) < 3:
                    mio_socket.send("REG_RETRY|Username troppo corto (minimo 3 caratteri)".encode('utf-8'))
                    continue
                
                if username_esiste(username):
                    mio_socket.send("REG_RETRY|Username già esistente, scegline un altro".encode('utf-8'))
                    continue
                
                break
            
            mio_socket.send("REG_PASSWORD|Scegli una password (lunghezza min. 4): ".encode('utf-8'))
            password = mio_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            
            if len(password) < 4:
                mio_socket.send("REG_FAIL|Password troppo corta (minimo 4 caratteri)".encode('utf-8'))
                return False, None
            
            # Registra utente
            registra_utente(username, password, client_address[0], client_address[1])
            mio_socket.send(f"REG_SUCCESS|Account creato! Benvenuto {username}!".encode('utf-8'))
            
            logger.log_to_xml(log_filename, "INFO", "REGISTRATION", f"Nuovo utente registrato: {username}")
            
            return True, username
        else:
            mio_socket.send("AUTH_FAIL|Risposta non valida".encode('utf-8'))
            return False, None
            
    except Exception as e:
        logger.log_to_xml(log_filename, "ERROR", "AUTH_ERROR", f"Errore durante autenticazione: {e}")
        return False, None