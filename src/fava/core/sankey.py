
from beancount.core.inventory import Inventory
from beancount.core.realization import realize, RealAccount, iter_children, compute_balance

from typing import NamedTuple, Any

SankeyTreeEdge = NamedTuple(
    'SankeyTreeEdge', [
        ('u', str),
        ('v', str),
        ('weight', float), # TODO: multiple currencies support
        ('child', RealAccount)])

class SankeyTree:
    """
    """
    def __init__(self, txns, prune=None, collapse=None, finalize=None):
        self.txns_ = txns
        self.root_ = realize(self.txns_, compute_balance=True)
        children = iter_children(self.root_)
        for child in children:
            child.balance = compute_balance(child)

        self.prune_ = prune or SankeyTree.prune_default
        self.collapse_ = collapse or SankeyTree.collapse_default
        self.finalize_ = finalize or SankeyTree.finalize_default

        self.name_id_ = dict()
        self.id_name_ = dict()
        self.balance_map_ = dict()

        self.links_ = list()
        self.nodes_ = set()

    @staticmethod
    def get_balance(real_account):
        if isinstance(real_account, tuple):
            # (key, value)
            # print(real_account[0], real_account[1].balance)
            return abs(real_account[1].balance.get_currency_units("CNY").number)
        elif isinstance(real_account, RealAccount):
            # print(real_account.account, real_account.balance)
            return abs(real_account.balance.get_currency_units("CNY").number)
        else:
            assert False


    @staticmethod
    def prune_default(edge: SankeyTreeEdge) -> bool:
        return False

    @staticmethod
    def collapse_default(edge: SankeyTreeEdge) -> bool:
        return False

    @staticmethod
    def finalize_default(tree):
        return dict()

    def encode_name(self, id : float, account : str):
        return str(id) + "_" + account

    def add_results(self, id, nid, edge: SankeyTreeEdge):
        u = self.encode_name(id, edge.u)
        v = self.encode_name(nid, edge.v)

        if "Income" in u or "Asset" in u:
            u, v = v, u

        elif len(edge.u) == 0:
            # NOTE: we do NOT add root edges
            return

        w = str(edge.weight)

        self.nodes_.add(u)
        self.nodes_.add(v)
        self.links_.append([u, v, w])

    def dfs(self, real_account: RealAccount, parent=None, id=100) -> None:
        self.name_id_[real_account.account] = id
        self.id_name_[id] = real_account.account
        i = 0
        for k, child in sorted(real_account.items(), key=SankeyTree.get_balance, reverse=True):
            # k is a str looks like: Assets:Current:Bank
            assert isinstance(child, RealAccount)
            weight = SankeyTree.get_balance(child)
            self.balance_map_[child.account] = weight
            edge = SankeyTreeEdge(real_account.account, child.account, weight, child)

            # Prune out edges first, NOTE: we do not swap direction here
            # TODO: handle number mismatch issue caused by pruning edges.
            if self.prune_(edge): continue

            # Collapse edge if possiable
            if self.collapse_(edge): continue

            # Assign new id
            nid = id * 100 + i
            i += 1

            self.add_results(id, nid, edge)

            self.dfs(child, parent=real_account, id=nid)

    def run(self):
        self.dfs(self.root_)

        if self.finalize_:
            return self.finalize_(self)

        return dict()


def test_basic():
    raw = """
2022-08-31 * "test income to asset"
    Assets:Bank:BoA      100 CNY
    Income:Google:Salary  -100 CNY

2022-09-19 * "test asset to expense"
    Asset:PrepaidRent     -100.00 CNY
    Expenses:Housing:Rent   100.00 CNY

2022-12-30 * "test liabilities to expense"
    Liabilities:CreditCard:CMB  -43.97 CNY
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
    Assets:Bank:BoA      100 CNY
    Income:Google:Salary  -100 CNY

2022-09-19 * "test asset to expense"
    Asset:PrepaidRent     -100.00 CNY
    Expenses:Housing:Rent   100.00 CNY

2022-12-30 * "test liabilities to expense"
    Liabilities:CreditCard:CMB  -43.97 CNY
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