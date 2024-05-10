# LDIF (LDAP Data Interchange Format) Samples

This documentation presents supported LDIF content records in the
`glauth-utils` charmed operator. Please refer to
the [RFC 2849](https://datatracker.ietf.org/doc/html/rfc2849) for more
information about the LDIF.

## Add a Group

```ldif
dn: ou=superheros,ou=supergroup,dc=glauth,dc=com
objectClass: posixGroup
ou: superheros
gidNumber: 5501
```

> ⚠️ **NOTE**
>
> - `ou` and `gidNumber` **MUST** be provided.
> - `ou` **MUST** be unique.

## Add a Group with an association with another Group

```ldif
dn: ou=caped,ou=superheros,dc=glauth,dc=com
objectClass: posixGroup
ou: caped
gidNumber: 5502
```

> ⚠️ **NOTE**
>
> - This assumes that the Group `superheros` already exists.

## Modify a Group

```ldif
dn: ou=superheros,dc=glauth,dc=com
changetype: modify
replace: gidNumber
gidNumber: 5500
```

## Delete a Group

```ldif
dn: ou=superheros,dc=glauth,dc=com
changetype: delete
```

## Add a User

```ldif
# Without password

dn: cn=hackers,ou=superheros,dc=glauth,dc=com
objectClass: posixAccount
uidNumber: 5001
gidNumber: 5501
cn: hackers
sn: hackers
mail: hackers@glauth.com
```

```ldif
# With password

dn: cn=johndoe,ou=superheros,dc=glauth,dc=com
changetype: add
objectClass: posixAccount
uidNumber: 5002
gidNumber: 5501
cn: johndoe
sn: doe
uid: john
mail: john@glauth.com
userPassword: {SHA256}6478579e37aff45f013e14eeb30b3cc56c72ccdc310123bcdf53e0333e3f416a
```

> ⚠️ **NOTE**
>
> - `cn`, `uidNumber`, and `gidNumber` **MUST** be provided.
> - `cn` **MUST** be unique.
> - `userPassword` **ONLY** supports SHA-256 (prefixed with `{SHA256}`) and
    BCRYPT (prefixed with `{BCRYPT}`) hashed passwords.

## Modify a User (add, replace, and delete attributes)

```ldif
dn: cn=johndoe,ou=superheros,dc=glauth,dc=com
changetype: modify
add: loginShell
loginShell: /bin/bash
replace: sn
sn: wick
delete: mail
```

> ⚠️ **NOTE**
>
> - Custom attributes are also supported.

## Rename a User

```ldif
# Rename a user
dn: cn=hackers,ou=superheros,dc=glauth,dc=com
changetype: modrdn
newrdn: cn=serviceuser
deleteoldrdn: 1
```

## Move a User

```ldif
dn: cn=hackers,ou=superheros,dc=glauth,dc=com
changetype: modrdn
newrdn: cn=hackers
deleteoldrdn: 1
newsuperior: ou=svcaccts,dc=glauth,dc=com
```

## Move a Group

```ldif
dn: ou=svcaccts,dc=glauth,dc=com
objectClass: posixGroup
changetype: modrdn
deleteoldrdn: 1
newsuperior: ou=superheros,dc=glauth,dc=com
```

## Add Users to additional Group

```ldif
dn: ou=civilians,dc=glauth,dc=com
changetype: modify
add: memberUid
memberUid: 5001
memberUid: 5002
```

> ⚠️ **NOTE**
>
> - The group should **NOT** be the user's primary group.

## Remove Users from additional Group

```ldif
dn: ou=civilians,dc=glauth,dc=com
changetype: modify
delete: memberUid
memberUid: 5001
memberUid: 5002
```

> ⚠️ **NOTE**
>
> - The group should **NOT** be the user's primary group.
