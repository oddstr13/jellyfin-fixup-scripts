#!/usr/bin/env python3 
# Copyright (c) Oddstr13
# License: MIT - https://opensource.org/licenses/MIT
#
# Based on cvium's SQL statements; https://github.com/jellyfin/jellyfin/pull/1338#issuecomment-488223840

import os
import sys
import sqlite3
import pwd

DBFILE = "/var/lib/jellyfin/data/library.db"

def isRunning():
    return not os.system("ps axwwo comm --no-headers | grep -i '^jellyfin$' > /dev/null")

if __name__ == "__main__":
    # Make sure that Jellyfin is not running.
    if isRunning():
        print("You should stop jellyfin before running this script.")
        print("$ systemctl stop jellyfin")
        exit(50)

    # Make sure we can write to the DB file
    if not os.access(DBFILE, os.W_OK):
        print("ERROR: No write access to {}".format(DBFILE))
        print("Try running this script as the jellyfin user:")
        print("sudo -u {} {}".format(pwd.getpwuid(os.stat(DBFILE).st_uid).pw_name, ' '.join([sys.executable] + sys.argv)))
        exit(100)


    with sqlite3.connect(DBFILE) as conn:
        cur = conn.cursor()

        # Get a list of incorrect UserDataKeys
        res = cur.execute("SELECT tbi2.UserDataKey, tbi2.type, tbi2.ExtraIds FROM TypedBaseItems tbi1 INNER JOIN TypedBaseItems tbi2 ON tbi2.Path = tbi1.Path and tbi1.Guid <> tbi2.Guid WHERE tbi2.ExtraType is not NULL and tbi1.ExtraType is NULL").fetchall()
        blacklist = []
        for item in res:
            udk = item[0]
            if item[0] not in blacklist:
                blacklist.append(item[0])

        # Remove the incorrect UserDataKeys from ExtraIds fields
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
