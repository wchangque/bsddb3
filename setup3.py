#!/usr/bin/env python

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

import os
import re
import sys
import glob

if (sys.version_info[0] < 3) and (sys.version_info >= (2, 6)) :
    # Silence deprecation warnings during "setup"
    import warnings
    warnings.filterwarnings('ignore',
            message='in 3.x, bsddb has been removed; ' \
                    'please use the pybsddb project instead',
            category=DeprecationWarning)
    warnings.filterwarnings('ignore',
            message='in 3.x, the bsddb module has been removed; ' \
                    'please use the pybsddb project instead',
            category=DeprecationWarning)

    if sys.version_info[:2] == (2, 7) :
        with warnings.catch_warnings() :
            # Python 2.7.0
            warnings.filterwarnings('ignore',
                message='The CObject type is marked Pending Deprecation ' \
                        'in Python 2.7.  Please use capsule objects instead.',
                category=PendingDeprecationWarning)

            # Python 2.7.1
            warnings.filterwarnings('ignore',
                message='CObject type is not supported in 3.x. ' \
                        'Please use capsule objects instead.',
                category=DeprecationWarning)

            try :  # 'bsddb' library could be not available
                import bsddb  # Import the 2.7 version, that uses CObject
            except ImportError :
                pass

    # setuptools warnings
    warnings.filterwarnings('ignore',
            message='tuple parameter unpacking has been removed in 3.x',
            category=SyntaxWarning)
    warnings.filterwarnings('ignore',
            message='the dl module has been removed in Python 3.0; ' \
                    'use the ctypes module instead',
            category=DeprecationWarning)


try :
  from setuptools import setup, Extension
except :
  from distutils.core import setup, Extension

from distutils.dep_util import newer
import distutils.ccompiler

# read the module version number out of the .c file
VERSION = None
_ver_re = re.compile('^#\s*define\s+PY_BSDDB_VERSION\s+"(\d+\.\d+\.\d+.*)"')
try:
    _srcFile = open('Modules/bsddb.h', 'r')
except IOError:
    print("Could not open module source to read the version number.")
    raise
for line in _srcFile.readlines():
    m = _ver_re.match(line)
    if m:
        VERSION = m.group(1)
        continue

# We close first, to avoid a "ResourceWarning"
_srcFile.close()
del _srcFile
del _ver_re
del m
if not VERSION:
    raise RuntimeError("could not find PY_BSDDB_VERSION in Modules/bsddb.h")

#----------------------------------------------------------------------

debug = '--debug' in sys.argv or '-g' in sys.argv

lflags_arg = []


