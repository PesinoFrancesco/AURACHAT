import socket
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import os
import sys
import time
import platform
from colorama import Fore, Style, init

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

SECRET_TOKEN = "AURACHAT"  # PAROLA CHIAVE IDENTIFICATORE DISCOVERY
DISCOVERY_PORT = 9999
DISCOVERY_TIMEOUT = 5  # Secondi da aspettare per risposte

def mostra_menu():
    """Mostra menu comandi disponibili"""
    print("\n" + "=" * 60)
    print(f"{Colori.BOLD}COMANDI DISPONIBILI:{Colori.RESET}")
    print("=" * 60)
    print("  TIME                → Richiedi ora corrente del server")
    print("  NAME                → Richiedi hostname del server")
    print("  INFO <type>         → Richiedi informazioni specifiche")
    print("                      1: Client collegati al server")
    print("                      2: Utenti nel database")
    print("                      3: Info rete del server")
    print("                      4: Info rete del client")
    print("                      5: Lista utenti per chat")
    print("  LOG [date]          → Scarica il tuo log personale")
    print("                      Format: YYYY-MM-DD (Es: 2026-01-01)")
    print("                      Default: Scarica il log di oggi")
    print("  EX [fmt] [n] [tgt]  → Scarica/Esporta file di log")
    print("                        [fmt]: xml | csv | txt (Default xml)")
    print("                        [n]  : Numero righe da scaricare (Default all)")
    print("                        [tgt]: client | server (Default entambi)")
    print(f"                        {Colori.GRIGIO}Esempio: EX csv 5 client{Colori.RESET}")

    # Chiusura
    print("-" * 60)
    print("  EXIT          → Disconnetti e chiudi client")
    print("  HELP          → Mostra questo menu")
    print("=" * 60)

def autenticazione(mio_socket):
    """
    Gestisce il processo di autenticazione con il server
    Restituisce: username se successo, None altrimenti
    """
    try:
        while True:
            # Ricevi richiesta dal server
            data = mio_socket.recv(1024).decode('utf-8', errors='ignore')
            
            if not data:
                return None
            
            # Parse del messaggio: TIPO|Messaggio
            if '|' in data:
                msg_type, msg_text = data.split('|', 1)
            else:
                print(data)
                continue
            
            # AUTH_REQUEST - Chiedi se ha account
            if msg_type == "AUTH_REQUEST":
                print(f"\n{Colori.CIANO}{msg_text}{Colori.RESET}", end='')
                risposta = input().strip().upper()
                mio_socket.send(risposta.encode('utf-8'))
                
            # AUTH_USERNAME - Login username
            elif msg_type == "AUTH_USERNAME":
                print(f"{Colori.GIALLO}{msg_text}{Colori.RESET}", end='')
                username = input().strip()
                mio_socket.send(username.encode('utf-8'))
                
            # AUTH_PASSWORD - Login password
            elif msg_type == "AUTH_PASSWORD":
                print(f"{Colori.GIALLO}{msg_text}{Colori.RESET}", end='')
                password = input().strip()
                mio_socket.send(password.encode('utf-8'))
                
            # REG_USERNAME - Registrazione username
            elif msg_type == "REG_USERNAME":
                print(f"{Colori.VERDE}{msg_text}{Colori.RESET}", end='')
                username = input().strip()
                mio_socket.send(username.encode('utf-8'))
                
            # REG_PASSWORD - Registrazione password
            elif msg_type == "REG_PASSWORD":
                print(f"{Colori.VERDE}{msg_text}{Colori.RESET}", end='')
                password = input().strip()
                mio_socket.send(password.encode('utf-8'))
                
            # AUTH_RETRY - Riprova login
            elif msg_type == "AUTH_RETRY":
                print(f"{Colori.ROSSO} {msg_text}{Colori.RESET}")
                
            # REG_RETRY - Riprova registrazione
            elif msg_type == "REG_RETRY":
                print(f"{Colori.GIALLO} {msg_text}{Colori.RESET}")
                
            # AUTH_SUCCESS - Login riuscito
            elif msg_type == "AUTH_SUCCESS":
                print(f"{Colori.VERDE} {msg_text}{Colori.RESET}")
                # Estrai username dal messaggio
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                return username
                
            # REG_SUCCESS - Registrazione riuscita
            elif msg_type == "REG_SUCCESS":
                print(f"{Colori.VERDE} {msg_text}{Colori.RESET}")
                username = msg_text.split("Benvenuto ")[1].rstrip("!")
                return username
                
            # AUTH_FAIL / REG_FAIL - Fallimento
            elif msg_type in ["AUTH_FAIL", "REG_FAIL"]:
                print(f"{Colori.ROSSO} {msg_text}{Colori.RESET}")
                return None
                
    except Exception as e:
        print(f"{Colori.ROSSO}Errore durante autenticazione: {e}{Colori.RESET}")
        return None

