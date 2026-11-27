"""Composed, compatible v1 case store with operations + signed receipt tables."""
from .operations import OperationsStore
from .revenue import ReceiptStore

class PlatformStore(OperationsStore, ReceiptStore):
    pass
