# Chord-DHT-for-File-Sharing

Distributed Hash Table based File Sharing System using Chord protocol

## Background

Chord is a distributed lookup protocol that can be used for peer-to-peer (p2p) file sharing. Chord distributes objects over a dynamic network of nodes, and implements a protocol for finding these objects once they have been placed in the network. Data location is implemented on top of Chord by associating a key with each data item, and storing the key/data item pair at the node to which the key maps. Every node in this network is a server capable of looking up keys for client applications, but also participates as key store. Moreover, chord adapts efficiently as nodes join and leave the system, and can answer queries even if the system is continuously changing. Hence, Chord is a decentralized system in which no particular node is necessarily a performance bottleneck or a single point of failure.

### Keys

Every key (based on the name of a file) inserted into the DHT is hashed to fit into the keyspace supported by the particular implementation of Chord. The keyspace (the range of possible hashes), in this implementation resides between 0 and 2<sup>m</sup>-1 inclusive where m = 10 (denoted by MAX_BITS in the code). So the keyspace is between 0 and 1023.

### 'Ring' of Nodes

Just as each key that is inserted into the DHT has hash value, each node in the system also has a hash value in the keyspace of the DHT. To get this hash value, we simply use the hash of the combination of IP and port, using the same hashing algorithm we use to hash keys inserted into the DHT. Chord orders the node in a circular fashion, in which each node's successor is the node with the next highest hash. The node with the largest hash, however, has the node with the smallest hash as its successor. It is easy to imagine the nodes placed in a ring, where each node's successor is the node after it when following a clockwise rotation.

### Chord Overlay

Chord makes it possible to look up any particular key in log(n) time. Chord employs a clever overlay network that, when the topology of the network is stable, routes requests to the successor of a particular key in log(n) time, where n is the number of nodes in the network. This optimized search for successors is made possible by maintaining a finger table at each node. The number of entries in the finger table is equal to m (denoted by MAX_BITS in the code).

### Failure Resilience

The Chord supports uninformed disconnection/failure of Nodes by continously pinging its successor Node. On detecting failed Node, the Chord will self stabilize. Files in the network are also replicated to the successor Node, so in case a Node goes down while another Node is downloading from it, the latter Node will be redirected to its successor.

## Node.py Program

Since this is a decentralized system, there are no separate server and client scripts. Instead each Node.py script acts as both a server and a client therefore allowing p2p connections to other Nodes.
Any Node can join the network but initially it must know the IP and Port of another Node that is already part of the Chord network.

To Node.py requires command line arguments in the form:  python Node.py *IP* *Port*  
For example:
```python Node.py 127.0.0.1 5000```

All subsequent Nodes also start in the same way.  
**Remember**: A Node can have the same IP as another, but not the same IP **and** same Port.

### Example to Get Started

**Disclaimer**: The IP and Port numbers are just for illustration. You can use a different combination.

The first Node of the Chord network will be initialized in same way as stated above.  
To reiterate, we begin in the Node.py directory and run the command:  
```python Node.py 127.0.0.1 5000```  
Lets call this Node 1 for this example.

You start one or more subsequent Nodes in the same way by providing each with an IP Port combination. Lets call them Node 2, Node 3 and so on.

When the nodes start, you will be displayed with a number of options:

### Join

Now you can connect one Node to another in any way. Once you choose to join the network, you can use any other's Node's IP Port combination to join the network. If you go to Node 2, choose join network and type in Node 1's IP Port. Both Node 1 and Node will be now be joined and part of the network. Similarly, other Nodes can join.

### Leave

Nodes can leave the network by informing the Chord and hence other Nodes of its departure.
Note: The Chord also supports uninformed disconnection/failure of nodes, however informed leaving is still preferred.

### Upload and Download File

Type the name of the file present in the same directory. Uploading file will send the file to the relevant Node based on hash of filename. Downloading will be done from the relevant Node with the file.
Chord supports large file transfer by sending file in chunks (based on buffer size).

##### Improvements/Issues:

* A need of 'successors list', in addition to the fingertable implemented, to have better failure resilience. Right now, the Chord may fail when two or more consecutive Nodes leave before the Chord has time to stabilize.
* Files are duplicated only once when they are uploaded. After a Node leaves (uninformed), its uploaded files are no longer duplicated.

**Disclaimer**: The work is still in progress and may have issues other than those mentioned above.
