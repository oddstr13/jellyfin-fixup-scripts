#!/usr/bin/env python3 
# Copyright (c) Oddstr13
# License: MIT - https://opensource.org/licenses/MIT
#
# Based on cvium's SQL statements; https://github.com/jellyfin/jellyfin/pull/1338#issuecomment-488223840

import os
import sys
import sqlite3
import platform
import subprocess

DATA_PATHS = [
    "/var/lib/jellyfin/data/",
]

if os.environ.get('LOCALAPPDATA'):
    DATA_PATHS.append(os.path.join(os.environ.get('LOCALAPPDATA'), "jellyfin", "data"))

if os.environ.get('XDG_DATA_HOME'):
    DATA_PATHS.append(os.path.join(os.environ.get('XDG_DATA_HOME'), "jellyfin", "data"))

if os.environ.get('HOME'):
    DATA_PATHS.append(os.path.join(os.environ.get('HOME'), ".local", "jellyfin", "data"))


# Python on msys returns 'MSYS_NT-10.0-14393' on platform.system() for some reason.
is_windows = platform.system() == "Windows" or sys.platform in ["win32", "cygwin", "msys"]
is_linux   = platform.system() == "Linux"
is_macos   = platform.system() == "Darwin"

class Exit(Exception): pass

def getDB(name):
    for dpath in DATA_PATHS:
        dbfile = os.path.join(dpath, name + ".db")
        if os.path.exists(dbfile):
            return dbfile
    return None

def isRunning():
    if is_windows:
        return subprocess.check_output([
            "tasklist", "-fo", "table", "-nh", "-fi", "imagename eq jellyfin.exe"
        ]).replace(b'\xff', b'').strip().startswith(b"jellyfin.exe")
    else:
        # busybox ps usually only accepts the w (wide) option.
        # FIXME: Implement this in a way that is compatible with both standard and busybox `ps`
        return not os.system("ps axwwo comm --no-headers | grep -i '^jellyfin$' > /dev/null")

def main(dbfile=None, *args):
    if args:
        print("Ignoring extra arguments: {}".format(', '.join(args)))

    # Make sure that Jellyfin is not running
    if isRunning():
        print("You should stop Jellyfin before running this script.")
        if is_linux:
            print("$ systemctl stop jellyfin")
        raise Exit("Jellyfin is running")

    # Locate the library database
    if dbfile is None:
        dbfile = getDB("library")
    
    if dbfile is None:
        print("ERROR: Unable to locate the Jellyfin library database.")
        print("Please supply the file `library.db` as a command line parameter,")
        print("or drag-drop the db file on top of this script.")
        raise Exit("Unable to locate database file")
    
    print("Attempting to use database `{}`.".format(dbfile))


    # Make sure we can write to the DB file
    if not os.access(dbfile, os.W_OK):
        print("ERROR: No write access to database {}".format(dbfile))
        print("Try running this script as the jellyfin user or as an Administrator if you're on Windows.")
        if sys.platform == "linux":
            # Importing PWD here as it's not a module for Windows and this is the only time it's used.
            import pwd
            print("sudo -u {} {}".format(pwd.getpwuid(os.stat(dbfile).st_uid).pw_name, ' '.join([sys.executable] + sys.argv)))
        raise Exit("No write access to database file `{}`".format(dbfile))

    with sqlite3.connect(dbfile) as conn:
        cur = conn.cursor()

        # Get a list of incorrect UserDataKeys
        print("Building list of incorrect UserDataKeys to fix...")
        res = cur.execute("SELECT tbi2.UserDataKey, tbi2.type, tbi2.ExtraIds FROM TypedBaseItems tbi1 INNER JOIN TypedBaseItems tbi2 ON tbi2.Path = tbi1.Path and tbi1.Guid <> tbi2.Guid WHERE tbi2.ExtraType is not NULL and tbi1.ExtraType is NULL").fetchall()
        blacklist = []
        for item in res:
            udk = item[0]
            if item[0] not in blacklist:
                blacklist.append(item[0])

        # Remove the incorrect UserDataKeys from ExtraIds fields
        print("Removing incorrect UserDataKeys...")
        res = cur.execute("SELECT guid, ExtraIds, Name FROM TypedBaseItems;").fetchall()
        for guid, _eids, name in res:
            if not _eids: continue

            eids = _eids.split('|')

            new_eids = list(filter(lambda i: i not in blacklist, eids))

            if len(eids) != len(new_eids):
                print(guid, len(eids), len(new_eids))
                cur.execute("UPDATE TypedBaseItems SET ExtraIds=:eids WHERE guid=:guid", {'eids':'|'.join(new_eids), 'guid': guid})
                print(name)

        # Delete the incorrect items
        res = cur.execute("SELECT tbi2.guid, tbi2.ExtraType, tbi2.Name FROM TypedBaseItems tbi1 INNER JOIN TypedBaseItems tbi2 ON tbi2.Path = tbi1.Path and tbi1.Guid <> tbi2.Guid WHERE tbi2.ExtraType is not NULL and tbi1.ExtraType is NULL").fetchall()
        for guid, etype, name in res:
            print([name, etype])
            cur.execute("DELETE FROM TypedBaseItems WHERE guid=:guid", {'guid': guid})

        # Clean up empty ExtraIds - Jellyfin will crash and burn if we don't.
        cur.execute("UPDATE TypedBaseItems SET ExtraIds=NULL WHERE ExtraIds='';")

    print("Done.")

if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except Exit:
        pass
    except Exception as e:
        print("""
An error has occured. Please check
https://github.com/oddstr13/jellyfin-fixup-scripts/issues
and submit a new issue if it has not already been reported.

Please include all of the following information in the issue report:
""")
        print("Python version: {}".format(platform.python_version()))
        print("Python implementation: {}".format(platform.python_implementation()))
        print("Arguments: {!r}".format(sys.argv))
        print("Platform: {}".format(platform.platform()))

        print()
        import traceback
        traceback.print_exc()
    
    if is_windows:
        print()
        input("Press enter to exit.")