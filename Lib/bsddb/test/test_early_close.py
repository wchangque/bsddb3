"""
Copyright (c) 2008-2020, Jesus Cea Avion <jcea@jcea.es>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

    1. Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions and the following
    disclaimer in the documentation and/or other materials provided
    with the distribution.

    3. Neither the name of Jesus Cea Avion nor the names of its
    contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
    CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
    MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS
    BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
    EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
            TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
            DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
    TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
    THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
    SUCH DAMAGE.
    """

"""TestCases for checking that it does not segfault when a DBEnv object
is closed before its DB objects.
"""

import os, sys
import unittest

from test_all import db, test_support, verbose, get_new_environment_path, get_new_database_path

# We're going to get warnings in this module about trying to close the db when
# its env is already closed.  Let's just ignore those.
try:
    import warnings
except ImportError:
    pass
else:
    warnings.filterwarnings('ignore',
                            message='DB could not be closed in',
                            category=RuntimeWarning)


#----------------------------------------------------------------------

class DBEnvClosedEarlyCrash(unittest.TestCase):
    def setUp(self):
        self.homeDir = get_new_environment_path()
        self.filename = "test"

    def tearDown(self):
        test_support.rmtree(self.homeDir)

    def test01_close_dbenv_before_db(self):
        dbenv = db.DBEnv()
        dbenv.open(self.homeDir,
                   db.DB_INIT_CDB| db.DB_CREATE |db.DB_THREAD|db.DB_INIT_MPOOL,
                   0666)

        d = db.DB(dbenv)
        d2 = db.DB(dbenv)
        d.open(self.filename, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)

        self.assertRaises(db.DBNoSuchFileError, d2.open,
                self.filename+"2", db.DB_BTREE, db.DB_THREAD, 0666)

        d.put("test","this is a test")
        self.assertEqual(d.get("test"), "this is a test", "put!=get")
        dbenv.close()  # This "close" should close the child db handle also
        self.assertRaises(db.DBError, d.get, "test")

    def test02_close_dbenv_before_dbcursor(self):
        dbenv = db.DBEnv()
        dbenv.open(self.homeDir,
                   db.DB_INIT_CDB| db.DB_CREATE |db.DB_THREAD|db.DB_INIT_MPOOL,
                   0666)

        d = db.DB(dbenv)
        d.open(self.filename, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)

        d.put("test","this is a test")
        d.put("test2","another test")
        d.put("test3","another one")
        self.assertEqual(d.get("test"), "this is a test", "put!=get")
        c=d.cursor()
        c.first()
        c.next()
        d.close()  # This "close" should close the child db handle also
     # db.close should close the child cursor
        self.assertRaises(db.DBError,c.next)

        d = db.DB(dbenv)
        d.open(self.filename, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)
        c=d.cursor()
        c.first()
        c.next()
        dbenv.close()
    # The "close" should close the child db handle also, with cursors
        self.assertRaises(db.DBError, c.next)

    def test03_close_db_before_dbcursor_without_env(self):
        import os.path
        path=os.path.join(self.homeDir,self.filename)
        d = db.DB()
        d.open(path, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)

        d.put("test","this is a test")
        d.put("test2","another test")
        d.put("test3","another one")
        self.assertEqual(d.get("test"), "this is a test", "put!=get")
        c=d.cursor()
        c.first()
        c.next()
        d.close()
    # The "close" should close the child db handle also
        self.assertRaises(db.DBError, c.next)

    def test04_close_massive(self):
        dbenv = db.DBEnv()
        dbenv.open(self.homeDir,
                   db.DB_INIT_CDB| db.DB_CREATE |db.DB_THREAD|db.DB_INIT_MPOOL,
                   0666)

        dbs=[db.DB(dbenv) for i in xrange(16)]
        cursors=[]
        for i in dbs :
            i.open(self.filename, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)

        dbs[10].put("test","this is a test")
        dbs[10].put("test2","another test")
        dbs[10].put("test3","another one")
        self.assertEqual(dbs[4].get("test"), "this is a test", "put!=get")

        for i in dbs :
            cursors.extend([i.cursor() for j in xrange(32)])

        for i in dbs[::3] :
            i.close()
        for i in cursors[::3] :
            i.close()

    # Check for missing exception in DB! (after DB close)
        self.assertRaises(db.DBError, dbs[9].get, "test")

    # Check for missing exception in DBCursor! (after DB close)
        self.assertRaises(db.DBError, cursors[101].first)

        cursors[80].first()
        cursors[80].next()
        dbenv.close()  # This "close" should close the child db handle also
    # Check for missing exception! (after DBEnv close)
        self.assertRaises(db.DBError, cursors[80].next)

    def test05_close_dbenv_delete_db_success(self):
        dbenv = db.DBEnv()
        dbenv.open(self.homeDir,
                   db.DB_INIT_CDB| db.DB_CREATE |db.DB_THREAD|db.DB_INIT_MPOOL,
                   0666)

        d = db.DB(dbenv)
        d.open(self.filename, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)

        dbenv.close()  # This "close" should close the child db handle also

        del d
        try:
            import gc
        except ImportError:
            gc = None
        if gc:
            # force d.__del__ [DB_dealloc] to be called
            gc.collect()

    def test06_close_txn_before_dup_cursor(self) :
        dbenv = db.DBEnv()
        dbenv.open(self.homeDir,db.DB_INIT_TXN | db.DB_INIT_MPOOL |
                db.DB_INIT_LOG | db.DB_CREATE)
        d = db.DB(dbenv)
        txn = dbenv.txn_begin()
        d.open(self.filename, dbtype = db.DB_HASH, flags = db.DB_CREATE,
                txn=txn)
        d.put("XXX", "yyy", txn=txn)
        txn.commit()
        txn = dbenv.txn_begin()
        c1 = d.cursor(txn)
        c2 = c1.dup()
        self.assertEqual(("XXX", "yyy"), c1.first())

        # Not interested in warnings about implicit close.
        import warnings
        with warnings.catch_warnings() :
            warnings.filterwarnings("ignore")
            txn.commit()

        self.assertRaises(db.DBCursorClosedError, c2.first)

    def test07_close_db_before_sequence(self):
        import os.path
        path=os.path.join(self.homeDir,self.filename)
        d = db.DB()
        d.open(path, db.DB_BTREE, db.DB_CREATE | db.DB_THREAD, 0666)
        dbs=db.DBSequence(d)
        d.close()  # This "close" should close the child DBSequence also
        dbs.close()  # If not closed, core dump (in Berkeley DB 4.6.*)

#----------------------------------------------------------------------

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(DBEnvClosedEarlyCrash))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
