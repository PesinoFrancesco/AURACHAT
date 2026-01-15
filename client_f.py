import socket

# 1. Creazione del socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 2. Connessione al server (IP localhost e porta 12345)
client_socket.connect(("127.0.0.1", 12345))

#ciclo che consente di continuare a inviare messaggi finche non si digita exit
while True:
    #input messaggio
    messaggio = input("Nuovo messaggio: ")
    #invio del messaggio
    client_socket.send(messaggio.encode())

    #verifica testo del messaggio
    data = client_socket.recv(1024).decode().strip()
    if data != "-1":
        print(f"Risposta dal server: {data}")
        print()
    else:
        break

    # 4. Ricezione risposta
    

#chiusura socket del client   
client_socket.close()