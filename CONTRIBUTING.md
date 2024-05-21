# Contributing

You can use the environments created by `tox` for development. It helps
install `pre-commit` hooks, `mypy` type checker, linting tools, and
formatting tools.

```shell
tox -e dev
source .tox/dev/bin/activate
```

## Testing

This project uses `tox` for managing test environments. There are some
pre-configured environments that can be used for linting and formatting code
when you're preparing contributions to the charm:

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e unit          # unit tests
tox -e integration   # integration tests
```

> ⚠️ **NOTE**
>
> The `python-openldap` dependency requires several software packages to be
> install at the first hand. Please run `tox -e build-prerequisites` before
> running any tests.

## Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack -v
```

## Render the database schema diagram

The following command generates an SVG diagram of the database schema used by
the backend datastore.

```shell
tox -e render-database-diagram
```
