#!/usr/bin/env python3 
# Copyright (c) Oddstr13
# License: MIT - https://opensource.org/licenses/MIT

import json
import sqlite3
import os
import sys
import base64
import xml.dom.minidom
import getpass
import hashlib
import pwd

XMLPATH = "/etc/jellyfin/users/"
DBFILE = "/var/lib/jellyfin/data/users.db"

def decodeGUID(b):
    return base64.b16encode(bytes([b[3], b[2], b[1], b[0], b[5], b[4], b[7], b[6]]) + b[8:]).decode("utf-8").lower()

def isRunning():
    return not os.system("ps axwwo comm --no-headers | grep -i '^jellyfin$' > /dev/null")

def prompt(s, default=None):
    yes = ["y", "yes", "true", "1"]
    no  = ["n", "no", "false", "0"]

    if default is None:
        q = "y/n"
    elif default:
        q = "[Y]n"
    else:
        q = "y[N]"

    while True:
        r = input("{}? {} ".format(s, q)).lower().strip()

        if default is None:
            if r in yes:
                return True
            if r in no:
                return False
        elif default:
            if not r or r in yes:
                return True
            if r in no:
                return False
        else:
            if r in yes:
                return True
            if not r or r in no:
                return False

        print("Answer Yes or No!")

if __name__ == "__main__":
  # Make sure that Jellyfin is not running.
  if isRunning():
      print("You should stop jellyfin before running this script.")
      print("$ systemctl stop jellyfin")
      exit(50)

  with sqlite3.connect(DBFILE) as conn:
    cur = conn.cursor()
    users = cur.execute('SELECT * FROM LocalUsersv2').fetchall()

    for id, bguid, data in users:
        guid = decodeGUID(bytes(bguid))
        if type(data) is bytes:
            data = data.decode("utf-8")
        data = json.loads(data)

        pdir = os.path.join(XMLPATH, guid)

        policy_xml = os.path.join(pdir, "policy.xml")
        with open(policy_xml, "r") as fh:
            policy = xml.dom.minidom.parse(fh)

        config_xml = os.path.join(pdir, "config.xml")
        with open(config_xml, "r") as fh:
            config = xml.dom.minidom.parse(fh)


        is_disabled = policy.getElementsByTagName('IsDisabled')[0].firstChild.data == "true"
        login_attempts = int(policy.getElementsByTagName('InvalidLoginAttemptCount')[0].firstChild.data)
        user_pass = data.get('Password')
        user_name = data.get('Name')
        user_pin  = data.get('EasyPassword')
        enable_local_password = config.getElementsByTagName('EnableLocalPassword')[0].firstChild.data == "true"


        print("---------")
        print("User {}".format(user_name))

        if login_attempts:
            print("Account has {} failed login attempts.".format(login_attempts))

        if is_disabled:
            print("Account is disabled.")

        if user_pin:
            print("PIN code is set.")

        if enable_local_password:
            print("Local PIN login is enabled.")

        do_restore = False
        if login_attempts or is_disabled or user_pin or enable_local_password:
            if prompt("Restore user", True):
                do_restore = True
                if not os.access(policy_xml, os.W_OK) or not os.access(config_xml, os.W_OK) or not os.access(DBFILE, os.W_OK):
                    print("ERROR: No write access to {}, {} or {}".format(config_xml, policy_xml, DBFILE))
                    print("Try running this script as the jellyfin user:")
                    print("sudo -u {} {}".format(pwd.getpwuid(os.stat(config_xml).st_uid).pw_name, ' '.join([sys.executable] + sys.argv)))
                    exit(100)

        new_pass = None
        if prompt("Reset password", False):
            if not os.access(DBFILE, os.W_OK):
                print("ERROR: No write access to {}".format(DBFILE))
                print("Try running this script as the jellyfin user:")
                print("sudo -u {} {}".format(pwd.getpwuid(os.stat(config_xml).st_uid).pw_name, ' '.join([sys.executable] + sys.argv)))
                exit(100)
            new_pass = "$SHA1${}".format(hashlib.sha1(getpass.getpass().encode("utf-8")).hexdigest().upper())

        if do_restore:
            if login_attempts or is_disabled:
                if is_disabled:
                    print("Enabling account...")
                    policy.getElementsByTagName('IsDisabled')[0].firstChild.data = "false"

                if login_attempts:
                    print("Resetting login attempts...")
                    policy.getElementsByTagName('InvalidLoginAttemptCount')[0].firstChild.data = "0"

                with open(policy_xml, "w") as fh:
                    policy.writexml(fh)

            if enable_local_password:
                print("Disabling local PIN login...")

                config.getElementsByTagName('EnableLocalPassword')[0].firstChild.data = "false"
                with open(config_xml, "w") as fh:
                    config.writexml(fh)

            if user_pin:
                print("Clearing PIN code...")
                data.pop('EasyPassword')

        if new_pass:
            print("Changing user password...")
            data["Password"] = new_pass

        if (do_restore and user_pin) or new_pass:
            cur.execute("UPDATE LocalUsersv2 SET data = :data WHERE id=:id", {'data':json.dumps(data), 'id': id})
