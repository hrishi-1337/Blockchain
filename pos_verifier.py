import json
import sys
import threading
import pickle
import random
import time
from threading import Thread, Lock
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
        self.currentBlock = None
        self.currentBlockAmount = 0
        self.mutex = Lock()

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
            if len(self.blockChain) != 0:
                if self.contribution[chosen]/len(self.blockChain)  <= 0.25:
                    self.map[str(chosen)].createBlock()          
                    time.sleep(20)
                else:
                    print(f"Verifier {chosen} skipped since they have more than 25% of the blocks in the blockchain")
            else:
                self.map[str(chosen)].createBlock()          
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
                print(f"Invalid Transaction: {transaction}")
        print("Block transactions validated")
        for transaction in transactions:
            self.currentBlockAmount += transaction.amount
        creator = Transaction(int(self.id), 0, 10, True)
        block = Block(self.blockNumber, transactions, self.currentHash, creator)
        shahash = sha256(str(block).encode('utf-8')).hexdigest()
        block.selfHash = shahash
        if self.blockNumber == 1:
            block.stake = 400
        else:                            
            if int(self.id) not in self.ledger:
                self.ledger[int(self.id)]= 0 
            block.stake = self.ledger[int(self.id)]/4
            print(f"Tokens staked {block.stake}")
        self.currentBlock = block
        print("Broadcasting Block to validators")
        self.mutex.acquire()
        self.broadcastBlock(block)
        self.mutex.release()

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
                hash, id, stake = v.receiveBlock(block)
                if hash != None and isinstance(self.currentBlock, Block):
                        if self.currentBlock.selfHash == hash:
                            if id not in self.currentBlock.verifiers:
                                self.currentBlock.verifiers.append(id)
                                self.currentBlock.stake+=stake

    def deductStake(self, amount):
        self.ledger[int(self.id)]-= amount

    def receiveBlock(self, block_dict):
        flag = True
        transactions = []
        transaction_amount = 0
        for transaction in block_dict['transactions']:
            transactions.append(Transaction(transaction['sender'], transaction['receiver'], transaction['amount'], transaction['reward']))
            transaction_amount += transaction['amount']
        creator = Transaction(block_dict['creator']['sender'], block_dict['creator']['receiver'], block_dict['creator']['amount'], block_dict['creator']['reward'])
        verifier = [ v for v in block_dict['verifiers']]
        block = Block(block_dict['blockNumber'], transactions, block_dict['prevHash'], creator, block_dict['stake'], block_dict['selfHash'], verifier)
        print("Block Received")   
        print(repr(block))

        for transaction in block.transactions:
            if not self.validateTransaction(transaction):
                print(f"Invalid Transaction: {transaction}, deducting stake from Verifier {block.creator.sender}")
                self.ledger[block.creator.sender] -= block.stake
                self.map[str(block.creator.sender)].deductStake(block.stake)
                flag = False
        if flag:
            if block.stake >= transaction_amount:
                print("Received Block Verified, already has sufficient stake")
                return None, None, None
            else:                            
                if int(self.id) not in self.ledger:
                    self.ledger[int(self.id)]= 0             
                stake = self.ledger[int(self.id)]/4
                print("Recieved Block Verified")
                print(f"Transactions total: {transaction_amount}; Additional Tokens staked {block.stake}")
                return block.selfHash, int(self.id), stake
    
    def broadcastVerifiedBlock(self, block):
        for k, v, in self.map.items():
            if k != str(self.id):
                v.addBlock(block)

    def addBlock(self, block_dict):
        transactions = []
        transaction_amount = 0
        for transaction in block_dict['transactions']:
            transactions.append(Transaction(transaction['sender'], transaction['receiver'], transaction['amount'], transaction['reward']))
            transaction_amount += transaction['amount']
        creator = Transaction(block_dict['creator']['sender'], block_dict['creator']['receiver'], block_dict['creator']['amount'], block_dict['creator']['reward'])
        verifier = [ v for v in block_dict['verifiers']]
        block = Block(block_dict['blockNumber'], transactions, block_dict['prevHash'], creator, block_dict['stake'], block_dict['selfHash'], verifier)
        for i in range(4):
            self.transactionPool.pop(0)
        self.blockChain.append(block)
        self.blockNumber += 1
        self.currentHash = block.selfHash

    def checkStakeThread(self):
        thread = threading.Thread(target=self.checkStake)
        thread.daemon = True
        thread.start()
        return thread

    def checkStake(self):
        while True:
            if isinstance(self.currentBlock, Block):
                if self.currentBlock.stake >= self.currentBlockAmount:
                    self.blockChain.append(self.currentBlock)
                    self.blockNumber += 1
                    self.currentHash = self.currentBlock.selfHash
                    self.mutex.acquire()
                    self.broadcastVerifiedBlock(self.currentBlock)
                    self.mutex.release()
                    self.currentBlock = None
                    self.currentBlockAmount = 0

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
                        if transaction.sender not in self.ledger:
                            self.ledger[transaction.sender] = 0                
                        if transaction.receiver not in self.ledger:
                            self.ledger[transaction.receiver] = 0
                        if not transaction.reward:
                            self.ledger[transaction.sender] -= transaction.amount
                        self.ledger[transaction.receiver] += transaction.amount                
                    if block.creator.sender not in self.ledger:
                        self.ledger[block.creator.sender] = 0 
                    self.ledger[block.creator.sender] += block.creator.amount
                    for v in block.verifiers:
                        if v not in self.ledger:
                            self.ledger[v] = 0 
                        self.ledger[v] += 5
                    self.contribution[block.creator.sender]+=1                    
                self.ledgerIndex = len(self.blockChain)

    def displayTransactions(self):
        for block in self.blockChain:
            print("===========================")
            print(f"Block Number: {block.blockNumber}")
            for transaction in block.transactions:
                print(transaction)
            print(f"Creator: {block.creator.sender} Reward: 10")
            print(f"Verifiers: {block.verifiers} Reward: 5")
            print(f"Amount staked: {block.stake}")
        print("===========================")

    def menu(self):
        while True:
            print("Display Ledger\t\t[l]")
            print("Display Blockchain\t[b]")
            print("Display Transaction\t[t]")
            resp = input("Choice: ").lower().split()
            if not resp:
                continue
            elif resp[0] == 'l':
                print("===========================")
                print("Balance")
                for k, v in self.ledger.items():
                    print(f"{k}: {v}")                
                print("===========================")
            elif resp[0] == 'b':
                for block in self.blockChain:
                    print("===========================")
                    print(repr(block))
                print("===========================")
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
        input("Press <enter> to start verifier")
        print(f"Bully algorithm Leader Elected : Node {self.leader}")
        if self.leader == self.id:
            self.rollDiceThread()
        self.checkStakeThread()
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
    def __init__(self, blockNumber, transactions, prevHash, creator, stake=0, selfHash=None,verifiers=[]):
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
        return "Block Number:{0} Transaction_count:{1} prevHash:{2} selfHash:{3} creator: {4} verifiers: {5} stake: {6}\t" \
            .format(self.blockNumber, len(self.transactions), self.prevHash, self.selfHash, self.creator, self.verifiers, self.stake)

if __name__ == '__main__':
    miner = POSMiner()
    miner.main()