"""File-use-case composition, also used by recovery probes; no UI is constructed."""
from ..adapters.sqlite_operation_journal import SQLiteOperationJournal
from ..adapters.transaction_files import LocalTransactionFiles
from ..application.executing import Execution


def build_execution(profile, *, checkpoint=None):
    journal = SQLiteOperationJournal(profile / 'operations')
    try:
        return Execution(journal, LocalTransactionFiles(journal.buffer_root), checkpoint=checkpoint)
    except BaseException:
        journal.close()
        raise
