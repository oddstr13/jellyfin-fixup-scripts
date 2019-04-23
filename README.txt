$ sudo systemctl stop jellyfin
$ ./jellyfin-login-fix.py
---------
User oddstr13
Account has 5 failed login attempts.
Account is disabled.
PIN code is set.
Local PIN login is enabled.
Restore user? [Y]n 
ERROR: No write access to /etc/jellyfin/users/7b2664944327497a9e2b200138f22671/config.xml, /etc/jellyfin/users/7b2664944327497a9e2b200138f22671/policy.xml or /var/lib/jellyfin/data/users.db
Try running this script as the jellyfin user:
sudo -u jellyfin ./jellyfin-login-fix.py

$ sudo -u jellyfin ./jellyfin-login-fix.py
---------
User oddstr13
Account has 5 failed login attempts.
Account is disabled.
PIN code is set.
Local PIN login is enabled.
Restore user? [Y]n 
Reset password? y[N] 
Enabling account...
Resetting login attempts...
Disabling local PIN login...
Clearing PIN code...

$ sudo -u jellyfin ./jellyfin-login-fix.py
---------
User oddstr13
Reset password? y[N] y
Password: 
Changing user password...

$ sudo systemctl start jellyfin
