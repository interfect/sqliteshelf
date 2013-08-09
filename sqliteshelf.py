"""
By default, things are stored in a "shelf" table

>>> d = SQLiteShelf("test.sdb")

You can put multiple shelves into a single SQLite database. Some can be lazy.

>>> e = SQLiteShelf("test.sdb", "othertable", lazy=True)

Both are empty to start with.

>>> d
{}
>>> e
{}

Adding stuff is as simple as a regular dict.
>>> d['a'] = "moo"
>>> e['a'] = "moo"

Regular dict actions work.

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

Lazy shelves should be synced to disk, but accesses to non-lazy shelves in the
same database can happen just fine (and will actually do the same thing
internally).

>>> e['thing'] = "stuff"
>>> d['stuff'] = "thing"
>>> e['otherthing'] = "more stuff"
>>> e.sync()

Objects can be stored in shelves.

>> class Test:
..    def __init__(self):
..        self.foo = "bar"
..
>> t = Test()
>> d['t'] = t
>> print d['t'].foo
bar

Errors are as normal for a dict.

>>> d['x']
Traceback (most recent call last):
    ...
KeyError: 'x'
>>> del d['x']
Traceback (most recent call last):
    ...
KeyError: 'x'

When you're done, you probably want to close your shelves, which will sync lazy
shelves to disk.

>>> d.close()
>>> e.close()

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
        multiple tables can be used in the same file at the same time; they will
        share the same underlying database connection. flags and mode exist to
        match the shelve module's interface and are ignored. By default, data is
        saved to disk after every operation; passing lazy=True will require you
        to call the sync() and close() methods for changes to be guaranteed to
        make it to disk.
        
        Note that this object is not thread safe. It is willing to be used by
        multiple threads, but access should be controlled by a lock. If multiple
        SqliteDicts are using different tables in the same database, they all
        should be controlled by the same lock.
        
        """
        
        self.filename = filename
        self.table = table
        self.lazy = lazy 
        MAKE_SHELF = 'CREATE TABLE IF NOT EXISTS '+self.table+' (key TEXT, value TEXT)'
        MAKE_INDEX = 'CREATE UNIQUE INDEX IF NOT EXISTS '+self.table+'_keyndx ON '+self.table+'(key)'
        self.conn = SQLiteDict.get_connection(filename)
        self.conn.text_factory = str
        self.conn.execute(MAKE_SHELF)
        self.conn.execute(MAKE_INDEX)
        self.maybe_sync()

    # This is the database connection cache
    connection_cache = {}
    
    # This is the reference counts for connections by filename.
    connection_references = {}

    @staticmethod
    def get_connection(filename):
        """
        Since we can't have transactions from more than one connection happening
        at the same time, but we may want to have more than one SqliteDict
        accessing the same database (on different tables) when some of them are
        lazy. Thus, we need to share database connections, stored by file name.
        
        This function gets the database connection to use for a given database
        filename.
        
        """
        
        if not SQLiteDict.connection_cache.has_key(filename):
            # We need to make the connection
            SQLiteDict.connection_cache[filename] = sqlite3.connect(filename, check_same_thread=False)
            # It starts with no references
            SQLiteDict.connection_references[filename] = 0
            
        # Add a reference so we can close the connection when all the shelves close.
        SQLiteDict.connection_references[filename] += 1
            
        # Use the cached connection.
        return SQLiteDict.connection_cache[filename]
        
    @staticmethod
    def drop_connection(filename):
        """
        Drop a reference to the given database. If the database now has no
        references, close its connection.
        
        """
        
        SQLiteDict.connection_references[filename] -= 1
        
        if SQLiteDict.connection_references[filename] == 0:
            # We can get rid of this connection. All the SQLiteDicts are done
            # with it.
            SQLiteDict.connection_cache[filename].commit()
            SQLiteDict.connection_cache[filename].close()
            del SQLiteDict.connection_cache[filename]
            
        

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
            SQLiteDict.drop_connection(self.filename)            
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
    
"""
The MIT License (MIT)

Copyright (c) 2013 Shish <webmaster@shishnet.org>

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
