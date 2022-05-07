import json
import sys
import threading
import pickle
import random
import time
from hashlib import sha256
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer


class POWMiner:
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
        self.currentHash = 000000000
        self.mineBreak = False

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
        while True:
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
            minedBlock = self.hasher(transactions)
            if isinstance(minedBlock, Block):
                self.blockChain.append(minedBlock)
                self.blockNumber += 1
                self.currentHash = minedBlock.selfHash
                self.broadcastBlock(minedBlock)
            else:
                pass

    def validateTransaction(self, transaction):
        if transaction.sender not in self.ledger:
            self.ledger[transaction.sender] = 0
        if (self.ledger[transaction.sender] >=  transaction.amount) or transaction.reward:
            return True
        else:
            return False

    def hasher(self, transactions):
        shahash = "aa"
        print("Mining a Block")
        while shahash[:2] != "00":
            nonce = random.randint(0, 100000)
            block = Block(self.blockNumber, transactions, self.currentHash, nonce)
            shahash = sha256(str(block).encode('utf-8')).hexdigest()
            time.sleep(0.25)
            if self.mineBreak:
                self.mineBreak = False
                print("Mining next block")
                return False
            if shahash[:2] == "00":
                print("Block Mined!")
                print(f"nonce: {nonce};  sha: {shahash}")
                block.selfHash = shahash
                reward = Transaction(int(self.id), 0, 10, True)
                block.coinbase = reward
                return block

    def broadcastBlock(self, block):
        for k, v, in self.map.items():
            if k != str(self.id):
                v.receiveBlock(block)
  
    def receiveBlock(self, block_dict):
        flag = True
        transactions = []
        for transaction in block_dict['transactions']:
            transactions.append(Transaction(transaction['sender'], transaction['receiver'], transaction['amount'], transaction['reward']))
        coinbase = Transaction(block_dict['coinbase']['sender'], block_dict['coinbase']['receiver'], block_dict['coinbase']['amount'], block_dict['coinbase']['reward'])
        block = Block(block_dict['blockNumber'], transactions, block_dict['prevHash'], block_dict['nonce'], block_dict['selfHash'], coinbase)
        print("Block Received")
        print(block)
        if  block.prevHash != self.currentHash:
            print(f"Block doesnt match current chain. Current hash: {self.currentHash};  Block prevHash: {block.prevHash}")
            flag = False
        else:
            for transaction in block.transactions:
                if not self.validateTransaction(transaction):
                    print(f"Invalid Transaction: {transaction}")
                    flag = False
        if flag:
            print("Recived Block Validate and Added")
            self.blockChain.append(block)
            self.blockNumber += 1
            self.currentHash = block.selfHash
            self.mineBreak = True

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
            print("===========================")
            print(f"Block Number: {block.blockNumber}")
            for transaction in block.transactions:
                print(transaction)
            print(f"Miner Reward: {block.coinbase}")

    def menu(self):
        while True:
            print("Display Ledger\t\t[l]")
            print("Display Blockchain\t[b]")
            print("Display Transactions\t[t]")
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
        self.updateLedgerThread()
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
    def __init__(self, blockNumber, transactions, prevHash, nonce, selfHash=None, coinbase=None):
        self.blockNumber = blockNumber
        self.transactions = transactions
        self.prevHash = prevHash
        self.nonce = nonce
        self.selfHash = selfHash
        self.coinbase = coinbase

    def __str__(self):
        return "Block Number:{0} Nonce:{1} Transactions:{2} prevHash:{3} \t".format(self.blockNumber, self.nonce, self.transactions, self.prevHash)

    def __repr__(self):
        return "Block Number:{0} Nonce:{1} Transaction_count:{2} prevHash:{3} selfHash:{4} Coinbase: {5}\t" \
            .format(self.blockNumber, self.nonce, len(self.transactions), self.prevHash, self.selfHash, self.coinbase)

if __name__ == '__main__':
    miner = POWMiner()
    miner.main()

    