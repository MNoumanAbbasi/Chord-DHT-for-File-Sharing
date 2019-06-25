import socket, random
import threading
import pickle
import sys
import time
import hashlib
from collections import OrderedDict
# Default values if command line arguments not given
IP = "127.0.0.1"
PORT = 2000
buffer = 100000

MAX_BITS = 6        # 6-bit                           # TODO Data replication between several nodes
MAX_NODES = 2 ** MAX_BITS
# Takes key string, uses SHA-1 hashing and returns a 10-bit (1024) compressed integer
def getHash(key):
    result = hashlib.sha1(key.encode())
    return int(result.hexdigest(), 16) % MAX_NODES

class Node:

    def __init__(self, ip, port):
        self.filenameList = []
        self.ip = ip
        self.port = port
        self.address = (ip, port)
        self.id = getHash(ip + ":" + str(port))
        self.pred = (ip, port)            # Predecessor of this node
        self.predID = self.id
        self.succ = (ip, port)            # Successor to this node
        self.succID = self.id
        self.succ2 = (ip, port)            # Second Successor to this node
        self.succ2ID = self.id
        self.fingerTable = OrderedDict()        # Dictionary: key = IDs and value = (IP, port) tuple
        # Making sockets
            # Server socket used as listening socket for incoming connections hence threaded
            # Client socket used for connections and data transfers p2p
        try:
            self.ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.ServerSocket.bind((IP, PORT))
            self.ServerSocket.listen()
            
        except socket.error:
            print("Socket not opened")

    def listenThread(self):
        # Storing the IP and port in address and saving the connection and threading
        while True:
            try:
                connection, address = self.ServerSocket.accept()
                connection.settimeout(120)
                print("Connected with the client on")
                print("IP: " + address[0])
                print("Port: " + str(address[1]))
                threading.Thread(target=self.connectionThread, args=(connection, address)).start()
            except socket.error:
                pass#print("Error: Connection not accepted. Try again.")

    # Thread for each peer connection
    def connectionThread(self, connection, address):
        print("Connection with:", address[0], ":", address[1])
        rDataList = pickle.loads(connection.recv(buffer))
        # 5 Types of connections
        # type 0: peer connect, type 1: client, type 2: ping, type 3: lookupID, type 4: updateSucc/Pred
        connectionType = rDataList[0]
        if connectionType == 0:
            print("Join network request recevied")
            self.joinNode(connection, address, rDataList)
        elif connectionType == 1:
            print("Upload/Download request recevied")
            self.transferFile(connection, address, rDataList)
        elif connectionType == 2:
            print("Ping recevied")
            connection.sendall(pickle.dumps(self.pred))
        elif connectionType == 3:
            print("Lookup request recevied")
            self.lookupID(connection, address, rDataList)
        elif connectionType == 4:
            print("Predecessor/Successor update request recevied")
            if rDataList[1] == 1:
                self.updateSucc(rDataList)
            else:
                self.updatePred(rDataList)
        elif connectionType == 5:
            print("Update Finger Table request recevied")
            self.updateFTable()
            connection.sendall(pickle.dumps(self.succ))
        else:
            print("Problem with connection type")
        print("my new pred:", self.predID, "my succ", self.succID)
        # print("FInal f table")
        self.printFTable()
        connection.close()
    
    # Deals with join network request by other node
    def joinNode(self, connection, address, rDataList):
        if rDataList:
            peerIPport = rDataList[1]
            peerID = getHash(peerIPport[0] + ":" + str(peerIPport[1]))
            oldPred = self.pred
            # Updating pred
            self.pred = peerIPport
            self.predID = peerID
            # Sending new peer's pred back to it
            sDataList = [oldPred]
            connection.sendall(pickle.dumps(sDataList))
            #Updating F table
            time.sleep(0.1)
            self.updateFTable()
            # Then asking other peers to update their f table as well
            self.updateOtherFTables()

    def transferFile(self, connection, address, rDataList):
        # Choice: 0 = download, 1 = upload
        choice = rDataList[1]
        filename = rDataList[2]
        fileID = getHash(filename)
        sDataList = [-1, filename]   # Default as file not found
        # IF client wants to download file
        if choice == 0:
            print("Download request for file:", filename)
            try:
                # First it searches its own directory (fileIDList). If not found, send does not exist
                if filename not in self.filenameList:
                    sDataList = [-1, filename]
                    print("File not found")
                else:   # If file exists in its directory   # Sending DATA LIST Structure (sDataList):
                    with open(filename, 'rb') as file:
                        fileData = file.read()
                        sDataList = [1, filename, fileData]
                        print("File sent to:", address)
                connection.sendall(pickle.dumps(sDataList))
            except ConnectionResetError as error:
                print(error, "\nClient disconnected\n\n")
        # ELSE IF client wants to upload something to network
        elif choice == 1 or choice == -1:
            fileData = rDataList[3]
            print("Upload request for file:", filename)
            fileID = getHash(filename)
            print(fileID)
            self.filenameList.append(filename)
            print("Receiving file:", filename)
            with open(filename, 'wb') as file:
                file.write(fileData)
            print("Upload complete")
            # Replicating file to successor as well
            if choice == 1:
                if self.address != self.succ:
                    self.uploadFile(filename, self.succ, False)
            # if choice == 1:
            #     try:
            #         with open(filename, 'rb') as file:
            #             if self.succ == self.address:  # Upload to itself
            #                 self.filenameList.append(filename)
            #             else:
            #                 fileData = file.read()
            #                 sDataList = [1, -1, filename, fileData]
            #                 cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #                 cSocket.connect(self.succ)
            #                 cSocket.sendall(pickle.dumps(sDataList))
            #                 cSocket.close()
            #             print("File uploaded")
            #     except socket.error:
            #         print("Error in uploading file")


    def lookupID(self, connection, address, rDataList):
        keyID = rDataList[1]
        sDataList = []
        print(self.id, keyID)
        if self.id == keyID:        # Case 0: If keyId at self
            sDataList = [0, self.address]
        elif self.succID == self.id:  # Case 1: If only one node
            sDataList = [0, self.address]
        elif self.id > keyID:       # Case 2: Node id greater than keyId, ask pred
            if self.predID < keyID:   # If pred is higher than key, then self is the node
                sDataList = [0, self.address]
            elif self.predID > self.id:
                sDataList = [0, self.address]
            else:       # Else send the pred back
                sDataList = [1, self.pred]
        else:                       # Case 3: node id less than keyId
            # IF last node before chord circle completes
            if self.id > self.succID:
                sDataList = [0, self.succ]
            else:
                sDataList = [1, self.succ]
        connection.sendall(pickle.dumps(sDataList))
        print(sDataList)

    def updateSucc(self, rDataList):
        newSucc = rDataList[2]
        self.succ = newSucc
        self.succID = getHash(newSucc[0] + ":" + str(newSucc[1]))
        print("Updated succ to", self.succID)
    
    def updatePred(self, rDataList):
        newPred = rDataList[2]
        self.pred = newPred
        self.predID = getHash(newPred[0] + ":" + str(newPred[1]))
        print("Updated pred to", self.predID)

    def start(self):
        # Accepting connections from other threads
        threading.Thread(target=self.listenThread, args=()).start()
        # threading.Thread(target=self.outgoingConnectionThread, args=()).start()
        threading.Thread(target=self.pingSucc, args=()).start()
        # In case of connecting to other clients
        while True:
            print("Listening to other clients")   
            self.asAClientThread()
    
    def pingSucc(self):
        while True:
            # Ping every 5 seconds
            time.sleep(10)
            # If only one node, no need to ping
            if self.address == self.succ:
                continue
            try:
                print("Pinging succ", self.succ)
                pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                pSocket.connect(self.succ)
                pSocket.sendall(pickle.dumps([2]))  # Send ping request
                recvPred = pickle.loads(pSocket.recv(buffer))
            except:
                print("\nOffline node dedected!\nStabilizing...")
                # Search for the next succ from the F table
                newSuccFound = False
                value = ()
                for key, value in self.fingerTable.items():
                    if value[0] != self.succID:
                        newSuccFound = True
                        break
                if newSuccFound:
                    print("new succ", value[1])
                    self.succ = value[1]   # Update your succ to new Succ
                    self.succID = getHash(self.succ[0] + ":" + str(self.succ[1]))
                    # Inform new succ to update its pred to me now
                    pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    pSocket.connect(self.succ)
                    pSocket.sendall(pickle.dumps([4, 0, self.address]))
                    pSocket.close()
                else:       # In case Im only node left
                    self.pred = self.address            # Predecessor of this node
                    self.predID = self.id
                    self.succ = self.address            # Successor to this node
                    self.succID = self.id
                self.updateFTable()
                self.updateOtherFTables()

    # Handles all outgoing connections
    def asAClientThread(self):
        # Printing options
        userChoice = input("1. Join Network\n2. Leave Network\n3. Upload File\n4. Download File\n")
        if userChoice == "1":
            ip = input("Enter IP to connect: ")
            port = input("Enter port: ")
            self.sendJoinRequest(ip, int(port))
        elif userChoice == "2":
            self.leaveNetwork()
        elif userChoice == "3":
            filename = input("Enter filename: ")
            fileID = getHash(filename)
            recvIPport = self.getSuccessor(self.succ, fileID)
            self.uploadFile(filename, recvIPport, True)
        elif userChoice == "4":
            filename = input("Enter filename: ")
            self.downloadFile(filename)

    def sendJoinRequest(self, ip, port):
        try:
            recvIPPort = self.getSuccessor((ip, port), self.id)
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peerSocket.connect(recvIPPort)
            sDataList = [0, self.address]
            # Sending self peer address to add to network
            peerSocket.sendall(pickle.dumps(sDataList))
            # Receiving new pred
            rDataList = pickle.loads(peerSocket.recv(buffer))
            # Updating pred and succ
            print('before', self.predID, self.succID)
            self.pred = rDataList[0]
            self.predID = getHash(self.pred[0] + ":" + str(self.pred[1]))
            self.succ = recvIPPort
            self.succID = getHash(recvIPPort[0] + ":" + str(recvIPPort[1]))
            print('after', self.predID, self.succID)
            # Tell pred to update its successor which is now me
            sDataList = [4, 1, self.address]
            pSocket2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pSocket2.connect(self.pred)
            pSocket2.sendall(pickle.dumps(sDataList))
            pSocket2.close()
            # Sending confirmation that pred and succ are updated
            # peerSocket.sendall(pickle.dumps(True))
            peerSocket.close()
        except socket.error:
            print("Socket error. Recheck IP/Port.")
    
    def leaveNetwork(self):
        # First inform my succ to update its pred
        pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pSocket.connect(self.succ)
        pSocket.sendall(pickle.dumps([4, 0, self.pred]))
        pSocket.close()
        # Then inform my pred to update its succ
        pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pSocket.connect(self.pred)
        pSocket.sendall(pickle.dumps([4, 1, self.succ]))
        pSocket.close()
        print("I had files:", self.filenameList)
        # And also replicating its files to succ as a client
        print("Replicating files to other nodes before leaving")
        for filename in self.filenameList:
            pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pSocket.connect(self.succ)
            file = open(filename, 'rb')
            fileData = file.read()
            # Sending self peer address to add to network
            pSocket.sendall(pickle.dumps([1, 1, filename, fileData]))
            file.close()
            pSocket.close()
        # Telling others to update their f tables
        self.updateOtherFTables()
        # Chaning the pointers to default
        self.pred = (self.ip, self.port)            # Predecessor of this node
        self.predID = self.id
        self.succ = (self.ip, self.port)            # Successor to this node
        self.succID = self.id
        self.fingerTable.clear()
        print(self.address, "has left the network")
    
    def uploadFile(self, filename, recvIPport, replicate):
        print("Uploading file", filename)
        # If not found send lookup request to get peer to upload file
        sDataList = [1]
        if replicate:
            sDataList.append(1)
        else:
            sDataList.append(-1)
        try:
            with open(filename, 'rb') as file:
                # if recvIPport == self.address:  # Upload to itself
                #     self.filenameList.append(filename)
                # else:
                fileData = file.read()
                sDataList = sDataList + [filename, fileData]
                cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cSocket.connect(recvIPport)
                cSocket.sendall(pickle.dumps(sDataList))
                cSocket.close()
                print("File uploaded")
        except socket.error:
            print("Error in uploading file")
    
    def downloadFile(self, filename):
        print("Downloading file", filename)
        fileID = getHash(filename)
        # First finding node with the file
        recvIPport = self.getSuccessor(self.succ, fileID)
        sDataList = [1, 0, filename]
        cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cSocket.connect(recvIPport)
        cSocket.sendall(pickle.dumps(sDataList))      
        # Receiving confirmation if file found or not
        rDataList = pickle.loads(cSocket.recv(buffer))
        fileStatus = rDataList[0]
        # IF file found, proceed to extract fileData from dataList
        if fileStatus == 1:
            filename = rDataList[1]
            print("Receiving file:", filename)
            with open(filename, 'wb') as file:
                fileData = rDataList[2]
                file.write(fileData)
        elif fileStatus == -1:
            filename = rDataList[1]
            print("File not found:", filename)


    def getSuccessor(self, address, keyID):
        rDataList = [1, address]      # Deafult values to run while loop
        recvIPPort = rDataList[1]
        while rDataList[0] == 1:
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                peerSocket.connect(recvIPPort)  # Connecting to server
                print("Connection established")
            except socket.error:
                print("Connection denied")
            # Send continous lookup requests until required peer ID
            sDataList = [3, keyID]
            peerSocket.sendall(pickle.dumps(sDataList))
            # Do continous lookup until you get your postion (0)
            rDataList = pickle.loads(peerSocket.recv(buffer))
            recvIPPort = rDataList[1]
            peerSocket.close()
        print(rDataList)
        # # IF found the required succ IPPort
        print(recvIPPort)
        #peerSocket.close()
        return recvIPPort
    
    def updateFTable(self):
        for i in range(MAX_BITS):
            entryId = self.id + (2 ** i)
            # If only one node in network
            if self.succ == self.address:
                self.fingerTable[entryId] = (self.id, self.address)
                continue
            # If multiple nodes in network, we find succ for each entryID
            # Send lookup request to your succ
            recvIPPort = self.getSuccessor(self.succ, entryId)
            recvId = getHash(recvIPPort[0] + ":" + str(recvIPPort[1]))
            self.fingerTable[entryId] = (recvId, recvIPPort)
        # time.sleep(0.5)
        print('F table after update')
        self.printFTable()
    
    def updateOtherFTables(self):
        here = self.succ
        while True:
            if here == self.address:
                break
            pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                pSocket.connect(here)  # Connecting to server
                pSocket.sendall(pickle.dumps([5]))
                here = pickle.loads(pSocket.recv(buffer))
                pSocket.close()
                if here == self.succ:
                    break
            except socket.error:
                print("Connection denied")

    def printFTable(self):
        print("Printing F Table")
        for key, value in self.fingerTable.items(): 
            print("KeyID:", key, "Value", value)

if len(sys.argv) < 3:
    print("Arguments not supplied (Defaults used)")
else:
    IP = sys.argv[1]
    PORT = int(sys.argv[2])

myNode = Node(IP, PORT)
print("My ID is:", myNode.id)
myNode.start()
# Closing socket
myNode.ServerSocket.close()