def discover_server():
    """
    Cerca il server sulla rete locale usando UDP broadcast
    Restituisce: IP del server se trovato, None altrimenti
    """
    print(f"\n{Colori.CIANO} Ricerca server sulla rete locale...{Colori.RESET}")
    
    # Crea socket UDP
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(1.0)  # Timeout per ricezione

    try:
        # Messaggio di discovery con token segreto
        messaggio = f"DISCOVER|{SECRET_TOKEN}"
        
        # Broadcast sulla porta discovery
        broadcast_address = ('255.255.255.255', DISCOVERY_PORT)
        
        print(f"{Colori.GRIGIO}   Invio broadcast su porta {DISCOVERY_PORT}...{Colori.RESET}")
        
        server_trovato = None
        start_time = time.time()
        tentativi = 0

        # Continua a cercare fino al timeout
        while time.time() - start_time < DISCOVERY_TIMEOUT:
            try:
                # Invia broadcast a tutta la rete sulla porta 9999
                udp_socket.sendto(messaggio.encode('utf-8'), broadcast_address)
                tentativi += 1

                try:
                    data, server_addr = udp_socket.recvfrom(1024)
                    risposta = data.decode('utf-8', errors='ignore').strip()
                    
                    # Analizza la risposta: FOUND|TOKEN|HOSTNAME|PORTA
                    parti = risposta.split('|')
                    
                    # Verifica che la risposta sia valida
                    if len(parti) == 4 and parti[0] == "FOUND" and parti[1] == SECRET_TOKEN:
                        server_ip = server_addr[0]
                        server_hostname = parti[2]
                        server_porta = int(parti[3])
                        
                        print(f"\n{Colori.VERDE}Server trovato!{Colori.RESET}")
                        print(f"   IP: {Colori.BLU}{server_ip}{Colori.RESET}")
                        print(f"   Hostname: {Colori.BLU}{server_hostname}{Colori.RESET}")
                        print(f"   Porta: {Colori.BLU}{server_porta}{Colori.RESET}")
                        
                        
                        server_trovato = (server_ip, server_porta)
                        break

                except socket.timeout:
                # Nessuna risposta in questo secondo, riprova
                    pass

                time.sleep(0.5)

            except Exception as e:
                print(f"{Colori.GRIGIO}   Tentativo {tentativi} fallito{Colori.RESET}")

        # Fine ricerca
        if not server_trovato:
            print(f"\n{Colori.ROSSO}Nessun server trovato dopo {DISCOVERY_TIMEOUT} secondi{Colori.RESET}")
            print(f"   {Colori.GIALLO}Verifica che:{Colori.RESET}")
            print(f"   - Il server sia avviato")
            print(f"   - Sia sulla stessa rete")
            print(f"   - Il firewall permetta UDP porta {DISCOVERY_PORT}")
            
        
        return server_trovato
        
    except Exception as e:
        print(f"\n{Colori.ROSSO}Errore fatale durante discovery: {e}{Colori.RESET}")
        return None
    finally:
        udp_socket.close()

