import socket, random
import threading
import pickle
import sys
import hashlib
from collections import OrderedDict
# Default values if command line arguments not given
IP = "127.0.0.1"
PORT = 2000
buffer = 100000

MAX_BITS = 10        # 10-bit                           # TODO Data replication between several nodes
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
            print("Peer Connection request recevied")
            self.joinNode(connection, address, rDataList)
        elif connectionType == 1:
            print("Client request recevied")
            #self.clientConnection(connection, address, rDataList)
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
        else:
            print("Problem with connection type")
        print("my new pred:", self.predID, "my succ", self.succID)
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

    def lookupID(self, connection, address, rDataList):
        keyID = rDataList[1]
        sDataList = []
        print(self.id, keyID)
        if self.id == keyID:        # Case 0: If keyId at self
            sDataList = [0, self.address]
        elif self.succID == self.id:  # Case 1: If only one node
            sDataList = [0, self.address]
        elif self.id > keyID:       # Case 2: Node id greater than keyId, ask pred
            if self.predID > self.id:   # If pred is higher than me, then self is the node
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
        # In case of connecting to other clients
        while True:
            print("Listening to other clients")   
            self.asAClientThread()
    
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

    def sendJoinRequest(self, ip, port):
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
        for filename in self.filenameList:
            pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pSocket.connect(self.succ)
            file = open(filename, 'rb')
            fileData = file.read()
            # Sending self peer address to add to network
            pSocket.sendall(pickle.dumps([1, 1, filename, fileData]))
            file.close()
            pSocket.close()

        print(self.address, "has left the network")

    def getSuccessor(self, address, keyID):
        peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            peerSocket.connect(address)  # Connecting to server
            print("Connection established")
        except socket.error:
            print("Connection denied")
        # Send continous lookup requests until required peer ID
        sDataList = [3, keyID]
        peerSocket.sendall(pickle.dumps(sDataList))
        # Do continous lookup until you get your postion (0)
        rDataList = pickle.loads(peerSocket.recv(buffer))
        recvIPPort = rDataList[1]
        print(rDataList)
        # IF Ive been forwarded to another peer, connect to that peer
        if rDataList[0] == 1:
            peerSocket.close()
            self.getSuccessor(recvIPPort, keyID)
        # IF found the required succ IPPort
        print(recvIPPort)
        return recvIPPort

    # Sending data
    def sendData(self, connection, filename):
        filename = "version_history.txt"
        # First send filename ...
        connection.sendall(pickle.dumps(filename))
        file = open(filename, 'rb')
        fileData = file.read()
        # ... then send file data
        connection.sendall(pickle.dumps(fileData))
        print("Data sent from server")
        file.close()




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
