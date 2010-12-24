"""
>>> class Test:
...    def __init__(self):
...        self.foo = "bar"

by default, things are stored in a "shelf" table

>>> d = SQLiteShelf("test.sdb")

you can put multiple shelves into a single SQLite database

>>> e = SQLiteShelf("test.sdb", "othertable")

both are empty to start with

>>> print d
{}
>>> print e
{}

adding stuff is as simple as a regular dict
>>> d['a'] = "moo"
>>> e['a'] = "moo"

regular dict actions work

>>> print d['a']
moo
>>> print e['a']
moo
>>> print 'a' in d
True
>>> del d['a']
>>> print 'a' in d
False

objects can be stored in shelves

>>> t = Test()
>>> d['t'] = t
>>> print d['t'].foo
bar
"""

from UserDict import DictMixin
import cPickle
import sqlite3
 
class SQLiteDict(DictMixin):
    # MyDict only needs to implement getitem, setitem, delitem and keys (at a 
    # minimum) and UserDict will provide the rest of the standard dictionary
    # methods based on these four.
    #
    # getitem and delitem should raise KeyError if no item exists for the given
    # key. getitem, setitem and delitem should raise TypeError if the given key
    # is of the wrong type.
    def __init__(self, filename=':memory:', table='shelf', flags='r', mode=None):
        self.table = table
        MAKE_SHELF = 'CREATE TABLE IF NOT EXISTS '+self.table+' (key TEXT, value TEXT)'
        MAKE_INDEX = 'CREATE UNIQUE INDEX IF NOT EXISTS '+self.table+'_keyndx ON '+self.table+'(key)'
        self.conn = sqlite3.connect(filename)
        self.conn.text_factory = str
        self.conn.execute(MAKE_SHELF)
        self.conn.execute(MAKE_INDEX)
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
        self.conn.commit()
 
    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        DEL_ITEM = 'DELETE FROM '+self.table+' WHERE key = ?'       
        self.conn.execute(DEL_ITEM, (key,))
        self.conn.commit()
 
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

class SQLiteShelf(SQLiteDict):
    def __getitem__(self, key):
        return cPickle.loads(SQLiteDict.__getitem__(self, key))
 
    def __setitem__(self, key, item):
        SQLiteDict.__setitem__(self, key, cPickle.dumps(item))