if os.name == 'posix':
    # Allow setting the DB dir and additional link flags either in
    # the environment or on the command line.
    # First check the environment...
    BERKELEYDB_INCDIR = os.environ.get('BERKELEYDB_INCDIR', '')
    BERKELEYDB_LIBDIR = os.environ.get('BERKELEYDB_LIBDIR', '')
    BERKELEYDB_DIR = os.environ.get('BERKELEYDB_DIR', '')
    LFLAGS = os.environ.get('LFLAGS', [])
    LIBS = os.environ.get('LIBS', [])

    # ...then the command line.
    # Handle --berkeley-db=[PATH] and --lflags=[FLAGS]
    args = sys.argv[:]
    for arg in args:
        if arg.startswith('--berkeley-db-incdir='):
            BERKELEYDB_INCDIR = arg.split('=')[1]
            sys.argv.remove(arg)
        if arg.startswith('--berkeley-db-libdir='):
            BERKELEYDB_LIBDIR = arg.split('=')[1]
            sys.argv.remove(arg)
        if arg.startswith('--berkeley-db='):
            BERKELEYDB_DIR = arg.split('=')[1]
            sys.argv.remove(arg)
        elif arg.startswith('--lflags='):
            LFLAGS = arg.split('=')[1].split()
            sys.argv.remove(arg)
        elif arg.startswith('--libs='):
            LIBS = arg.split('=')[1].split()
            sys.argv.remove(arg)

    if LFLAGS or LIBS:
        lflags_arg = LFLAGS + LIBS

    # Supported Berkeley DB versions, in order of preference.
    db_ver_list = ((6, 2), (6, 1),
            (5, 3), (5, 1),
            (4, 8), (4, 7))
    db_ver = None

    # If we were not told where it is, go looking for it.
    dblib = 'db'
    incdir = libdir = None
    if not BERKELEYDB_DIR and not BERKELEYDB_LIBDIR and not BERKELEYDB_INCDIR:
        # construct a list of paths to look for the header file in on
        # top of the normal inc_dirs.
        db_inc_paths = []
        db_major = set()
        bitness = ""
        import platform
        if (platform.architecture()[0] == "64bit") and \
           (platform.platform(True, True).startswith("Solaris-")) and \
           (not platform.uname()[3].startswith('joyent_')):
               bitness = "/64"

        for major, minor in db_ver_list :
            if major not in db_major :
                db_major.add(major)
                db_inc_paths.extend([
                    '/usr/include/db%d%s' %(major, bitness),
                    '/usr/local/include/db%d%s' %(major, bitness),
                    '/opt/local/include/db%d%s' %(major, bitness),
                    '/opt/sfw/include/db%d%s' %(major, bitness),
                    '/sw/include/db%d%s' %(major, bitness),
                    '/usr/local/opt/berkeley-db@%s/include' % (major),
                    ])

            db_inc_paths.append('/usr/include/db%d%d%s' % \
                (major, minor, bitness))
            db_inc_paths.append('/usr/local/BerkeleyDB.%d.%d%s/include' % \
                (major, minor, bitness))
            db_inc_paths.append('/usr/local/include/db%d%d%s' % \
                (major, minor, bitness))
            db_inc_paths.append('/pkg/db-%d.%d%s/include' % \
                (major, minor, bitness))
            db_inc_paths.append('/opt/db-%d.%d%s/include' % \
                (major, minor, bitness))

        db_ver_inc_map = {}

        class db_found(Exception): pass
        try:
            # this CCompiler object is only used to locate include files
            compiler = distutils.ccompiler.new_compiler()

            lib_dirs = compiler.library_dirs + [
                '/lib64', '/usr/lib64',
                '/lib', '/usr/lib',
                '/usr/lib/x86_64-linux-gnu/',
            ]
            inc_dirs = compiler.include_dirs + [
                '/usr/include', '/usr/local/opt/berkeley-db/include',
            ]

            # See whether there is a Oracle or Sleepycat header in the standard
            # search path.
            for d in inc_dirs + db_inc_paths:
                f = os.path.join(d, "db.h")
                if debug: print("db: looking for db.h in", f)
                if os.path.exists(f):
                    with open(f) as fichero :
                        f = fichero.read()
                    m = re.search(r"#define\WDB_VERSION_MAJOR\W(\d+)", f)
                    if m:
                        db_major = int(m.group(1))
                        m = re.search(r"#define\WDB_VERSION_MINOR\W(\d+)", f)
                        db_minor = int(m.group(1))
                        db_ver = (db_major, db_minor)

                        if ( (db_ver not in db_ver_inc_map) and
                           (db_ver in db_ver_list) ):
                            # save the include directory with the db.h version
                            # (first occurrance only)
                            db_ver_inc_map[db_ver] = d
                            if debug: print("db.h: found", db_ver, "in", d)
                        else:
                            # we already found a header for this library version
                            if debug: print("db.h: ignoring", d)
                    else:
                        # ignore this header, it didn't contain a version number
                        if debug: print("db.h: unsupported version", db_ver, "in", d)

            db_found_vers = list(db_ver_inc_map.keys())
            db_found_vers.sort()

            while db_found_vers:
                db_ver = db_found_vers.pop()
                db_incdir = db_ver_inc_map[db_ver]

                # check lib directories parallel to the location of the header
                db_dirs_to_check = [
                    os.path.join(db_incdir, '..', 'lib64'),
                    os.path.join(db_incdir, '..', 'lib'),
                    os.path.join(db_incdir, '..', '..', 'lib64'),
                    os.path.join(db_incdir, '..', '..', 'lib'),
                ]
                db_dirs_to_check = list(filter(os.path.isdir, db_dirs_to_check))

                # Look for a version specific db-X.Y before an ambiguoius dbX
                # XXX should we -ever- look for a dbX name?  Do any
                # systems really not name their library by version and
                # symlink to more general names?
                for dblib in (
                        ('db%d-%d.%d' % (db_ver[0], db_ver[0], db_ver[1])),
                        ('db-%d.%d' % db_ver),
                        ('db%d' % db_ver[0])
                        ):
                    dblib_file = compiler.find_library_file(
                                    db_dirs_to_check + lib_dirs, dblib )
                    if dblib_file:
                        db_libdir = os.path.abspath(os.path.dirname(dblib_file))
                        raise db_found
                    else:
                        if debug: print("db lib: ", dblib, "not found")
        except db_found:
            print("Found Berkeley DB %d.%d installation." % db_ver)
            print("  include files in", db_incdir)
            print("  library files in", db_libdir)
            print("  library name is lib"+dblib)
            if debug: print("db: lib dir", db_libdir, "inc dir", db_incdir)

            incdir  = db_incdir
            libdir  = db_libdir
        else:
            # this means Berkeley DB could not be found
            pass

    if BERKELEYDB_LIBDIR or BERKELEYDB_INCDIR:
        libdir = BERKELEYDB_LIBDIR or None
        incdir = BERKELEYDB_INCDIR or None

    if not BERKELEYDB_DIR and not incdir and not libdir:
        print("Can't find a local Berkeley DB installation.")
        print("(suggestion: try the --berkeley-db=/path/to/bsddb option)")
        sys.exit(1)

    # figure out from the base setting where the lib and .h are
    if not incdir:
        incdir = os.path.join(BERKELEYDB_DIR, 'include')
    if not libdir:
        libdir = os.path.join(BERKELEYDB_DIR, 'lib')
    if not '-ldb' in LIBS:
        libname = [dblib]
    else:
        if debug: print("LIBS already contains '-ldb' not adding our own", "'-l"+dblib+"'")
        libname = []
    utils = []

    # Test if the old bsddb is built-in
    static = 0
    try:
        # Possibly already imported in the "warning" section (python 2.7)
        import bsddb
        if str(bsddb).find('built-in') >= 0:
            static = 1
    except ImportError:
        pass

    # On Un*x, double check that no other built-in module pulls libdb in as a
    # side-effect. TBD: how/what to do on other platforms?
    fp = os.popen('ldd %s 2>&1' % sys.executable)
    results = fp.read()
    status = fp.close()
    if not status and results.find('libdb.') >= 0:
        static = 1

    if static:
        print("""\
\aWARNING:
\tIt appears that the old bsddb module is staticly linked in the
\tPython executable. This will cause various random problems for
\tbsddb3, up to and including segfaults. Please rebuild your
\tPython either with bsddb disabled, or with it built as a shared
\tdynamic extension. Watch out for other modules (e.g. dbm) that create
\tdependencies in the python executable to libdb as a side effect.""")
        st = input("Build anyway? (yes/[no]) ")
        if st != "yes":
            sys.exit(1)

    # read db.h to figure out what version of Berkeley DB this is
    ver = None
    with open(os.path.join(incdir, 'db.h'), 'r') as f :
        db_h_lines = f.readlines()
    db_ver_re = re.compile(
        r'^#define\s+DB_VERSION_STRING\s.*Berkeley DB (\d+\.\d+).*')
    db_ver2 = db_ver
    if db_ver is None :
        print("Trying to use the Berkeley DB you specified...")
    for line in db_h_lines:
        match = db_ver_re.match(line)
        if not match:
            continue
        fullverstr = match.group(1)
        ver = fullverstr[0] + fullverstr[2]   # 31 == 3.1, 32 == 3.2, etc.
        db_ver = (int(fullverstr[0]), int(fullverstr[2]))
    if (db_ver2 is not None) and (db_ver != db_ver2) :
        raise AssertionError("Detected Berkeley DB version is inconsistent")
    if db_ver not in db_ver_list:
        raise AssertionError("pybsddb untested with this Berkeley DB "
                "version %d.%d" %db_ver)
    print('Detected Berkeley DB version %d.%d from db.h' %db_ver)