def connetti_al_server(host, porta, tentativi=3):
    """Tenta di connettersi al server con retry automatico"""
    for tentativo in range(1, tentativi + 1):
        try:
            print(f"{Colori.GRIGIO}Tentativo {tentativo}/{tentativi} di connessione a {host}:{porta}...{Colori.RESET}")
            
            mio_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mio_socket.settimeout(5)
            mio_socket.connect((host, porta))
            
            print(f"{Colori.VERDE}Connesso al server {host}:{porta}{Colori.RESET}")
            
            return mio_socket
            
        except socket.timeout:
            print(f"{Colori.ROSSO}Timeout connessione{Colori.RESET}")
        except ConnectionRefusedError:
            print(f"{Colori.ROSSO}Server non raggiungibile{Colori.RESET}")
        except Exception as e:
            print(f"{Colori.ROSSO}Errore: {e}{Colori.RESET}")
        
        if tentativo < tentativi:
            print(f"Riprovo tra 2 secondi...")
            time.sleep(2)
    
    return None

def get_info_client(mio_socket):
    """Restituisce informazioni di rete del client in formato semplice"""
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "N/A"
    try:
        local_addr = mio_socket.getsockname()
        remote_addr = mio_socket.getpeername()
        local_port = local_addr[1]
        server_ip = remote_addr[0]
        server_port = remote_addr[1]
    except:
        local_port = "N/A"
        server_ip = "N/A"
        server_port = "N/A"
    sistema = platform.system()
    versione = platform.version()
    info = (
        f"CLIENT INFO:\n"
        f"  Hostname: {hostname}\n"
        f"  IP Locale: {ip_address}\n"
        f"  Porta Locale: {local_port}\n"
        f"  Server IP: {server_ip}\n"
        f"  Server Porta: {server_port}\n"
        f"  Sistema: {sistema}\n"
        f"  Versione: {versione[:40]}"
    )
    return info

