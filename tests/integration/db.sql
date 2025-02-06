-- Bind account
INSERT INTO ldapgroups(name, gidnumber) VALUES ('juju', 5501);
INSERT INTO users(name, uidnumber, primarygroup, passsha256) VALUES('serviceuser', 5001, 5501, '652c7dc687d98c9889304ed2e408c74b611e86a40caa51c4b43f1dd5913c5cd0');
INSERT INTO capabilities(userid, action, object) VALUES (5001, 'search', '*');

-- Modify
INSERT INTO ldapgroups(name, gidnumber) VALUES ('svcaccts', 5504);
INSERT INTO ldapgroups(name, gidnumber) VALUES ('smoker', 5505);
INSERT INTO users(name, mail, uidnumber, primarygroup, sn, passsha256) VALUES ('modify', 'modify.glauth.com', 5003, 5505, 'modify', '652c7dc687d98c9889304ed2e408c74b611e86a40caa51c4b43f1dd5913c5cd0');

-- Rename
INSERT INTO ldapgroups(name, gidnumber) VALUES ('rename', 5506);
INSERT INTO users(name, uidnumber, primarygroup, sn) VALUES ('rename', 5004, 5506, 'rename');

-- Move
INSERT INTO ldapgroups(name, gidnumber) VALUES ('top', 5507);
INSERT INTO ldapgroups(name, gidnumber) VALUES ('sub', 5508);
INSERT INTO users(name, uidnumber, primarygroup, sn) VALUES ('move', 5005, 5507, 'move');

-- Attach & detach
INSERT INTO ldapgroups(name, gidnumber) VALUES ('primary', 5509);
INSERT INTO ldapgroups(name, gidnumber) VALUES ('secondary', 5510);
INSERT INTO users(name, uidnumber, primarygroup, sn) VALUES ('attach', 5006, 5509, 'attach');
INSERT INTO users(name, uidnumber, primarygroup, othergroups, sn) VALUES ('detach', 5007, 5509, '5510', 'detach');

-- Delete
INSERT INTO ldapgroups(name, gidnumber) VALUES ('delete', 5511);
INSERT INTO users(name, uidnumber, primarygroup) VALUES ('delete', 5008, 5511);