elif os.name == 'nt':

    # The default build of Berkeley DB for windows just leaves
    # everything in the build dirs in the db source tree. That means
    # that we either have to hunt around to find it, (which would be
    # even more difficult than the mess above for Unix...) or we make
    # the builder specify everything here. Compounding the problem is
    # version numbers in default path names, and different library
    # names for debug/release or dll/static.
    #
    # So to make things easier, I'm just going to expect that the DB stuff
    # has been moved to the ./db directory. There's an updatedb.bat file to
    # help.
    #
    # You'll need to edit the project file that comes with Berkeley DB so it
    # uses "Multithreaded DLL" and "Debug Multithreaded DLL"  (/MD and /MDd)
    # settings as appropriate to build .lib file (the db_static project).

    incdir = 'db/include'
    libdir = 'db/lib'

    # read db.h to figure out what version of Berkeley DB this is
    ver = None
    with open(os.path.join(incdir, 'db.h'), 'r') as f :
        db_h_lines = f.readlines()
    db_ver_re = re.compile(
        r'^#define\s+DB_VERSION_STRING\s.*Berkeley DB (\d+\.\d+).*')
    for line in db_h_lines:
        match = db_ver_re.match(line)
        if not match:
            continue
        fullverstr = match.group(1)
        ver = fullverstr[0] + fullverstr[2]   # 31 == 3.1, 32 == 3.2, etc.
        db_ver = (int(fullverstr[0]), int(fullverstr[2]))
    if db_ver not in db_ver_list:
        raise AssertionError("pybsddb untested with this Berkeley DB "
                "version %d.%d" %db_ver)
    print('Detected Berkeley DB version %d.%d from db.h' %db_ver)

    if debug:
        libname = ['libdb%ssd' % ver]     # Debug, static
    else:
        libname = ['libdb%ss' % ver]      # Release, static
    utils = [("bsddb3/utils",
              ["db/bin/db_archive.exe",
               "db/bin/db_checkpoint.exe",
               "db/bin/db_deadlock.exe",
               "db/bin/db_dump.exe",
               "db/bin/db_load.exe",
               "db/bin/db_printlog.exe",
               "db/bin/db_recover.exe",
               "db/bin/db_stat.exe",
               "db/bin/db_upgrade.exe",
               "db/bin/db_verify.exe",
               "db/bin/libdb%s.dll" % ver,
               ]),
             ("bsddb3/test", glob.glob("test/*.py"))
             ]

