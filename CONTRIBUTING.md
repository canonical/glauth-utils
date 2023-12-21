# Contributing

You can use the environments created by `tox` for development:

```shell
$ tox -e dev
$ source .tox/dev/bin/activate
```

## Testing

This project uses `tox` for managing test environments. There are some
pre-configured environments that can be used for linting and formatting code
when you're preparing contributions to the charm:

```shell
$ tox -e fmt           # update your code according to linting rules
$ tox -e lint          # code style
$ tox -e unit          # unit tests
$ tox -e integration   # integration tests
```

## Build the charm

Build the charm in this git repository using:

```shell
$ charmcraft pack -v
```
