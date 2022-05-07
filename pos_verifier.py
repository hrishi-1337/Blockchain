import json
import sys
import threading
import pickle
import random
import time
from hashlib import sha256
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer


class POSMiner:
    def __init__(self):
        self.id = None
        self.host = None
        self.port = None
        self.config = None
        self.map = {}
        self.blockChain = []
        self.ledger = {}
        self.ledgerIndex = 0
        self.transactionPool = []
        self.blockNumber = 1
        self.leader = None
        self.currentHash = 000000000
        self.contribution = {}

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
            self.contribution[int(k)] = 0
        print("Map: " +str(self.map))

    def rollDiceThread(self):
        thread = threading.Thread(target=self.rollDice)
        thread.daemon = True
        thread.start()
        return thread

    def rollDice(self):
        node_count = len(self.map.keys())
        while True:
            chosen = random.randint(1, node_count)
            print(f"Verifier {chosen} chosen to create block")
            if self.contribution[chosen] <= 25:
                self.map[str(chosen)].createBlock()
            else:
                pass           
            time.sleep(20)
            
    def createBlock(self):
        print(f"Chosen to create block by Leader node {self.leader}")
        transactions = []
        while len(transactions) < 4:
            transaction = self.transactionPool.pop(0)
            if self.validateTransaction(transaction):
                transactions.append(transaction)
                # print("Valid Transaction")
            else:
                # print("Invalid Transaction")
                pass
        print("Block transactions validated")
        reward = Transaction(int(self.id), 0, 10, True)
        block = Block(self.blockNumber, transactions, self.currentHash, reward)
        shahash = sha256(str(block).encode('utf-8')).hexdigest()
        block.selfHash = shahash
        self.broadcastBlock(block)

    def validateTransaction(self, transaction):
        if transaction.sender not in self.ledger:
            self.ledger[transaction.sender] = 0
        if (self.ledger[transaction.sender] >=  transaction.amount) or transaction.reward:
            return True
        else:
            return False

    def broadcastBlock(self, block):
        for k, v, in self.map.items():
            if k != str(self.id):
                v.receiveBlock(block)

    def receiveVote(self):
        pass
 
    def receiveBlock(self, block_dict):
        flag = True
        transactions = []
        for transaction in block_dict['transactions']:
            transactions.append(Transaction(transaction['sender'], transaction['receiver'], transaction['amount'], transaction['reward']))
        creator = Transaction(block_dict['creator']['sender'], block_dict['creator']['receiver'], block_dict['creator']['amount'], block_dict['creator']['reward'])
        verifier = [ v for v in block_dict['verifiers']]
        block = Block(block_dict['blockNumber'], transactions, block_dict['prevHash'], creator, block_dict['stake'], block_dict['selfHash'], verifier)
        
        
        # print("Block Received")
        # print(block)
        # if  block.prevHash != self.currentHash:
        #     print(f"Block doesnt match current chain. Current hash: {self.currentHash};  Block prevHash: {block.prevHash}")
        #     flag = False
        # else:
        #     for transaction in block.transactions:
        #         if not self.validateTransaction(transaction):
        #             print(f"Invalid Transaction: {transaction}")
        #             flag = False
        # if flag:
        #     print("Recived Block Added")
        #     self.blockChain.append(block)
        #     self.blockNumber += 1
        #     self.currentHash = block.selfHash

    def updateLedgerThread(self):
        thread = threading.Thread(target=self.updateLedger)
        thread.daemon = True
        thread.start()
        return thread

    def updateLedger(self):
        while True:
            if self.ledgerIndex < len(self.blockChain):
                for block in self.blockChain[self.ledgerIndex:]:
                    for transaction in block.transactions:
                        if not transaction.reward:
                            self.ledger[transaction.sender] -= transaction.amount
                        self.ledger[transaction.receiver] += transaction.amount
                    self.ledger[block.coinbase.sender] += block.coinbase.amount
                self.ledgerIndex = len(self.blockChain)

    def displayTransactions(self):
        for block in self.blockChain:
            for transaction in block.transactions:
                print(transaction)

    def menu(self):
        while True:
            print("Display Ledger\t\t[l]")
            print("Display Blockchain\t[b]")
            print("Display Transaction\t[t]")
            resp = input("Choice: ").lower().split()
            if not resp:
                continue
            elif resp[0] == 'l':
                print(self.ledger)
            elif resp[0] == 'b':
                print(self.blockChain)
            elif resp[0] == 't':
                self.displayTransactions()
            elif resp[0] == 'e':
                exit(0)

    def main(self):        
        if len(sys.argv) > 1:
            self.id = sys.argv[1]

        print("Node number : " +self.id)
        with open("local_config_2.json", "r") as jsonfile:
            self.config = json.load(jsonfile)
            self.host = self.config[self.id][0]
            self.port = self.config[self.id][1]

        self.createRPCServer()
        self.createProxyMap()
        with open('transactions.pkl', 'rb') as f:
            self.transactionPool = pickle.load(f)
        if self.leader == None:
            self.leader = max(self.map.keys())
        print(f"Leader Elected : {self.leader}")
        input("Press <enter> to start miner")
        if self.leader == self.id:
            self.rollDiceThread()
        # self.updateLedgerThread()
        self.menu()


class Transaction:
    def __init__(self, sender, receiver, amount, reward=False):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.reward = reward

    def __repr__(self):
        return "Sender: {0} Receiver: {1} Amount: {2}\t".format(self.sender, self.receiver, self.amount)


class Block:
    def __init__(self, blockNumber, transactions, prevHash, creator, stake, selfHash=None,verifiers=[]):
        self.blockNumber = blockNumber
        self.transactions = transactions
        self.prevHash = prevHash
        self.selfHash = selfHash
        self.creator = creator
        self.verifiers = verifiers
        self.stake = stake

    def __str__(self):
        return "Block Number:{0} Transactions:{1} prevHash:{2}\t".format(self.blockNumber, self.transactions, self.prevHash)

    def __repr__(self):
        return "Block Number:{0} Transaction_count:{1} prevHash:{2} selfHash:{3} creator: {4} verifiers: {5}\t" \
            .format(self.blockNumber, len(self.transactions), self.prevHash, self.selfHash, self.creator, self.verifiers)

if __name__ == '__main__':
    miner = POSMiner()
    miner.main()

    