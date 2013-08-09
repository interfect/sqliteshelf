"""
by default, things are stored in a "shelf" table

>>> d = SQLiteShelf("test.sdb")

you can put multiple shelves into a single SQLite database

>>> e = SQLiteShelf("test.sdb", "othertable")

both are empty to start with

>>> d
{}
>>> e
{}

adding stuff is as simple as a regular dict
>>> d['a'] = "moo"
>>> e['a'] = "moo"

regular dict actions work

>>> d['a']
'moo'
>>> e['a']
'moo'
>>> 'a' in d
True
>>> len(d)
1
>>> del d['a']
>>> 'a' in d
False
>>> len(d)
0
>>> del e['a']

objects can be stored in shelves

>> class Test:
..    def __init__(self):
..        self.foo = "bar"
..
>> t = Test()
>> d['t'] = t
>> print d['t'].foo
bar

errors are as normal for a dict

>>> d['x']
Traceback (most recent call last):
    ...
KeyError: 'x'
>>> del d['x']
Traceback (most recent call last):
    ...
KeyError: 'x'
"""

try:
    from UserDict import DictMixin
except ImportError:
    from collections import MutableMapping as DictMixin

try:
    import cPickle as pickle
except ImportError:
    import pickle

import sqlite3, threading

class SQLiteDict(DictMixin):
    def __init__(self, filename=':memory:', table='shelf', flags='r', mode=None, lazy=False):
        """
        Make a new SQLite-backed dict that holds strings. filename specifies the
        file to use; by default a special filename of ":memory:" is used to keep
        all data in memory. table specifies the name of the table to use;
        multiple tables can be used in the same file at the same time. flags and
        mode exist to match the shelve module's interface and are ignored. By
        default, data is saved to disk after every operation; passing lazy=True
        will require you to call the sync() and close() methods for changes to
        be guaranteed to make it to disk.
        
        Note that this object is not thread safe. It is willing to be used by
        multiple threads, but access should be controlled by a lock.
        
        """
        
        self.table = table
        self.lazy = lazy 
        MAKE_SHELF = 'CREATE TABLE IF NOT EXISTS '+self.table+' (key TEXT, value TEXT)'
        MAKE_INDEX = 'CREATE UNIQUE INDEX IF NOT EXISTS '+self.table+'_keyndx ON '+self.table+'(key)'
        self.conn = sqlite3.connect(filename, check_same_thread=False)
        self.conn.text_factory = str
        self.conn.execute(MAKE_SHELF)
        self.conn.execute(MAKE_INDEX)
        self.maybe_sync()

    def maybe_sync(self):
        """
        Sync to disk if this SqliteDict is not lazy.
        
        """

        if not self.lazy:
            # We're not lazy. Commit now!
            self.conn.commit()
            
    def sync(self):
        """
        Sync to disk. Finishes any internal sqlite transactions.
        
        """
        self.conn.commit()
            
    def __getitem__(self, key):
        GET_ITEM = 'SELECT value FROM '+self.table+' WHERE key = ?'
        item = self.conn.execute(GET_ITEM, (key,)).fetchone()
        if item is None:
            raise KeyError(key)
        return item[0]

    def __setitem__(self, key, item):
        ADD_ITEM = 'REPLACE INTO '+self.table+' (key, value) VALUES (?,?)'
        self.conn.execute(ADD_ITEM, (key, item))
        self.maybe_sync()

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        DEL_ITEM = 'DELETE FROM '+self.table+' WHERE key = ?'
        self.conn.execute(DEL_ITEM, (key,))
        self.maybe_sync()

    def __iter__(self):
        c = self.conn.cursor()
        try:
            c.execute('SELECT key FROM '+self.table+' ORDER BY key')
            for row in c:
                yield row[0]
        finally:
            c.close()

    def keys(self):
        c = self.conn.cursor()
        try:
            c.execute('SELECT key FROM '+self.table+' ORDER BY key')
            return [row[0] for row in c]
        finally:
            c.close()

    ###################################################################
    # optional bits

    def __len__(self):
        GET_LEN =  'SELECT COUNT(*) FROM '+self.table
        return self.conn.execute(GET_LEN).fetchone()[0]

    def close(self):
        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def __del__(self):
        self.close()

    def __repr__(self):
        return repr(dict(self))

class SQLiteShelf(SQLiteDict):
    def __getitem__(self, key):
        return pickle.loads(SQLiteDict.__getitem__(self, key))

    def __setitem__(self, key, item):
        SQLiteDict.__setitem__(self, key, pickle.dumps(item))

if __name__ == "__main__":
    import doctest
    doctest.testmod()
