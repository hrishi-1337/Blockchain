import json
import sys
import threading
import hashlib
from xmlrpc.client import ServerProxy
from xmlrpc.server import SimpleXMLRPCServer


class Miner:

    def __init__(self,):
        self.id = None
        self.host = None
        self.port = None
        self.config = None
        self.map = {}

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

    def test(self, var):
        print("Hi from Node " +str(var))

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


        ans = input()
        if ans == "1":
            for k, v in self.map.items():
                v.test(self.id)
        ans2 = input()


if __name__ == '__main__':
    miner = Miner()
    miner.main()

    