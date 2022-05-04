import json
import sys
import threading
import pickle
import random
import time
from hashlib import sha256
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer


class Miner:

    def __init__(self):
        self.id = None
        self.host = None
        self.port = None
        self.config = None
        self.map = {}
        self.blockChain = []
        self.ledger = {}
        self.chainLength = 0
        self.transactionPool = []
        self.blockNumber = 0
        self.prevHash = 000000000
        self.currentHash = None

    def createRPCServer(self):
        print("Creating the RPC server for the Node {0}".format(self.id))
        print("Node {0} IP:{1} port: {2}".format(self.id, self.host, self.port))
        thread = threading.Thread(target=self._executeRPCServer)
        thread.daemon = True
        thread.start()
        return thread

    def _executeRPCServer(self):
        server = SimpleXMLRPCServer((self.host, self.port), logRequests=True, allow_none=True)
        server.register_instance(self)
        try:
            print("Accepting connections..")
            server.serve_forever()
        except KeyboardInterrupt:
            print("Exiting")

    def createProxyMap(self):
        for k, v in self.config.items():
            uri = r"http://" + v[0] + ":" + str(v[1])
            self.map[k] = ServerProxy(uri, allow_none=True)
        print("Map: " +str(self.map))

    def createMineThread(self):
        thread = threading.Thread(target=self.mineBlocks)
        thread.daemon = True
        thread.start()
        return thread

    def mineBlocks(self):
        transactions = [self.transactionPool.pop(0) for i in range(5)]
        self.validateTransactions(transactions)
        minedBlock = self.hasher(transactions)
        self.blockChain.append(minedBlock)
        self.broadcastBlock(minedBlock)


    def hasher(self, transactions):
        shahash = "aa"
        while shahash[:2] != "00":
            nonce = random.randint(0, 100000)
            block = Block(self.blockNumber, transactions, self.prevHash, nonce)
            shahash = sha256(str(block).encode('utf-8')).hexdigest()
            time.sleep(0.25)
            print(f"nonce: {nonce}")
            print(f"sha: {shahash}")
            if shahash[:2] == "00":
                block.selfHash = shahash
                return block


    def addBlock(self):
        pass

    def validateTransactions(self, transactions):
        pass

    def broadcastBlock(block):
        pass

    def menu(self):
        while True:
            print("Print log\t[p]")
            resp = input("Choice: ").lower().split()
            if not resp:
                continue
            elif resp[0] == 'r':
                self._diagnostics()
            elif resp[0] == 'p':
                self.printLog()
            elif resp[0] == 'e':
                exit(0)

    def main(self):        
        if len(sys.argv) > 1:
            self.id = sys.argv[1]

        print("Node number : " +self.id)
        with open("local_config.json", "r") as jsonfile:
            self.config = json.load(jsonfile)
            self.host = self.config[self.id][0]
            self.port = self.config[self.id][1]

        self.createRPCServer()
        self.createProxyMap()
        with open('transactions.pkl', 'rb') as f:
            self.transactionPool = pickle.load(f)
        input("Press <enter> to start miner")
        self.createMineThread()
        self.menu()


class Transaction:
    def __init__(self, sender, receiver, amount, reward=False):
        self.sender = sender
        self.reciever = receiver
        self.amount = amount
        self.reward = reward

    def __repr__(self):
        return "Sender: {0} Receiver: {1} Amount: {2}\t".format(self.sender, self.reciever, self.amount)


class Block:
    def __init__(self, blockNumber, transactions, prevHash, nonce):
        self.blockNumber = blockNumber
        self.transactions = transactions
        self.prevHash = prevHash
        self.nonce = nonce
        self.selfHash = None

    def __str__(self):
        return "Block Number:{0} Nonce:{1} Transactions:{2} prevHash:{3} \t".format(self.blockNumber, self.nonce, self.transactions, self.prevHash)


if __name__ == '__main__':
    miner = Miner()
    miner.main()

    