def main():
    """Funzione principale del client"""
    print("=" * 60)
    print("AVVIO CLIENT TCP (Con Autenticazione + Discovery)")
    print("=" * 60)
    print(f"Token Discovery: {SECRET_TOKEN}")
    
    
    # DISCOVERY: Cerca il server sulla rete
    server_info = discover_server()

    if not server_info:
        print(f"\n{Colori.ROSSO}ERRORE: Impossibile trovare il server!{Colori.RESET}")
        
        # Opzione fallback: chiedi IP manualmente
        print(f"\n{Colori.GIALLO}Vuoi inserire l'IP manualmente? (SI/NO): {Colori.RESET}", end='')
        scelta = input().strip().upper()
        
        if scelta == "SI":
            ip_manuale = input(f"{Colori.CIANO}Inserisci IP server: {Colori.RESET}").strip()
            porta_manuale = input(f"{Colori.CIANO}Inserisci porta (default 12345): {Colori.RESET}").strip()
            porta_manuale = int(porta_manuale) if porta_manuale else 12345
            server_info = (ip_manuale, porta_manuale)
        else:
            sys.exit(1)
    
    server_ip, server_porta = server_info
    
    # Connessione al server
    mio_socket = connetti_al_server(host=server_ip, porta=server_porta)
    if not mio_socket:
        print("\nERRORE: Impossibile connettersi al server!")
        print("Verifica che il server sia in esecuzione su porta 12345")
        sys.exit(1)
    
    mio_socket.settimeout(None)
    
    print(f"\n{Colori.BOLD}=== AUTENTICAZIONE ==={Colori.RESET}")
    
    # AUTENTICAZIONE
    username = autenticazione(mio_socket)
    
    if not username:
        print(f"\n{Colori.ROSSO}Autenticazione fallita. Chiusura client.{Colori.RESET}")
        mio_socket.close()
        sys.exit(1)
    
    print(f"\n{Colori.VERDE}Sei connesso come: {Colori.BLU}{username}{Colori.RESET}")
    
    # Mostra menu
    mostra_menu()
    
    try:
        while True:
            print("\n" + "-" * 50)
            messaggio = input(f"[{Colori.BLU}{username}{Colori.RESET}] Comando (HELP per aiuto): ").strip()
            
            if messaggio.upper() == "HELP":
                mostra_menu()
                continue
            
            if not messaggio:
                print("Inserisci un comando valido!")
                continue
            
            if messaggio.upper() == "EXIT":
                print("\nDisconnessione in corso...")
                # Inviamo comunque EXIT al server per chiudere pulito
                try:
                    mio_socket.send(messaggio.encode('utf-8'))
                except:
                    pass
                break

            # --- INVIO COMANDO ---
            try:
                mio_socket.send(messaggio.encode('utf-8'))
            except Exception as e:
                print(f"Errore invio: {e}")
                break

            # --- BLOCCO RICEZIONE MODIFICATO (PER FILE MULTIPLI) ---
            streaming_log = False 

            while True: 
                try:
                    data = mio_socket.recv(8192).decode('utf-8', errors='ignore')
                    
                    if not data:
                        print("\nServer disconnesso")
                        raise Exception("Server closed connection")

                    # 1. SEGNALI DI CONTROLLO STREAMING (Per il comando LOG)
                    if "START_DISPLAY_LOG" in data:
                        streaming_log = True
                        # Puliamo la stringa se per caso il server ha unito il comando al testo
                        data = data.replace("START_DISPLAY_LOG", "")
                        print(f"\n{Colori.CIANO}--- INIZIO LOG ---{Colori.RESET}")
                        if not data:
                            continue # Se c'era solo il comando, passa al prossimo recv

                    # 2. CONTROLLO FINE OPERAZIONE (Per EX e LOG)
                    if "FINE_INVIO" in data:
                        # Stampa l'ultima parte di dati prima della parola chiave
                        ultimo_pezzo = data.replace("FINE_INVIO", "")
                        if ultimo_pezzo:
                            print(ultimo_pezzo, end="")
                        print(f"\n{Colori.VERDE}--- OPERAZIONE COMPLETATA ---{Colori.RESET}")
                        break # ORA usciamo dal ciclo e torniamo al men

                    # 3. GESTIONE DOWNLOAD FILE (Comando EX)
                    elif data.startswith("FILE_START:"):
                        parti_header = data.split(":") 
                        tipo_file = parti_header[1]      # "CLIENT" o "SERVER"
                        dimensione_totale = int(parti_header[2])

                        print(f"Ricezione file {tipo_file} ({dimensione_totale} bytes)...")
                        mio_socket.send("READY".encode('utf-8'))

                        dati_ricevuti = b""
                        while len(dati_ricevuti) < dimensione_totale:
                            mancanti = dimensione_totale - len(dati_ricevuti)
                            chunk = mio_socket.recv(min(4096, mancanti))
                            if not chunk: break
                            dati_ricevuti += chunk

                        # Determiniamo estensione dal messaggio inviato prima
                        estensione = "xml"
                        if "csv" in messaggio.lower(): estensione = "csv"
                        elif "txt" in messaggio.lower(): estensione = "txt"

                        nome_output = f"log_scaricato_{username}.{estensione}" if tipo_file == "CLIENT" else f"log_scaricato_server.{estensione}"

                        with open(nome_output, "wb") as f_out:
                            f_out.write(dati_ricevuti)

                        print(f"File salvato: {Colori.BLU}{nome_output}{Colori.RESET}")
                        continue # Molto importante: continua a cercare altri file o FINE_INVIO

                    # 4. GESTIONE INFO SPECIALE (INFO 4)
                    elif data == "CLIENT_HANDLE_INFO_4":
                        info_client = get_info_client(mio_socket)
                        print(f"\n{info_client}")
                        break 

                    # 5. MESSAGGI NORMALI O CONTENUTO LOG
                    else:
                        # Pulizia estetica (caratteri tabella)
                        testo_pulito = data.replace(chr(9552),'-').replace(chr(9553),'|')
                        
                        if streaming_log:
                            # Se siamo in modalità LOG, stampiamo senza uscire (senza break)
                            print(testo_pulito, end="")
                            continue 
                        else:
                            # Se è un messaggio normale (TIME, NAME, ERRORI), stampa ed esci
                            print(f"\n{testo_pulito}")
                            break 

                except Exception as e:
                    print(f"Errore ricezione: {e}")
                    raise e
            
            # --- FINE BLOCCO RICEZIONE ---

    except KeyboardInterrupt:
        print("\nInterruzione utente")
    except Exception as e:
        print(f"{Colori.ROSSO}Errore critico o disconnessione: {e}{Colori.RESET}")
    finally:
        try:
            mio_socket.close()
        except:
            pass
        print("\nConnessione chiusa dal client")

if __name__ == "__main__":
    main()