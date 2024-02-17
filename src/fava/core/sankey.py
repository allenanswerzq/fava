
from beancount.core.inventory import Inventory
from beancount.core.realization import realize, RealAccount, iter_children, compute_balance

from typing import NamedTuple, Any
from beancount.core.number import Decimal
from fava.core.conversion import *
from fava.core.conversion import *

SankeyTreeEdge = NamedTuple(
    'SankeyTreeEdge', [
        ('u', str),
        ('v', str),
        ('weight', float), # TODO: multiple currencies support
        ('child', RealAccount),
        ('collapsed', bool)])

class SankeyTree:
    """
    """
    def __init__(self, txns, prune=None, collapse=None, finalize=None, 
                 conversion=None, price_map=None):
        self.txns_ = txns
        self.root_ = realize(self.txns_, compute_balance=True)
        children = iter_children(self.root_)
        for child in children:
            child.balance = compute_balance(child)

        self.prune_ = prune or SankeyTree.prune_default
        self.collapse_ = collapse or SankeyTree.collapse_default
        self.finalize_ = finalize or SankeyTree.finalize_default
        self.conversion = conversion
        self.price_map = price_map

        self.name_id_ = dict()
        self.id_name_ = dict()
        self.balance_map_ = dict()

        self.links_ = list()
        self.nodes_ = set()
    
    def inv_to_dict(self, inventory: Inventory) -> dict[str, Decimal]:
        """Convert an inventory to a simple cost->number dict."""
        return {
            pos.units.currency: pos.units.number
            for pos in inventory
            if pos.units.number is not None
        }

    def get_balance(self, real_account):
        inventory = None
        account = None
        if isinstance(real_account, tuple):
            account = real_account[0]
            inventory = real_account[1].balance
        elif isinstance(real_account, RealAccount):
            account = real_account.account
            inventory = real_account.balance
        else:
            assert False

        balance = self.inv_to_dict(
            cost_or_value(inventory, self.conversion, self.price_map)
        )

        if not inventory.is_empty():
            print('\n\n------------------------------')
            print(account)
            print(inventory)
            print(balance)

        if len(balance) == 0:
            return 0
        elif self.conversion in balance:
            return balance[self.conversion]
        else:
            assert False, inventory
        

    @staticmethod
    def prune_default(edge: SankeyTreeEdge) -> bool:
        return False

    @staticmethod
    def collapse_default(edge: SankeyTreeEdge) -> bool:
        return False

    @staticmethod
    def finalize_default(tree):
        return dict()

    def add_fake_income(self):
        edge = SankeyTreeEdge("Income", "Income:Fake", 0.1, None, False)
        self.add_results(0, 10, edge)

    def add_fake_expenses(self):
        edge = SankeyTreeEdge("Expenses", "Expenses:Fake", 0.1, None, False)
        self.add_results(0, 10, edge)

    def encode_name(self, id : float, account : str):
        return str(id) + "_" + account

    def encode_weight(self, weight, collapsed):
        if collapsed:
            return str(weight) + " " + "collapsed"
        return str(weight)

    def add_results(self, id, nid, edge: SankeyTreeEdge):
        u = self.encode_name(id, edge.u)
        v = self.encode_name(nid, edge.v)

        if "Income" in u or "Asset" in u:
            u, v = v, u

        if len(edge.u) == 0:
            # NOTE: we do NOT add root edges
            return
        
        if edge.u == "Liabilities":
            return

        w = self.encode_weight(edge.weight, edge.collapsed)

        self.nodes_.add(u)
        self.nodes_.add(v)
        self.links_.append([u, v, w])
    
    def sortkey_balance(self, real_account):
        if isinstance(real_account, tuple):
            account = real_account[0]
        elif isinstance(real_account, RealAccount):
            account = real_account.account
        else:
            assert False

        if 'Income:' in account:
            return -self.get_balance(real_account)
        else:
            return self.get_balance(real_account)

    def dfs(self, real_account: RealAccount, parent=None, id=100, collapsed=False) -> None:
        self.name_id_[real_account.account] = id
        self.id_name_[id] = real_account.account
        i = 0
        for k, child in sorted(real_account.items(), key=self.sortkey_balance, reverse='Income' not in real_account.account):
            # k is a str looks like: Assets:Current:Bank
            assert isinstance(child, RealAccount)
            weight = self.get_balance(child)
            self.balance_map_[child.account] = weight
            edge = SankeyTreeEdge(real_account.account, child.account, weight, child, collapsed)

            # Prune out edges first
            # NOTE: we do not swap direction here
            if self.prune_(edge): continue

            # Collapse edge if possiable
            edge = self.collapse_(edge)

            # Assign new id
            nid = id * 100 + i
            i += 1

            self.add_results(id, nid, edge)

            self.dfs(child, parent=real_account, id=nid, collapsed=edge.collapsed)

    def run(self):
        self.dfs(self.root_)

        if self.finalize_:
            return self.finalize_(self)

        return dict()


def test_basic():
    raw = """
2022-08-31 * "test income to asset"
    Assets:CurrentAssets:Bank:BoA      100 CNY
    Income:Google:Salary  -100 CNY

2022-09-19 * "test asset to expense"
    Asset:PrepaidRent     -100.00 CNY
    Expenses:Housing:Rent   100.00 CNY

2022-12-30 * "test liabilities to expense"
    Liabilities:Current:CreditCard-CMB  -43.97 CNY
    Expenses:Food:Shop           43.97 CNY
"""
    from beancount.loader import load_string
    entries, errors, options_map = load_string(raw)
    assert len(entries) == 3

    tree = SankeyTree(entries)
    data = tree.run()
    assert len(data) == 0

    def finalize(tree):
        for x in tree.links_:
            print(x)
        return (tree.nodes_, tree.links_)

    tree = SankeyTree(entries, finalize=finalize)
    data = tree.run()
    assert len(data) > 0


def test_prune_collapse():
    raw = """
2022-08-31 * "test income to asset"
    Assets:CurrentAssets:Bank:BoA      100 CNY
    Income:Google:Salary  -100 CNY

2022-09-19 * "test asset to expense"
    Asset:PrepaidRent     -100.00 CNY
    Expenses:Housing:Rent   100.00 CNY

2022-12-30 * "test liabilities to expense"
    Liabilities:Current:CreditCard-CMB  -43.97 CNY
    Expenses:Food:Shop           43.97 CNY
"""
    from beancount.loader import load_string
    entries, errors, options_map = load_string(raw)
    assert len(entries) == 3

    def finalize(tree):
        for x in tree.links_:
            print(x)
        return (tree.nodes_, tree.links_)

    def prune(edge: SankeyTreeEdge):
        # For income statement
        if len(edge.u) == 0:
            # prune out edge not from root -> income/expenses
            return edge.v not in ("Income", "Expenses")

        return False

    def collapse(edge: SankeyTreeEdge):
        if len(edge.v.split(":")) >= 3:
            return True
        return False

    tree = SankeyTree(entries, finalize=finalize, prune=prune, collapse=collapse)
    data = tree.run()
    assert len(data) > 0



if __name__ == "__main__":
    # test_basic()
    test_prune_collapse()