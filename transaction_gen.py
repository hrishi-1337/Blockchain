import random
import pickle
from pow_miner import Transaction

def main():
    transactions = []
    for i in range(1,5):
        transactions.append(Transaction(i, i, 100, True))
    for i in range(1000):
        s = random.randint(1, 4)
        r = random.randint(1, 4)
        if s != r:
            transactions.append(Transaction(s, r, random.randint(5, 30)))

    # print(transactions)

    with open('transactions.pkl', 'wb') as f:
        pickle.dump(transactions, f)


if __name__ == '__main__':
    main()