if (db_ver in ((6, 0), (6, 1), (6, 2))) and \
  ("YES_I_HAVE_THE_RIGHT_TO_USE_THIS_BERKELEY_DB_VERSION" not in os.environ) :
    print (
        "\n"
        "******* COMPILATION ABORTED *******\n"
        "\n"
        "You are linking a Berkeley DB version licensed under "
        "AGPL3 or have a commercial license.\n"
        "\n"
        "AGPL3 is a strong copyleft license and derivative "
        "works must be equivalently licensed.\n"
        "\n"
        "You have two choices:\n"
        "\n"
        "  1. If your code is AGPL3 or you have a commercial Berkeley DB "
        "license from Oracle, please, define the environment variable "
        "'YES_I_HAVE_THE_RIGHT_TO_USE_THIS_BERKELEY_DB_VERSION' to "
        "any value, and try to install this python library again.\n"
        "\n"
        "  2. In any other case, you have to link to a previous version "
        "of Berkeley DB. Remove Berlekey DB version 6.x and let this "
        "python library try to locate an older version of the "
        "Berkeley DB library in your system. Alternatively, you can "
        "define the environment variable 'BERKELEYDB_DIR', or "
        "'BERKELEYDB_INCDIR' and 'BERKELEYDB_LIBDIR', with the path of "
        "the Berkeley DB you want to use and try to install this "
        "python library again.\n"
        "\n"
        "Sorry for the inconvenience. I am trying to protect you.\n"
        "\n"
        "More details:\n"
        "\n"
        "    https://forums.oracle.com/message/11184885\n"
        "    http://lists.debian.org/debian-legal/2013/07/\n"
        "\n"
        "******* COMPILATION ABORTED *******\n"
        )
    sys.exit(1)

version_suffix = ""
if sys.version_info[0] > 2 :
    version_suffix = "3"


# #############################

# Delete pkgsrc stale info
# This is something that eventually should be not necesary.
# XXX - jcea@jcea.es - 20170125
from distutils import sysconfig

# The same dictionary is always returned, so we abuse it
# and modify it in place.
config_vars = sysconfig.get_config_vars()
for k, v in list(config_vars.items()):
    if isinstance(v, str) and ('/db4' in v):
        j = ' '.join([i for i in v.split() if not i.endswith('/db4')])
        config_vars[k] = j
del config_vars

# #############################


# do the actual build, install, whatever...
setup(name = 'bsddb3',
      version = VERSION,
      description = 'Python bindings for Oracle Berkeley DB',
      long_description = """\
This module provides a nearly complete wrapping of the Oracle/Sleepycat C API
for the Database Environment, Database, Cursor, Log Cursor, Sequence and
Transaction objects, and each of these is exposed as a Python type in the
bsddb3.db module. The database objects can use various access methods: btree,
hash, recno, and queue.  Complete support of Berkeley DB distributed
transactions. Complete support for Berkeley DB Replication Manager. Complete
support for Berkeley DB Base Replication. Support for RPC.

Please see the documents in the docs directory of the source distribution or at
the website for more details on the types and methods provided. The goal is to
mirror most of the real Berkeley DB API so fall back to the Oracle Berkeley DB
documentation as appropriate.

If you need to support ancient versions of Python and/or Berkeley DB , you can
use old releases of this bindings.


`Homepage <https://www.jcea.es/programacion/
pybsddb.htm>`__ --
`Releases (changelog) <https://www.jcea.es/programacion/
pybsddb.htm#Releases>`__ --
`Documentation <https://www.jcea.es/programacion/
pybsddb_doc/>`__ --
`Mailing List <https://mailman.jcea.es/listinfo/pybsddb>`__ --
`Donation <https://www.jcea.es/programacion/pybsddb_doc/donate.html>`__

.. warning::

   This library is deprecated. If you are running Python 3 >= 3.6, please
   upgrade to `berkeleydb <https://pypi.org/project/berkeleydb/>`_ library.
   Check `details <https://www.jcea.es/programacion/pybsddb.htm>`__.

   Take note that upgrading to `berkeleydb`_ is easy but not transparent.
   Notably, keys and values are **bytes** in `berkeleydb`_ lib, while in
   'bsddb3' they are **strings**. You would only need to change your code to
   add or remove type encoding/decoding, depending of how you use the library.
   The process should be simple, nevertheless.
""",
      long_description_content_type = 'text/x-rst',

      author = 'Jesus Cea, Robin Dunn, Gregory P. Smith, Andrew Kuchling, Barry Warsaw',
      author_email = 'pybsddb@jcea.es',
      url = 'https://www.jcea.es/programacion/pybsddb.htm',
      license = "3-clause BSD License",

      packages = ['bsddb3', 'bsddb3/tests'],
      package_dir = {'bsddb3': 'Lib%s/bsddb' %version_suffix,
                     'bsddb3/tests': 'Lib%s/bsddb/test' %version_suffix},
      ext_modules = [Extension('bsddb3._pybsddb',
                               sources = ['Modules/_bsddb.c'],
                               depends = ['Modules/bsddb.h'],
                               include_dirs = [ incdir ],
                               library_dirs = [ libdir ],
                               runtime_library_dirs = [ libdir ],
                               libraries = libname,
                               extra_link_args = lflags_arg,
                               )],
      headers = ['Modules/bsddb.h'],
      data_files = utils,
      classifiers = [
                    'License :: OSI Approved :: BSD License',
                    'Development Status :: 5 - Production/Stable',
                    'Intended Audience :: Developers',
                    'Intended Audience :: Information Technology',
                    'Natural Language :: English',
                    'Natural Language :: Spanish',
                    'Operating System :: OS Independent',
                    'Programming Language :: Python',
                    'Topic :: Database',
                    'Topic :: Software Development',
                    'Topic :: System :: Clustering',
                    'Programming Language :: Python :: 2',
                    'Programming Language :: Python :: 2.6',
                    'Programming Language :: Python :: 2.7',
                    'Programming Language :: Python :: 3',
                    'Programming Language :: Python :: 3.3',
                    'Programming Language :: Python :: 3.4',
                    'Programming Language :: Python :: 3.5',
                    'Programming Language :: Python :: 3.6',
                    'Programming Language :: Python :: 3.7',
                    'Programming Language :: Python :: 3.8',
                    'Programming Language :: Python :: 3.9',
                    ],
      )

if sys.version_info >= (3, 6):
    print(
          "\n"
          "\n"
          "\n"
          "******* WARNING *******\n"
          "\n"
          "This library (bsddb3) is legacy. Please, upgrade to "
          "'berkeleydb' library. Check details at:\n"
          "\n"
          "    https://www.jcea.es/programacion/pybsddb.htm\n"
          "\n"
          "Take note that upgrading to 'berkeleydb' is easy but not "
          "transparent. Notably, keys and values are *bytes* in "
          "'berkeleydb' lib, while in 'bsddb3' they are *strings*. "
          "You would only need to change your code to add or remove type "
          "encoding/decoding, depending of how you use the library. The "
          "process should be simple, nevertheless.\n"
          "\n"
          )

